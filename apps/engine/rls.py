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


def _pred_sql(p: RlsPredicate, *, qualifier: str | None = None) -> str:
    col = f"{qualifier}.{p.column_name}" if qualifier else p.column_name
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


def _frag_for_table(
    preds: list[RlsPredicate],
    schema: str,
    table: str,
    *,
    qualifier: str | None = None,
) -> str:
    by_col: dict[str, list[str]] = {}
    for p in preds:
        if p.schema_name.lower() == schema and p.table_name.lower() == table:
            by_col.setdefault(p.column_name.lower(), []).append(
                _pred_sql(p, qualifier=qualifier)
            )
    col_parts: list[str] = []
    for _col, frags in by_col.items():
        col_parts.append("(" + " OR ".join(frags) + ")" if len(frags) > 1 else frags[0])
    return " AND ".join(col_parts)


def merge_predicates(preds: list[RlsPredicate]) -> dict[tuple[str, str], str]:
    """Return map (schema, table) -> AND-combined WHERE fragment (no leading AND)."""
    keys = {(p.schema_name.lower(), p.table_name.lower()) for p in preds}
    return {key: _frag_for_table(preds, key[0], key[1]) for key in keys}


def _direct_outer_tables(select: exp.Select) -> list[exp.Table]:
    """FROM/JOIN tables of the outermost Select only (not nested subquery tables)."""
    out: list[exp.Table] = []
    from_ = select.args.get("from_")
    if from_ is not None and isinstance(from_.this, exp.Table):
        out.append(from_.this)
    for join in select.args.get("joins") or []:
        if isinstance(join.this, exp.Table):
            out.append(join.this)
    return out


def _table_qualifier(t: exp.Table) -> str:
    if t.alias:
        return t.alias
    if t.db:
        return f"{t.db}.{t.name}"
    return t.name


def _matches_policy_table(
    schema: str, table: str, policy_schema: str, policy_table: str
) -> bool:
    if table != policy_table:
        return False
    return schema == policy_schema if schema else True


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

    all_tables = list(tree.find_all(exp.Table))
    used_tables = [((t.db or "").lower(), t.name.lower()) for t in all_tables]

    # Unqualified FROM t: match by table_name alone; reject if multiple schemas collide.
    unqualified_names = {u_tbl for u_sch, u_tbl in used_tables if not u_sch}
    for name in unqualified_names:
        schemas = {sch for sch, tbl in merged if tbl == name}
        if len(schemas) > 1:
            raise SqlGuardError(
                f"ambiguous unqualified table {name}: multiple schema policies {sorted(schemas)}"
            )

    needed_keys = [
        key
        for key in merged
        if any(
            _matches_policy_table(u_sch, u_tbl, key[0], key[1])
            for u_sch, u_tbl in used_tables
        )
    ]
    if not needed_keys:
        return sql

    if not isinstance(tree, exp.Select):
        raise SqlGuardError("cannot safely apply rls to this SQL")

    outer_tables = _direct_outer_tables(tree)
    outer_by_policy: dict[tuple[str, str], list[exp.Table]] = {k: [] for k in needed_keys}
    for t in outer_tables:
        u_sch, u_tbl = (t.db or "").lower(), t.name.lower()
        for key in needed_keys:
            if _matches_policy_table(u_sch, u_tbl, key[0], key[1]):
                outer_by_policy[key].append(t)

    for key in needed_keys:
        matches = outer_by_policy[key]
        if len(matches) != 1:
            # Missing from outer FROM/JOIN, only nested, or ambiguous self-join.
            raise SqlGuardError("cannot safely apply rls to this SQL")

    # Qualify when multiple outer tables so JOIN predicates bind unambiguously.
    qualify = len(outer_tables) > 1
    for key in needed_keys:
        t = outer_by_policy[key][0]
        qualifier = _table_qualifier(t) if qualify else None
        frag = _frag_for_table(preds, key[0], key[1], qualifier=qualifier)
        if not frag:
            continue
        try:
            tree = tree.where(frag, copy=False)
        except Exception:
            tree = tree.where(sqlglot.condition(frag), copy=False)
    return tree.sql(dialect=read)


def format_rls_prompt(preds: list[RlsPredicate]) -> str:
    if not preds:
        return ""
    lines = [
        f"- {p.schema_name}.{p.table_name}.{p.column_name} {p.op} {list(p.values)}"
        for p in preds
    ]
    return "行级权限（必须遵守，即使未写出也会被系统强制注入）:\n" + "\n".join(lines)
