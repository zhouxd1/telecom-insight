from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp

from apps.engine.sql_guard import SqlGuardError, resolve_sqlglot_dialect


@dataclass(frozen=True)
class RlsPredicate:
    schema_name: str
    table_name: str
    column_name: str
    op: str  # in | eq
    values: tuple[str, ...] | list[str]


def _quote_lit(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def _pred_sql(p: RlsPredicate) -> str:
    col = p.column_name  # validated against catalog before call
    vals = list(p.values)
    if p.op == "eq":
        if len(vals) != 1:
            raise SqlGuardError("eq requires exactly one value")
        return f"{col} = {_quote_lit(vals[0])}"
    if p.op == "in":
        if not vals:
            raise SqlGuardError("in requires values")
        return f"{col} IN ({', '.join(_quote_lit(v) for v in vals)})"
    raise SqlGuardError(f"unsupported op: {p.op}")


def merge_predicates(preds: list[RlsPredicate]) -> dict[tuple[str, str], str]:
    """Return map (schema, table) -> AND-combined WHERE fragment (no leading AND)."""
    by_table: dict[tuple[str, str], dict[str, list[str]]] = {}
    for p in preds:
        key = (p.schema_name.lower(), p.table_name.lower())
        by_table.setdefault(key, {})
        by_table[key].setdefault(p.column_name.lower(), []).append(_pred_sql(p))
    out: dict[tuple[str, str], str] = {}
    for table_key, cols in by_table.items():
        col_parts = []
        for _col, frags in cols.items():
            col_parts.append("(" + " OR ".join(frags) + ")" if len(frags) > 1 else frags[0])
        out[table_key] = " AND ".join(col_parts)
    return out


def apply_rls(sql: str, preds: list[RlsPredicate], *, dialect: str = "postgres") -> str:
    if not preds:
        return sql
    merged = merge_predicates(preds)
    read = resolve_sqlglot_dialect(dialect)
    try:
        tree = sqlglot.parse_one(sql, read=read)
    except Exception as e:
        raise SqlGuardError(f"rls parse failed: {e}") from e
    if not isinstance(tree, (exp.Select, exp.Union)):
        raise SqlGuardError("rls only supports SELECT")

    used_tables = []
    for t in tree.find_all(exp.Table):
        schema = (t.db or "").lower()
        name = t.name.lower()
        used_tables.append((schema, name))

    # Unqualified FROM t: match by table_name alone; reject if multiple schemas collide.
    unqualified_names = {u_tbl for u_sch, u_tbl in used_tables if not u_sch}
    for name in unqualified_names:
        schemas = {sch for sch, tbl in merged if tbl == name}
        if len(schemas) > 1:
            raise SqlGuardError(
                f"ambiguous unqualified table {name}: multiple schema policies {sorted(schemas)}"
            )

    needed = []
    for key, frag in merged.items():
        sch, tbl = key
        if any(
            u_tbl == tbl and (u_sch == sch if u_sch else True)
            for u_sch, u_tbl in used_tables
        ):
            needed.append(frag)

    if not needed:
        return sql

    if isinstance(tree, exp.Select):
        for frag in needed:
            try:
                tree = tree.where(frag, copy=False)
            except Exception:
                tree = tree.where(sqlglot.condition(frag), copy=False)
        return tree.sql(dialect=read)

    raise SqlGuardError("cannot safely apply rls to this SQL")


def format_rls_prompt(preds: list[RlsPredicate]) -> str:
    if not preds:
        return ""
    lines = [
        f"- {p.schema_name}.{p.table_name}.{p.column_name} {p.op} {list(p.values)}"
        for p in preds
    ]
    return "行级权限（必须遵守，即使未写出也会被系统强制注入）:\n" + "\n".join(lines)
