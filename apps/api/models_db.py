from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TiOrg(SQLModel, table=True):
    __tablename__ = "ti_org"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=_utcnow)


class TiWorkspace(SQLModel, table=True):
    __tablename__ = "ti_workspace"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="ti_org.id", index=True)
    name: str
    status: str = "active"  # active | archived
    created_at: datetime = Field(default_factory=_utcnow)


class TiUser(SQLModel, table=True):
    __tablename__ = "ti_user"

    id: Optional[int] = Field(default=None, primary_key=True)
    org_id: int = Field(foreign_key="ti_org.id", index=True)
    username: str = Field(index=True)
    password_hash: str
    display_name: str = ""
    org_role: str = "viewer"  # org_admin | analyst | viewer
    enabled: bool = True


class TiWorkspaceMember(SQLModel, table=True):
    __tablename__ = "ti_workspace_member"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="ti_workspace.id", index=True)
    user_id: int = Field(foreign_key="ti_user.id", index=True)
    role: str = "viewer"  # org_admin | analyst | viewer
    domains: Optional[list[Any]] = Field(default=None, sa_column=Column(JSON))


class TiDatasource(SQLModel, table=True):
    __tablename__ = "ti_datasource"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(foreign_key="ti_workspace.id", index=True)
    name: str
    db_type: str
    host: str = ""
    port: Optional[int] = None
    database: str = ""
    username: str = ""
    password_enc: str = ""
    extra_json: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    is_default: bool = False
    last_ok_at: Optional[datetime] = None
    last_error: Optional[str] = None


class TiChatSession(SQLModel, table=True):
    __tablename__ = "ti_chat_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = ""
    domain: str
    workspace_id: Optional[int] = Field(default=None, index=True)
    datasource_id: Optional[int] = Field(default=None, index=True)
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
    workspace_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TiTerm(SQLModel, table=True):
    __tablename__ = "ti_term"

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str
    term: str
    standard: str
    maps_to: Optional[str] = None
    workspace_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class TiSqlExample(SQLModel, table=True):
    __tablename__ = "ti_sql_example"

    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str
    question: str
    sql: str
    workspace_id: Optional[int] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


# Ensure models are imported for metadata registration
_MODELS: tuple[type[SQLModel], ...] = (
    TiOrg,
    TiWorkspace,
    TiUser,
    TiWorkspaceMember,
    TiDatasource,
    TiChatSession,
    TiChatMessage,
    TiAiModel,
    TiTerm,
    TiSqlExample,
)
