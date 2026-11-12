"""Minimal PayPal REST client for merchant-initiated charges against a vaulted wallet.

Flow per purchase (no buyer present):
1. OAuth2 client-credentials: trade client id + secret for a bearer token (cached).
2. POST /v2/checkout/orders with payment_source.paypal.vault_id and a stored_credential
   saying the MERCHANT initiates a SUBSEQUENT charge against an earlier-approved token.
3. In sandbox, that order usually comes back COMPLETED with the capture inside it.
   If not, call /capture explicitly. Both shapes are handled.
"""

import time
import uuid
from dataclasses import dataclass

import requests

TIMEOUT_SECONDS = 30
DESCRIPTION_MAX = 127  # PayPal purchase_units[].description limit


class PayPalError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChargeResult:
    order_id: str
    capture_id: str | None
    status: str


def cents_to_value(cents: int) -> str:
    """Integer cents -> PayPal's decimal string, with no float rounding."""
    return f"{cents // 100}.{cents % 100:02d}"


class PayPalClient:
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        vault_id: str | None,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.vault_id = vault_id or None
        self.session = session or requests.Session()
        self._token: str | None = None
        self._token_expires_at = 0.0

    def _access_token(self) -> str:
        # Reuse the token until ~1 minute before it expires (they last hours).
        if self._token and time.monotonic() < self._token_expires_at - 60:
            return self._token
        resp = self.session.post(
            f"{self.base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(self.client_id, self.client_secret),
            headers={"Accept": "application/json"},
            timeout=TIMEOUT_SECONDS,
        )
        if not resp.ok:
            raise PayPalError(f"OAuth token request failed: HTTP {resp.status_code}")
        body = resp.json()
        self._token = body["access_token"]
        self._token_expires_at = time.monotonic() + int(body.get("expires_in", 0))
        return self._token

    def _post(self, path: str, body: dict | None = None) -> dict:
        resp = self.session.post(
            f"{self.base_url}{path}",
            json=body,
            headers={
                "Authorization": f"Bearer {self._access_token()}",
                "Content-Type": "application/json",
                # Idempotency key: if a retry resends this request, PayPal won't double-charge.
                "PayPal-Request-Id": str(uuid.uuid4()),
            },
            timeout=TIMEOUT_SECONDS,
        )
        if not resp.ok:
            # Log-safe: status + PayPal's error name/debug_id, never our credentials.
            try:
                err = resp.json()
                detail = f"{err.get('name', '')} {err.get('debug_id', '')}".strip()
            except ValueError:
                detail = ""
            raise PayPalError(f"PayPal {path} failed: HTTP {resp.status_code} {detail}".strip())
        return resp.json()

    @staticmethod
    def _first_capture(order: dict) -> dict | None:
        for unit in order.get("purchase_units", []):
            captures = unit.get("payments", {}).get("captures", [])
            if captures:
                return captures[0]
        return None

    def charge_vault(self, amount_cents: int, description: str, currency: str = "USD") -> ChargeResult:
        if not self.vault_id:
            raise PayPalError("PAYPAL_VAULT_ID is not configured; run scripts/vault_poc.py first.")
        if amount_cents <= 0:
            raise PayPalError("Amount must be positive.")

        order = self._post(
            "/v2/checkout/orders",
            {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "amount": {"currency_code": currency, "value": cents_to_value(amount_cents)},
                        "description": description[:DESCRIPTION_MAX],
                    }
                ],
                "payment_source": {
                    "paypal": {
                        "vault_id": self.vault_id,
                        "stored_credential": {
                            "payment_initiator": "MERCHANT",
                            "payment_type": "UNSCHEDULED",
                            "usage": "SUBSEQUENT",
                        },
                    }
                },
            },
        )
        if order.get("status") != "COMPLETED":
            order = self._post(f"/v2/checkout/orders/{order['id']}/capture")

        capture = self._first_capture(order)
        return ChargeResult(
            order_id=order["id"],
            capture_id=capture["id"] if capture else None,
            status=order.get("status", "UNKNOWN"),
        )
