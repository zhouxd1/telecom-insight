import re

from apps.engine.sql_guard import SqlGuardError

_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def quote_ident(name: str, dialect: str = "postgres") -> str:
    if not name or not _IDENT.match(name):
        raise SqlGuardError(f"invalid identifier: {name!r}")
    family = (dialect or "postgres").lower()
    if family in {"mysql", "tidb", "oceanbase_mysql", "hive"}:
        return f"`{name}`"
    return f'"{name}"'
