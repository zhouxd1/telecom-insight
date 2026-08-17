from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlmodel import SQLModel

from apps.catalog.db import get_engine
from apps.catalog.routes import router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Import models so metadata is registered.
    import apps.catalog.models  # noqa: F401

    SQLModel.metadata.create_all(get_engine())
    yield


app = FastAPI(title="元景.智数 Catalog", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "catalog"}
