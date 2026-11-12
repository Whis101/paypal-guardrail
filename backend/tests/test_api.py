"""End-to-end API tests: real routers + real rules engine + real DB (in-memory),
with Claude and PayPal swapped for fakes via FastAPI dependency overrides."""

from datetime import UTC, datetime, timedelta

import pytest

from app.deps import get_llm_client, get_paypal
from app.llm import Classification, LLMError
from app.main import app
from app.models import BudgetRule, RuleType, Transaction, TxStatus
from app.paypal_client import ChargeResult, PayPalError
from app.services import month_spend_by_category, seed_default_rules


class FakePayPal:
    def __init__(self, fail: bool = False):
        self.fail = fail
        self.charges: list[tuple[int, str]] = []

    def charge_vault(self, amount_cents, description, currency="USD"):
        self.charges.append((amount_cents, description))
        if self.fail:
            raise PayPalError("PayPal /v2/checkout/orders failed: HTTP 422")
        n = len(self.charges)
        return ChargeResult(order_id=f"ORDER-{n}", capture_id=f"CAP-{n}", status="COMPLETED")


@pytest.fixture
def paypal():
    fake = FakePayPal()
    app.dependency_overrides[get_paypal] = lambda: fake
    return fake


@pytest.fixture
def agent(monkeypatch):
    """Controls what the fake 'Claude' proposes and classifies."""
    state = {"classification": None, "error": None}

    def fake_generate(client, mandate):
        if state["error"]:
            raise state["error"]
        return f"PROPOSAL for: {mandate}"

    def fake_classify(client, text):
        return state["classification"]

    monkeypatch.setattr("app.services.generate_proposal", fake_generate)
    monkeypatch.setattr("app.services.classify", fake_classify)
    app.dependency_overrides[get_llm_client] = lambda: object()
    return state


def cls(merchant="Costco", cents=4000, category="groceries") -> Classification:
    return Classification(
        merchant=merchant, amount_cents=cents, category=category,
        item_description="stuff", confidence=0.9,
    )


def add_rule(db, **kw):
    db.add(BudgetRule(**kw))
    db.commit()


# ---------- agent run ----------

def test_run_auto_approves_and_captures(client, db_session, paypal, agent):
    agent["classification"] = cls()
    resp = client.post("/api/agent/run", json={"mandate": "buy groceries"})
    assert resp.status_code == 200, resp.text
    tx = resp.json()
    assert tx["status"] == "CAPTURED"
    assert tx["paypal_order_id"] == "ORDER-1" and tx["paypal_capture_id"] == "CAP-1"
    assert tx["amount_cents"] == 4000 and tx["category"] == "groceries"
    assert paypal.charges == [(4000, "Costco: stuff")]
    assert tx["agent_run_id"] is not None


def test_run_over_limit_goes_to_human_and_does_not_charge(client, db_session, paypal, agent):
    add_rule(db_session, rule_type=RuleType.SINGLE_TRANSACTION_LIMIT, limit_cents=1000)
    agent["classification"] = cls(cents=4000)
    tx = client.post("/api/agent/run", json={}).json()
    assert tx["status"] == "PENDING_APPROVAL"
    assert "$10.00" in tx["decision_reason"]
    assert paypal.charges == []
    assert [t["id"] for t in client.get("/api/approvals/pending").json()] == [tx["id"]]


def test_run_blocked_merchant_never_charges(client, db_session, paypal, agent):
    add_rule(db_session, rule_type=RuleType.BLOCKED_MERCHANT, merchant="costco")
    agent["classification"] = cls()
    tx = client.post("/api/agent/run", json={}).json()
    assert tx["status"] == "AUTO_BLOCKED"
    assert paypal.charges == []


def test_run_paypal_failure_is_recorded_not_raised(client, db_session, agent):
    app.dependency_overrides[get_paypal] = lambda: FakePayPal(fail=True)
    agent["classification"] = cls()
    tx = client.post("/api/agent/run", json={}).json()
    assert tx["status"] == "CAPTURE_FAILED"
    assert "422" in tx["decision_reason"]


def test_run_llm_error_returns_502(client, paypal, agent):
    agent["error"] = LLMError("Agent stopped early: refusal")
    resp = client.post("/api/agent/run", json={})
    assert resp.status_code == 502
    assert "refusal" in resp.json()["detail"]


def test_run_rejects_huge_mandate(client, paypal, agent):
    resp = client.post("/api/agent/run", json={"mandate": "x" * 5000})
    assert resp.status_code == 422


def test_category_cap_counts_this_months_captured_spend(client, db_session, paypal, agent):
    add_rule(db_session, rule_type=RuleType.CATEGORY_MONTHLY_CAP, category="groceries",
             limit_cents=10000)
    agent["classification"] = cls(cents=6000)
    assert client.post("/api/agent/run", json={}).json()["status"] == "CAPTURED"
    # 6000 already captured + 6000 more > 10000 cap -> ask the human.
    assert client.post("/api/agent/run", json={}).json()["status"] == "PENDING_APPROVAL"


# ---------- month spend ----------

