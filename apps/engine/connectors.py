"""Datasource connection factory and smoke-test helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from apps.api.crypto import decrypt_secret
from apps.api.db_types import PROTOCOL_FAMILY, build_sqlalchemy_url, is_p0
from apps.api.models_db import TiDatasource


def _password_plain(ds: TiDatasource) -> str:
    token = (ds.password_enc or "").strip()
    if not token:
        return ""
    try:
        return decrypt_secret(token)
    except Exception:
        # Legacy / empty / non-encrypted placeholder
        return ""


def _connect_args(db_type: str) -> dict[str, Any]:
    """Short timeouts so test_connection fails fast on bad hosts."""
    family = PROTOCOL_FAMILY.get(db_type, db_type)
    if family == "postgres":
        return {"connect_timeout": 2}
    if family == "mysql":
        return {"connect_timeout": 2}
    if db_type == "sqlite":
        return {}
    return {}


def build_engine_from_datasource(ds: TiDatasource) -> Engine:
    """Create a SQLAlchemy Engine from a TiDatasource row."""
    db_type = ds.db_type
    password = _password_plain(ds)

    if db_type == "sqlite":
        database = ds.database or ":memory:"
        if database in {":memory:", ""}:
            url = "sqlite://"
        else:
            url = f"sqlite:///{database}"
        return create_engine(url)

    if not is_p0(db_type):
        raise ValueError(f"unsupported db_type: {db_type}")

    url = build_sqlalchemy_url(
        db_type=db_type,
        host=ds.host or "",
        port=ds.port,
        database=ds.database or "",
        username=ds.username or "",
        password=password,
        extra=ds.extra_json,
    )
    return create_engine(url, connect_args=_connect_args(db_type))


def test_connection(ds: TiDatasource) -> tuple[bool, str | None]:
    """Try connect + SELECT 1; return (ok, error_message)."""
    try:
        engine = build_engine_from_datasource(ds)
    except ImportError as e:
        return False, f"driver not installed: {e}"
    except Exception as e:
        return False, str(e)

    try:
        with engine.connect() as conn:
            family = PROTOCOL_FAMILY.get(ds.db_type, ds.db_type)
            if family == "mssql":
                conn.execute(text("SELECT 1"))
            else:
                conn.execute(text("SELECT 1"))
        return True, None
    except ImportError as e:
        return False, f"driver not installed: {e}"
    except Exception as e:
        return False, str(e)
    finally:
        engine.dispose()


def introspect_schema(ds: TiDatasource) -> list[str] | dict[str, Any]:
    """Optional schema probe stub — returns empty until wired."""
    _ = ds
    return []
