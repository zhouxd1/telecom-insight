import re
import sqlglot
from sqlglot import exp


class SqlGuardError(ValueError):
    pass


_FORBIDDEN = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|MERGE|REPLACE|ATTACH|COPY)\b",
    re.I,
)


def _base_table_name(name: str) -> str:
    return name.split(".")[-1].strip('"').lower()


def guard_sql(sql: str, table_whitelist: set[str] | list[str]) -> str:
    raw = (sql or "").strip().rstrip(";")
    if not raw:
        raise SqlGuardError("empty sql")
    if ";" in raw:
        raise SqlGuardError("multiple statements are not allowed")
    if _FORBIDDEN.search(raw):
        raise SqlGuardError("only SELECT statements are allowed")

    try:
        trees = sqlglot.parse(raw, read="postgres")
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
    unknown = used - allowed
    if unknown:
        raise SqlGuardError(f"tables not in domain whitelist: {sorted(unknown)}")
    return raw
