from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Column, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TiChatSession(SQLModel, table=True):
    __tablename__ = "ti_chat_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = ""
    domain: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TiChatMessage(SQLModel, table=True):
    __tablename__ = "ti_chat_message"

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: int = Field(foreign_key="ti_chat_session.id", index=True)
    role: str
    content_json: str = Field(sa_column=Column(Text, nullable=False, default="{}"))
    created_at: datetime = Field(default_factory=_utcnow)


class TiAiModel(SQLModel, table=True):
    __tablename__ = "ti_ai_model"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = False
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TiTerm(SQLModel, table=True):
    __tablename__ = "ti_term"

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str
    term: str
    standard: str
    maps_to: Optional[str] = None
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TiSqlExample(SQLModel, table=True):
    __tablename__ = "ti_sql_example"

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str
    question: str
    sql: str
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


# Ensure models are imported for metadata registration
_MODELS: tuple[type[SQLModel], ...] = (
    TiChatSession,
    TiChatMessage,
    TiAiModel,
    TiTerm,
    TiSqlExample,
)
