"""Member RLS policy CRUD, org bypass settings, and domain column catalog."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from apps.api.db import get_session
from apps.api.deps import get_current_user, require_org_admin
from apps.api.models_db import TiOrg, TiRlsPolicy, TiUser, TiWorkspace, TiWorkspaceMember
from apps.api.rls_columns import is_allowed_column, list_rls_columns
from apps.api.schemas import (
    RlsPolicyCreate,
    RlsPolicyOut,
    RlsPolicyUpdate,
    RlsSettingsOut,
    RlsSettingsUpdate,
)

router = APIRouter(tags=["rls"])

_ALLOWED_OPS = frozenset({"in", "eq"})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _policy_out(row: TiRlsPolicy) -> RlsPolicyOut:
    return RlsPolicyOut(
        id=row.id,  # type: ignore[arg-type]
        workspace_id=row.workspace_id,
        member_id=row.member_id,
        domain=row.domain,
        schema_name=row.schema_name,
        table_name=row.table_name,
        column_name=row.column_name,
        op=row.op,
        values=[str(v) for v in (row.values or [])],
    )


def _get_org_workspace(session: Session, workspace_id: int, org_id: int) -> TiWorkspace:
    workspace = session.get(TiWorkspace, workspace_id)
    if workspace is None or workspace.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        )
    return workspace


def _get_workspace_member(
    session: Session, workspace_id: int, member_id: int
) -> TiWorkspaceMember:
    member = session.get(TiWorkspaceMember, member_id)
    if member is None or member.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    return member


def _validate_op_values(op: str, values: list[str]) -> None:
    if op not in _ALLOWED_OPS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid op",
        )
    if not values:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="values must be non-empty",
        )
    if op == "eq" and len(values) != 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="eq requires exactly one value",
        )


def _validate_create(body: RlsPolicyCreate) -> None:
    _validate_op_values(body.op, body.values)
    if not is_allowed_column(
        body.domain, body.schema_name, body.table_name, body.column_name
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="column not allowed for domain",
        )


@router.get(
    "/workspaces/{workspace_id}/members/{member_id}/rls",
    response_model=list[RlsPolicyOut],
)
def list_member_rls(
    workspace_id: int,
    member_id: int,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    _get_workspace_member(session, workspace_id, member_id)
    rows = session.exec(
        select(TiRlsPolicy)
        .where(
            TiRlsPolicy.workspace_id == workspace_id,
            TiRlsPolicy.member_id == member_id,
        )
        .order_by(TiRlsPolicy.id)
    ).all()
    return [_policy_out(r) for r in rows]


@router.post(
    "/workspaces/{workspace_id}/members/{member_id}/rls",
    response_model=RlsPolicyOut,
)
def create_member_rls(
    workspace_id: int,
    member_id: int,
    body: RlsPolicyCreate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    _get_workspace_member(session, workspace_id, member_id)
    _validate_create(body)
    row = TiRlsPolicy(
        workspace_id=workspace_id,
        member_id=member_id,
        domain=body.domain,
        schema_name=body.schema_name,
        table_name=body.table_name,
        column_name=body.column_name,
        op=body.op,
        values=list(body.values),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _policy_out(row)


@router.put("/workspaces/{workspace_id}/rls/{policy_id}", response_model=RlsPolicyOut)
def update_rls_policy(
    workspace_id: int,
    policy_id: int,
    body: RlsPolicyUpdate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    row = session.get(TiRlsPolicy, policy_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="policy not found",
        )
    data = body.model_dump(exclude_unset=True)
    op = data.get("op", row.op)
    values = data.get("values", list(row.values or []))
    values = [str(v) for v in values]
    _validate_op_values(op, values)
    row.op = op
    row.values = values
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return _policy_out(row)


@router.delete("/workspaces/{workspace_id}/rls/{policy_id}")
def delete_rls_policy(
    workspace_id: int,
    policy_id: int,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    row = session.get(TiRlsPolicy, policy_id)
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="policy not found",
        )
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.get("/orgs/me/rls-settings", response_model=RlsSettingsOut)
def get_rls_settings(
    user: TiUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    org = session.get(TiOrg, user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="org not found",
        )
    return RlsSettingsOut(rls_admin_bypass=bool(org.rls_admin_bypass))


@router.patch("/orgs/me/rls-settings", response_model=RlsSettingsOut)
def patch_rls_settings(
    body: RlsSettingsUpdate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    org = session.get(TiOrg, user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="org not found",
        )
    org.rls_admin_bypass = body.rls_admin_bypass
    session.add(org)
    session.commit()
    session.refresh(org)
    return RlsSettingsOut(rls_admin_bypass=bool(org.rls_admin_bypass))


@router.get("/domains/{domain_id}/rls-columns")
def get_rls_columns(
    domain_id: str,
    _user: TiUser = Depends(get_current_user),
):
    return list_rls_columns(domain_id)
