"""Column-level ACL checks for SELECT SQL (sqlglot)."""

from __future__ import annotations

import sqlglot
from sqlglot import exp

from apps.engine.sql_guard import SqlGuardError, resolve_sqlglot_dialect


def _base_table_name(name: str) -> str:
    return name.split(".")[-1].strip('"').lower()


def _normalize_allowed(
    allowed_columns_by_table: dict[str, set[str]],
) -> dict[str, set[str]]:
    return {
        _base_table_name(t): {c.lower() for c in cols}
        for t, cols in allowed_columns_by_table.items()
    }


def _alias_to_table(tree: exp.Expression) -> dict[str, str]:
    """Map alias / bare table name → base table name (lower)."""
    mapping: dict[str, str] = {}
    for t in tree.find_all(exp.Table):
        base = _base_table_name(t.name)
        mapping[base] = base
        if t.alias:
            mapping[t.alias.lower()] = base
    return mapping


def _outer_table_bases(tree: exp.Expression) -> list[str]:
    """Distinct base table names appearing in the statement (order preserved)."""
    seen: list[str] = []
    for t in tree.find_all(exp.Table):
        base = _base_table_name(t.name)
        if base not in seen:
            seen.append(base)
    return seen


def assert_columns_allowed(
    sql: str,
    allowed_columns_by_table: dict[str, set[str]],
    dialect: str = "postgres",
) -> None:
    """Raise SqlGuardError if SQL references columns outside the allow map.

    v1 rules:
    - SELECT * / table.* is always rejected
    - Unauthorized columns are rejected
    - Unqualified columns require exactly one table in the statement
    """
    raw = (sql or "").strip().rstrip(";")
    if not raw:
        raise SqlGuardError("empty sql")

    read = resolve_sqlglot_dialect(dialect)
    try:
        tree = sqlglot.parse_one(raw, read=read)
    except Exception as e:
        raise SqlGuardError(f"sql parse failed: {e}") from e

    if any(isinstance(node, exp.Star) for node in tree.find_all(exp.Star)):
        raise SqlGuardError("SELECT * is not allowed")

    allowed = _normalize_allowed(allowed_columns_by_table)
    alias_map = _alias_to_table(tree)
    tables = _outer_table_bases(tree)

    for col in tree.find_all(exp.Column):
        col_name = (col.name or "").lower()
        if not col_name:
            continue
        table_ref = (col.table or "").lower() if col.table else ""

        if table_ref:
            base = alias_map.get(table_ref) or _base_table_name(table_ref)
            allowed_cols = allowed.get(base)
            if allowed_cols is None:
                raise SqlGuardError(f"table not in column allow list: {base}")
            if col_name not in allowed_cols:
                raise SqlGuardError(f"column not allowed: {base}.{col_name}")
            continue

        if len(tables) != 1:
            raise SqlGuardError(
                "unqualified column requires a single-table query: "
                f"{col_name}"
            )
        base = tables[0]
        allowed_cols = allowed.get(base)
        if allowed_cols is None:
            raise SqlGuardError(f"table not in column allow list: {base}")
        if col_name not in allowed_cols:
            raise SqlGuardError(f"column not allowed: {base}.{col_name}")
