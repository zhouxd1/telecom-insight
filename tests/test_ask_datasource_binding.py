"""Ask binds to workspace default datasource; role/domain gates."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlmodel import Session, select

from apps.api import db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.models_db import TiDatasource
from apps.api.settings import settings
from apps.engine.ask import AskRequest, AskResponse
from tests.api_helpers import login_headers, workspace_headers


class FakeAskEngine:
    def ask(self, req: AskRequest, **_kwargs) -> AskResponse:
        return AskResponse(
            status="ok",
            message="",
            sql="SELECT 1",
            rows=[{"x": 1}],
            truncated=False,
            chart={},
            narrative="ok",
        )


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "ask_bind.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    db.reset_engine()
    engine = db.get_engine()
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    with TestClient(app) as c:
        yield c
    db.reset_engine()


def test_ask_uses_default_datasource(client: TestClient, monkeypatch):
    recorded: list[int] = []

    def fake_build(ds: TiDatasource):
        recorded.append(ds.id)  # type: ignore[arg-type]
        return create_engine("sqlite://")

    monkeypatch.setattr(
        "apps.api.routes_sessions.build_engine_from_datasource",
        fake_build,
    )
    monkeypatch.setattr(
        "apps.api.deps.get_ask_engine",
        lambda *_a, **_k: FakeAskEngine(),
    )

    with Session(db.get_engine()) as session:
        ds = session.exec(
            select(TiDatasource).where(TiDatasource.is_default.is_(True))
        ).one()
        default_id = ds.id

    headers = workspace_headers(client)
    created = client.post(
        "/sessions",
        headers=headers,
        json={"domain": "biz", "title": "bind"},
    )
    assert created.status_code == 200
    sid = created.json()["id"]

    ask = client.post(
        f"/sessions/{sid}/ask",
        headers=headers,
        json={"question": "hello"},
    )
    assert ask.status_code == 200
    assert recorded == [default_id]


def test_viewer_cannot_ask(client: TestClient):
    admin = workspace_headers(client)
    me = client.get("/auth/me", headers=admin)
    assert me.status_code == 200
    ws_id = me.json()["workspaces"][0]["id"]

    r = client.post(
        "/admin/users",
        headers=admin,
        json={
            "username": "viewer1",
            "password": "viewer123",
            "display_name": "Viewer",
            "org_role": "viewer",
        },
    )
    assert r.status_code == 200
    uid = r.json()["id"]

    m = client.post(
        f"/workspaces/{ws_id}/members",
        headers=admin,
        json={"user_id": uid, "role": "viewer", "domains": ["biz", "network", "cs"]},
    )
    assert m.status_code == 200

    created = client.post(
        "/sessions",
        headers=admin,
        json={"domain": "biz", "title": "hist"},
    )
    assert created.status_code == 200
    sid = created.json()["id"]

    auth = login_headers(client, username="viewer1", password="viewer123")
    headers = workspace_headers(client, auth)
    ask = client.post(
        f"/sessions/{sid}/ask",
        headers=headers,
        json={"question": "should fail"},
    )
    assert ask.status_code == 403


def test_analyst_cannot_ask_outside_domains(client: TestClient):
    admin = workspace_headers(client)
    me = client.get("/auth/me", headers=admin)
    assert me.status_code == 200
    ws_id = me.json()["workspaces"][0]["id"]

    r = client.post(
        "/admin/users",
        headers=admin,
        json={
            "username": "analyst_net",
            "password": "analyst123",
            "display_name": "Net Analyst",
            "org_role": "analyst",
        },
    )
    assert r.status_code == 200
    uid = r.json()["id"]

    m = client.post(
        f"/workspaces/{ws_id}/members",
        headers=admin,
        json={"user_id": uid, "role": "analyst", "domains": ["network"]},
    )
    assert m.status_code == 200

    created = client.post(
        "/sessions",
        headers=admin,
        json={"domain": "biz", "title": "biz-only"},
    )
    assert created.status_code == 200
    sid = created.json()["id"]

    auth = login_headers(client, username="analyst_net", password="analyst123")
    headers = workspace_headers(client, auth)
    ask = client.post(
        f"/sessions/{sid}/ask",
        headers=headers,
        json={"question": "biz question"},
    )
    assert ask.status_code == 403
