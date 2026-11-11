import os

# Dummy credentials so tests never depend on (or touch) the real .env values.
# Real env vars beat the .env file in pydantic-settings, so these win.
os.environ.update(
    PAYPAL_CLIENT_ID="test-client-id",
    PAYPAL_CLIENT_SECRET="test-client-secret",
    PAYPAL_BASE_URL="https://api-m.sandbox.paypal.com",
    PAYPAL_VAULT_ID="",
    DATABASE_URL="sqlite://",
)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app


@pytest.fixture
def db_session():
    # In-memory SQLite normally gives each connection its own empty DB.
    # StaticPool reuses one connection, so every session sees the same tables.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
