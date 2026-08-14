from sqlmodel import Session, select

from apps.api.init_db import init_db
from apps.api.models_db import TiChatSession
from sqlalchemy import create_engine


def test_init_db_creates_tables_and_inserts_session():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    with Session(engine) as session:
        row = TiChatSession(title="demo", domain="biz")
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.id is not None
        assert row.title == "demo"
        assert row.domain == "biz"
        assert row.created_at is not None
        assert row.updated_at is not None

        found = session.exec(select(TiChatSession).where(TiChatSession.id == row.id)).one()
        assert found.title == "demo"
