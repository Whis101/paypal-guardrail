"""Typed application settings, loaded from environment variables and the repo-root .env.

pydantic-settings validates every value at startup: a missing required variable
fails immediately with a clear error instead of a KeyError deep inside a request.
Real environment variables take precedence over values in the .env file.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PayPal sandbox app credentials (required).
    paypal_client_id: str
    paypal_client_secret: str
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"

    # Set after the one-time Vault approval. When absent, the app falls back to
    # plain (uncaptured) order creation instead of merchant-initiated charges.
    paypal_vault_id: str | None = None

    # Needed from Slice 3 onward (proposal generation + classification).
    anthropic_api_key: str | None = None

    # Absolute path so the DB location doesn't depend on the working directory.
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'guardrail.db').as_posix()}"

    # The Vite dev server; the browser blocks cross-origin calls unless allowed here.
    cors_origins: list[str] = ["http://localhost:5173"]


@lru_cache
def get_settings() -> Settings:
    return Settings()
