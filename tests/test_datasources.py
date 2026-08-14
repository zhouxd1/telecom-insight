import pytest
from fastapi.testclient import TestClient

from apps.api import db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.settings import settings
from tests.api_helpers import workspace_headers


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "ds.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    db.reset_engine()
    engine = db.get_engine()
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    with TestClient(app) as c:
        yield c
    db.reset_engine()


def test_create_datasource_hides_password(client: TestClient):
    headers = workspace_headers(client)
    r = client.post(
        "/admin/datasources",
        headers=headers,
        json={
            "name": "mysql-demo",
            "db_type": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "database": "demo",
            "username": "root",
            "password": "secret-pass",
            "is_default": False,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "mysql-demo"
    assert body["db_type"] == "mysql"
    assert "password" not in body
    assert "password_enc" not in body

    got = client.get(f"/admin/datasources/{body['id']}", headers=headers)
    assert got.status_code == 200
    detail = got.json()
    assert "password" not in detail
    assert "password_enc" not in detail

    listed = client.get("/admin/datasources", headers=headers)
    assert listed.status_code == 200
    for item in listed.json():
        assert "password" not in item
        assert "password_enc" not in item


def test_set_default_uniqueness(client: TestClient):
    headers = workspace_headers(client)
    a = client.post(
        "/admin/datasources",
        headers=headers,
        json={
            "name": "ds-a",
            "db_type": "postgres",
            "host": "a",
            "port": 5432,
            "database": "db",
            "username": "u",
            "password": "p",
            "is_default": False,
        },
    ).json()
    b = client.post(
        "/admin/datasources",
        headers=headers,
        json={
            "name": "ds-b",
            "db_type": "postgres",
            "host": "b",
            "port": 5432,
            "database": "db",
            "username": "u",
            "password": "p",
            "is_default": False,
        },
    ).json()

    r = client.post(f"/admin/datasources/{a['id']}/default", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_default"] is True

    r = client.post(f"/admin/datasources/{b['id']}/default", headers=headers)
    assert r.status_code == 200
    assert r.json()["is_default"] is True

    listed = {d["id"]: d for d in client.get("/admin/datasources", headers=headers).json()}
    assert listed[a["id"]]["is_default"] is False
    assert listed[b["id"]]["is_default"] is True


def test_p1_default_rejected(client: TestClient):
    headers = workspace_headers(client)
    created = client.post(
        "/admin/datasources",
        headers=headers,
        json={
            "name": "gbase-p1",
            "db_type": "gbase",
            "host": "h",
            "port": 5258,
            "database": "db",
            "username": "u",
            "password": "p",
            "is_default": True,
        },
    )
    assert created.status_code == 400

    created = client.post(
        "/admin/datasources",
        headers=headers,
        json={
            "name": "gbase-p1",
            "db_type": "gbase",
            "host": "h",
            "port": 5258,
            "database": "db",
            "username": "u",
            "password": "p",
            "is_default": False,
        },
    )
    assert created.status_code == 200
    ds_id = created.json()["id"]

    r = client.post(f"/admin/datasources/{ds_id}/default", headers=headers)
    assert r.status_code == 400


def test_test_connection_endpoint_structured(client: TestClient):
    headers = workspace_headers(client)
    created = client.post(
        "/admin/datasources",
        headers=headers,
        json={
            "name": "unreachable-pg",
            "db_type": "postgres",
            "host": "invalid.invalid",
            "port": 5432,
            "database": "nope",
            "username": "u",
            "password": "p",
            "is_default": False,
        },
    )
    assert created.status_code == 200
    ds_id = created.json()["id"]

    r = client.post(f"/admin/datasources/{ds_id}/test", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert "ok" in body
    assert body["ok"] is False or body["ok"] is True
    # unreachable host should not 500; when fail, error present
    if not body["ok"]:
        assert body.get("error")

    detail = client.get(f"/admin/datasources/{ds_id}", headers=headers).json()
    if body["ok"]:
        assert detail.get("last_ok_at") is not None
    else:
        assert detail.get("last_error")