def test_month_spend_only_counts_captured_this_month(db_session):
    now = datetime(2026, 11, 12, tzinfo=UTC)
    def tx(cents, status, when, cat="groceries"):
        return Transaction(merchant_raw="m", amount_cents=cents, category=cat, status=status,
                           created_at=when)
    db_session.add_all([
        tx(1000, TxStatus.CAPTURED, now),
        tx(2000, TxStatus.CAPTURED, now, cat="dining"),
        tx(4000, TxStatus.PENDING_APPROVAL, now),          # not spent
        tx(8000, TxStatus.AUTO_BLOCKED, now),              # not spent
        tx(16000, TxStatus.CAPTURED, now - timedelta(days=30)),  # last month
    ])
    db_session.commit()
    assert month_spend_by_category(db_session, now) == {"groceries": 1000, "dining": 2000}


# ---------- approvals ----------

def make_pending(client, db_session, agent):
    add_rule(db_session, rule_type=RuleType.SINGLE_TRANSACTION_LIMIT, limit_cents=1)
    agent["classification"] = cls()
    return client.post("/api/agent/run", json={}).json()


def test_approve_charges_and_audits(client, db_session, paypal, agent):
    pending = make_pending(client, db_session, agent)
    resp = client.post(f"/api/approvals/{pending['id']}/decision",
                       json={"decision": "APPROVE", "note": "ok"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "CAPTURED"
    assert len(paypal.charges) == 1
    tx = db_session.get(Transaction, pending["id"])
    assert tx.approval_decisions[0].note == "ok"


def test_deny_never_charges(client, db_session, paypal, agent):
    pending = make_pending(client, db_session, agent)
    resp = client.post(f"/api/approvals/{pending['id']}/decision", json={"decision": "DENY"})
    assert resp.json()["status"] == "DENIED_BY_HUMAN"
    assert paypal.charges == []


def test_second_decision_is_409_and_never_double_charges(client, db_session, paypal, agent):
    pending = make_pending(client, db_session, agent)
    url = f"/api/approvals/{pending['id']}/decision"
    assert client.post(url, json={"decision": "APPROVE"}).status_code == 200
    assert client.post(url, json={"decision": "APPROVE"}).status_code == 409
    assert len(paypal.charges) == 1


def test_decision_on_unknown_tx_404(client, paypal):
    assert client.post("/api/approvals/999/decision", json={"decision": "DENY"}).status_code == 404


def test_decision_value_validated(client, paypal):
    assert client.post("/api/approvals/1/decision", json={"decision": "MAYBE"}).status_code == 422


# ---------- rules CRUD ----------

def test_rules_crud(client):
    r = client.post("/api/rules", json={"rule_type": "CATEGORY_MONTHLY_CAP",
                                        "category": "Dining", "limit_cents": 20000})
    assert r.status_code == 201, r.text
    rule = r.json()
    assert rule["category"] == "dining" and rule["active"] is True  # normalised

    assert [x["id"] for x in client.get("/api/rules").json()] == [rule["id"]]

    r = client.patch(f"/api/rules/{rule['id']}", json={"active": False})
    assert r.json()["active"] is False

    assert client.delete(f"/api/rules/{rule['id']}").status_code == 204
    assert client.get("/api/rules").json() == []
    assert client.delete(f"/api/rules/{rule['id']}").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"rule_type": "CATEGORY_MONTHLY_CAP", "limit_cents": 100},            # no category
        {"rule_type": "CATEGORY_MONTHLY_CAP", "category": "x"},               # no limit
        {"rule_type": "SINGLE_TRANSACTION_LIMIT", "limit_cents": -5},         # negative
        {"rule_type": "BLOCKED_MERCHANT", "merchant": "   "},                 # blank
        {"rule_type": "NOPE"},
    ],
)
def test_invalid_rules_rejected(client, body):
    assert client.post("/api/rules", json=body).status_code == 422


# ---------- read endpoints ----------

def test_transactions_newest_first_and_summary(client, db_session, paypal, agent):
    agent["classification"] = cls(cents=1000)
    first = client.post("/api/agent/run", json={}).json()
    agent["classification"] = cls(cents=2500, category="dining", merchant="Chipotle")
    second = client.post("/api/agent/run", json={}).json()

    ids = [t["id"] for t in client.get("/api/transactions").json()]
    assert ids == [second["id"], first["id"]]

    s = client.get("/api/summary").json()
    assert s["total_captured_cents"] == 3500
    assert s["counts_by_status"]["CAPTURED"] == 2
    assert s["month_spend_by_category"] == {"groceries": 1000, "dining": 2500}


def test_health_reports_llm_flag(client):
    body = client.get("/api/health").json()
    assert "llm_configured" in body


def test_seed_default_rules_is_idempotent(db_session):
    seed_default_rules(db_session)
    n = len(db_session.query(BudgetRule).all())
    assert n > 0
    seed_default_rules(db_session)
    assert len(db_session.query(BudgetRule).all()) == n


def test_timestamps_are_serialized_as_utc(client, db_session, paypal, agent):
    # SQLite drops tzinfo; without an explicit offset, browsers would read UTC as local time.
    agent["classification"] = cls()
    tx = client.post("/api/agent/run", json={}).json()
    listed = client.get("/api/transactions").json()[0]
    for value in (tx["created_at"], listed["created_at"]):
        assert value.endswith(("Z", "+00:00")), value
