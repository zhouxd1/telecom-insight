import pytest

from apps.engine.preview_sql import build_preview_sql
from apps.engine.sql_guard import SqlGuardError


def test_build_preview_sql_postgres():
    sql = build_preview_sql(
        "biz",
        "sub_month",
        ["region", "sub_cnt"],
        dialect="postgres",
        limit=50,
    )
    assert sql == 'SELECT "region", "sub_cnt" FROM "biz"."sub_month" LIMIT 51'


def test_build_preview_sql_sqlite_main_omits_schema():
    sql = build_preview_sql(
        "main",
        "sub_month",
        ["region"],
        dialect="sqlite",
        limit=50,
    )
    assert sql == 'SELECT "region" FROM "sub_month" LIMIT 51'


def test_rejects_bad_identifier():
    with pytest.raises(SqlGuardError):
        build_preview_sql("biz", "sub_month;drop", ["region"], dialect="postgres", limit=50)
