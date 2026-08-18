from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine

from apps.engine.schema_introspect import _format_pg_data_type, introspect_tables


def test_format_pg_data_type_varchar_numeric_integer():
    assert (
        _format_pg_data_type(
            {
                "data_type": "character varying",
                "character_maximum_length": 64,
                "numeric_precision": None,
                "numeric_scale": None,
            }
        )
        == "character varying(64)"
    )
    assert (
        _format_pg_data_type(
            {
                "data_type": "numeric",
                "character_maximum_length": None,
                "numeric_precision": 10,
                "numeric_scale": 2,
            }
        )
        == "numeric(10,2)"
    )
    assert (
        _format_pg_data_type(
            {
                "data_type": "integer",
                "character_maximum_length": None,
                "numeric_precision": 32,
                "numeric_scale": 0,
            }
        )
        == "integer"
    )


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


def test_introspect_sqlite_includes_pk_default_ordinal():
    engine = create_engine("sqlite:///:memory:")
    meta = MetaData()
    Table(
        "sub_month",
        meta,
        Column("id", Integer, primary_key=True),
        Column("region", String, nullable=False, server_default="华东"),
        Column("sub_cnt", Integer, nullable=True),
    )
    meta.create_all(engine)
    rows = introspect_tables(engine, db_type="sqlite")
    table = next(r for r in rows if r["table_name"] == "sub_month")
    assert table["table_kind"] in {"table", "BASE TABLE"}
    assert "table_comment" in table
    cols = {c["name"]: c for c in table["columns"]}
    assert cols["id"]["is_primary_key"] is True
    assert cols["region"]["is_primary_key"] is False
    assert cols["id"]["ordinal_position"] == 1
    assert cols["region"]["ordinal_position"] == 2
    assert cols["sub_cnt"]["nullable"] is True
    assert "column_default" in cols["region"]
    assert "column_comment" in cols["region"]
