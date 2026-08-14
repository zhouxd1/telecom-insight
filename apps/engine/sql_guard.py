import re
import sqlglot
from sqlglot import exp


class SqlGuardError(ValueError):
    pass


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|MERGE|REPLACE|ATTACH|COPY)\b",
    re.I,
)

# protocol_family / aliases → sqlglot read dialect
_SQLGLOT_DIALECT: dict[str, str] = {
    "postgres": "postgres",
    "mysql": "mysql",
    "mssql": "tsql",
    "tsql": "tsql",
    "hive": "hive",
    "dm": "postgres",
    "sqlite": "sqlite",
}


def resolve_sqlglot_dialect(dialect: str) -> str:
    """Map protocol family or dialect alias to a sqlglot read dialect."""
    key = (dialect or "postgres").lower()
    return _SQLGLOT_DIALECT.get(key, "postgres")


def _base_table_name(name: str) -> str:
    return name.split(".")[-1].strip('"').lower()


def guard_sql(
    sql: str,
    table_whitelist: set[str] | list[str],
    dialect: str = "postgres",
) -> str:
    raw = (sql or "").strip().rstrip(";")
    if not raw:
        raise SqlGuardError("empty sql")
    if ";" in raw:
        raise SqlGuardError("multiple statements are not allowed")
    if _FORBIDDEN.search(raw):
        raise SqlGuardError("only SELECT statements are allowed")

    read_dialect = resolve_sqlglot_dialect(dialect)
    try:
        trees = sqlglot.parse(raw, read=read_dialect)
    except Exception as e:
        raise SqlGuardError(f"sql parse failed: {e}") from e
    if len(trees) != 1 or trees[0] is None:
        raise SqlGuardError("exactly one statement required")
    tree = trees[0]
    if not isinstance(tree, exp.Select):
        if not any(isinstance(tree, t) for t in (exp.Select, exp.Union)):
            raise SqlGuardError("only SELECT is allowed")

    allowed = {t.lower() for t in table_whitelist}
    used = set()
    for t in tree.find_all(exp.Table):
        used.add(_base_table_name(t.name))
    # Empty whitelist: allow statements with no tables (e.g. SELECT 1)
    unknown = used - allowed
    if unknown:
        raise SqlGuardError(f"tables not in domain whitelist: {sorted(unknown)}")
    return raw
