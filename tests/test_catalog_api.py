"""Catalog API tests (TestClient + temp SQLite)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Column, Integer, MetaData, String, Table, create_engine, inspect, text

from apps.catalog import db
from apps.catalog.main import app
from apps.catalog.migrate import ensure_catalog_columns
from apps.catalog.settings import settings


@pytest.fixture
def catalog_client(tmp_path, monkeypatch):
    cat_db = tmp_path / "catalog.db"
    monkeypatch.setattr(settings, "catalog_database_url", f"sqlite:///{cat_db}")  # TI_CATALOG_DATABASE_URL
    db.reset_engine()
    with TestClient(app) as client:
        yield client
    db.reset_engine()


@pytest.fixture
def source_sqlite(tmp_path):
    path = tmp_path / "source.db"
    url = f"sqlite:///{path}"
    engine = create_engine(url)
    meta = MetaData()
    Table(
        "sub_month",
        meta,
        Column("region", String, nullable=False),
        Column("sub_cnt", Integer, nullable=True),
    )
    Table(
        "channel_day",
        meta,
        Column("channel", String, nullable=False),
        Column("orders", Integer, nullable=True),
    )
    meta.create_all(engine)
    engine.dispose()
    return url


def test_health(catalog_client: TestClient):
    r = catalog_client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok", "service": "catalog"}


def test_ensure_catalog_columns_adds_missing_on_legacy_sqlite(tmp_path):
    """Migrate old cat_table/cat_column schemas; BOOLEAN DEFAULT FALSE must work on SQLite."""
    db_path = tmp_path / "legacy_catalog.db"
    engine = create_engine(f"sqlite:///{db_path}")
    if engine.dialect.name != "sqlite":
        pytest.skip("legacy migrate fixture uses SQLite DDL")

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE cat_table (
                    id INTEGER PRIMARY KEY,
                    datasource_id INTEGER NOT NULL,
                    schema_name VARCHAR NOT NULL,
                    table_name VARCHAR NOT NULL,
                    refreshed_at DATETIME NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE cat_column (
                    id INTEGER PRIMARY KEY,
                    table_id INTEGER NOT NULL,
                    column_name VARCHAR NOT NULL,
                    data_type VARCHAR NOT NULL DEFAULT '',
                    nullable BOOLEAN NOT NULL DEFAULT 1,
                    FOREIGN KEY(table_id) REFERENCES cat_table (id)
                )
                """
            )
        )

    before_table = {c["name"] for c in inspect(engine).get_columns("cat_table")}
    before_column = {c["name"] for c in inspect(engine).get_columns("cat_column")}
    assert "table_kind" not in before_table
    assert "is_primary_key" not in before_column

    ensure_catalog_columns(engine)

    after_table = {c["name"] for c in inspect(engine).get_columns("cat_table")}
    after_column = {c["name"] for c in inspect(engine).get_columns("cat_column")}
    assert {"table_kind", "table_comment"} <= after_table
    assert {
        "ordinal_position",
        "column_default",
        "is_primary_key",
        "column_comment",
    } <= after_column

    # Second call is a no-op (idempotent).
    ensure_catalog_columns(engine)
    engine.dispose()


def test_introspect_schema_grants_effective(
    catalog_client: TestClient, source_sqlite: str
):
    introspect = catalog_client.post(
        "/v1/introspect",
        json={
            "workspace_id": 1,
            "datasource_id": 10,
            "db_type": "sqlite",
            "sqlalchemy_url": source_sqlite,
        },
    )
    assert introspect.status_code == 200, introspect.text
    body = introspect.json()
    assert body["tables"] == 2
    assert body["columns"] == 4

    empty_eff = catalog_client.get(
        "/v1/workspaces/1/effective",
        params={"datasource_id": 10},
    )
    assert empty_eff.status_code == 200
    assert empty_eff.json() == {"tables": [], "columns": {}, "empty": True}

    schema = catalog_client.get(
        "/v1/workspaces/1/schema",
        params={"datasource_id": 10},
    )
    assert schema.status_code == 200
    tree = schema.json()
    by_name = {t["table_name"]: t for t in tree["tables"]}
    assert set(by_name) == {"sub_month", "channel_day"}
    assert by_name["sub_month"]["granted"] is False
    col_names = {c["name"] for c in by_name["sub_month"]["columns"]}
    assert col_names == {"region", "sub_cnt"}
    assert all(c["granted"] is False for c in by_name["sub_month"]["columns"])

    sub = by_name["sub_month"]
    assert sub["table_kind"] in {"table", "view"}
    assert "table_comment" in sub
    region = next(c for c in sub["columns"] if c["name"] == "region")
    assert "ordinal_position" in region
    assert "column_default" in region
    assert "is_primary_key" in region
    assert "column_comment" in region

    schema_name = by_name["sub_month"]["schema_name"]
    grants = catalog_client.put(
        "/v1/workspaces/1/grants",
        json={
            "datasource_id": 10,
            "tables": [
                {
                    "schema_name": schema_name,
                    "table_name": "sub_month",
                    "columns": ["region"],
                }
            ],
        },
    )
    assert grants.status_code == 200, grants.text
    assert grants.json()["tables"] == 1
    assert grants.json()["columns"] == 1

    schema2 = catalog_client.get(
        "/v1/workspaces/1/schema",
        params={"datasource_id": 10},
    )
    by_name2 = {t["table_name"]: t for t in schema2.json()["tables"]}
    assert by_name2["sub_month"]["granted"] is True
    granted_cols = {
        c["name"]: c["granted"] for c in by_name2["sub_month"]["columns"]
    }
    assert granted_cols["region"] is True
    assert granted_cols["sub_cnt"] is False

    eff = catalog_client.get(
        "/v1/workspaces/1/effective",
        params={"datasource_id": 10},
    )
    assert eff.status_code == 200
    payload = eff.json()
    assert payload["empty"] is False
    assert payload["tables"] == ["sub_month"]
    assert payload["columns"] == {"sub_month": ["region"]}


def test_put_grants_replaces(catalog_client: TestClient, source_sqlite: str):
    catalog_client.post(
        "/v1/introspect",
        json={
            "workspace_id": 1,
            "datasource_id": 10,
            "db_type": "sqlite",
            "sqlalchemy_url": source_sqlite,
        },
    )
    schema = catalog_client.get(
        "/v1/workspaces/1/schema",
        params={"datasource_id": 10},
    ).json()
    schema_name = schema["tables"][0]["schema_name"]

    catalog_client.put(
        "/v1/workspaces/1/grants",
        json={
            "datasource_id": 10,
            "tables": [
                {
                    "schema_name": schema_name,
                    "table_name": "sub_month",
                    "columns": ["region", "sub_cnt"],
                }
            ],
        },
    )
    catalog_client.put(
        "/v1/workspaces/1/grants",
        json={
            "datasource_id": 10,
            "tables": [
                {
                    "schema_name": schema_name,
                    "table_name": "channel_day",
                    "columns": ["channel"],
                }
            ],
        },
    )
    eff = catalog_client.get(
        "/v1/workspaces/1/effective",
        params={"datasource_id": 10},
    ).json()
    assert eff["tables"] == ["channel_day"]
    assert eff["columns"] == {"channel_day": ["channel"]}
