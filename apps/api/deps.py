from functools import lru_cache
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlmodel import Session, select

from apps.api.auth import decode_token
from apps.api.db import get_session
from apps.api.models_db import TiAiModel, TiSqlExample, TiTerm, TiUser
from apps.api.settings import settings
from apps.engine.ask import AskEngine
from apps.engine.llm import OpenAICompatibleLLM
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


def get_ask_engine(session: Session | None = None) -> AskEngine:
    packs = get_packs()
    warehouse = create_engine(settings.database_url)
    llm = resolve_llm(session, packs)
    return AskEngine(warehouse=warehouse, llm=llm, packs_by_domain=packs)


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
