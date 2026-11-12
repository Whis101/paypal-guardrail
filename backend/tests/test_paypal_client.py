"""PayPal client against a fake HTTP session: verifies the exact requests we send
and both response shapes PayPal can return for a vaulted order."""

from types import SimpleNamespace

import pytest

from app.paypal_client import PayPalClient, PayPalError, cents_to_value


class FakeResponse:
    def __init__(self, status: int, body: dict):
        self.status_code = status
        self._body = body
        self.ok = 200 <= status < 300
        self.text = str(body)

    def json(self):
        return self._body


class FakeSession:
    """Returns queued responses in order and records every request."""

    def __init__(self, responses: list[FakeResponse]):
        self.responses = list(responses)
        self.requests: list[SimpleNamespace] = []

    def post(self, url, **kwargs):
        self.requests.append(SimpleNamespace(url=url, **kwargs))
        return self.responses.pop(0)


TOKEN = FakeResponse(200, {"access_token": "tok-123", "expires_in": 32400})


def make(session, vault_id="VAULT-1") -> PayPalClient:
    return PayPalClient(
        base_url="https://api-m.sandbox.paypal.com",
        client_id="cid",
        client_secret="secret",
        vault_id=vault_id,
        session=session,
    )


@pytest.mark.parametrize(
    ("cents", "value"), [(500, "5.00"), (8743, "87.43"), (1, "0.01"), (100000, "1000.00")]
)
def test_cents_to_value_is_exact_string(cents, value):
    assert cents_to_value(cents) == value


def test_charge_completed_on_create():
    order = {
        "id": "ORDER-1",
        "status": "COMPLETED",
        "purchase_units": [
            {"payments": {"captures": [{"id": "CAP-1", "status": "COMPLETED"}]}}
        ],
    }
    session = FakeSession([TOKEN, FakeResponse(201, order)])
    result = make(session).charge_vault(8743, "Paper towels")

    assert (result.order_id, result.capture_id, result.status) == ("ORDER-1", "CAP-1", "COMPLETED")

    token_req, order_req = session.requests
    assert token_req.url.endswith("/v1/oauth2/token")
    assert token_req.auth == ("cid", "secret")
    assert token_req.data == {"grant_type": "client_credentials"}

    assert order_req.url.endswith("/v2/checkout/orders")
    assert order_req.headers["Authorization"] == "Bearer tok-123"
    assert order_req.headers["PayPal-Request-Id"]  # idempotency key present
    body = order_req.json
    assert body["intent"] == "CAPTURE"
    assert body["purchase_units"][0]["amount"] == {"currency_code": "USD", "value": "87.43"}
    paypal = body["payment_source"]["paypal"]
    assert paypal["vault_id"] == "VAULT-1"
    assert paypal["stored_credential"]["payment_initiator"] == "MERCHANT"
    assert paypal["stored_credential"]["usage"] == "SUBSEQUENT"
    assert order_req.timeout  # never hang forever on a network call


def test_charge_falls_back_to_explicit_capture():
    created = {"id": "ORDER-2", "status": "APPROVED"}
    captured = {
        "id": "ORDER-2",
        "status": "COMPLETED",
        "purchase_units": [
            {"payments": {"captures": [{"id": "CAP-2", "status": "COMPLETED"}]}}
        ],
    }
    session = FakeSession([TOKEN, FakeResponse(201, created), FakeResponse(201, captured)])
    result = make(session).charge_vault(500, "x")
    assert (result.order_id, result.capture_id, result.status) == ("ORDER-2", "CAP-2", "COMPLETED")
    assert session.requests[2].url.endswith("/v2/checkout/orders/ORDER-2/capture")


def test_unique_request_id_per_post():
    order = {"id": "O", "status": "COMPLETED", "purchase_units": []}
    session = FakeSession([TOKEN, FakeResponse(201, order), FakeResponse(201, order)])
    client = make(session)
    client.charge_vault(100, "a")
    client.charge_vault(100, "b")  # token cached: no second oauth call
    ids = [r.headers["PayPal-Request-Id"] for r in session.requests[1:]]
    assert len(ids) == 2 and ids[0] != ids[1]


def test_http_error_raises_with_status():
    session = FakeSession([TOKEN, FakeResponse(422, {"name": "UNPROCESSABLE_ENTITY"})])
    with pytest.raises(PayPalError, match="422"):
        make(session).charge_vault(100, "x")


def test_missing_vault_id_raises_before_any_request():
    session = FakeSession([])
    with pytest.raises(PayPalError, match="PAYPAL_VAULT_ID"):
        make(session, vault_id=None).charge_vault(100, "x")
    assert session.requests == []


def test_non_positive_amount_rejected():
    with pytest.raises(PayPalError):
        make(FakeSession([])).charge_vault(0, "x")


def test_description_is_truncated_to_paypal_limit():
    order = {"id": "O", "status": "COMPLETED", "purchase_units": []}
    session = FakeSession([TOKEN, FakeResponse(201, order)])
    make(session).charge_vault(100, "d" * 500)
    assert len(session.requests[1].json["purchase_units"][0]["description"]) <= 127
