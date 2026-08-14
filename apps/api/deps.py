from functools import lru_cache
from pathlib import Path

from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from apps.api.acl import EffectiveAccess, resolve_access
from apps.api.auth import decode_token
from apps.api.db import get_session
from apps.api.db_types import PROTOCOL_FAMILY
from apps.api.models_db import (
    TiAiModel,
    TiDatasource,
    TiSqlExample,
    TiTerm,
    TiUser,
    TiWorkspace,
    TiWorkspaceMember,
)
from apps.api.settings import settings
from apps.engine.ask import AskEngine
from apps.engine.llm import OpenAICompatibleLLM
from apps.engine.sql_guard import resolve_sqlglot_dialect
from apps.packs.loader import load_pack
from apps.packs.models import Example, IndustryPack, Term

_bearer = HTTPBearer(auto_error=False)

DOMAIN_CATALOG: list[tuple[str, str]] = [
    ("biz", "经营分析"),
    ("network", "网络运维"),
    ("cs", "客户服务"),
]


class DemoFakeLLM:
    """When no API key: return first matching pack example SQL, else SELECT 1."""

    def __init__(self, packs_by_domain: dict[str, IndustryPack]):
        self._fallback_examples: list[tuple[str, str]] = []
        for pack in packs_by_domain.values():
            for ex in pack.examples:
                self._fallback_examples.append((ex.question, ex.sql))

    def generate_sql(
        self,
        *,
        question: str,
        schema_ctx: str,
        examples: list[tuple[str, str]],
        terminology: str,
    ) -> str:
        pool = examples or self._fallback_examples
        q_upper = question.upper()
        for eq, sql in pool:
            if eq.upper() in q_upper or any(
                token and token.upper() in q_upper
                for token in eq.replace("，", " ").replace(",", " ").split()
                if len(token) >= 2
            ):
                return sql
        for eq, sql in pool:
            if "ARPU" in eq.upper() and "ARPU" in q_upper:
                return sql
        if pool:
            return pool[0][1]
        return "SELECT 1"

    def narrate(self, *, question: str, sql: str, rows_preview: list[dict]) -> str:
        if not rows_preview:
            return "查询完成，暂无数据。"
        return f"根据查询结果，共返回 {len(rows_preview)} 行数据。"


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> TiUser:
    if creds is None or creds.scheme.lower() != "bearer" or not creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
        )
    sub = decode_token(creds.credentials)
    try:
        user_id = int(sub)
    except (TypeError, ValueError) as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid token",
        ) from e
    user = session.get(TiUser, user_id)
    if user is None or not user.enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid credentials",
        )
    return user


def get_workspace_access(
    session: Session,
    user: TiUser,
    workspace_id: int,
) -> tuple[TiWorkspace, EffectiveAccess]:
    """Load workspace and resolve effective access for the user."""
    workspace = session.get(TiWorkspace, workspace_id)
    if workspace is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="workspace not found",
        )

    if user.org_role == "org_admin" and workspace.org_id == user.org_id:
        access = resolve_access(
            org_role=user.org_role,
            member_role=None,
            member_domains=None,
            is_org_admin=True,
        )
        return workspace, access

    member = session.exec(
        select(TiWorkspaceMember).where(
            TiWorkspaceMember.workspace_id == workspace_id,
            TiWorkspaceMember.user_id == user.id,
        )
    ).first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="not a workspace member",
        )

    access = resolve_access(
        org_role=user.org_role,
        member_role=member.role,
        member_domains=list(member.domains or []),
        is_org_admin=False,
    )
    return workspace, access


_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def require_workspace(
    request: Request,
    x_workspace_id: int = Header(..., alias="X-Workspace-Id"),
    user: TiUser = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> tuple[TiWorkspace, EffectiveAccess]:
    workspace, access = get_workspace_access(session, user, x_workspace_id)
    if workspace.status == "archived" and request.method.upper() in _WRITE_METHODS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="workspace is archived",
        )
    return workspace, access


def require_org_admin(user: TiUser = Depends(get_current_user)) -> TiUser:
    if user.org_role != "org_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="org_admin required",
        )
    return user


def _load_packs(packs_root: Path) -> dict[str, IndustryPack]:
    packs: dict[str, IndustryPack] = {}
    if not packs_root.is_dir():
        return packs
    for domain, _ in DOMAIN_CATALOG:
        pack_dir = packs_root / domain
        if (pack_dir / "manifest.yaml").exists():
            packs[domain] = load_pack(pack_dir)
    return packs


@lru_cache
def get_packs() -> dict[str, IndustryPack]:
    return _load_packs(Path(settings.packs_root))


def load_domain_terms(session: Session, domain: str) -> list[Term]:
    rows = session.exec(select(TiTerm).where(TiTerm.domain == domain)).all()
    return [
        Term(term=r.term, standard=r.standard, maps_to=r.maps_to) for r in rows
    ]


def load_domain_examples(session: Session, domain: str) -> list[Example]:
    rows = session.exec(select(TiSqlExample).where(TiSqlExample.domain == domain)).all()
    return [Example(question=r.question, sql=r.sql) for r in rows]


def resolve_datasource(
    session: Session,
    workspace_id: int,
    chat_datasource_id: int | None = None,
) -> TiDatasource | None:
    """Prefer session-bound datasource (if in workspace), else workspace default."""
    if chat_datasource_id is not None:
        ds = session.get(TiDatasource, chat_datasource_id)
        if ds is not None and ds.workspace_id == workspace_id:
            return ds
    return session.exec(
        select(TiDatasource).where(
            TiDatasource.workspace_id == workspace_id,
            TiDatasource.is_default.is_(True),
        )
    ).first()


def dialect_for_datasource(ds: TiDatasource) -> str:
    """sqlglot dialect for a datasource db_type / protocol family."""
    family = PROTOCOL_FAMILY.get(ds.db_type, ds.db_type)
    return resolve_sqlglot_dialect(family)


def resolve_llm(session: Session | None, packs: dict[str, IndustryPack]):
    """Prefer enabled TiAiModel with api_key; else DemoFakeLLM (or settings key)."""
    if session is not None:
        model = session.exec(select(TiAiModel).where(TiAiModel.enabled.is_(True))).first()
        if model is not None and model.api_key:
            return OpenAICompatibleLLM(
                model=model.model or settings.llm_model,
                api_key=model.api_key,
                base_url=model.base_url or None,
            )
    if settings.llm_api_key:
        return OpenAICompatibleLLM(
            model=settings.llm_model,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
        )
    return DemoFakeLLM(packs)


def get_ask_engine(
    session: Session | None = None,
    *,
    warehouse: Engine | None = None,
    dialect: str = "postgres",
) -> AskEngine:
    packs = get_packs()
    eng = warehouse if warehouse is not None else create_engine(settings.database_url)
    llm = resolve_llm(session, packs)
    return AskEngine(
        warehouse=eng,
        llm=llm,
        packs_by_domain=packs,
        dialect=dialect,
    )


def domain_version(domain: str) -> str:
    packs_root = Path(settings.packs_root)
    pack_dir = packs_root / domain
    if (pack_dir / "manifest.yaml").exists():
        try:
            return load_pack(pack_dir).version
        except Exception:
            return "0.0.0"
    return "0.0.0"


def domain_recommended(domain: str) -> list:
    packs_root = Path(settings.packs_root)
    pack_dir = packs_root / domain
    if not (pack_dir / "manifest.yaml").exists():
        return []
    try:
        return load_pack(pack_dir).recommended
    except Exception:
        return []
