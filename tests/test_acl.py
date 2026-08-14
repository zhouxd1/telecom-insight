from apps.api.acl import EffectiveAccess, resolve_access


def test_org_admin_gets_all_domains():
    access = resolve_access(
        org_role="org_admin",
        member_role=None,
        member_domains=None,
        is_org_admin=True,
    )
    assert access.role == "org_admin"
    assert set(access.domains) == {"biz", "network", "cs"}


def test_viewer_cannot_ask():
    access = resolve_access(
        org_role="viewer",
        member_role="viewer",
        member_domains=["biz"],
        is_org_admin=False,
    )
    assert access.can_ask is False
    assert access.can_manage_users is False
