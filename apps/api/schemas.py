from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class DomainInfo(BaseModel):
    id: str
    name: str
    version: str


class AskBody(BaseModel):
    domain: str
    question: str


class AskApiResponse(BaseModel):
    status: str
    message: str = ""
    sql: str | None = None
    rows: list[dict[str, Any]] = Field(default_factory=list)
    truncated: bool = False
    chart: dict[str, Any] = Field(default_factory=dict)
    narrative: str = ""
