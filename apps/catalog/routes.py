from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, delete
from sqlmodel import Session, select

from apps.catalog.db import get_session
from apps.catalog.models import (
    CatColumn,
    CatDatasourceRef,
    CatTable,
    CatWsColumnGrant,
    CatWsTableGrant,
)
from apps.engine.schema_introspect import introspect_tables

router = APIRouter()


class IntrospectBody(BaseModel):
    workspace_id: int
    datasource_id: int
    db_type: str
    sqlalchemy_url: str


class GrantTableBody(BaseModel):
    schema_name: str
    table_name: str
    columns: list[str] = Field(default_factory=list)


class PutGrantsBody(BaseModel):
    datasource_id: int
    tables: list[GrantTableBody] = Field(default_factory=list)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clear_snapshot(session: Session, datasource_id: int) -> None:
    tables = session.exec(
        select(CatTable).where(CatTable.datasource_id == datasource_id)
    ).all()
    table_ids = [t.id for t in tables if t.id is not None]
    if table_ids:
        session.execute(
            delete(CatColumn).where(CatColumn.table_id.in_(table_ids))
        )
    session.execute(
        delete(CatTable).where(CatTable.datasource_id == datasource_id)
    )


def _upsert_ref(
    session: Session,
    *,
    workspace_id: int,
    datasource_id: int,
    db_type: str,
) -> CatDatasourceRef:
    ref = session.exec(
        select(CatDatasourceRef).where(
            CatDatasourceRef.workspace_id == workspace_id,
            CatDatasourceRef.datasource_id == datasource_id,
        )
    ).first()
    if ref is None:
        ref = CatDatasourceRef(
            workspace_id=workspace_id,
            datasource_id=datasource_id,
            db_type=db_type,
        )
        session.add(ref)
    else:
        ref.db_type = db_type
    ref.last_introspected_at = _utcnow()
    # Fingerprint: type only (no password / URL).
    ref.fingerprint = f"{db_type}:{datasource_id}"
    session.add(ref)
    return ref


def _snapshot_counts(session: Session, datasource_id: int) -> dict[str, int]:
    tables = session.exec(
        select(CatTable).where(CatTable.datasource_id == datasource_id)
    ).all()
    col_count = 0
    for t in tables:
        col_count += len(
            session.exec(select(CatColumn).where(CatColumn.table_id == t.id)).all()
        )
    return {"tables": len(tables), "columns": col_count}


