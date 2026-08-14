from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from apps.api.acl import ALL_DOMAINS
from apps.api.db import get_session
from apps.api.deps import get_current_user, require_org_admin
from apps.api.models_db import TiUser, TiWorkspace, TiWorkspaceMember
from apps.api.schemas import (
    MemberCreate,
    MemberOut,
    MemberUpdate,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


def _member_out(row: TiWorkspaceMember) -> MemberOut:
    return MemberOut(
        id=row.id,  # type: ignore[arg-type]
        workspace_id=row.workspace_id,
        user_id=row.user_id,
        role=row.role,
        domains=list(row.domains or []),
    )


def _get_org_workspace(session: Session, workspace_id: int, org_id: int) -> TiWorkspace:
    workspace = session.get(TiWorkspace, workspace_id)
    if workspace is None or workspace.org_id != org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        )
    return workspace


@router.get("", response_model=list[WorkspaceOut])
def list_workspaces(
    user: TiUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    if user.org_role == "org_admin":
        rows = session.exec(
            select(TiWorkspace)
            .where(TiWorkspace.org_id == user.org_id)
            .order_by(TiWorkspace.id)
        ).all()
        return rows

    rows = session.exec(
        select(TiWorkspace)
        .join(TiWorkspaceMember, TiWorkspaceMember.workspace_id == TiWorkspace.id)
        .where(TiWorkspaceMember.user_id == user.id)
        .order_by(TiWorkspace.id)
    ).all()
    return rows


@router.post("", response_model=WorkspaceOut)
def create_workspace(
    body: WorkspaceCreate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    workspace = TiWorkspace(
        org_id=user.org_id,
        name=body.name,
        status="active",
    )
    session.add(workspace)
    session.flush()
    session.add(
        TiWorkspaceMember(
            workspace_id=workspace.id,  # type: ignore[arg-type]
            user_id=user.id,  # type: ignore[arg-type]
            role="org_admin",
            domains=list(ALL_DOMAINS),
        )
    )
    session.commit()
    session.refresh(workspace)
    return workspace


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
def update_workspace(
    workspace_id: int,
    body: WorkspaceUpdate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    workspace = _get_org_workspace(session, workspace_id, user.org_id)
    data = body.model_dump(exclude_unset=True)
    if "status" in data and data["status"] not in (None, "active", "archived"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid status",
        )
    for key, value in data.items():
        setattr(workspace, key, value)
    session.add(workspace)
    session.commit()
    session.refresh(workspace)
    return workspace


@router.get("/{workspace_id}/members", response_model=list[MemberOut])
def list_members(
    workspace_id: int,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    rows = session.exec(
        select(TiWorkspaceMember)
        .where(TiWorkspaceMember.workspace_id == workspace_id)
        .order_by(TiWorkspaceMember.id)
    ).all()
    return [_member_out(r) for r in rows]


@router.post("/{workspace_id}/members", response_model=MemberOut)
def add_member(
    workspace_id: int,
    body: MemberCreate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    target = session.get(TiUser, body.user_id)
    if target is None or target.org_id != user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    existing = session.exec(
        select(TiWorkspaceMember).where(
            TiWorkspaceMember.workspace_id == workspace_id,
            TiWorkspaceMember.user_id == body.user_id,
        )
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="member already exists",
        )
    row = TiWorkspaceMember(
        workspace_id=workspace_id,
        user_id=body.user_id,
        role=body.role,
        domains=list(body.domains),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _member_out(row)


@router.patch("/{workspace_id}/members/{user_id}", response_model=MemberOut)
def update_member(
    workspace_id: int,
    user_id: int,
    body: MemberUpdate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    row = session.exec(
        select(TiWorkspaceMember).where(
            TiWorkspaceMember.workspace_id == workspace_id,
            TiWorkspaceMember.user_id == user_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(row, key, value)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _member_out(row)


@router.delete("/{workspace_id}/members/{user_id}")
def delete_member(
    workspace_id: int,
    user_id: int,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    _get_org_workspace(session, workspace_id, user.org_id)
    row = session.exec(
        select(TiWorkspaceMember).where(
            TiWorkspaceMember.workspace_id == workspace_id,
            TiWorkspaceMember.user_id == user_id,
        )
    ).first()
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="member not found",
        )
    session.delete(row)
    session.commit()
    return {"ok": True}
