import pytest
from fastapi.testclient import TestClient

from apps.api import catalog_client, db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.settings import settings
from tests.api_helpers import login_headers, workspace_headers

# Re-export helpers for tests that import from conftest.
__all__ = ["login_headers", "workspace_headers"]

# Permissive default so ask API tests work without a live Catalog.
# Specific tests (e.g. test_ask_catalog_grants) override get_effective.
_DEFAULT_EFFECTIVE = {
    "tables": ["users", "sub_month", "channel_day"],
    "columns": {
        "users": ["month", "arpu", "region", "n"],
        "sub_month": ["region", "n", "sub_cnt", "secret", "arpu"],
        "channel_day": ["region", "channel", "day"],
    },
    "empty": False,
}


@pytest.fixture(autouse=True)
def _permissive_catalog_effective(monkeypatch):
    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_kw: dict(_DEFAULT_EFFECTIVE),
    )


@pytest.fixture
def client_with_seed(tmp_path, monkeypatch):
    db_path = tmp_path / "auth.db"
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
def auth_headers(client_with_seed: TestClient) -> dict[str, str]:
    return login_headers(client_with_seed)


@pytest.fixture
def authenticated_client(client_with_seed: TestClient):
    """TestClient plus Authorization + X-Workspace-Id for the seeded demo user."""
    client_with_seed.headers.update(workspace_headers(client_with_seed))
    yield client_with_seed


@pytest.fixture
def client_admin(client_with_seed: TestClient):
    """Demo org_admin client with default Authorization + X-Workspace-Id headers."""
    client_with_seed.headers.update(workspace_headers(client_with_seed))
    yield client_with_seed


@pytest.fixture
def analyst_user_id(client_admin: TestClient) -> int:
    users = client_admin.get("/admin/users")
    assert users.status_code == 200
    existing = next((u for u in users.json() if u["username"] == "analyst1"), None)
    if existing is not None:
        uid = existing["id"]
    else:
        r = client_admin.post(
            "/admin/users",
            json={
                "username": "analyst1",
                "password": "analyst123",
                "display_name": "Analyst",
                "org_role": "analyst",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert "password_hash" not in body
        uid = body["id"]

    # Add to default workspace so analyst can use workspace-scoped APIs.
    me = client_admin.get("/auth/me")
    assert me.status_code == 200
    default_ws = me.json()["workspaces"][0]["id"]
    m = client_admin.post(
        f"/workspaces/{default_ws}/members",
        json={
            "user_id": uid,
            "role": "analyst",
            "domains": ["biz", "network", "cs"],
        },
    )
    # Seed may already have membership for analyst1.
    assert m.status_code in (200, 409)
    return uid


@pytest.fixture
def analyst_headers(client_with_seed: TestClient, analyst_user_id: int) -> dict[str, str]:
    auth = login_headers(client_with_seed, username="analyst1", password="analyst123")
    return workspace_headers(client_with_seed, auth)
