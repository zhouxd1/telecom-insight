from apps.packs.models import IndustryPack, Term, Metric
from apps.engine.schema_rag import retrieve_schema_context


def test_retrieve_prefers_arpu_section():
    pack = IndustryPack(
        domain="biz",
        version="0.1.0",
        table_whitelist=["users", "channel"],
        terminology=[Term(term="ARPU", standard="每用户平均收入", maps_to="users.arpu")],
        metrics=[Metric(name="arpu", label="ARPU", description="月均收入", dimensions=["month"])],
        schema_docs="## biz.users\n- arpu: 每用户平均收入\n\n## biz.channel\n- channel_name: 渠道名\n",
    )
    ctx = retrieve_schema_context(pack, "上月ARPU是多少", top_k=1)
    assert "biz.users" in ctx
    assert "channel" not in ctx.lower() or "arpu" in ctx.lower()
