import pytest
from apps.engine.sql_guard import guard_sql, SqlGuardError

WL = {"users", "orders"}


def test_allows_simple_select():
    sql = guard_sql("SELECT month, AVG(arpu) FROM users GROUP BY month", WL)
    assert "select" in sql.lower()


def test_rejects_insert():
    with pytest.raises(SqlGuardError):
        guard_sql("INSERT INTO users VALUES (1)", WL)


def test_rejects_multi_statement():
    with pytest.raises(SqlGuardError):
        guard_sql("SELECT 1; DROP TABLE users", WL)


def test_rejects_unknown_table():
    with pytest.raises(SqlGuardError):
        guard_sql("SELECT * FROM secrets", WL)


def test_allows_schema_qualified_whitelist_name():
    sql = guard_sql("SELECT * FROM biz.users", {"users"})
    assert "users" in sql.lower()
