from sqlalchemy import create_engine, text
from apps.packs.models import IndustryPack, Example, Recommended, Term, Metric
from apps.engine.ask import AskEngine, AskRequest
from apps.engine.llm import FakeLLM
from apps.engine.rls import RlsPredicate


def _pack():
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


class _RecordingFakeLLM(FakeLLM):
    def __init__(self, sql: str, narrative: str):
        super().__init__(sql=sql, narrative=narrative)
        self.last_terminology: str | None = None

    def generate_sql(self, **kwargs) -> str:
        self.last_terminology = kwargs.get("terminology")
        return super().generate_sql(**kwargs)


def test_ask_returns_table_chart_narrative(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
        c.execute(text("INSERT INTO users VALUES ('2026-01', 50), ('2026-02', 60)"))
    llm = FakeLLM(sql="SELECT month, arpu FROM users ORDER BY month", narrative="ARPU 呈上升趋势。")
    engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _pack()})
    resp = engine.ask(AskRequest(domain="biz", question="2026年各月ARPU是多少"))
    assert resp.status == "ok"
    assert len(resp.rows) == 2
    assert resp.chart["type"] in {"line", "bar"}
    assert "ARPU" in resp.narrative or "上升" in resp.narrative
    assert resp.sql.lower().startswith("select")


def test_ask_blocks_write_sql(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'t.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
    llm = FakeLLM(sql="DELETE FROM users", narrative="x")
    engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _pack()})
    resp = engine.ask(AskRequest(domain="biz", question="删掉用户"))
    assert resp.status == "error"
    assert "安全" in resp.message


def test_ask_applies_rls_after_guard(tmp_path):
    """FakeLLM returns unfiltered SQL; AskEngine must inject RLS and prompt policy."""
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL, region TEXT)"))
        c.execute(
            text(
                "INSERT INTO users VALUES "
                "('2026-01', 50, '华东'), ('2026-01', 40, '华北')"
            )
        )
    llm = _RecordingFakeLLM(
        sql="SELECT month, arpu FROM users ORDER BY month",
        narrative="filtered",
    )
    engine = AskEngine(
        warehouse=eng,
        llm=llm,
        packs_by_domain={"biz": _pack()},
        dialect="sqlite",
    )
    preds = [RlsPredicate("biz", "users", "region", "in", ["华东"])]
    resp = engine.ask(
        AskRequest(domain="biz", question="2026年各月ARPU是多少"),
        rls_predicates=preds,
    )
    assert resp.status == "ok"
    assert resp.sql is not None
    assert "华东" in resp.sql
    assert "region" in resp.sql.lower()
    assert llm.last_terminology is not None
    assert "行级权限" in llm.last_terminology
    assert "华东" in llm.last_terminology
    assert len(resp.rows) == 1
    assert resp.rows[0]["arpu"] == 50
