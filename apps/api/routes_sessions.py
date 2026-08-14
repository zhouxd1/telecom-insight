import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from apps.api import deps
from apps.api.db import get_session
from apps.api.deps import get_current_user
from apps.api.models_db import TiChatMessage, TiChatSession
from apps.api.schemas import (
    AskApiResponse,
    MessageOut,
    SessionAskBody,
    SessionCreate,
    SessionOut,
    SessionUpdate,
    StepInfo,
)
from apps.engine.ask import AskRequest, AskResponse

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def build_steps(resp: AskResponse) -> list[StepInfo]:
    """Build a ChatBI step strip from ask outcome."""
    labels = [
        ("understand", "理解"),
        ("retrieve", "检索"),
        ("sql", "SQL"),
        ("execute", "执行"),
        ("chart", "图表"),
    ]
    if resp.status == "clarify":
        states = ["done", "pending", "pending", "pending", "pending"]
    elif resp.status == "error":
        states = ["done", "done", "done", "done", "pending"]
        if resp.sql is None:
            states = ["done", "done", "done", "pending", "pending"]
    else:
        states = ["done", "done", "done", "done", "done"]
    return [
        StepInfo(id=step_id, label=label, state=state)
        for (step_id, label), state in zip(labels, states, strict=True)
    ]


@router.get("", response_model=list[SessionOut])
def list_sessions(
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    return session.exec(select(TiChatSession).order_by(TiChatSession.id.desc())).all()


@router.post("", response_model=SessionOut)
def create_session(
    body: SessionCreate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    title = body.title or "新会话"
    row = TiChatSession(title=title, domain=body.domain)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/{session_id}", response_model=SessionOut)
def get_session_row(
    session_id: int,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiChatSession, session_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return row


@router.patch("/{session_id}", response_model=SessionOut)
def update_session(
    session_id: int,
    body: SessionUpdate,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiChatSession, session_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(row, key, value)
    row.updated_at = _utcnow()
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.delete("/{session_id}")
def delete_session(
    session_id: int,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiChatSession, session_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    messages = session.exec(
        select(TiChatMessage).where(TiChatMessage.session_id == session_id)
    ).all()
    for msg in messages:
        session.delete(msg)
    session.delete(row)
    session.commit()
    return {"ok": True}


@router.get("/{session_id}/messages", response_model=list[MessageOut])
def list_messages(
    session_id: int,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    row = session.get(TiChatSession, session_id)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return session.exec(
        select(TiChatMessage)
        .where(TiChatMessage.session_id == session_id)
        .order_by(TiChatMessage.id)
    ).all()


@router.post("/{session_id}/ask", response_model=AskApiResponse)
def ask_in_session(
    session_id: int,
    body: SessionAskBody,
    session: Session = Depends(get_session),
    _user: str = Depends(get_current_user),
):
    chat = session.get(TiChatSession, session_id)
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")

    user_msg = TiChatMessage(
        session_id=session_id,
        role="user",
        content_json=json.dumps({"text": body.question}, ensure_ascii=False),
    )
    session.add(user_msg)
    session.commit()

    engine = deps.get_ask_engine()
    resp = engine.ask(AskRequest(domain=chat.domain, question=body.question))
    steps = build_steps(resp)
    card = AskApiResponse(
        status=resp.status,
        message=resp.message,
        sql=resp.sql,
        rows=resp.rows,
        truncated=resp.truncated,
        chart=resp.chart,
        narrative=resp.narrative,
        steps=steps,
    )

    assistant_msg = TiChatMessage(
        session_id=session_id,
        role="assistant",
        content_json=card.model_dump_json(),
    )
    chat.updated_at = _utcnow()
    if not chat.title or chat.title == "新会话":
        chat.title = body.question[:40]
    session.add(assistant_msg)
    session.add(chat)
    session.commit()
    return card
