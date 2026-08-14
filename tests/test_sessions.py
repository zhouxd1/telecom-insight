import json

import pytest
from fastapi.testclient import TestClient

from apps.api import db
from apps.api.init_db import init_db
from apps.api.main import app
from apps.api.settings import settings
from apps.engine.ask import AskRequest, AskResponse


class FakeAskEngine:
    def ask(self, req: AskRequest, **_kwargs) -> AskResponse:
        assert req.domain == "biz"
        return AskResponse(
            status="ok",
            message="",
            sql="SELECT month, arpu FROM users ORDER BY month",
            rows=[{"month": "2026-01", "arpu": 50}],
            truncated=False,
            chart={"type": "line"},
            narrative="ARPU 稳定。",
        )


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    db.reset_engine()
    init_db(db.get_engine())
    monkeypatch.setattr("apps.api.deps.get_ask_engine", lambda _session=None: FakeAskEngine())
    with TestClient(app) as c:
        yield c
    db.reset_engine()


def _auth_headers(client: TestClient) -> dict[str, str]:
    r = client.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_session_crud_and_ask_persists_messages(client: TestClient):
    headers = _auth_headers(client)

    created = client.post(
        "/sessions",
        headers=headers,
        json={"domain": "biz", "title": "ARPU 分析"},
    )
    assert created.status_code == 200
    session = created.json()
    assert session["domain"] == "biz"
    sid = session["id"]

    listed = client.get("/sessions", headers=headers)
    assert listed.status_code == 200
    assert any(s["id"] == sid for s in listed.json())

    patched = client.patch(
        f"/sessions/{sid}",
        headers=headers,
        json={"title": "月度 ARPU"},
    )
    assert patched.status_code == 200
    assert patched.json()["title"] == "月度 ARPU"

    ask = client.post(
        f"/sessions/{sid}/ask",
        headers=headers,
        json={"question": "各月ARPU是多少"},
    )
    assert ask.status_code == 200
    card = ask.json()
    assert card["status"] == "ok"
    assert card["sql"]
    assert card["rows"]
    assert card["chart"]
    assert card["narrative"]
    assert card["steps"]
    assert all("id" in s and "label" in s and "state" in s for s in card["steps"])

    messages = client.get(f"/sessions/{sid}/messages", headers=headers)
    assert messages.status_code == 200
    msgs = messages.json()
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant"
    content = json.loads(msgs[1]["content_json"])
    assert content["sql"]
    assert "chart" in content
    assert content.get("steps")

    deleted = client.delete(f"/sessions/{sid}", headers=headers)
    assert deleted.status_code == 200
    assert client.get(f"/sessions/{sid}/messages", headers=headers).status_code == 404
