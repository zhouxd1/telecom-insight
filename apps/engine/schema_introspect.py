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
        c.is_nullable,
        c.column_default,
        c.ordinal_position,
        c.character_maximum_length,
        c.numeric_precision,
        c.numeric_scale
    FROM information_schema.columns AS c
    WHERE c.table_schema IN ('biz', 'network', 'cs')
    ORDER BY c.table_schema, c.table_name, c.ordinal_position
    """
)

_PG_PK_SQL = text(
    """
    SELECT
        tc.table_schema,
        tc.table_name,
        kcu.column_name
    FROM information_schema.table_constraints AS tc
    JOIN information_schema.key_column_usage AS kcu
        ON tc.constraint_name = kcu.constraint_name
        AND tc.table_schema = kcu.table_schema
        AND tc.table_name = kcu.table_name
    WHERE tc.constraint_type = 'PRIMARY KEY'
        AND tc.table_schema IN ('biz', 'network', 'cs')
    """
)

_PG_TABLE_KIND_SQL = text(
    """
    SELECT table_schema, table_name, table_type
    FROM information_schema.tables
    WHERE table_schema IN ('biz', 'network', 'cs')
    """
)

_PG_TABLE_COMMENTS_SQL = text(
    """
    SELECT n.nspname AS schema_name, c.relname AS table_name,
           obj_description(c.oid, 'pg_class') AS table_comment
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname IN ('biz', 'network', 'cs')
    """
)

_PG_COLUMN_COMMENTS_SQL = text(
    """
    SELECT n.nspname AS schema_name, c.relname AS table_name, a.attname AS column_name,
           col_description(c.oid, a.attnum) AS column_comment
    FROM pg_attribute a
    JOIN pg_class c ON a.attrelid = c.oid
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE a.attnum > 0 AND NOT a.attisdropped
      AND n.nspname IN ('biz', 'network', 'cs')
    """
)


def _col_dict(
    name: str,
    data_type: str,
    nullable: bool,
    *,
    ordinal_position: int,
    column_default: str | None = None,
    is_primary_key: bool = False,
    column_comment: str | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "data_type": data_type,
        "nullable": nullable,
        "ordinal_position": ordinal_position,
        "column_default": column_default,
        "is_primary_key": is_primary_key,
        "column_comment": column_comment,
    }


def _table_dict(
    schema_name: str,
    table_name: str,
    columns: list[dict[str, Any]],
    *,
    table_kind: str,
    table_comment: str | None = None,
) -> dict[str, Any]:
    return {
        "schema_name": schema_name,
        "table_name": table_name,
        "table_kind": table_kind,
        "table_comment": table_comment,
        "columns": columns,
    }


def _format_pg_data_type(row: dict[str, Any]) -> str:
    data_type = row["data_type"]
    if row.get("character_maximum_length") is not None:
        return f"{data_type}({row['character_maximum_length']})"
    if data_type in {"numeric", "decimal"} and row.get("numeric_precision") is not None:
        scale = row.get("numeric_scale") or 0
        return f"{data_type}({row['numeric_precision']},{scale})"
    return data_type


def _normalize_pg_table_kind(table_type: str | None) -> str:
    if table_type == "BASE TABLE":
        return "table"
    if table_type == "VIEW":
        return "view"
    return table_type or "table"


def _sqlite_table_comment(inspector: Any, table_name: str, schema: str | None) -> str | None:
    try:
        result = inspector.get_table_comment(table_name, schema=schema)
    except Exception:
        return None
    if isinstance(result, dict):
        return result.get("text")
    return None


def _sqlite_column_comments(
    inspector: Any, table_name: str, schema: str | None
) -> dict[str, str | None]:
    try:
        raw = inspector.get_column_comments(table_name, schema=schema)
    except Exception:
        return {}
    if not isinstance(raw, dict):
        return {}
    return {name: (info.get("text") if isinstance(info, dict) else info) for name, info in raw.items()}


def _sqlite_columns(
    inspector: Any,
    table_name: str,
    schema: str | None,
) -> list[dict[str, Any]]:
    try:
        raw_cols = inspector.get_columns(table_name, schema=schema)
    except Exception:
        return []
    try:
        pk = inspector.get_pk_constraint(table_name, schema=schema) or {}
        pk_cols = set(pk.get("constrained_columns") or [])
    except Exception:
        pk_cols = set()
    col_comments = _sqlite_column_comments(inspector, table_name, schema)
    columns: list[dict[str, Any]] = []
    for ordinal, col in enumerate(raw_cols, start=1):
        default = col.get("default")
        columns.append(
            _col_dict(
                col["name"],
                str(col.get("type") or ""),
                bool(col.get("nullable", True)),
                ordinal_position=ordinal,
                column_default=str(default) if default is not None else None,
                is_primary_key=col["name"] in pk_cols,
                column_comment=col_comments.get(col["name"]),
            )
        )
    return columns


def _introspect_postgres(engine: Engine) -> list[dict[str, Any]]:
    tables: dict[tuple[str, str], list[dict[str, Any]]] = {}
    table_kinds: dict[tuple[str, str], str] = {}
    table_comments: dict[tuple[str, str], str | None] = {}
    column_comments: dict[tuple[str, str, str], str | None] = {}
    pk_columns: set[tuple[str, str, str]] = set()

    try:
        with engine.connect() as conn:
            for row in conn.execute(_PG_COLUMNS_SQL).mappings():
                key = (row["table_schema"], row["table_name"])
                tables.setdefault(key, []).append(
                    _col_dict(
                        row["column_name"],
                        _format_pg_data_type(row),
                        str(row["is_nullable"]).upper() == "YES",
                        ordinal_position=int(row["ordinal_position"]),
                        column_default=row["column_default"],
                        is_primary_key=False,
                        column_comment=None,
                    )
                )

            for row in conn.execute(_PG_PK_SQL).mappings():
                pk_columns.add(
                    (row["table_schema"], row["table_name"], row["column_name"])
                )

            for row in conn.execute(_PG_TABLE_KIND_SQL).mappings():
                key = (row["table_schema"], row["table_name"])
                table_kinds[key] = _normalize_pg_table_kind(row["table_type"])

            try:
                for row in conn.execute(_PG_TABLE_COMMENTS_SQL).mappings():
                    key = (row["schema_name"], row["table_name"])
                    table_comments[key] = row["table_comment"]
            except Exception:
                pass

            try:
                for row in conn.execute(_PG_COLUMN_COMMENTS_SQL).mappings():
                    key = (row["schema_name"], row["table_name"], row["column_name"])
                    column_comments[key] = row["column_comment"]
            except Exception:
                pass
    except Exception:
        pass

    for key, cols in tables.items():
        schema, name = key
        for col in cols:
            pk_key = (schema, name, col["name"])
            col["is_primary_key"] = pk_key in pk_columns
            col["column_comment"] = column_comments.get(pk_key)

    return [
        _table_dict(
            schema,
            name,
            cols,
            table_kind=table_kinds.get((schema, name), "table"),
            table_comment=table_comments.get((schema, name)),
        )
        for (schema, name), cols in tables.items()
    ]


def _introspect_sqlite(engine: Engine) -> list[dict[str, Any]]:
    inspector = inspect(engine)
    out: list[dict[str, Any]] = []
    schema_names = inspector.get_schema_names() or [None]
    if "main" in schema_names:
        schema_names = ["main"]
    elif not schema_names:
        schema_names = [None]

    for schema in schema_names:
        try:
            table_names = inspector.get_table_names(schema=schema)
        except Exception:
            table_names = []
        for table_name in table_names:
            columns = _sqlite_columns(inspector, table_name, schema)
            if not columns:
                continue
            out.append(
                _table_dict(
                    schema or "main",
                    table_name,
                    columns,
                    table_kind="table",
                    table_comment=_sqlite_table_comment(inspector, table_name, schema),
                )
            )

        try:
            view_names = inspector.get_view_names(schema=schema)
        except Exception:
            view_names = []
        for view_name in view_names:
            columns = _sqlite_columns(inspector, view_name, schema)
            if not columns:
                continue
            out.append(
                _table_dict(
                    schema or "main",
                    view_name,
                    columns,
                    table_kind="view",
                    table_comment=_sqlite_table_comment(inspector, view_name, schema),
                )
            )
    return out


def introspect_tables(
    engine: Engine, *, db_type: str = "postgres"
) -> list[dict[str, Any]]:
    """Return table/column metadata for Postgres (biz/network/cs) or SQLite tests."""
    kind = (db_type or "postgres").lower()
    if kind in {"sqlite", "sqlite3"}:
        return _introspect_sqlite(engine)
    if kind in {"postgres", "postgresql"}:
        return _introspect_postgres(engine)
    return _introspect_sqlite(engine)
