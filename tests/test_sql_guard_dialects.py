from apps.engine.sql_guard import guard_sql


def test_guard_mysql_read():
    sql = guard_sql("SELECT 1 AS x", table_whitelist=set(), dialect="mysql")
    assert "SELECT" in sql.upper()


def test_guard_postgres_select_one_empty_whitelist():
    sql = guard_sql("SELECT 1 AS x", table_whitelist=set(), dialect="postgres")
    assert "SELECT" in sql.upper()


def test_guard_tsql_dialect():
    sql = guard_sql("SELECT 1 AS x", table_whitelist=set(), dialect="tsql")
    assert "SELECT" in sql.upper()


def test_guard_hive_dialect():
    sql = guard_sql("SELECT 1 AS x", table_whitelist=set(), dialect="hive")
    assert "SELECT" in sql.upper()
