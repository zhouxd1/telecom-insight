from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_COLUMNS = [
    ("cat_table", "table_kind", "VARCHAR DEFAULT 'table'"),
    ("cat_table", "table_comment", "VARCHAR DEFAULT ''"),
    ("cat_column", "ordinal_position", "INTEGER DEFAULT 0"),
    ("cat_column", "column_default", "VARCHAR DEFAULT ''"),
    ("cat_column", "is_primary_key", "BOOLEAN DEFAULT 0"),
    ("cat_column", "column_comment", "VARCHAR DEFAULT ''"),
]


def ensure_catalog_columns(engine: Engine) -> None:
    inspector = inspect(engine)
    names = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table, column, col_type in _COLUMNS:
            if table not in names:
                continue
            existing = {c["name"] for c in inspect(engine).get_columns(table)}
            if column in existing:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
