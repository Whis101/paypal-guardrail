"""
Slice 0 proof-of-concept: PayPal sandbox Vault flow, end to end.

Not part of the app - a throwaway exploratory script to de-risk the riskiest
piece of the plan (agent-initiated payments with no buyer present at charge
time) before any FastAPI code is written.

Usage:
    python scripts/vault_poc.py create-setup-token
    python scripts/vault_poc.py create-payment-token <setup_token_id>
    python scripts/vault_poc.py create-and-capture-order <vault_id> <amount_usd>

Field names are taken from PayPal's official integration guide
(developer.paypal.com/platforms/checkout/save-payment-methods/purchase-later/payment-tokens-api/paypal)
as of Oct 2026, with a couple of points the guide itself leaves ambiguous
(the exact placement of vault_id, whether stored_credential is required for
step 3, which optional headers are needed for a non-partner sandbox app).
This script surfaces the raw PayPal response on every call so those points
get resolved against the real sandbox instead of guessed.
"""

import json
import uuid
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.environ["PAYPAL_BASE_URL"]
CLIENT_ID = os.environ["PAYPAL_CLIENT_ID"]
CLIENT_SECRET = os.environ["PAYPAL_CLIENT_SECRET"]


def get_access_token() -> str:
    resp = requests.post(
        f"{BASE_URL}/v1/oauth2/token",
        data={"grant_type": "client_credentials"},
        auth=(CLIENT_ID, CLIENT_SECRET),
        headers={"Accept": "application/json"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def dump(resp: requests.Response) -> None:
    print(f"HTTP {resp.status_code}")
    try:
        print(json.dumps(resp.json(), indent=2))
    except ValueError:
        print(resp.text)


def create_setup_token() -> None:
    token = get_access_token()
    body = {
        "customer": {"merchant_customer_id": "dave_demo_customer"},
        "payment_source": {
            "paypal": {
                "description": "Guardrail AI shopping agent - payment method setup",
                "permit_multiple_payment_tokens": False,
                "usage_pattern": "IMMEDIATE",
                "usage_type": "MERCHANT",
                "customer_type": "CONSUMER",
                "experience_context": {
                    "shipping_preference": "NO_SHIPPING",
                    "payment_method_preference": "IMMEDIATE_PAYMENT_REQUIRED",
                    "brand_name": "PayPal Guardrail",
                    "locale": "en-US",
                    "return_url": "https://example.com/vault/return",
                    "cancel_url": "https://example.com/vault/cancel",
                },
            }
        },
    }
    resp = requests.post(
        f"{BASE_URL}/v3/vault/setup-tokens",
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": str(uuid.uuid4()),
        },
    )
    dump(resp)
    if resp.ok:
        data = resp.json()
        approve_link = next(
            (link["href"] for link in data.get("links", []) if link["rel"] == "approve"),
            None,
        )
        print(f"\nSetup token id: {data['id']}")
        print(f"Open this URL, log in with a sandbox PERSONAL (buyer) test account, and approve:\n{approve_link}")
        print("\nThen run: python scripts/vault_poc.py create-payment-token", data["id"])


def create_payment_token(setup_token_id: str) -> None:
    token = get_access_token()
    body = {
        "customer": {"merchant_customer_id": "dave_demo_customer"},
        "payment_source": {"token": {"id": setup_token_id, "type": "SETUP_TOKEN"}},
    }
    resp = requests.post(
        f"{BASE_URL}/v3/vault/payment-tokens",
        json=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": str(uuid.uuid4()),
        },
    )
    dump(resp)
    if resp.ok:
        vault_id = resp.json()["id"]
        print(f"\nVault id (save as PAYPAL_VAULT_ID in .env): {vault_id}")


def create_and_capture_order(vault_id: str, amount_usd: str) -> None:
    token = get_access_token()
    order_body = {
        "intent": "CAPTURE",
        "purchase_units": [
            {"amount": {"currency_code": "USD", "value": amount_usd}}
        ],
        "payment_source": {
            "paypal": {
                "vault_id": vault_id,
                "stored_credential": {
                    "payment_initiator": "MERCHANT",
                    "payment_type": "UNSCHEDULED",
                    "usage": "SUBSEQUENT",
                },
            }
        },
    }
    resp = requests.post(
        f"{BASE_URL}/v2/checkout/orders",
        json=order_body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "PayPal-Request-Id": str(uuid.uuid4()),
        },
    )
    dump(resp)
    if not resp.ok:
        return
    order = resp.json()
    order_id = order["id"]
    print(f"\nOrder id: {order_id}, status: {order['status']}")

    if order["status"] == "COMPLETED":
        print("Order auto-completed on create (no separate capture call needed).")
        return

    capture_resp = requests.post(
        f"{BASE_URL}/v2/checkout/orders/{order_id}/capture",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    dump(capture_resp)


if __name__ == "__main__":
    command = sys.argv[1] if len(sys.argv) > 1 else None
    if command == "create-setup-token":
        create_setup_token()
    elif command == "create-payment-token":
        create_payment_token(sys.argv[2])
    elif command == "create-and-capture-order":
        create_and_capture_order(sys.argv[2], sys.argv[3])
    else:
        print(__doc__)
        sys.exit(1)
