import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlmodel import Session, select

from apps.api import deps
from apps.api.acl import EffectiveAccess
from apps.api.db import get_session
from apps.api.deps import dialect_for_datasource, require_workspace, resolve_datasource
from apps.api.models_db import TiChatMessage, TiChatSession, TiWorkspace
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
from apps.engine.connectors import build_engine_from_datasource

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


def _get_workspace_session(
    session: Session,
    session_id: int,
    workspace: TiWorkspace,
) -> TiChatSession:
    row = session.get(TiChatSession, session_id)
    if not row or row.workspace_id != workspace.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="session not found")
    return row


def _error_card(message: str) -> AskApiResponse:
    resp = AskResponse(status="error", message=message)
    return AskApiResponse(
        status=resp.status,
        message=resp.message,
        sql=resp.sql,
        rows=resp.rows,
        truncated=resp.truncated,
        chart=resp.chart,
        narrative=resp.narrative,
        steps=build_steps(resp),
    )


def _persist_ask_result(
    session: Session,
    *,
    chat: TiChatSession,
    session_id: int,
    question: str,
    card: AskApiResponse,
) -> AskApiResponse:
    assistant_msg = TiChatMessage(
        session_id=session_id,
        role="assistant",
        content_json=card.model_dump_json(),
    )
    chat.updated_at = _utcnow()
    if not chat.title or chat.title == "新会话":
        chat.title = question[:40]
    session.add(assistant_msg)
    session.add(chat)
    session.commit()
    return card


@router.get("", response_model=list[SessionOut])
def list_sessions(
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    return session.exec(
        select(TiChatSession)
        .where(TiChatSession.workspace_id == workspace.id)
        .order_by(TiChatSession.id.desc())
    ).all()


@router.post("", response_model=SessionOut)
def create_session(
    body: SessionCreate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    if not access.can_ask:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="viewer cannot create sessions",
        )
    if body.domain not in access.domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="domain not allowed",
        )
    title = body.title or "新会话"
    row = TiChatSession(title=title, domain=body.domain, workspace_id=workspace.id)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


@router.get("/{session_id}", response_model=SessionOut)
def get_session_row(
    session_id: int,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    return _get_workspace_session(session, session_id, workspace)


@router.patch("/{session_id}", response_model=SessionOut)
def update_session(
    session_id: int,
    body: SessionUpdate,
    session: Session = Depends(get_session),
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    row = _get_workspace_session(session, session_id, workspace)
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
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    row = _get_workspace_session(session, session_id, workspace)
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
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, _access = ws_access
    _get_workspace_session(session, session_id, workspace)
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
    ws_access: tuple[TiWorkspace, EffectiveAccess] = Depends(require_workspace),
):
    workspace, access = ws_access
    if not access.can_ask:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="viewer cannot ask",
        )
    chat = _get_workspace_session(session, session_id, workspace)
    if chat.domain not in access.domains:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="domain not allowed",
        )

    user_msg = TiChatMessage(
        session_id=session_id,
        role="user",
        content_json=json.dumps({"text": body.question}, ensure_ascii=False),
    )
    session.add(user_msg)
    session.commit()

    ds = resolve_datasource(session, workspace.id, chat.datasource_id)  # type: ignore[arg-type]
    if ds is None:
        return _persist_ask_result(
            session,
            chat=chat,
            session_id=session_id,
            question=body.question,
            card=_error_card("未配置可用数据源，请先在数据源管理中设置默认数据源。"),
        )

    warehouse = None
    try:
        warehouse = build_engine_from_datasource(ds)
        with warehouse.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        if warehouse is not None:
            warehouse.dispose()
        return _persist_ask_result(
            session,
            chat=chat,
            session_id=session_id,
            question=body.question,
            card=_error_card("数据源连接失败，请检查数据源配置后重试。"),
        )

    dialect = dialect_for_datasource(ds)
    extra_terms = deps.load_domain_terms(session, chat.domain)
    extra_examples = deps.load_domain_examples(session, chat.domain)
    try:
        engine = deps.get_ask_engine(session, warehouse=warehouse, dialect=dialect)
        resp = engine.ask(
            AskRequest(domain=chat.domain, question=body.question),
            extra_terms=extra_terms,
            extra_examples=extra_examples,
        )
    finally:
        warehouse.dispose()

    card = AskApiResponse(
        status=resp.status,
        message=resp.message,
        sql=resp.sql,
        rows=resp.rows,
        truncated=resp.truncated,
        chart=resp.chart,
        narrative=resp.narrative,
        steps=build_steps(resp),
    )
    return _persist_ask_result(
        session,
        chat=chat,
        session_id=session_id,
        question=body.question,
        card=card,
    )
