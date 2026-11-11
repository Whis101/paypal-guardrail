"""SQLAlchemy engine, session factory, and the FastAPI DB dependency."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# SQLite forbids using a connection from a thread other than the one that opened
# it. FastAPI runs sync endpoints in a threadpool, so that check must be disabled.
engine = create_engine(
    get_settings().database_url,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db() -> Iterator[Session]:
    """One session per request, always closed afterwards (even on error).

    Endpoints declare `db: Session = Depends(get_db)`; tests swap this function
    out via `app.dependency_overrides` to point at an in-memory database.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Reusable type for endpoint params: `def endpoint(db: DbSession)`.
# Annotated bundles the type with its dependency, so FastAPI injects a session.
DbSession = Annotated[Session, Depends(get_db)]
