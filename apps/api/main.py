from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from apps.api import deps
from apps.api.db import get_engine, get_session
from apps.api.deps import get_current_user
from apps.api.init_db import init_db, seed_pack_catalog, seed_tenant_bootstrap
from apps.api.models_db import TiUser
from apps.api.routes_admin import router as admin_router
from apps.api.routes_auth import router as auth_router
from apps.api.routes_sessions import router as sessions_router
from apps.api.schemas import (
    AskApiResponse,
    AskBody,
    DomainInfo,
)
from apps.api.settings import settings
from apps.engine.ask import AskRequest


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
app.include_router(admin_router)
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
    _user: TiUser = Depends(get_current_user),
):
    extra_terms = deps.load_domain_terms(session, body.domain)
    extra_examples = deps.load_domain_examples(session, body.domain)
    engine = deps.get_ask_engine(session)
    resp = engine.ask(
        AskRequest(domain=body.domain, question=body.question),
        extra_terms=extra_terms,
        extra_examples=extra_examples,
    )
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
