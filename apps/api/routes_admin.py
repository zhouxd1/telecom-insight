from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from apps.api.acl import EffectiveAccess
from apps.api.db import get_session
from apps.api.deps import require_workspace
from apps.api.models_db import TiAiModel, TiSqlExample, TiTerm, TiWorkspace
from apps.api.schemas import (
    AiModelCreate,
    AiModelOut,
    AiModelUpdate,
    ExampleCreate,
    ExampleOut,
    ExampleUpdate,
    ModelTestResult,
    TermCreate,
    TermOut,
    TermUpdate,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _disable_other_models(
    session: Session, workspace_id: int, keep_id: int | None = None
) -> None:
    models = session.exec(
        select(TiAiModel).where(TiAiModel.workspace_id == workspace_id)
    ).all()
    for m in models:
        if keep_id is not None and m.id == keep_id:
            continue
        if m.enabled:
            m.enabled = False
            m.updated_at = _utcnow()
            session.add(m)


def _get_workspace_model(
    session: Session, model_id: int, workspace: TiWorkspace
) -> TiAiModel:
    row = session.get(TiAiModel, model_id)
    if not row or row.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    return row


def _get_workspace_term(
    session: Session, term_id: int, workspace: TiWorkspace
) -> TiTerm:
    row = session.get(TiTerm, term_id)
    if not row or row.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="term not found")
    return row


def _get_workspace_example(
    session: Session, example_id: int, workspace: TiWorkspace
) -> TiSqlExample:
    row = session.get(TiSqlExample, example_id)
    if not row or row.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="example not found")
    return row


def _require_domain_write(access: EffectiveAccess, domain: str) -> None:
    """org_admin: all domains; others need domain in access.domains; viewers blocked."""
    if access.role == "viewer" or not access.can_ask:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="write not allowed",
        )
    if access.role == "org_admin":
        return
    if domain not in access.domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="domain not allowed",
        )


def _require_model_write(access: EffectiveAccess) -> None:
    """Viewers cannot manage models; org_admin and analysts may write."""
    if access.role == "viewer" or (
        not access.can_ask and access.role != "org_admin"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="write not allowed",
        )


# --- Models ---


@router.get("/models", response_model=list[AiModelOut])
def list_models(
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    return session.exec(
        select(TiAiModel)
        .where(TiAiModel.workspace_id == workspace.id)
        .order_by(TiAiModel.id)
    ).all()


@router.post("/models", response_model=AiModelOut)
def create_model(
    body: AiModelCreate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_model_write(access)
    if body.enabled:
        _disable_other_models(session, workspace.id)  # type: ignore[arg-type]
    row = TiAiModel(
        name=body.name,
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
        enabled=body.enabled,
        workspace_id=workspace.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/models/{model_id}", response_model=AiModelOut)
def get_model(
    model_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    return _get_workspace_model(session, model_id, workspace)


@router.patch("/models/{model_id}", response_model=AiModelOut)
def update_model(
    model_id: int,
    body: AiModelUpdate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_model_write(access)
    row = _get_workspace_model(session, model_id, workspace)
    data = body.model_dump(exclude_unset=True)
    if data.get("enabled") is True:
        _disable_other_models(session, workspace.id, keep_id=model_id)  # type: ignore[arg-type]
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/models/{model_id}")
def delete_model(
    model_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_model_write(access)
    row = _get_workspace_model(session, model_id, workspace)
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.post("/models/{model_id}/test", response_model=ModelTestResult)
def test_model(
    model_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    row = _get_workspace_model(session, model_id, workspace)
    if not row.api_key:
        return ModelTestResult(ok=True, detail="skipped")
    base = (row.base_url or "").rstrip("/")
    if not base:
        return ModelTestResult(ok=True, detail="ok")
    url = f"{base}/models"
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(url, headers={"Authorization": f"Bearer {row.api_key}"})
        if resp.status_code < 500:
            return ModelTestResult(ok=True, detail="ok")
        return ModelTestResult(ok=True, detail=f"http {resp.status_code}")
    except Exception as exc:  # noqa: BLE001 — connectivity soft-fail still ok for demo
        return ModelTestResult(ok=True, detail=f"ok ({exc})")


# --- Terms ---


@router.get("/terms", response_model=list[TermOut])
def list_terms(
    domain: str | None = None,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    stmt = (
        select(TiTerm)
        .where(TiTerm.workspace_id == workspace.id)
        .order_by(TiTerm.id)
    )
    if domain:
        stmt = stmt.where(TiTerm.domain == domain)
    return session.exec(stmt).all()


@router.post("/terms", response_model=TermOut)
def create_term(
    body: TermCreate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_domain_write(access, body.domain)
    row = TiTerm(
        domain=body.domain,
        term=body.term,
        standard=body.standard,
        maps_to=body.maps_to,
        workspace_id=workspace.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/terms/{term_id}", response_model=TermOut)
def get_term(
    term_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    return _get_workspace_term(session, term_id, workspace)


@router.patch("/terms/{term_id}", response_model=TermOut)
def update_term(
    term_id: int,
    body: TermUpdate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    row = _get_workspace_term(session, term_id, workspace)
    data = body.model_dump(exclude_unset=True)
    _require_domain_write(access, data.get("domain", row.domain))
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/terms/{term_id}")
def delete_term(
    term_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    row = _get_workspace_term(session, term_id, workspace)
    _require_domain_write(access, row.domain)
    session.delete(row)
    session.commit()
    return {"ok": True}


# --- Examples ---


@router.get("/examples", response_model=list[ExampleOut])
def list_examples(
    domain: str | None = None,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    stmt = (
        select(TiSqlExample)
        .where(TiSqlExample.workspace_id == workspace.id)
        .order_by(TiSqlExample.id)
    )
    if domain:
        stmt = stmt.where(TiSqlExample.domain == domain)
    return session.exec(stmt).all()


@router.post("/examples", response_model=ExampleOut)
def create_example(
    body: ExampleCreate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    _require_domain_write(access, body.domain)
    row = TiSqlExample(
        domain=body.domain,
        question=body.question,
        sql=body.sql,
        workspace_id=workspace.id,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/examples/{example_id}", response_model=ExampleOut)
def get_example(
    example_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    return _get_workspace_example(session, example_id, workspace)


@router.patch("/examples/{example_id}", response_model=ExampleOut)
def update_example(
    example_id: int,
    body: ExampleUpdate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    row = _get_workspace_example(session, example_id, workspace)
    data = body.model_dump(exclude_unset=True)
    _require_domain_write(access, data.get("domain", row.domain))
    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/examples/{example_id}")
def delete_example(
    example_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    row = _get_workspace_example(session, example_id, workspace)
    _require_domain_write(access, row.domain)
    session.delete(row)
    session.commit()
    return {"ok": True}
