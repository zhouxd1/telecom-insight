"""API-level SQL injection / write-SQL must be rejected by the guard."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from apps.api import db
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.settings import settings
from apps.engine.ask import AskEngine
from apps.engine.llm import FakeLLM
from apps.packs.models import Example, IndustryPack, Metric, Recommended, Term
from tests.api_helpers import workspace_headers


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "guard_api.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    db.reset_engine()
    eng = db.get_engine()
    init_db(eng)
    seed_tenant_bootstrap(eng, default_database_url="sqlite://")
    with TestClient(app) as c:
        yield c
    db.reset_engine()


def _biz_pack() -> IndustryPack:
    return IndustryPack(
        domain="biz",
        version="0.1.0",
        schemas=["biz"],
        table_whitelist=["users"],
        terminology=[Term(term="ARPU", standard="每用户平均收入", maps_to="users.arpu")],
        metrics=[Metric(name="arpu", label="ARPU", description="月均收入", dimensions=["month"])],
        examples=[Example(question="上月ARPU", sql="SELECT month, arpu FROM users ORDER BY month")],
        recommended=[Recommended(id="1", text="上月ARPU是多少")],
        schema_docs="## users\n- month\n- arpu\n",
    )


def test_ask_rejects_multi_statement_injection(client: TestClient, tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'inj.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
        c.execute(text("INSERT INTO users VALUES ('2026-01', 50)"))

    llm = FakeLLM(sql="SELECT 1; DROP TABLE users", narrative="should not run")
    ask_engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _biz_pack()})
    monkeypatch.setattr(
        "apps.api.deps.get_ask_engine", lambda *_a, **_k: ask_engine
    )
    monkeypatch.setattr(
        "apps.api.main.build_engine_from_datasource",
        lambda _ds: create_engine("sqlite://"),
    )

    r = client.post(
        "/ask",
        headers=workspace_headers(client),
        json={"domain": "biz", "question": "2026年各月ARPU是多少"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert "安全" in body["message"]


def test_ask_rejects_delete(client: TestClient, tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'del.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))

    llm = FakeLLM(sql="DELETE FROM users", narrative="x")
    ask_engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _biz_pack()})
    monkeypatch.setattr(
        "apps.api.deps.get_ask_engine", lambda *_a, **_k: ask_engine
    )
    monkeypatch.setattr(
        "apps.api.main.build_engine_from_datasource",
        lambda _ds: create_engine("sqlite://"),
    )

    r = client.post(
        "/ask",
        headers=workspace_headers(client),
        json={"domain": "biz", "question": "2026年各月ARPU是多少"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert "安全" in body["message"]
