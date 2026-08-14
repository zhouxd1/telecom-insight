from sqlmodel import Session, SQLModel, create_engine, select

from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.models_db import TiOrg, TiUser, TiWorkspace, TiWorkspaceMember, TiDatasource


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
        mem = s.exec(select(TiWorkspaceMember)).first()
        assert mem is not None and "biz" in (mem.domains or [])
        ds = s.exec(select(TiDatasource).where(TiDatasource.is_default == True)).first()  # noqa: E712
        assert ds is not None and ds.workspace_id == ws.id
