import pytest

from apps.engine.column_guard import assert_columns_allowed
from apps.engine.sql_guard import SqlGuardError


def test_allows_whitelisted_columns():
    sql = "SELECT region, sub_cnt FROM biz.sub_month"
    allowed = {"sub_month": {"region", "sub_cnt", "arpu"}}
    assert_columns_allowed(sql, allowed, dialect="postgres")  # no raise


def test_rejects_unknown_column():
    sql = "SELECT region, secret FROM biz.sub_month"
    allowed = {"sub_month": {"region", "sub_cnt"}}
    with pytest.raises(SqlGuardError):
        assert_columns_allowed(sql, allowed, dialect="postgres")


def test_star_rejected_when_not_all_columns_granted():
    sql = "SELECT * FROM biz.sub_month"
    allowed = {"sub_month": {"region"}}
    with pytest.raises(SqlGuardError):
        assert_columns_allowed(sql, allowed, dialect="postgres")


def test_star_always_rejected_in_v1():
    sql = "SELECT * FROM biz.sub_month"
    allowed = {"sub_month": {"region", "sub_cnt", "arpu"}}
    with pytest.raises(SqlGuardError):
        assert_columns_allowed(sql, allowed, dialect="postgres")


def test_allows_qualified_alias_column():
    sql = "SELECT a.region FROM biz.sub_month a"
    allowed = {"sub_month": {"region", "sub_cnt"}}
    assert_columns_allowed(sql, allowed, dialect="postgres")


def test_rejects_unqualified_with_multiple_tables():
    sql = (
        "SELECT region FROM biz.sub_month a "
        "JOIN biz.channel_day b ON a.region = b.region"
    )
    allowed = {
        "sub_month": {"region", "sub_cnt"},
        "channel_day": {"region", "channel"},
    }
    with pytest.raises(SqlGuardError):
        assert_columns_allowed(sql, allowed, dialect="postgres")


def test_allows_qualified_multi_table():
    sql = (
        "SELECT a.region, b.channel FROM biz.sub_month a "
        "JOIN biz.channel_day b ON a.region = b.region"
    )
    allowed = {
        "sub_month": {"region", "sub_cnt"},
        "channel_day": {"region", "channel"},
    }
    assert_columns_allowed(sql, allowed, dialect="postgres")
