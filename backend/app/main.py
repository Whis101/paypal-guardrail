"""FastAPI entrypoint. Run from backend/: uvicorn app.main:app --reload"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.config import get_settings
from app.db import Base, DbSession, SessionLocal, engine
from app.routers.api import router as api_router
from app.services import seed_default_rules


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # No migrations tool: create any missing tables on startup.
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_default_rules(db)
    yield


settings = get_settings()

app = FastAPI(title="Guardrail API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)

app.include_router(api_router)


@app.get("/api/health")
def health(db: DbSession) -> dict:
    db.execute(text("SELECT 1"))  # proves the DB actually answers
    return {
        "status": "ok",
        "db": "ok",
        "vault_configured": bool(get_settings().paypal_vault_id),
        "llm_configured": bool(get_settings().anthropic_api_key),
    }
