from apps.engine.rls import RlsPredicate, apply_rls, merge_predicates, format_rls_prompt
from apps.engine.sql_guard import SqlGuardError
import pytest


def test_merge_same_column_or():
    preds = [
        RlsPredicate("biz", "sub_month", "region", "in", ["华东"]),
        RlsPredicate("biz", "sub_month", "region", "in", ["华北"]),
    ]
    merged = merge_predicates(preds)
    assert ("biz", "sub_month") in merged
    # single region IN with both values or OR of two — either OK if semantically equal
    sql_frag = merged[("biz", "sub_month")]
    assert "华东" in sql_frag and "华北" in sql_frag


def test_apply_rls_simple_select():
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    out = apply_rls(
        "SELECT region, SUM(sub_cnt) AS sub_cnt FROM biz.sub_month GROUP BY region",
        preds,
        dialect="postgres",
    )
    assert "华东" in out
    assert "region" in out.lower()


def test_apply_rls_eq():
    preds = [RlsPredicate("biz", "channel_day", "channel", "eq", ["营业厅"])]
    out = apply_rls(
        "SELECT day, new_users FROM biz.channel_day",
        preds,
        dialect="postgres",
    )
    assert "营业厅" in out


def test_no_matching_table_unchanged():
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    sql = "SELECT 1 AS x"
    assert apply_rls(sql, preds, dialect="postgres") == sql


def test_prompt_mentions_policy():
    text = format_rls_prompt([RlsPredicate("biz", "sub_month", "region", "in", ["华东"])])
    assert "region" in text and "华东" in text


def test_apply_rls_unqualified_table():
    """FROM sub_month (no schema) must still match policy on biz.sub_month."""
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    out = apply_rls(
        "SELECT region, SUM(sub_cnt) AS sub_cnt FROM sub_month GROUP BY region",
        preds,
        dialect="postgres",
    )
    assert "华东" in out
    assert "region" in out.lower()


def test_merge_cross_column_and():
    preds = [
        RlsPredicate("biz", "sub_month", "region", "in", ["华东"]),
        RlsPredicate("biz", "sub_month", "channel", "eq", ["营业厅"]),
    ]
    merged = merge_predicates(preds)
    sql_frag = merged[("biz", "sub_month")]
    assert "region" in sql_frag.lower()
    assert "华东" in sql_frag
    assert "channel" in sql_frag.lower()
    assert "营业厅" in sql_frag
    assert " AND " in sql_frag


def test_apply_rls_unsupported_op_raises():
    preds = [RlsPredicate("biz", "sub_month", "region", "like", ["华东%"])]
    with pytest.raises(SqlGuardError):
        apply_rls(
            "SELECT region FROM biz.sub_month",
            preds,
            dialect="postgres",
        )


def test_apply_rls_union_with_policies_raises():
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    with pytest.raises(SqlGuardError):
        apply_rls(
            "SELECT region FROM biz.sub_month UNION SELECT region FROM biz.sub_month",
            preds,
            dialect="postgres",
        )


def test_apply_rls_subquery_only_policy_table_raises():
    """Policy table only inside EXISTS/subquery must refuse — never silent outer WHERE."""
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    with pytest.raises(SqlGuardError, match="cannot safely apply rls"):
        apply_rls(
            "SELECT id FROM other_table WHERE EXISTS (SELECT 1 FROM biz.sub_month)",
            preds,
            dialect="postgres",
        )


def test_apply_rls_exists_subquery_only_raises():
    """Policy table only inside EXISTS must not silently filter the outer SELECT."""
    preds = [RlsPredicate("biz", "sub_month", "region", "in", ["华东"])]
    sql = (
        "SELECT u.id FROM other.users AS u "
        "WHERE EXISTS (SELECT 1 FROM biz.sub_month AS s WHERE s.region = u.region)"
    )
    with pytest.raises(SqlGuardError, match="cannot safely apply rls"):
        apply_rls(sql, preds, dialect="postgres")


def test_apply_rls_join_two_policy_tables():
    """JOIN of two policy tables: qualified injection or refuse — never ambiguous cols."""
    preds = [
        RlsPredicate("biz", "sub_month", "region", "in", ["华东"]),
        RlsPredicate("biz", "channel_day", "channel", "eq", ["营业厅"]),
    ]
    sql = (
        "SELECT s.region, c.channel FROM biz.sub_month AS s "
        "JOIN biz.channel_day AS c ON s.day = c.day"
    )
    try:
        out = apply_rls(sql, preds, dialect="postgres")
    except SqlGuardError as e:
        assert "cannot safely apply rls" in str(e).lower()
        return
    assert "华东" in out and "营业厅" in out
    # Filters must bind to the correct join side (not bare region/channel)
    where_part = out.upper().split("WHERE", 1)[-1] if "WHERE" in out.upper() else ""
    assert where_part, "expected WHERE clause with RLS filters"
    wlow = where_part.lower()
    assert "s.region" in wlow or "biz.sub_month.region" in wlow
    assert "c.channel" in wlow or "biz.channel_day.channel" in wlow
    assert " region in" not in f" {wlow}" and " channel =" not in f" {wlow}"
