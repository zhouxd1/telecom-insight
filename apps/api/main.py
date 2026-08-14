from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware

from apps.api import deps
from apps.api.auth import create_access_token
from apps.api.deps import get_current_user
from apps.api.schemas import (
    AskApiResponse,
    AskBody,
    DomainInfo,
    LoginRequest,
    TokenResponse,
)
from apps.api.settings import settings
from apps.engine.ask import AskRequest

app = FastAPI(title="元景.智数", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "service": "telecom-insight"}


@app.post("/auth/login", response_model=TokenResponse)
def login(body: LoginRequest):
    if body.username != settings.demo_username or body.password != settings.demo_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )
    return TokenResponse(access_token=create_access_token(body.username))


@app.get("/domains", response_model=list[DomainInfo])
def list_domains(_user: str = Depends(get_current_user)):
    return [
        DomainInfo(id=domain_id, name=name, version=deps.domain_version(domain_id))
        for domain_id, name in deps.DOMAIN_CATALOG
    ]


@app.get("/domains/{domain_id}/recommended")
def list_recommended(domain_id: str, _user: str = Depends(get_current_user)):
    known = {d for d, _ in deps.DOMAIN_CATALOG}
    if domain_id not in known:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="unknown domain")
    items = deps.domain_recommended(domain_id)
    return [{"id": r.id, "text": r.text} for r in items]


@app.post("/ask", response_model=AskApiResponse)
def ask(body: AskBody, _user: str = Depends(get_current_user)):
    engine = deps.get_ask_engine()
    resp = engine.ask(AskRequest(domain=body.domain, question=body.question))
    return AskApiResponse(
        status=resp.status,
        message=resp.message,
        sql=resp.sql,
        rows=resp.rows,
        truncated=resp.truncated,
        chart=resp.chart,
        narrative=resp.narrative,
    )
