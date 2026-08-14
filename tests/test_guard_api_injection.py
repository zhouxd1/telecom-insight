"""API-level SQL injection / write-SQL must be rejected by the guard."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from apps.api.main import app
from apps.engine.ask import AskEngine
from apps.engine.llm import FakeLLM
from apps.packs.models import Example, IndustryPack, Metric, Recommended, Term

client = TestClient(app)


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


def _token() -> str:
    r = client.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert r.status_code == 200
    return r.json()["access_token"]


def test_ask_rejects_multi_statement_injection(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'inj.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
        c.execute(text("INSERT INTO users VALUES ('2026-01', 50)"))

    llm = FakeLLM(sql="SELECT 1; DROP TABLE users", narrative="should not run")
    ask_engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _biz_pack()})
    monkeypatch.setattr("apps.api.deps.get_ask_engine", lambda: ask_engine)

    r = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"domain": "biz", "question": "2026年各月ARPU是多少"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert "安全" in body["message"]


def test_ask_rejects_delete(tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 'del.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))

    llm = FakeLLM(sql="DELETE FROM users", narrative="x")
    ask_engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _biz_pack()})
    monkeypatch.setattr("apps.api.deps.get_ask_engine", lambda: ask_engine)

    r = client.post(
        "/ask",
        headers={"Authorization": f"Bearer {_token()}"},
        json={"domain": "biz", "question": "2026年各月ARPU是多少"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert "安全" in body["message"]
