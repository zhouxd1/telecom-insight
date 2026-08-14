from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class WorkspaceSummary(BaseModel):
    id: int
    name: str
    role: str
    domains: list[str]


class MeResponse(BaseModel):
    id: int
    username: str
    display_name: str
    org_id: int
    org_name: str
    org_role: str
    workspaces: list[WorkspaceSummary]


class DomainInfo(BaseModel):
    id: str
    name: str
    version: str


class AskBody(BaseModel):
    domain: str
    question: str


class StepInfo(BaseModel):
    id: str
    label: str
    state: str


class AskApiResponse(BaseModel):
    status: str
    message: str = ""
    sql: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False
    chart: dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""
    steps: list[StepInfo] = Field(default_factory=list)


# --- AI models ---


class AiModelCreate(BaseModel):
    name: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    enabled: bool = False


class AiModelUpdate(BaseModel):
    name: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    model: Optional[str] = None
    enabled: Optional[bool] = None


class AiModelOut(BaseModel):
    id: int
    name: str
    base_url: str
    api_key: str
    model: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ModelTestResult(BaseModel):
    ok: bool
    detail: str = ""


# --- Terms ---


class TermCreate(BaseModel):
    domain: str
    term: str
    standard: str
    maps_to: Optional[str] = None


class TermUpdate(BaseModel):
    domain: Optional[str] = None
    term: Optional[str] = None
    standard: Optional[str] = None
    maps_to: Optional[str] = None


class TermOut(BaseModel):
    id: int
    domain: str
    term: str
    standard: str
    maps_to: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# --- SQL examples ---


class ExampleCreate(BaseModel):
    domain: str
    question: str
    sql: str


class ExampleUpdate(BaseModel):
    domain: Optional[str] = None
    question: Optional[str] = None
    sql: Optional[str] = None


class ExampleOut(BaseModel):
    id: int
    domain: str
    question: str
    sql: str
    created_at: datetime
    updated_at: datetime


# --- Sessions ---


class SessionCreate(BaseModel):
    domain: str
    title: str = ""


class SessionUpdate(BaseModel):
    title: Optional[str] = None
    domain: Optional[str] = None


class SessionOut(BaseModel):
    id: int
    title: str
    domain: str
    created_at: datetime
    updated_at: datetime


class MessageOut(BaseModel):
    id: int
    session_id: int
    role: str
    content_json: str
    created_at: datetime


class SessionAskBody(BaseModel):
    question: str
