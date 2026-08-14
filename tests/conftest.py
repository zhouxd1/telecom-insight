import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from apps.api import db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.models_db import TiUser
from apps.api.settings import settings


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
    r = client_with_seed.post(
        "/auth/login",
        json={"username": "demo", "password": "demo123"},
    )
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture
def authenticated_client(client_with_seed: TestClient, auth_headers: dict[str, str]):
    """TestClient plus Authorization headers for the seeded demo user."""
    client_with_seed.headers.update(auth_headers)
    yield client_with_seed
