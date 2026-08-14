from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from sqlmodel import Session, select

from apps.api.acl import ALL_DOMAINS
from apps.api.auth import create_access_token
from apps.api.db import get_session
from apps.api.deps import get_current_user
from apps.api.models_db import TiOrg, TiUser, TiWorkspace, TiWorkspaceMember
from apps.api.schemas import LoginRequest, MeResponse, TokenResponse, WorkspaceSummary

router = APIRouter(tags=["auth"])

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@router.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest, session: Session = Depends(get_session)):
    user = session.exec(select(TiUser).where(TiUser.username == body.username)).first()
    if (
        user is None
        or not user.enabled
        or not _pwd_context.verify(body.password, user.password_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )
    return TokenResponse(
        access_token=create_access_token(str(user.id), org_id=user.org_id)
    )


@router.get("/auth/me", response_model=MeResponse)
def me(
    user: TiUser = Depends(get_current_user),
    session: Session = Depends(get_session),
):
    org = session.get(TiOrg, user.org_id)
    if org is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="org not found",
        )

    workspaces: list[WorkspaceSummary] = []
    if user.org_role == "org_admin":
        rows = session.exec(
            select(TiWorkspace).where(TiWorkspace.org_id == user.org_id)
        ).all()
        for ws in rows:
            workspaces.append(
                WorkspaceSummary(
                    id=ws.id,  # type: ignore[arg-type]
                    name=ws.name,
                    role="org_admin",
                    domains=list(ALL_DOMAINS),
                )
            )
    else:
        memberships = session.exec(
            select(TiWorkspaceMember, TiWorkspace)
            .join(TiWorkspace, TiWorkspace.id == TiWorkspaceMember.workspace_id)
            .where(TiWorkspaceMember.user_id == user.id)
        ).all()
        for member, ws in memberships:
            workspaces.append(
                WorkspaceSummary(
                    id=ws.id,  # type: ignore[arg-type]
                    name=ws.name,
                    role=member.role,
                    domains=list(member.domains or []),
                )
            )

    return MeResponse(
        id=user.id,  # type: ignore[arg-type]
        username=user.username,
        display_name=user.display_name,
        org_id=user.org_id,
        org_name=org.name,
        org_role=user.org_role,
        workspaces=workspaces,
    )
