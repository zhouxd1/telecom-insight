"""Idempotent demo Catalog grants for biz demo tables (post-bootstrap)."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from apps.api import catalog_client
from apps.api.crypto import decrypt_secret
from apps.api.db_types import build_sqlalchemy_url, is_p0
from apps.api.models_db import TiDatasource, TiWorkspace

logger = logging.getLogger(__name__)

# Known core columns when introspect returns nothing (e.g. empty sqlite demo DS).
_DEMO_GRANT_TABLES: list[tuple[str, str, list[str]]] = [
    ("biz", "sub_month", ["month", "region", "sub_cnt", "arpu", "revenue"]),
    ("biz", "channel_day", ["day", "channel", "new_users"]),
]


def _password_plain(ds: TiDatasource) -> str:
    token = (ds.password_enc or "").strip()
    if not token:
        return ""
    try:
        return decrypt_secret(token)
    except Exception:  # noqa: BLE001
        return ""


def _sqlalchemy_url_for_ds(ds: TiDatasource) -> str | None:
    """Build SQLAlchemy URL the same way as the datasource schema proxy."""
    password = _password_plain(ds)
    if ds.db_type == "sqlite":
        database = ds.database or ":memory:"
        if database in {":memory:", ""}:
            return "sqlite://"
        return f"sqlite:///{database}"
    if not is_p0(ds.db_type):
        return None
    try:
        return build_sqlalchemy_url(
            db_type=ds.db_type,
            host=ds.host or "",
            port=ds.port,
            database=ds.database or "",
            username=ds.username or "",
            password=password,
            extra=ds.extra_json,
        )
    except ValueError:
        return None


def _pick_columns(
    snapshot_tables: list[dict[str, Any]],
    schema_name: str,
    table_name: str,
    fallback: list[str],
) -> tuple[str, list[str]]:
    """Prefer exact schema.table match; else any schema with that table name."""
    for row in snapshot_tables:
        if row.get("table_name") == table_name and row.get("schema_name") == schema_name:
            cols = [c["name"] for c in (row.get("columns") or []) if c.get("name")]
            if cols:
                return schema_name, cols
    for row in snapshot_tables:
        if row.get("table_name") == table_name:
            cols = [c["name"] for c in (row.get("columns") or []) if c.get("name")]
            if cols:
                return str(row.get("schema_name") or schema_name), cols
    return schema_name, list(fallback)


def _default_workspace_datasource(
    session: Session,
) -> tuple[TiWorkspace, TiDatasource] | None:
    workspace = session.exec(
        select(TiWorkspace).where(TiWorkspace.name == "默认")
    ).first()
    if workspace is None:
        workspace = session.exec(select(TiWorkspace)).first()
    if workspace is None or workspace.id is None:
        return None

    ds = session.exec(
        select(TiDatasource).where(
            TiDatasource.workspace_id == workspace.id,
            TiDatasource.is_default.is_(True),  # type: ignore[arg-type]
        )
    ).first()
    if ds is None:
        ds = session.exec(
            select(TiDatasource).where(TiDatasource.workspace_id == workspace.id)
        ).first()
    if ds is None or ds.id is None:
        return None
    return workspace, ds


def seed_demo_catalog_grants(engine: Engine) -> None:
    """Introspect default DS and PUT grants for biz demo tables; skip if catalog down."""
    with Session(engine) as session:
        pair = _default_workspace_datasource(session)
        if pair is None:
            logger.info("skip demo catalog grants: no default workspace datasource")
            return
        workspace, ds = pair
        workspace_id = workspace.id
        datasource_id = ds.id
        assert workspace_id is not None and datasource_id is not None
        sqlalchemy_url = _sqlalchemy_url_for_ds(ds)
        db_type = ds.db_type

    if not sqlalchemy_url:
        logger.info("skip demo catalog grants: cannot build sqlalchemy URL for default DS")
        return

    try:
        catalog_client.introspect(
            workspace_id=workspace_id,
            datasource_id=datasource_id,
            db_type=db_type,
            sqlalchemy_url=sqlalchemy_url,
        )
        schema = catalog_client.get_schema(
            workspace_id=workspace_id,
            datasource_id=datasource_id,
        )
        snapshot_tables = list(schema.get("tables") or [])
        grant_tables: list[dict[str, Any]] = []
        for schema_name, table_name, fallback_cols in _DEMO_GRANT_TABLES:
            sn, cols = _pick_columns(
                snapshot_tables, schema_name, table_name, fallback_cols
            )
            grant_tables.append(
                {
                    "schema_name": sn,
                    "table_name": table_name,
                    "columns": cols,
                }
            )
        catalog_client.put_grants(
            workspace_id=workspace_id,
            datasource_id=datasource_id,
            tables=grant_tables,
        )
        logger.info(
            "seeded demo catalog grants for workspace=%s datasource=%s tables=%s",
            workspace_id,
            datasource_id,
            [t["table_name"] for t in grant_tables],
        )
    except Exception as exc:  # noqa: BLE001 — never block API startup
        logger.warning("skip demo catalog grants (catalog unreachable or error): %s", exc)
