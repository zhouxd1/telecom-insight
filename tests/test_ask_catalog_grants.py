"""Ask paths enforce Catalog effective table/column grants."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from apps.api import catalog_client, db
from apps.api.deps import get_packs
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.settings import settings
from apps.engine.llm import FakeLLM
from apps.packs.models import Example, IndustryPack, Metric, Recommended, Term
from tests.api_helpers import login_headers, workspace_headers


def _biz_pack() -> IndustryPack:
    return IndustryPack(
        domain="biz",
        version="0.1.0",
        schemas=["biz"],
        table_whitelist=["sub_month", "secret_table"],
        terminology=[
            Term(term="区域", standard="region", maps_to="sub_month.region"),
        ],
        metrics=[
            Metric(
                name="subs",
                label="用户数",
                description="用户数",
                dimensions=["region"],
            )
        ],
        examples=[
            Example(
                question="各区域用户数",
                sql="SELECT region, sub_cnt FROM sub_month",
            )
        ],
        recommended=[Recommended(id="1", text="各区域用户数")],
        schema_docs="## sub_month\n- region\n- sub_cnt\n",
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "ask_catalog.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    get_packs.cache_clear()
    db.reset_engine()
    engine = db.get_engine()
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    with TestClient(app) as c:
        yield c
    db.reset_engine()
    get_packs.cache_clear()


def _wire_fake_ask(monkeypatch, tmp_path, *, sql: str):
    warehouse = create_engine(f"sqlite:///{tmp_path / 'wh.db'}")
    with warehouse.begin() as conn:
        conn.execute(text("CREATE TABLE sub_month(region TEXT, sub_cnt INTEGER, secret TEXT)"))
        conn.execute(
            text(
                "INSERT INTO sub_month VALUES ('华东', 10, 'x'), ('华北', 20, 'y')"
            )
        )

    packs = {"biz": _biz_pack()}
    llm = FakeLLM(sql=sql, narrative="ok")

    monkeypatch.setattr("apps.api.deps.get_packs", lambda: packs)
    monkeypatch.setattr("apps.api.deps.resolve_llm", lambda *_a, **_k: llm)
    monkeypatch.setattr(
        "apps.api.main.build_engine_from_datasource",
        lambda _ds: warehouse,
    )
    monkeypatch.setattr(
        "apps.api.routes_sessions.build_engine_from_datasource",
        lambda _ds: warehouse,
    )
    return warehouse


def test_ask_empty_effective_returns_403(client: TestClient, tmp_path, monkeypatch):
    _wire_fake_ask(
        monkeypatch,
        tmp_path,
        sql="SELECT region, sub_cnt FROM sub_month",
    )
    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_kw: {"tables": [], "columns": {}, "empty": True},
    )

    headers = workspace_headers(client)
    r = client.post(
        "/ask",
        headers=headers,
        json={"domain": "biz", "question": "各区域用户数"},
    )
    assert r.status_code == 403
    assert "请先在数据源中授权表字段" in r.json()["detail"]


def test_ask_rejects_unauthorized_column(client: TestClient, tmp_path, monkeypatch):
    _wire_fake_ask(
        monkeypatch,
        tmp_path,
        sql="SELECT region, secret FROM sub_month",
    )
    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_kw: {
            "tables": ["sub_month"],
            "columns": {"sub_month": ["region", "sub_cnt"]},
            "empty": False,
        },
    )

    headers = workspace_headers(client)
    r = client.post(
        "/ask",
        headers=headers,
        json={"domain": "biz", "question": "各区域用户数"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "error"
    assert "安全" in body["message"]


def test_ask_ok_with_granted_columns(client: TestClient, tmp_path, monkeypatch):
    _wire_fake_ask(
        monkeypatch,
        tmp_path,
        sql="SELECT region, sub_cnt FROM sub_month",
    )
    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_kw: {
            "tables": ["sub_month"],
            "columns": {"sub_month": ["region", "sub_cnt"]},
            "empty": False,
        },
    )

    headers = workspace_headers(client)
    r = client.post(
        "/ask",
        headers=headers,
        json={"domain": "biz", "question": "各区域用户数"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body.get("sql")
    assert len(body.get("rows") or []) >= 1


def test_session_ask_empty_effective_returns_403(
    client: TestClient, tmp_path, monkeypatch
):
    _wire_fake_ask(
        monkeypatch,
        tmp_path,
        sql="SELECT region, sub_cnt FROM sub_month",
    )
    monkeypatch.setattr(
        catalog_client,
        "get_effective",
        lambda **_kw: {"tables": [], "columns": {}, "empty": True},
    )

    headers = workspace_headers(client)
    created = client.post(
        "/sessions",
        headers=headers,
        json={"domain": "biz", "title": "grants"},
    )
    assert created.status_code == 200
    sid = created.json()["id"]

    r = client.post(
        f"/sessions/{sid}/ask",
        headers=headers,
        json={"question": "各区域用户数"},
    )
    assert r.status_code == 403
    assert "请先在数据源中授权表字段" in r.json()["detail"]
