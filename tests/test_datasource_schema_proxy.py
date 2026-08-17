"""Proxy tests for datasource schema/grants via monkeypatched catalog_client."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.api import catalog_client, db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.settings import settings
from tests.api_helpers import login_headers, workspace_headers


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "ds_proxy.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    db.reset_engine()
    engine = db.get_engine()
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    with TestClient(app) as c:
        yield c
    db.reset_engine()


@pytest.fixture
def analyst_headers(client: TestClient) -> dict[str, str]:
    admin = workspace_headers(client)
    r = client.post(
        "/admin/users",
        headers=admin,
        json={
            "username": "analyst_proxy",
            "password": "analyst123",
            "display_name": "Analyst Proxy",
            "org_role": "analyst",
        },
    )
    assert r.status_code == 200
    uid = r.json()["id"]
    me = client.get("/auth/me", headers=admin)
    assert me.status_code == 200
    ws_id = me.json()["workspaces"][0]["id"]
    m = client.post(
        f"/workspaces/{ws_id}/members",
        headers=admin,
        json={"user_id": uid, "role": "analyst", "domains": ["biz", "network", "cs"]},
    )
    assert m.status_code == 200
    auth = login_headers(client, username="analyst_proxy", password="analyst123")
    return workspace_headers(client, auth)


@pytest.fixture
def ds_id(client: TestClient) -> int:
    headers = workspace_headers(client)
    created = client.post(
        "/admin/datasources",
        headers=headers,
        json={
            "name": "proxy-pg",
            "db_type": "postgres",
            "host": "db.example",
            "port": 5432,
            "database": "biz",
            "username": "u",
            "password": "secret-pass",
            "is_default": False,
        },
    )
    assert created.status_code == 200
    return created.json()["id"]


def test_introspect_proxies_without_logging_password(
    client: TestClient, ds_id: int, monkeypatch
):
    captured: dict = {}

    def fake_introspect(**kwargs):
        captured.update(kwargs)
        return {"tables": 2, "columns": 4}

    monkeypatch.setattr(catalog_client, "introspect", fake_introspect)
    headers = workspace_headers(client)
    r = client.post(f"/admin/datasources/{ds_id}/introspect", headers=headers)
    assert r.status_code == 200
    assert r.json() == {"tables": 2, "columns": 4}
    assert captured["datasource_id"] == ds_id
    assert captured["db_type"] == "postgres"
    assert "secret-pass" in captured["sqlalchemy_url"]
    # Response must not echo password
    assert "secret-pass" not in r.text
    assert "password" not in r.json()


def test_get_schema_member_ok(client: TestClient, ds_id: int, analyst_headers, monkeypatch):
    monkeypatch.setattr(
        catalog_client,
        "get_schema",
        lambda **kwargs: {
            "datasource_id": kwargs["datasource_id"],
            "tables": [{"table_name": "sub_month", "granted": False, "columns": []}],
        },
    )
    r = client.get(f"/admin/datasources/{ds_id}/schema", headers=analyst_headers)
    assert r.status_code == 200
    assert r.json()["tables"][0]["table_name"] == "sub_month"


def test_put_grants_admin_ok(client: TestClient, ds_id: int, monkeypatch):
    captured: dict = {}

    def fake_put(**kwargs):
        captured.update(kwargs)
        return {"tables": 1, "columns": 1}

    monkeypatch.setattr(catalog_client, "put_grants", fake_put)
    headers = workspace_headers(client)
    r = client.put(
        f"/admin/datasources/{ds_id}/grants",
        headers=headers,
        json={
            "tables": [
                {
                    "schema_name": "biz",
                    "table_name": "sub_month",
                    "columns": ["region"],
                }
            ]
        },
    )
    assert r.status_code == 200
    assert r.json() == {"tables": 1, "columns": 1}
    assert captured["datasource_id"] == ds_id
    assert captured["tables"][0]["table_name"] == "sub_month"


def test_put_grants_analyst_forbidden(
    client: TestClient, ds_id: int, analyst_headers, monkeypatch
):
    called = {"n": 0}

    def boom(**_kwargs):
        called["n"] += 1
        raise AssertionError("catalog should not be called")

    monkeypatch.setattr(catalog_client, "put_grants", boom)
    r = client.put(
        f"/admin/datasources/{ds_id}/grants",
        headers=analyst_headers,
        json={"tables": [{"schema_name": "biz", "table_name": "t", "columns": ["c"]}]},
    )
    assert r.status_code == 403
    assert called["n"] == 0


def test_introspect_analyst_forbidden(
    client: TestClient, ds_id: int, analyst_headers, monkeypatch
):
    called = {"n": 0}

    def boom(**_kwargs):
        called["n"] += 1
        raise AssertionError("catalog should not be called")

    monkeypatch.setattr(catalog_client, "introspect", boom)
    r = client.post(f"/admin/datasources/{ds_id}/introspect", headers=analyst_headers)
    assert r.status_code == 403
    assert called["n"] == 0


def test_catalog_unavailable_returns_503(client: TestClient, ds_id: int, monkeypatch):
    from fastapi import HTTPException, status

    def raise_503(**_kwargs):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="catalog service unavailable",
        )

    monkeypatch.setattr(catalog_client, "get_schema", raise_503)
    headers = workspace_headers(client)
    r = client.get(f"/admin/datasources/{ds_id}/schema", headers=headers)
    assert r.status_code == 503
    assert "catalog" in r.json()["detail"].lower()
