from fastapi.testclient import TestClient
from sqlmodel import Session, select

from apps.api import db
from apps.api.models_db import TiUser


def test_login_demo_and_me(client_with_seed: TestClient):
    r = client_with_seed.post(
        "/auth/login",
        json={"username": "demo", "password": "demo123"},
    )
    assert r.status_code == 200
    token = r.json()["access_token"]
    me = client_with_seed.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "demo"
    assert body["org_role"] == "org_admin"
    assert len(body["workspaces"]) >= 1
    assert body["workspaces"][0]["role"] == "org_admin"
    assert set(body["workspaces"][0]["domains"]) == {"biz", "network", "cs"}


def test_login_wrong_password(client_with_seed: TestClient):
    r = client_with_seed.post(
        "/auth/login",
        json={"username": "demo", "password": "wrong"},
    )
    assert r.status_code == 401


def test_login_disabled_user(client_with_seed: TestClient):
    with Session(db.get_engine()) as session:
        user = session.exec(select(TiUser).where(TiUser.username == "demo")).one()
        user.enabled = False
        session.add(user)
        session.commit()

    r = client_with_seed.post(
        "/auth/login",
        json={"username": "demo", "password": "demo123"},
    )
    assert r.status_code == 401
