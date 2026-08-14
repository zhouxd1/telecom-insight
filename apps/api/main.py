from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlmodel import Session

from apps.api import deps
from apps.api.acl import EffectiveAccess
from apps.api.db import get_engine, get_session
from apps.api.deps import (
    dialect_for_datasource,
    get_current_user,
    require_workspace,
    resolve_datasource,
)
from apps.api.init_db import init_db, seed_pack_catalog, seed_tenant_bootstrap
from apps.api.models_db import TiUser, TiWorkspace
from apps.api.routes_admin import router as admin_router
from apps.api.routes_auth import router as auth_router
from apps.api.routes_datasources import router as datasources_router
from apps.api.routes_sessions import router as sessions_router
from apps.api.routes_users import router as users_router
from apps.api.routes_workspaces import router as workspaces_router
from apps.api.schemas import (
    AskApiResponse,
    AskBody,
    DomainInfo,
)
from apps.api.settings import settings
from apps.engine.ask import AskRequest
from apps.engine.connectors import build_engine_from_datasource


@asynccontextmanager
async def lifespan(_app: FastAPI):
    engine = get_engine()
    init_db(engine)
    seed_tenant_bootstrap(engine, default_database_url=settings.database_url)
    seed_pack_catalog(engine, Path(settings.packs_root))
    yield


app = FastAPI(title="元景.智数", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(workspaces_router)
app.include_router(users_router)
app.include_router(admin_router)
app.include_router(datasources_router)
app.include_router(sessions_router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "telecom-insight"}


@app.get("/domains", response_model=list[DomainInfo])
def list_domains(_user: TiUser = Depends(get_current_user)):
    return [
        DomainInfo(id=domain_id, name=name, version=deps.domain_version(domain_id))
        for domain_id, name in deps.DOMAIN_CATALOG
    ]


@app.get("/domains/{domain_id}/recommended")
def list_recommended(domain_id: str, _user: TiUser = Depends(get_current_user)):
    known = {d for d, _ in deps.DOMAIN_CATALOG}
    if domain_id not in known:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown domain")
    items = deps.domain_recommended(domain_id)
    return [{"id": r.id, "text": r.text} for r in items]


@app.post("/ask", response_model=AskApiResponse)
def ask(
    body: AskBody,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    if not access.can_ask:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="viewer cannot ask",
        )
    if body.domain not in access.domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="domain not allowed",
        )

    ds = resolve_datasource(session, workspace.id)  # type: ignore[arg-type]
    if ds is None:
        return AskApiResponse(
            status="error",
            message="未配置可用数据源，请先在数据源管理中设置默认数据源。",
            sql=None,
            rows=[],
            truncated=False,
            chart=None,
            narrative=None,
            steps=[],
        )

    warehouse = None
    try:
        warehouse = build_engine_from_datasource(ds)
        with warehouse.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        if warehouse is not None:
            warehouse.dispose()
        return AskApiResponse(
            status="error",
            message="数据源连接失败，请检查数据源配置后重试。",
            sql=None,
            rows=[],
            truncated=False,
            chart=None,
            narrative=None,
            steps=[],
        )

    dialect = dialect_for_datasource(ds)
    extra_terms = deps.load_domain_terms(session, body.domain, workspace.id)  # type: ignore[arg-type]
    extra_examples = deps.load_domain_examples(
        session, body.domain, workspace.id  # type: ignore[arg-type]
    )
    try:
        engine = deps.get_ask_engine(
            session,
            warehouse=warehouse,
            dialect=dialect,
            workspace_id=workspace.id,  # type: ignore[arg-type]
        )
        resp = engine.ask(
            AskRequest(domain=body.domain, question=body.question),
            extra_terms=extra_terms,
            extra_examples=extra_examples,
        )
    finally:
        warehouse.dispose()

    return AskApiResponse(
        status=resp.status,
        message=resp.message,
        sql=resp.sql,
        rows=resp.rows,
        truncated=resp.truncated,
        chart=resp.chart,
        narrative=resp.narrative,
        steps=[],
    )
