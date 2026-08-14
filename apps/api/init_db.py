from pathlib import Path

from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, select

import apps.api.models_db  # noqa: F401 — register table metadata
from apps.api.models_db import TiSqlExample, TiTerm
from apps.packs.loader import load_pack


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)


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
