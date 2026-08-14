from apps.engine.ask import AskEngine, AskRequest, merge_pack_context
from apps.packs.models import Example, IndustryPack, Metric, Term
from sqlalchemy import create_engine, text


def _pack() -> IndustryPack:
    return IndustryPack(
        domain="biz",
        version="0.1.0",
        schemas=["biz"],
        table_whitelist=["users"],
        terminology=[Term(term="ARPU", standard="每用户平均收入", maps_to="users.arpu")],
        metrics=[Metric(name="arpu", label="ARPU", description="月均收入", dimensions=["month"])],
        examples=[Example(question="上月ARPU", sql="SELECT month, arpu FROM users ORDER BY month")],
        schema_docs="## users\n- month\n- arpu\n",
    )


def test_merge_pack_context_includes_db_term_and_example():
    pack = _pack()
    extra_terms = [Term(term="DOU", standard="户均流量", maps_to="users.dou")]
    extra_examples = [Example(question="上月DOU", sql="SELECT month, dou FROM users")]

    terminology_str, examples_list = merge_pack_context(pack, extra_terms, extra_examples)

    assert "ARPU=>每用户平均收入" in terminology_str
    assert "DOU=>户均流量" in terminology_str
    assert ("上月ARPU", "SELECT month, arpu FROM users ORDER BY month") in examples_list
    assert ("上月DOU", "SELECT month, dou FROM users") in examples_list


def test_merge_pack_context_none_extras_uses_pack_only():
    pack = _pack()
    terminology_str, examples_list = merge_pack_context(pack, None, None)
    assert "ARPU=>每用户平均收入" in terminology_str
    assert "DOU" not in terminology_str
    assert len(examples_list) == 1


class RecordingLLM:
    def __init__(self):
        self.last_terminology: str | None = None
        self.last_examples: list[tuple[str, str]] | None = None

    def generate_sql(self, *, question, schema_ctx, examples, terminology):
        self.last_terminology = terminology
        self.last_examples = examples
        return "SELECT month, arpu FROM users ORDER BY month"

    def narrate(self, *, question, sql, rows_preview):
        return "ok"


def test_ask_merges_extra_terms_into_llm_context(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    with eng.begin() as c:
        c.execute(text("CREATE TABLE users(month TEXT, arpu REAL)"))
        c.execute(text("INSERT INTO users VALUES ('2026-01', 50)"))

    llm = RecordingLLM()
    engine = AskEngine(warehouse=eng, llm=llm, packs_by_domain={"biz": _pack()})
    resp = engine.ask(
        AskRequest(domain="biz", question="2026年各月ARPU是多少"),
        extra_terms=[Term(term="DOU", standard="户均流量")],
        extra_examples=[Example(question="上月DOU", sql="SELECT 1")],
    )
    assert resp.status == "ok"
    assert llm.last_terminology is not None
    assert "DOU=>户均流量" in llm.last_terminology
    assert llm.last_examples is not None
    assert ("上月DOU", "SELECT 1") in llm.last_examples
