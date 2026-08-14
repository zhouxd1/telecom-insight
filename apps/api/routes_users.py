from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from apps.api.auth import hash_password
from apps.api.db import get_session
from apps.api.deps import require_org_admin
from apps.api.models_db import TiUser
from apps.api.schemas import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/admin/users", tags=["users"])


def _user_out(user: TiUser) -> UserOut:
    return UserOut(
        id=user.id,  # type: ignore[arg-type]
        org_id=user.org_id,
        username=user.username,
        display_name=user.display_name,
        org_role=user.org_role,
        enabled=user.enabled,
    )


@router.get("", response_model=list[UserOut])
def list_users(
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(TiUser).where(TiUser.org_id == user.org_id).order_by(TiUser.id)
    ).all()
    return [_user_out(r) for r in rows]


@router.post("", response_model=UserOut)
def create_user(
    body: UserCreate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    existing = session.exec(
        select(TiUser).where(TiUser.username == body.username)
    ).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="username already exists",
        )
    if body.org_role not in ("org_admin", "analyst", "viewer"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid org_role",
        )
    row = TiUser(
        org_id=user.org_id,
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name or body.username,
        org_role=body.org_role,
        enabled=True,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _user_out(row)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    user: TiUser = Depends(require_org_admin),
    session: Session = Depends(get_session),
):
    row = session.get(TiUser, user_id)
    if row is None or row.org_id != user.org_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="user not found",
        )
    data = body.model_dump(exclude_unset=True)
    if "org_role" in data and data["org_role"] not in (
        "org_admin",
        "analyst",
        "viewer",
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="invalid org_role",
        )
    password = data.pop("password", None)
    for key, value in data.items():
        setattr(row, key, value)
    if password is not None:
        row.password_hash = hash_password(password)
    session.add(row)
    session.commit()
    session.refresh(row)
    return _user_out(row)
