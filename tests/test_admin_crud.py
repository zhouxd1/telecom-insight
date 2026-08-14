import pytest
from fastapi.testclient import TestClient

from apps.api import db
from apps.api.init_db import init_db
from apps.api.main import app
from apps.api.settings import settings


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "admin.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    db.reset_engine()
    init_db(db.get_engine())
    with TestClient(app) as c:
        yield c
    db.reset_engine()


def _auth_headers(client: TestClient) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_models_crud_and_unique_enabled(client: TestClient):
    headers = _auth_headers(client)

    r = client.post(
        "/admin/models",
        headers=headers,
        json={
            "name": "demo-a",
            "base_url": "https://api.example.com/v1",
            "api_key": "",
            "model": "gpt-test",
            "enabled": True,
        },
    )
    assert r.status_code == 200
    a = r.json()
    assert a["enabled"] is True
    assert a["id"]

    r = client.post(
        "/admin/models",
        headers=headers,
        json={
            "name": "demo-b",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-test",
            "model": "gpt-test-2",
            "enabled": True,
        },
    )
    assert r.status_code == 200
    b = r.json()
    assert b["enabled"] is True

    listed = client.get("/admin/models", headers=headers)
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 2
    by_id = {m["id"]: m for m in items}
    assert by_id[a["id"]]["enabled"] is False
    assert by_id[b["id"]]["enabled"] is True

    r = client.patch(
        f"/admin/models/{a['id']}",
        headers=headers,
        json={"enabled": True},
    )
    assert r.status_code == 200
    assert r.json()["enabled"] is True

    listed = client.get("/admin/models", headers=headers).json()
    by_id = {m["id"]: m for m in listed}
    assert by_id[a["id"]]["enabled"] is True
    assert by_id[b["id"]]["enabled"] is False

    test_no_key = client.post(f"/admin/models/{a['id']}/test", headers=headers)
    assert test_no_key.status_code == 200
    assert test_no_key.json() == {"ok": True, "detail": "skipped"}

    test_with_key = client.post(f"/admin/models/{b['id']}/test", headers=headers)
    assert test_with_key.status_code == 200
    body = test_with_key.json()
    assert body["ok"] is True
    assert "detail" in body

    deleted = client.delete(f"/admin/models/{b['id']}", headers=headers)
    assert deleted.status_code == 200
    assert len(client.get("/admin/models", headers=headers).json()) == 1


def test_terms_and_examples_crud_with_domain_filter(client: TestClient):
    headers = _auth_headers(client)

    t = client.post(
        "/admin/terms",
        headers=headers,
        json={"domain": "biz", "term": "ARPU", "standard": "每用户平均收入", "maps_to": "users.arpu"},
    )
    assert t.status_code == 200
    term = t.json()
    assert term["term"] == "ARPU"

    client.post(
        "/admin/terms",
        headers=headers,
        json={"domain": "cs", "term": "NPS", "standard": "净推荐值"},
    )

    biz_terms = client.get("/admin/terms", headers=headers, params={"domain": "biz"})
    assert biz_terms.status_code == 200
    assert len(biz_terms.json()) == 1
    assert biz_terms.json()[0]["term"] == "ARPU"

    ex = client.post(
        "/admin/examples",
        headers=headers,
        json={"domain": "biz", "question": "上月ARPU", "sql": "SELECT 1"},
    )
    assert ex.status_code == 200
    example = ex.json()

    client.post(
        "/admin/examples",
        headers=headers,
        json={"domain": "network", "question": "告警数", "sql": "SELECT 2"},
    )

    biz_ex = client.get("/admin/examples", headers=headers, params={"domain": "biz"})
    assert biz_ex.status_code == 200
    assert len(biz_ex.json()) == 1
    assert biz_ex.json()[0]["id"] == example["id"]

    patched = client.patch(
        f"/admin/terms/{term['id']}",
        headers=headers,
        json={"standard": "月均收入"},
    )
    assert patched.status_code == 200
    assert patched.json()["standard"] == "月均收入"

    assert client.delete(f"/admin/terms/{term['id']}", headers=headers).status_code == 200
    assert client.delete(f"/admin/examples/{example['id']}", headers=headers).status_code == 200
