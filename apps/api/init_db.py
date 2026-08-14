from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

from passlib.context import CryptContext
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

import apps.api.models_db  # noqa: F401 — register table metadata
from apps.api.models_db import (
    TiAiModel,
    TiChatSession,
    TiDatasource,
    TiOrg,
    TiSqlExample,
    TiTerm,
    TiUser,
    TiWorkspace,
    TiWorkspaceMember,
)
from apps.api.settings import settings
from apps.packs.loader import load_pack

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_ALL_DOMAINS = ["biz", "network", "cs"]


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


def _parse_database_url(url: str) -> dict:
    """Parse a SQLAlchemy-style URL into datasource fields."""
    raw = (url or "").strip()
    if not raw or raw.startswith("sqlite"):
        # sqlite:// or sqlite:///path
        database = ":memory:"
        if raw.startswith("sqlite:///") and len(raw) > len("sqlite:///"):
            database = raw[len("sqlite:///") :]
        elif raw.startswith("sqlite:////"):
            database = raw[len("sqlite:///") :]
        return {
            "db_type": "sqlite",
            "host": "",
            "port": None,
            "database": database or ":memory:",
            "username": "",
            "password_enc": "",
        }

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").split("+", 1)[0].lower()
    db_type = "postgres" if scheme in {"postgresql", "postgres"} else scheme or "postgres"
    database = unquote(parsed.path.lstrip("/")) if parsed.path else ""
    username = unquote(parsed.username) if parsed.username else ""
    password = unquote(parsed.password) if parsed.password else ""
    return {
        "db_type": db_type,
        "host": parsed.hostname or "",
        "port": parsed.port,
        "database": database,
        "username": username,
        "password_enc": password,
    }


def _backfill_workspace_id(session: Session, workspace_id: int) -> None:
    for model in (TiChatSession, TiAiModel, TiTerm, TiSqlExample):
        rows = session.exec(select(model).where(model.workspace_id.is_(None))).all()  # type: ignore[attr-defined]
        for row in rows:
            row.workspace_id = workspace_id
            session.add(row)


def seed_tenant_bootstrap(engine: Engine, default_database_url: str | None = None) -> None:
    """Idempotent org/workspace/demo user/default datasource + legacy workspace_id backfill."""
    url = default_database_url if default_database_url is not None else settings.database_url

    with Session(engine) as session:
        existing_org = session.exec(select(TiOrg)).first()
        if existing_org is None:
            org = TiOrg(name="演示运营商")
            session.add(org)
            session.flush()

            workspace = TiWorkspace(org_id=org.id, name="默认", status="active")
            session.add(workspace)
            session.flush()

            user = TiUser(
                org_id=org.id,
                username=settings.demo_username,
                password_hash=_pwd_context.hash(settings.demo_password),
                display_name="Demo",
                org_role="org_admin",
                enabled=True,
            )
            session.add(user)
            session.flush()

            session.add(
                TiWorkspaceMember(
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role="org_admin",
                    domains=list(_ALL_DOMAINS),
                )
            )

            ds_fields = _parse_database_url(url)
            session.add(
                TiDatasource(
                    workspace_id=workspace.id,
                    name="默认数据源",
                    is_default=True,
                    **ds_fields,
                )
            )
            session.flush()
        else:
            workspace = session.exec(
                select(TiWorkspace).where(TiWorkspace.org_id == existing_org.id)
            ).first()
            if workspace is None:
                workspace = session.exec(select(TiWorkspace)).first()

        if workspace is not None and workspace.id is not None:
            _backfill_workspace_id(session, workspace.id)

        session.commit()


def seed_pack_catalog(engine: Engine, packs_root: str | Path) -> None:
    """Import pack terminology/examples into ti_* tables (idempotent by term/question)."""
    root = Path(packs_root)
    if not root.is_dir():
        return

    with Session(engine) as session:
        for pack_dir in sorted(p for p in root.iterdir() if p.is_dir()):
            if not (pack_dir / "manifest.yaml").exists():
                continue
            try:
                pack = load_pack(pack_dir)
            except Exception:
                continue

            existing_terms = {
                t.term
                for t in session.exec(
                    select(TiTerm).where(TiTerm.domain == pack.domain)
                ).all()
            }
            for term in pack.terminology:
                if term.term in existing_terms:
                    continue
                session.add(
                    TiTerm(
                        domain=pack.domain,
                        term=term.term,
                        standard=term.standard,
                        maps_to=term.maps_to,
                    )
                )
                existing_terms.add(term.term)

            existing_questions = {
                e.question
                for e in session.exec(
                    select(TiSqlExample).where(TiSqlExample.domain == pack.domain)
                ).all()
            }
            for example in pack.examples:
                if example.question in existing_questions:
                    continue
                session.add(
                    TiSqlExample(
                        domain=pack.domain,
                        question=example.question,
                        sql=example.sql,
                    )
                )
                existing_questions.add(example.question)

        session.commit()
