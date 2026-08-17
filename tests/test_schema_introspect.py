from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from apps.engine.schema_introspect import introspect_tables


def test_introspect_sqlite_in_memory():
    engine = create_engine("sqlite:///:memory:")
    meta = MetaData()
    Table(
        "sub_month",
        meta,
        Column("region", String, nullable=False),
        Column("sub_cnt", Integer, nullable=True),
    )
    meta.create_all(engine)

    rows = introspect_tables(engine, db_type="sqlite")
    by_name = {r["table_name"]: r for r in rows}
    assert "sub_month" in by_name
    table = by_name["sub_month"]
    cols = {c["name"]: c for c in table["columns"]}
    assert cols["region"]["nullable"] is False
    assert cols["sub_cnt"]["nullable"] is True
    assert cols["region"]["data_type"]
    assert cols["sub_cnt"]["data_type"]


def test_introspect_sqlite_empty_db():
    engine = create_engine("sqlite:///:memory:")
    rows = introspect_tables(engine, db_type="sqlite")
    assert rows == []
