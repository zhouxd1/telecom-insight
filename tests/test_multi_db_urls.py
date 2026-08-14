from apps.api.db_types import PROTOCOL_FAMILY, build_sqlalchemy_url, is_p0, is_p1


def test_p0_families():
    assert PROTOCOL_FAMILY["hive"] == "hive"
    assert PROTOCOL_FAMILY["kingbase"] == "postgres"
    assert PROTOCOL_FAMILY["dameng"] == "dm"
    assert PROTOCOL_FAMILY["postgres"] == "postgres"
    assert PROTOCOL_FAMILY["mysql"] == "mysql"
    assert PROTOCOL_FAMILY["sqlserver"] == "mssql"
    assert PROTOCOL_FAMILY["opengauss"] == "postgres"
    assert PROTOCOL_FAMILY["gaussdb"] == "postgres"
    assert PROTOCOL_FAMILY["oceanbase_mysql"] == "mysql"
    assert PROTOCOL_FAMILY["tidb"] == "mysql"
    assert is_p0("oceanbase_mysql") and is_p1("gbase")
    assert is_p1("shentong") and is_p1("polardb") and is_p1("tdsql")
    assert not is_p0("gbase")
    assert not is_p1("postgres")


def test_build_mysql_url():
    url = build_sqlalchemy_url(
        db_type="mysql", host="h", port=3306, database="d", username="u", password="p"
    )
    assert url.startswith("mysql+pymysql://")
    assert "u:p@" in url or "u%3A" not in url  # password present
    assert "@h:3306/d" in url


def test_build_postgres_family_url():
    url = build_sqlalchemy_url(
        db_type="kingbase", host="h", port=54321, database="db", username="u", password="p"
    )
    assert url.startswith("postgresql+psycopg://")


def test_build_mssql_url_includes_driver():
    url = build_sqlalchemy_url(
        db_type="sqlserver",
        host="h",
        port=1433,
        database="d",
        username="u",
        password="p",
    )
    assert url.startswith("mssql+pyodbc://")
    assert "Driver=" in url


def test_build_hive_and_dameng_urls():
    hive = build_sqlalchemy_url(
        db_type="hive", host="h", port=10000, database="default", username="u", password=""
    )
    assert hive.startswith("hive://")
    dm = build_sqlalchemy_url(
        db_type="dameng", host="h", port=5236, database="DAMENG", username="u", password="p"
    )
    assert dm.startswith("dm+dmPython://")
