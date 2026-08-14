"""Terms / examples / LLM resolution must stay within workspace."""

from __future__ import annotations

import pytest
from sqlmodel import Session

from apps.api import db, deps
from apps.api.init_db import init_db, seed_tenant_bootstrap
from apps.api.models_db import TiTerm, TiWorkspace
from apps.api.settings import settings
from sqlmodel import select


@pytest.fixture
def engine(tmp_path, monkeypatch):
    db_path = tmp_path / "scoped_ctx.db"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "packs_root", str(tmp_path / "empty_packs"))
    db.reset_engine()
    eng = db.get_engine()
    init_db(eng)
    seed_tenant_bootstrap(eng, default_database_url="sqlite://")
    yield eng
    db.reset_engine()


def test_load_domain_terms_filters_by_workspace(engine):
    with Session(engine) as session:
        ws = session.exec(select(TiWorkspace)).first()
        assert ws is not None
        other = TiWorkspace(org_id=ws.org_id, name="other", status="active")
        session.add(other)
        session.flush()

        session.add(
            TiTerm(
                domain="biz",
                term="IN_WS",
                standard="in",
                maps_to="t.a",
                workspace_id=ws.id,
            )
        )
        session.add(
            TiTerm(
                domain="biz",
                term="OUT_WS",
                standard="out",
                maps_to="t.b",
                workspace_id=other.id,
            )
        )
        session.commit()

        loaded = deps.load_domain_terms(session, "biz", workspace_id=ws.id)  # type: ignore[arg-type]
        terms = {t.term for t in loaded}
        assert "IN_WS" in terms
        assert "OUT_WS" not in terms
