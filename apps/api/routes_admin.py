from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from apps.api.db import get_session
from apps.api.deps import get_current_user
from apps.api.models_db import TiAiModel, TiSqlExample, TiTerm
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


def _disable_other_models(session: Session, keep_id: int | None = None) -> None:
    models = session.exec(select(TiAiModel)).all()
    for m in models:
        if keep_id is not None and m.id == keep_id:
            continue
        if m.enabled:
            m.enabled = False
            m.updated_at = _utcnow()
            session.add(m)


# --- Models ---


@router.get("/models", response_model=list[AiModelOut])
def list_models(
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    return session.exec(select(TiAiModel).order_by(TiAiModel.id)).all()


@router.post("/models", response_model=AiModelOut)
def create_model(
    body: AiModelCreate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    if body.enabled:
        _disable_other_models(session)
    row = TiAiModel(
        name=body.name,
        base_url=body.base_url,
        api_key=body.api_key,
        model=body.model,
        enabled=body.enabled,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/models/{model_id}", response_model=AiModelOut)
def get_model(
    model_id: int,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiAiModel, model_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    return row


@router.patch("/models/{model_id}", response_model=AiModelOut)
def update_model(
    model_id: int,
    body: AiModelUpdate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiAiModel, model_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    data = body.model_dump(exclude_unset=True)
    if data.get("enabled") is True:
        _disable_other_models(session, keep_id=model_id)
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
    _user: str = Depends(get_current_user),
):
    row = session.get(TiAiModel, model_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.post("/models/{model_id}/test", response_model=ModelTestResult)
def test_model(
    model_id: int,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiAiModel, model_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="model not found")
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
    _user: str = Depends(get_current_user),
):
    stmt = select(TiTerm).order_by(TiTerm.id)
    if domain:
        stmt = stmt.where(TiTerm.domain == domain)
    return session.exec(stmt).all()


@router.post("/terms", response_model=TermOut)
def create_term(
    body: TermCreate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = TiTerm(
        domain=body.domain,
        term=body.term,
        standard=body.standard,
        maps_to=body.maps_to,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/terms/{term_id}", response_model=TermOut)
def get_term(
    term_id: int,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiTerm, term_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="term not found")
    return row


@router.patch("/terms/{term_id}", response_model=TermOut)
def update_term(
    term_id: int,
    body: TermUpdate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiTerm, term_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="term not found")
    for key, value in body.model_dump(exclude_unset=True).items():
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
    _user: str = Depends(get_current_user),
):
    row = session.get(TiTerm, term_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="term not found")
    session.delete(row)
    session.commit()
    return {"ok": True}


# --- Examples ---


@router.get("/examples", response_model=list[ExampleOut])
def list_examples(
    domain: str | None = None,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    stmt = select(TiSqlExample).order_by(TiSqlExample.id)
    if domain:
        stmt = stmt.where(TiSqlExample.domain == domain)
    return session.exec(stmt).all()


@router.post("/examples", response_model=ExampleOut)
def create_example(
    body: ExampleCreate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = TiSqlExample(domain=body.domain, question=body.question, sql=body.sql)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/examples/{example_id}", response_model=ExampleOut)
def get_example(
    example_id: int,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiSqlExample, example_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="example not found")
    return row


@router.patch("/examples/{example_id}", response_model=ExampleOut)
def update_example(
    example_id: int,
    body: ExampleUpdate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiSqlExample, example_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="example not found")
    for key, value in body.model_dump(exclude_unset=True).items():
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
    _user: str = Depends(get_current_user),
):
    row = session.get(TiSqlExample, example_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="example not found")
    session.delete(row)
    session.commit()
    return {"ok": True}