@router.post("/v1/introspect")
def post_introspect(
    body: IntrospectBody,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    try:
        src = create_engine(body.sqlalchemy_url)
    except Exception as exc:  # noqa: BLE001 — surface bad URL
        raise HTTPException(status_code=400, detail=f"invalid sqlalchemy_url: {exc}") from exc
    try:
        rows = introspect_tables(src, db_type=body.db_type)
    finally:
        src.dispose()

    _upsert_ref(
        session,
        workspace_id=body.workspace_id,
        datasource_id=body.datasource_id,
        db_type=body.db_type,
    )
    _clear_snapshot(session, body.datasource_id)

    now = _utcnow()
    for row in rows:
        table = CatTable(
            datasource_id=body.datasource_id,
            schema_name=row["schema_name"],
            table_name=row["table_name"],
            table_kind=str(row.get("table_kind") or "table"),
            table_comment=str(row.get("table_comment") or ""),
            refreshed_at=now,
        )
        session.add(table)
        session.flush()
        for col in row.get("columns") or []:
            session.add(
                CatColumn(
                    table_id=table.id,
                    column_name=col["name"],
                    data_type=str(col.get("data_type") or ""),
                    nullable=bool(col.get("nullable", True)),
                    ordinal_position=int(col.get("ordinal_position") or 0),
                    column_default=str(col.get("column_default") or ""),
                    is_primary_key=bool(col.get("is_primary_key", False)),
                    column_comment=str(col.get("column_comment") or ""),
                )
            )
    session.commit()
    return _snapshot_counts(session, body.datasource_id)


@router.get("/v1/workspaces/{workspace_id}/schema")
def get_schema(
    workspace_id: int,
    datasource_id: int = Query(...),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    tables = session.exec(
        select(CatTable).where(CatTable.datasource_id == datasource_id)
    ).all()
    table_grants = {
        (g.schema_name, g.table_name)
        for g in session.exec(
            select(CatWsTableGrant).where(
                CatWsTableGrant.workspace_id == workspace_id,
                CatWsTableGrant.datasource_id == datasource_id,
            )
        ).all()
    }
    col_grants = {
        (g.schema_name, g.table_name, g.column_name)
        for g in session.exec(
            select(CatWsColumnGrant).where(
                CatWsColumnGrant.workspace_id == workspace_id,
                CatWsColumnGrant.datasource_id == datasource_id,
            )
        ).all()
    }

    out: list[dict[str, Any]] = []
    for t in tables:
        cols = session.exec(
            select(CatColumn).where(CatColumn.table_id == t.id)
        ).all()
        key = (t.schema_name, t.table_name)
        out.append(
            {
                "schema_name": t.schema_name,
                "table_name": t.table_name,
                "table_kind": t.table_kind,
                "table_comment": t.table_comment,
                "granted": key in table_grants,
                "columns": [
                    {
                        "name": c.column_name,
                        "data_type": c.data_type,
                        "nullable": c.nullable,
                        "ordinal_position": c.ordinal_position,
                        "column_default": c.column_default,
                        "is_primary_key": c.is_primary_key,
                        "column_comment": c.column_comment,
                        "granted": (t.schema_name, t.table_name, c.column_name)
                        in col_grants,
                    }
                    for c in cols
                ],
            }
        )
    return {"datasource_id": datasource_id, "tables": out}


@router.put("/v1/workspaces/{workspace_id}/grants")
def put_grants(
    workspace_id: int,
    body: PutGrantsBody,
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    session.execute(
        delete(CatWsColumnGrant).where(
            CatWsColumnGrant.workspace_id == workspace_id,
            CatWsColumnGrant.datasource_id == body.datasource_id,
        )
    )
    session.execute(
        delete(CatWsTableGrant).where(
            CatWsTableGrant.workspace_id == workspace_id,
            CatWsTableGrant.datasource_id == body.datasource_id,
        )
    )
    col_count = 0
    for t in body.tables:
        session.add(
            CatWsTableGrant(
                workspace_id=workspace_id,
                datasource_id=body.datasource_id,
                schema_name=t.schema_name,
                table_name=t.table_name,
            )
        )
        for col in t.columns:
            col_count += 1
            session.add(
                CatWsColumnGrant(
                    workspace_id=workspace_id,
                    datasource_id=body.datasource_id,
                    schema_name=t.schema_name,
                    table_name=t.table_name,
                    column_name=col,
                )
            )
    session.commit()
    return {"tables": len(body.tables), "columns": col_count}


@router.get("/v1/workspaces/{workspace_id}/effective")
def get_effective(
    workspace_id: int,
    datasource_id: int = Query(...),
    session: Session = Depends(get_session),
) -> dict[str, Any]:
    table_grants = session.exec(
        select(CatWsTableGrant).where(
            CatWsTableGrant.workspace_id == workspace_id,
            CatWsTableGrant.datasource_id == datasource_id,
        )
    ).all()
    if not table_grants:
        return {"tables": [], "columns": {}, "empty": True}

    tables = sorted({g.table_name for g in table_grants})
    columns: dict[str, list[str]] = {name: [] for name in tables}
    for g in session.exec(
        select(CatWsColumnGrant).where(
            CatWsColumnGrant.workspace_id == workspace_id,
            CatWsColumnGrant.datasource_id == datasource_id,
        )
    ).all():
        columns.setdefault(g.table_name, []).append(g.column_name)
    for name in columns:
        columns[name] = sorted(set(columns[name]))
    return {"tables": tables, "columns": columns, "empty": False}
