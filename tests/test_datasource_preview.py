"""Preview endpoint: ACL, catalog match, empty-grant still 200, limit validation."""

from __future__ import annotations

from sqlalchemy import create_engine, text
from fastapi.testclient import TestClient
import pytest

from apps.api import catalog_client, db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.settings import settings
from apps.engine.rls import RlsPredicate
from tests.api_helpers import login_headers, workspace_headers


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "ds_preview.db"
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


def _patch_preview_warehouse(monkeypatch, tmp_path):
    warehouse = create_engine(f"sqlite:///{tmp_path / 'wh.db'}")
    with warehouse.begin() as conn:
        conn.execute(text("CREATE TABLE sub_month(region TEXT, secret TEXT)"))
        conn.execute(text("INSERT INTO sub_month VALUES ('华东','x'),('华北','y')"))
    monkeypatch.setattr(
        catalog_client,
        "get_schema",
        lambda **_k: {
            "tables": [
                {
                    "schema_name": "main",
                    "table_name": "sub_month",
                    "columns": [
                        {"name": "region"},
                        {"name": "secret"},
                    ],
                }
            ]
        },
    )
    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_k: {"tables": [], "columns": {}, "empty": True},
    )
    monkeypatch.setattr(
        "apps.api.routes_datasources.build_engine_from_datasource",
        lambda _ds: warehouse,
    )
    return warehouse


def test_preview_requires_schema_and_table(client: TestClient, ds_id: int):
    r = client.get(
        f"/admin/datasources/{ds_id}/preview",
        headers=workspace_headers(client),
    )
    assert r.status_code == 422


def test_preview_unknown_table_404(client: TestClient, ds_id: int, monkeypatch):
    monkeypatch.setattr(
        catalog_client,
        "get_schema",
        lambda **_k: {"tables": [{"schema_name": "biz", "table_name": "other", "columns": []}]},
    )
    r = client.get(
        f"/admin/datasources/{ds_id}/preview",
        headers=workspace_headers(client),
        params={"schema": "main", "table": "sub_month"},
    )
    assert r.status_code == 404
    assert "table not in catalog snapshot" in r.json()["detail"]


def test_preview_ok_when_effective_empty(client, ds_id, tmp_path, monkeypatch):
    _patch_preview_warehouse(monkeypatch, tmp_path)
    r = client.get(
        f"/admin/datasources/{ds_id}/preview",
        headers=workspace_headers(client),
        params={"schema": "main", "table": "sub_month"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "secret" in body["columns"]
    assert len(body["rows"]) >= 1
    assert "truncated" in body


def test_preview_analyst_ok(client, ds_id, analyst_headers, tmp_path, monkeypatch):
    _patch_preview_warehouse(monkeypatch, tmp_path)
    r = client.get(
        f"/admin/datasources/{ds_id}/preview",
        headers=analyst_headers,
        params={"schema": "main", "table": "sub_month"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "secret" in body["columns"]
    assert len(body["rows"]) >= 1


def test_preview_limit_too_large_422(client: TestClient, ds_id: int):
    r = client.get(
        f"/admin/datasources/{ds_id}/preview",
        headers=workspace_headers(client),
        params={"schema": "main", "table": "sub_month", "limit": 999},
    )
    assert r.status_code == 422


def test_preview_applies_rls_region_filter(
    client, ds_id, analyst_headers, tmp_path, monkeypatch
):
    _patch_preview_warehouse(monkeypatch, tmp_path)
    monkeypatch.setattr(
        "apps.api.routes_datasources.load_rls_predicates",
        lambda *_a, **_k: [
            RlsPredicate("biz", "sub_month", "region", "eq", ["华东"]),
        ],
    )
    r = client.get(
        f"/admin/datasources/{ds_id}/preview",
        headers=analyst_headers,
        params={"schema": "main", "table": "sub_month"},
    )
    assert r.status_code == 200
    regions = [row["region"] for row in r.json()["rows"]]
    assert "华东" in regions
    assert "华北" not in regions
