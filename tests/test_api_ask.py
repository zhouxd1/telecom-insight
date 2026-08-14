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
    db_path = tmp_path / "ask_api.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    db.reset_engine()
    engine = db.get_engine()
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    with TestClient(app) as c:
        yield c
    db.reset_engine()


def test_login_and_list_domains(client: TestClient):
    r = client.post("/auth/login", json={"username": "demo", "password": "demo123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    r2 = client.get("/domains", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200
    domains = {d["id"] for d in r2.json()}
    assert {"biz", "network", "cs"} <= domains


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


def test_ask_with_fake_engine(client: TestClient, tmp_path, monkeypatch):
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
        c.execute(text("INSERT INTO users VALUES ('2026-01', 50), ('2026-02', 60)"))

    llm = FakeLLM(sql="SELECT month, arpu FROM users ORDER BY month", narrative="ARPU 呈上升趋势。")
    ask_engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _biz_pack()})

    monkeypatch.setattr(
        "apps.api.deps.get_ask_engine", lambda *_a, **_k: ask_engine
    )
    monkeypatch.setattr(
        "apps.api.main.build_engine_from_datasource",
        lambda _ds: create_engine("sqlite://"),
    )

    headers = workspace_headers(client)
    r2 = client.post(
        "/ask",
        headers=headers,
        json={"domain": "biz", "question": "2026年各月ARPU是多少"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "ok"
    assert body.get("chart")
    assert body.get("narrative")
