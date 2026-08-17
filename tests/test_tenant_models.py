from passlib.context import CryptContext
from sqlmodel import Session, SQLModel, create_engine, select, func

from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.models_db import (
    TiOrg,
    TiOrgBranding,
    TiUser,
    TiWorkspace,
    TiWorkspaceMember,
    TiDatasource,
    TiTerm,
    TiRlsPolicy,
)


def test_seed_creates_org_workspace_demo_and_default_ds(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")
    with Session(engine) as s:
        assert s.exec(select(TiOrg)).first() is not None
        ws = s.exec(select(TiWorkspace)).first()
        assert ws is not None
        user = s.exec(select(TiUser).where(TiUser.username == "demo")).first()
        assert user is not None and user.org_role == "org_admin"
        assert user.password_hash != "demo123"
        assert CryptContext(schemes=["bcrypt"]).verify("demo123", user.password_hash)
        mem = s.exec(select(TiWorkspaceMember)).first()
        assert mem is not None and set(mem.domains or []) == {"biz", "network", "cs"}
        ds = s.exec(select(TiDatasource).where(TiDatasource.is_default == True)).first()  # noqa: E712
        assert ds is not None and ds.workspace_id == ws.id
        assert ds.password_enc == ""
        org = s.exec(select(TiOrg)).first()
        branding = s.get(TiOrgBranding, org.id)
        assert branding is not None
        assert branding.product_name == "元景.智数"
        assert branding.tagline == "运营商智能问数"
        assert branding.preset_id == "default"
        assert branding.color_mode == "light"
        assert org.rls_admin_bypass is True
        analyst = s.exec(select(TiUser).where(TiUser.username == "analyst1")).first()
        assert analyst is not None and analyst.org_role == "analyst"
        assert CryptContext(schemes=["bcrypt"]).verify("analyst123", analyst.password_hash)
        analyst_mem = s.exec(
            select(TiWorkspaceMember).where(TiWorkspaceMember.user_id == analyst.id)
        ).first()
        assert analyst_mem is not None and set(analyst_mem.domains or []) == {"biz", "network", "cs"}
        policy = s.exec(
            select(TiRlsPolicy).where(TiRlsPolicy.member_id == analyst_mem.id)
        ).first()
        assert policy is not None
        assert policy.table_name == "sub_month" and policy.column_name == "region"
        assert policy.op == "in" and policy.values == ["华东"]


def test_seed_tenant_bootstrap_is_idempotent_and_backfills_workspace_id():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url="sqlite://")

    with Session(engine) as s:
        default_ws = s.exec(select(TiWorkspace).where(TiWorkspace.name == "默认")).one()
        s.add(TiTerm(domain="biz", term="legacy", standard="遗留术语", workspace_id=None))
        branding = s.exec(select(TiOrgBranding)).one()
        branding.product_name = "自定义产品"
        branding.tagline = "自定义副标题"
        branding.preset_id = "ocean"
        branding.color_mode = "dark"
        s.add(branding)
        s.commit()

    seed_tenant_bootstrap(engine, default_database_url="sqlite://")

    with Session(engine) as s:
        assert s.exec(select(func.count()).select_from(TiOrg)).one() == 1
        assert s.exec(select(func.count()).select_from(TiUser)).one() == 2
        assert s.exec(select(func.count()).select_from(TiWorkspaceMember)).one() == 2
        assert s.exec(select(func.count()).select_from(TiDatasource)).one() == 1
        assert s.exec(select(func.count()).select_from(TiOrgBranding)).one() == 1
        assert s.exec(select(func.count()).select_from(TiRlsPolicy)).one() == 1

        default_ws = s.exec(select(TiWorkspace).where(TiWorkspace.name == "默认")).one()
        term = s.exec(select(TiTerm).where(TiTerm.term == "legacy")).one()
        assert term.workspace_id == default_ws.id

        branding = s.exec(select(TiOrgBranding)).one()
        assert branding.product_name == "自定义产品"
        assert branding.tagline == "自定义副标题"
        assert branding.preset_id == "ocean"
        assert branding.color_mode == "dark"
