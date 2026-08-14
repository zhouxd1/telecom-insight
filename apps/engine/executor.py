from typing import Any
from sqlalchemy import text
from sqlalchemy.engine import Engine


def execute_select(
    engine: Engine,
    sql: str,
    *,
    max_rows: int = 200,
    timeout_seconds: int = 15,
) -> tuple[list[dict[str, Any]], bool]:
    with engine.connect() as conn:
        if conn.dialect.name == "postgresql":
            conn.execute(text(f"SET LOCAL statement_timeout = '{int(timeout_seconds * 1000)}'"))
        result = conn.execute(text(sql))
        keys = list(result.keys())
        raw = result.fetchmany(max_rows + 1)
    truncated = len(raw) > max_rows
    raw = raw[:max_rows]
    rows = [dict(zip(keys, row)) for row in raw]
    return rows, truncated
