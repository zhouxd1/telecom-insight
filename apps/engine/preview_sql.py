from apps.engine.ident import quote_ident
from apps.engine.sql_guard import SqlGuardError


def build_preview_sql(
    schema_name: str,
    table_name: str,
    columns: list[str],
    *,
    dialect: str = "postgres",
    limit: int = 50,
) -> str:
    if not columns:
        raise SqlGuardError("preview requires columns")
    if limit < 1 or limit > 200:
        raise SqlGuardError("limit must be 1..200")
    cols = ", ".join(quote_ident(c, dialect) for c in columns)
    table = quote_ident(table_name, dialect)
    schema_key = (schema_name or "").lower()
    if schema_key in {"", "main", "public"} and dialect.lower() in {"sqlite", "sqlite3"}:
        from_ = table
    elif schema_key in {"", "main"}:
        from_ = table
    else:
        from_ = f"{quote_ident(schema_name, dialect)}.{table}"
    return f"SELECT {cols} FROM {from_} LIMIT {int(limit) + 1}"
