"""Admin datasource CRUD, test, default, introspect."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlmodel import Session, select

from apps.api import catalog_client
from apps.api.acl import EffectiveAccess
from apps.api.crypto import decrypt_secret, encrypt_secret
from apps.api.db import get_session
from apps.api.db_types import build_sqlalchemy_url, is_p0, is_p1
from apps.api.deps import dialect_for_datasource, get_current_user, require_workspace
from apps.api.models_db import TiDatasource, TiUser, TiWorkspace
from apps.api.rls_load import get_workspace_member, load_rls_predicates
from apps.api.schemas import (
    DatasourceCreate,
    DatasourceGrantsPut,
    DatasourceOut,
    DatasourceTestResult,
    DatasourceUpdate,
)
from apps.engine import connectors
from apps.engine.connectors import build_engine_from_datasource
from apps.engine.executor import execute_select
from apps.engine.preview_sql import build_preview_sql
from apps.engine.rls import apply_rls
from apps.engine.sql_guard import SqlGuardError, guard_sql

router = APIRouter(prefix="/admin/datasources", tags=["datasources"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_out(row: TiDatasource) -> DatasourceOut:
    return DatasourceOut(
        id=row.id,  # type: ignore[arg-type]
        workspace_id=row.workspace_id,
        name=row.name,
        db_type=row.db_type,
        host=row.host,
        port=row.port,
        database=row.database,
        username=row.username,
        extra_json=row.extra_json,
        is_default=row.is_default,
        last_ok_at=row.last_ok_at,
        last_error=row.last_error,
    )


def _get_workspace_ds(
    session: Session, ds_id: int, workspace: TiWorkspace
) -> TiDatasource:
    row = session.get(TiDatasource, ds_id)
    if not row or row.workspace_id != workspace.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="datasource not found"
        )
    return row


def _unset_other_defaults(
    session: Session, workspace_id: int, keep_id: int | None = None
) -> None:
    rows = session.exec(
        select(TiDatasource).where(TiDatasource.workspace_id == workspace_id)
    ).all()
    for row in rows:
        if keep_id is not None and row.id == keep_id:
            continue
        if row.is_default:
            row.is_default = False
            session.add(row)


def _reject_p1_default(db_type: str) -> None:
    if is_p1(db_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="P1 db_type cannot be set as default",
        )


def _require_ds_manage(access: EffectiveAccess) -> None:
    if not (access.role == "org_admin" or access.can_manage_workspace):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="org_admin required to manage datasources",
        )


def _validate_db_type(db_type: str) -> None:
    if not (is_p0(db_type) or is_p1(db_type) or db_type == "sqlite"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported db_type: {db_type}",
        )


def _password_plain(ds: TiDatasource) -> str:
    token = (ds.password_enc or "").strip()
    if not token:
        return ""
    try:
        return decrypt_secret(token)
    except Exception:
        return ""


def _sqlalchemy_url_for_ds(ds: TiDatasource) -> str:
    """Build a short-lived SQLAlchemy URL for Catalog introspect (never log)."""
    password = _password_plain(ds)
    if ds.db_type == "sqlite":
        database = ds.database or ":memory:"
        if database in {":memory:", ""}:
            return "sqlite://"
        return f"sqlite:///{database}"
    if not is_p0(ds.db_type):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported db_type for introspect: {ds.db_type}",
        )
    return build_sqlalchemy_url(
        db_type=ds.db_type,
        host=ds.host or "",
        port=ds.port,
        database=ds.database or "",
        username=ds.username or "",
        password=password,
        extra=ds.extra_json,
    )


@router.get("", response_model=list[DatasourceOut])
def list_datasources(
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    rows = session.exec(
        select(TiDatasource)
        .where(TiDatasource.workspace_id == workspace.id)
        .order_by(TiDatasource.id)
    ).all()
    return [_to_out(r) for r in rows]


@router.post("", response_model=DatasourceOut)
def create_datasource(
    body: DatasourceCreate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_ds_manage(access)
    _validate_db_type(body.db_type)
    if body.is_default:
        _reject_p1_default(body.db_type)
        _unset_other_defaults(session, workspace.id)  # type: ignore[arg-type]

    password_enc = ""
    if body.password:
        password_enc = encrypt_secret(body.password)

    row = TiDatasource(
        workspace_id=workspace.id,  # type: ignore[arg-type]
        name=body.name,
        db_type=body.db_type,
        host=body.host,
        port=body.port,
        database=body.database,
        username=body.username,
        password_enc=password_enc,
        extra_json=body.extra_json,
        is_default=body.is_default,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_out(row)


@router.get("/{ds_id}", response_model=DatasourceOut)
def get_datasource(
    ds_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    return _to_out(_get_workspace_ds(session, ds_id, workspace))


@router.patch("/{ds_id}", response_model=DatasourceOut)
def update_datasource(
    ds_id: int,
    body: DatasourceUpdate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_ds_manage(access)
    row = _get_workspace_ds(session, ds_id, workspace)
    data = body.model_dump(exclude_unset=True)
    password = data.pop("password", None)

    if "db_type" in data:
        _validate_db_type(data["db_type"])

    next_db_type = data.get("db_type", row.db_type)
    next_is_default = data["is_default"] if "is_default" in data else row.is_default
    if next_is_default:
        _reject_p1_default(next_db_type)
    if data.get("is_default") is True:
        _unset_other_defaults(session, workspace.id, keep_id=ds_id)  # type: ignore[arg-type]

    for key, value in data.items():
        setattr(row, key, value)

    if password is not None:
        row.password_enc = encrypt_secret(password) if password else ""

    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_out(row)


@router.delete("/{ds_id}")
def delete_datasource(
    ds_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_ds_manage(access)
    row = _get_workspace_ds(session, ds_id, workspace)
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.post("/{ds_id}/test", response_model=DatasourceTestResult)
def test_datasource(
    ds_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    row = _get_workspace_ds(session, ds_id, workspace)
    ok, error = connectors.test_connection(row)
    if ok:
        row.last_ok_at = _utcnow()
        row.last_error = None
    else:
        row.last_error = error
    session.add(row)
    session.commit()
    return DatasourceTestResult(ok=ok, error=error)


@router.post("/{ds_id}/default", response_model=DatasourceOut)
def set_default_datasource(
    ds_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_ds_manage(access)
    row = _get_workspace_ds(session, ds_id, workspace)
    _reject_p1_default(row.db_type)
    _unset_other_defaults(session, workspace.id, keep_id=ds_id)  # type: ignore[arg-type]
    row.is_default = True
    session.add(row)
    session.commit()
    session.refresh(row)
    return _to_out(row)


@router.post("/{ds_id}/introspect")
def introspect_datasource(
    ds_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_ds_manage(access)
    row = _get_workspace_ds(session, ds_id, workspace)
    sqlalchemy_url = _sqlalchemy_url_for_ds(row)
    # Never log sqlalchemy_url — it may embed the password.
    return catalog_client.introspect(
        workspace_id=workspace.id,  # type: ignore[arg-type]
        datasource_id=ds_id,
        db_type=row.db_type,
        sqlalchemy_url=sqlalchemy_url,
    )


@router.get("/{ds_id}/schema")
def get_datasource_schema(
    ds_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
) -> dict[str, Any]:
    workspace, _access = ws_access
    _get_workspace_ds(session, ds_id, workspace)
    return catalog_client.get_schema(
        workspace_id=workspace.id,  # type: ignore[arg-type]
        datasource_id=ds_id,
    )


@router.put("/{ds_id}/grants")
def put_datasource_grants(
    ds_id: int,
    body: DatasourceGrantsPut,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
) -> dict[str, Any]:
    workspace, access = ws_access
    _require_ds_manage(access)
    _get_workspace_ds(session, ds_id, workspace)
    tables = [t.model_dump() for t in body.tables]
    return catalog_client.put_grants(
        workspace_id=workspace.id,  # type: ignore[arg-type]
        datasource_id=ds_id,
        tables=tables,
    )


@router.get("/{ds_id}/preview")
def preview_datasource_table(
    ds_id: int,
    schema: str = Query(..., min_length=1),
    table: str = Query(..., min_length=1),
    limit: int = Query(50, ge=1, le=200),
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
    user: TiUser = Depends(get_current_user),
) -> dict[str, Any]:
    workspace, _access = ws_access
    row = _get_workspace_ds(session, ds_id, workspace)
    tree = catalog_client.get_schema(
        workspace_id=workspace.id,  # type: ignore[arg-type]
        datasource_id=ds_id,
    )
    match = next(
        (
            t
            for t in (tree.get("tables") or [])
            if t.get("schema_name") == schema and t.get("table_name") == table
        ),
        None,
    )
    if match is None:
        raise HTTPException(status_code=404, detail="table not in catalog snapshot")
    col_names = [c["name"] for c in (match.get("columns") or []) if c.get("name")]
    dialect = dialect_for_datasource(row)
    try:
        sql = build_preview_sql(
            schema, table, col_names, dialect=dialect, limit=limit
        )
        sql = guard_sql(sql, {table}, dialect=dialect)
        member = get_workspace_member(session, workspace.id, user.id)  # type: ignore[arg-type]
        preds = load_rls_predicates(session, user, workspace, member)
        if preds:
            sql = apply_rls(sql, preds, dialect=dialect)
            sql = guard_sql(sql, {table}, dialect=dialect)
        engine = build_engine_from_datasource(row)
        try:
            rows, truncated = execute_select(engine, sql, max_rows=limit)
        finally:
            engine.dispose()
    except SqlGuardError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="数据源连接失败，请检查数据源配置后重试。",
        )
    return {"columns": col_names, "rows": rows, "truncated": truncated}
