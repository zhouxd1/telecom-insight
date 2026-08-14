from dataclasses import dataclass

ALL_DOMAINS = ("biz", "network", "cs")


@dataclass
class EffectiveAccess:
    role: str
    domains: list[str]
    can_ask: bool
    can_manage_users: bool
    can_manage_workspace: bool


def resolve_access(
    *,
    org_role: str,
    member_role: str | None,
    member_domains: list[str] | None,
    is_org_admin: bool,
) -> EffectiveAccess:
    if is_org_admin or org_role == "org_admin":
        return EffectiveAccess("org_admin", list(ALL_DOMAINS), True, True, True)
    role = member_role or org_role
    domains = list(member_domains or [])
    return EffectiveAccess(
        role=role,
        domains=domains,
        can_ask=role in ("org_admin", "analyst"),
        can_manage_users=False,
        can_manage_workspace=False,
    )
