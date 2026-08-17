"""Datasource schema introspection (Postgres-first; SQLite for tests)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_PG_COLUMNS_SQL = text(
    """
    SELECT
        c.table_schema,
        c.table_name,
        c.column_name,
        c.data_type,
        c.is_nullable
    FROM information_schema.columns AS c
    WHERE c.table_schema IN ('biz', 'network', 'cs')
    ORDER BY c.table_schema, c.table_name, c.ordinal_position
    """
)


def _col_dict(name: str, data_type: str, nullable: bool) -> dict[str, Any]:
    return {
        "name": name,
        "data_type": data_type,
        "nullable": nullable,
    }


def _table_rows(
    tables: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    return [
        {
            "schema_name": schema,
            "table_name": name,
            "columns": cols,
        }
        for (schema, name), cols in tables.items()
    ]


def _introspect_postgres(engine: Engine) -> list[dict[str, Any]]:
    tables: dict[tuple[str, str], list[dict[str, Any]]] = {}
    try:
        with engine.connect() as conn:
            rows = conn.execute(_PG_COLUMNS_SQL).mappings()
            for row in rows:
                key = (row["table_schema"], row["table_name"])
                tables.setdefault(key, []).append(
                    _col_dict(
                        row["column_name"],
                        row["data_type"],
                        str(row["is_nullable"]).upper() == "YES",
                    )
                )
    except Exception:
        # Missing schemas / permissions / empty catalog — return what we have.
        return _table_rows(tables)

    return _table_rows(tables)


def _introspect_sqlite(engine: Engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    out: list[dict[str, Any]] = []
    schema_names = inspector.get_schema_names() or [None]
    # Prefer "main" when present; otherwise scan default / listed schemas.
    if "main" in schema_names:
        schema_names = ["main"]
    elif not schema_names:
        schema_names = [None]

    for schema in schema_names:
        try:
            table_names = inspector.get_table_names(schema=schema)
        except Exception:
            continue
        for table_name in table_names:
            try:
                raw_cols = inspector.get_columns(table_name, schema=schema)
            except Exception:
                continue
            columns = [
                _col_dict(
                    c["name"],
                    str(c.get("type") or ""),
                    bool(c.get("nullable", True)),
                )
                for c in raw_cols
            ]
            out.append(
                {
                    "schema_name": schema or "main",
                    "table_name": table_name,
                    "columns": columns,
                }
            )
    return out


def introspect_tables(
    engine: Engine, *, db_type: str = "postgres"
) -> list[dict[str, Any]]:
    """Return [{schema_name, table_name, columns: [{name, data_type, nullable}]}].

    Postgres: information_schema for schemas biz/network/cs (missing → empty/graceful).
    SQLite: SQLAlchemy Inspector for tests.
    """
    kind = (db_type or "postgres").lower()
    if kind in {"sqlite", "sqlite3"}:
        return _introspect_sqlite(engine)
    if kind in {"postgres", "postgresql"}:
        return _introspect_postgres(engine)
    # Fallback: inspector (best-effort for other engines in tests)
    return _introspect_sqlite(engine)
