from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CatDatasourceRef(SQLModel, table=True):
    __tablename__ = "cat_datasource_ref"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True)
    datasource_id: int = Field(index=True)
    db_type: str = ""
    fingerprint: str = ""
    last_introspected_at: Optional[datetime] = None


class CatTable(SQLModel, table=True):
    __tablename__ = "cat_table"

    id: Optional[int] = Field(default=None, primary_key=True)
    datasource_id: int = Field(index=True)
    schema_name: str
    table_name: str
    refreshed_at: datetime = Field(default_factory=_utcnow)


class CatColumn(SQLModel, table=True):
    __tablename__ = "cat_column"

    id: Optional[int] = Field(default=None, primary_key=True)
    table_id: int = Field(foreign_key="cat_table.id", index=True)
    column_name: str
    data_type: str = ""
    nullable: bool = True


class CatWsTableGrant(SQLModel, table=True):
    __tablename__ = "cat_ws_table_grant"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True)
    datasource_id: int = Field(index=True)
    schema_name: str
    table_name: str


class CatWsColumnGrant(SQLModel, table=True):
    __tablename__ = "cat_ws_column_grant"

    id: Optional[int] = Field(default=None, primary_key=True)
    workspace_id: int = Field(index=True)
    datasource_id: int = Field(index=True)
    schema_name: str
    table_name: str
    column_name: str
