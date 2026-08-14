from collections.abc import Generator

from sqlmodel import Session, create_engine
from sqlalchemy.engine import Engine

from apps.api.settings import settings

_engine: Engine | None = None
_engine_url: str | None = None


def get_engine() -> Engine:
    """Return a process-wide engine bound to settings.database_url."""
    global _engine, _engine_url
    url = settings.database_url
    if _engine is None or _engine_url != url:
        connect_args: dict = {}
        if url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        _engine = create_engine(url, connect_args=connect_args)
        _engine_url = url
    return _engine


def reset_engine() -> None:
    """Drop cached engine (for tests that change database_url)."""
    global _engine, _engine_url
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _engine_url = None


def get_session() -> Generator[Session, None, None]:
    with Session(get_engine()) as session:
        yield session
