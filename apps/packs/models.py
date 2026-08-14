from pydantic import BaseModel, Field


class Term(BaseModel):
    term: str
    standard: str
    maps_to: str | None = None


class Metric(BaseModel):
    name: str
    label: str
    description: str
    dimensions: list[str] = Field(default_factory=list)
    sql_hint: str | None = None


class Example(BaseModel):
    question: str
    sql: str


class Recommended(BaseModel):
    id: str
    text: str


class IndustryPack(BaseModel):
    domain: str
    version: str
    engine_compat: str = ">=0.1.0"
    schemas: list[str] = Field(default_factory=list)
    table_whitelist: list[str] = Field(default_factory=list)
    terminology: list[Term] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    recommended: list[Recommended] = Field(default_factory=list)
    schema_docs: str = ""
