"""Load workspace-member RLS predicates for ask paths."""

from __future__ import annotations

from sqlmodel import Session, select

from apps.api.models_db import TiOrg, TiRlsPolicy, TiUser, TiWorkspace, TiWorkspaceMember
from apps.engine.rls import RlsPredicate


def load_rls_predicates(
    session: Session,
    user: TiUser,
    workspace: TiWorkspace,
    member: TiWorkspaceMember | None,
) -> list[RlsPredicate]:
    org = session.get(TiOrg, user.org_id)
    if org and user.org_role == "org_admin" and org.rls_admin_bypass:
        return []
    if member is None:
        return []
    rows = session.exec(
        select(TiRlsPolicy).where(TiRlsPolicy.member_id == member.id)
    ).all()
    return [
        RlsPredicate(
            r.schema_name,
            r.table_name,
            r.column_name,
            r.op,
            list(r.values or []),
        )
        for r in rows
    ]


def get_workspace_member(
    session: Session, workspace_id: int, user_id: int
) -> TiWorkspaceMember | None:
    return session.exec(
        select(TiWorkspaceMember).where(
            TiWorkspaceMember.workspace_id == workspace_id,
            TiWorkspaceMember.user_id == user_id,
        )
    ).first()
