from sqlalchemy.engine import Engine
from sqlmodel import SQLModel

import apps.api.models_db  # noqa: F401 — register table metadata


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
