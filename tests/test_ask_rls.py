"""Ask paths load member RLS policies and apply them (or bypass for org_admin)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlmodel import Session, select

from apps.api import db
from apps.api.deps import get_packs
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.main import app
from apps.api.models_db import TiOrg, TiRlsPolicy, TiUser, TiWorkspaceMember
from apps.api.settings import settings
from apps.engine.llm import FakeLLM
from apps.packs.models import Example, IndustryPack, Metric, Recommended, Term
from tests.api_helpers import login_headers, workspace_headers


def _biz_pack() -> IndustryPack:
    return IndustryPack(
        domain="biz",
        version="0.1.0",
        schemas=["biz"],
        table_whitelist=["sub_month"],
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
                sql="SELECT region, COUNT(*) AS n FROM sub_month GROUP BY region",
            )
        ],
        recommended=[Recommended(id="1", text="各区域用户数")],
        schema_docs="## sub_month\n- region\n",
    )


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "ask_rls.db"
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
    """Real AskEngine path with FakeLLM + sqlite warehouse containing sub_month."""
    warehouse = create_engine(f"sqlite:///{tmp_path / 'wh.db'}")
    with warehouse.begin() as conn:
        conn.execute(text("CREATE TABLE sub_month(region TEXT, n INTEGER)"))
        conn.execute(
            text(
                "INSERT INTO sub_month VALUES ('华东', 10), ('华北', 20), ('华南', 30)"
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


def test_analyst_ask_applies_seeded_rls(client: TestClient, tmp_path, monkeypatch):
    unfiltered = "SELECT region, n FROM sub_month"
    _wire_fake_ask(monkeypatch, tmp_path, sql=unfiltered)

    auth = login_headers(client, username="analyst1", password="analyst123")
    headers = workspace_headers(client, auth)
    r = client.post(
        "/ask",
        headers=headers,
        json={"domain": "biz", "question": "各区域用户数"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body.get("sql")
    assert "华东" in body["sql"]
    regions = {row.get("region") for row in body.get("rows") or []}
    if regions:
        assert regions == {"华东"}


def test_analyst_session_ask_applies_seeded_rls(client: TestClient, tmp_path, monkeypatch):
    unfiltered = "SELECT region, n FROM sub_month"
    _wire_fake_ask(monkeypatch, tmp_path, sql=unfiltered)

    auth = login_headers(client, username="analyst1", password="analyst123")
    headers = workspace_headers(client, auth)
    created = client.post(
        "/sessions",
        headers=headers,
        json={"domain": "biz", "title": "rls"},
    )
    assert created.status_code == 200
    sid = created.json()["id"]

    ask = client.post(
        f"/sessions/{sid}/ask",
        headers=headers,
        json={"question": "各区域用户数"},
    )
    assert ask.status_code == 200
    body = ask.json()
    assert body["status"] == "ok"
    assert body.get("sql")
    assert "华东" in body["sql"]


def test_org_admin_bypass_skips_rls(client: TestClient, tmp_path, monkeypatch):
    unfiltered = "SELECT region, n FROM sub_month"
    _wire_fake_ask(monkeypatch, tmp_path, sql=unfiltered)

    with Session(db.get_engine()) as session:
        org = session.exec(select(TiOrg)).one()
        assert org.rls_admin_bypass is True
        admin = session.exec(select(TiUser).where(TiUser.username == "demo")).one()
        member = session.exec(
            select(TiWorkspaceMember).where(TiWorkspaceMember.user_id == admin.id)
        ).one()
        session.add(
            TiRlsPolicy(
                workspace_id=member.workspace_id,
                member_id=member.id,  # type: ignore[arg-type]
                domain="biz",
                schema_name="biz",
                table_name="sub_month",
                column_name="region",
                op="in",
                values=["华东"],
            )
        )
        session.commit()

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
    assert "华东" not in body["sql"]
    assert len(body.get("rows") or []) == 3


def test_org_admin_bypass_false_applies_member_rls(
    client: TestClient, tmp_path, monkeypatch
):
    """§7.3: org_admin with rls_admin_bypass=false and a membership policy is filtered."""
    unfiltered = "SELECT region, n FROM sub_month"
    _wire_fake_ask(monkeypatch, tmp_path, sql=unfiltered)

    with Session(db.get_engine()) as session:
        org = session.exec(select(TiOrg)).one()
        org.rls_admin_bypass = False
        admin = session.exec(select(TiUser).where(TiUser.username == "demo")).one()
        member = session.exec(
            select(TiWorkspaceMember).where(TiWorkspaceMember.user_id == admin.id)
        ).one()
        session.add(
            TiRlsPolicy(
                workspace_id=member.workspace_id,
                member_id=member.id,  # type: ignore[arg-type]
                domain="biz",
                schema_name="biz",
                table_name="sub_month",
                column_name="region",
                op="in",
                values=["华东"],
            )
        )
        session.commit()

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
    assert "华东" in body["sql"]
    regions = {row.get("region") for row in body.get("rows") or []}
    if regions:
        assert regions == {"华东"}
