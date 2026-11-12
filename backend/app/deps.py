"""External-service clients as FastAPI dependencies.

Endpoints receive these via Depends(), so tests replace them with fakes through
app.dependency_overrides: no real Claude or PayPal calls in the test suite.
"""

from functools import lru_cache
from typing import Annotated

import anthropic
from fastapi import Depends, HTTPException

from app.config import get_settings
from app.paypal_client import PayPalClient


@lru_cache
def _anthropic_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def get_llm_client() -> anthropic.Anthropic:
    if not get_settings().anthropic_api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY is not configured on the server.")
    return _anthropic_client()


@lru_cache
def get_paypal() -> PayPalClient:
    s = get_settings()
    return PayPalClient(s.paypal_base_url, s.paypal_client_id, s.paypal_client_secret,
                        s.paypal_vault_id)


LLMClient = Annotated[anthropic.Anthropic, Depends(get_llm_client)]
PayPal = Annotated[PayPalClient, Depends(get_paypal)]
