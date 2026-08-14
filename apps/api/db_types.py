"""P0/P1 database type catalog and SQLAlchemy URL builders."""

from __future__ import annotations

from urllib.parse import quote_plus

PROTOCOL_FAMILY: dict[str, str] = {
    "postgres": "postgres",
    "mysql": "mysql",
    "sqlserver": "mssql",
    "hive": "hive",
    "opengauss": "postgres",
    "gaussdb": "postgres",
    "oceanbase_mysql": "mysql",
    "tidb": "mysql",
    "kingbase": "postgres",
    "dameng": "dm",
}

P1_TYPES: frozenset[str] = frozenset({"gbase", "shentong", "polardb", "tdsql"})

_FAMILY_SCHEMES: dict[str, str] = {
    "postgres": "postgresql+psycopg",
    "mysql": "mysql+pymysql",
    "mssql": "mssql+pyodbc",
    "hive": "hive",
    "dm": "dm+dmPython",
}

_DEFAULT_MSSQL_DRIVER = "ODBC Driver 18 for SQL Server"


def is_p0(db_type: str) -> bool:
    return db_type in PROTOCOL_FAMILY


def is_p1(db_type: str) -> bool:
    return db_type in P1_TYPES


def build_sqlalchemy_url(
    db_type: str,
    host: str,
    port: int | None,
    database: str,
    username: str,
    password: str,
    extra: dict | None = None,
) -> str:
    """Build a SQLAlchemy URL for a P0 db_type."""
    family = PROTOCOL_FAMILY.get(db_type)
    if family is None:
        raise ValueError(f"unsupported db_type for URL build: {db_type}")

    scheme = _FAMILY_SCHEMES[family]
    user = quote_plus(username or "")
    pwd = quote_plus(password or "")
    auth = f"{user}:{pwd}@" if (username or password) else ""
    host_part = host or "localhost"
    port_part = f":{port}" if port is not None else ""
    db_part = quote_plus(database or "", safe="")

    base = f"{scheme}://{auth}{host_part}{port_part}/{db_part}"

    if family == "mssql":
        extra = extra or {}
        driver = extra.get("Driver") or extra.get("driver") or _DEFAULT_MSSQL_DRIVER
        query_parts = [f"Driver={quote_plus(driver)}"]
        for key, value in extra.items():
            if key in {"Driver", "driver"}:
                continue
            query_parts.append(f"{quote_plus(str(key))}={quote_plus(str(value))}")
        return f"{base}?{'&'.join(query_parts)}"

    if extra:
        query_parts = [
            f"{quote_plus(str(k))}={quote_plus(str(v))}" for k, v in extra.items()
        ]
        if query_parts:
            return f"{base}?{'&'.join(query_parts)}"

    return base
