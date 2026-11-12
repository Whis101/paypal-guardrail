"""Table-driven tests for the pure rules engine (no DB, no network)."""

import pytest

from app.models import BudgetRule, RuleType
from app.rules_engine import Action, Proposal, evaluate


def cap(category: str, limit: int, active: bool = True) -> BudgetRule:
    return BudgetRule(
        rule_type=RuleType.CATEGORY_MONTHLY_CAP, category=category, limit_cents=limit, active=active
    )


def single_limit(limit: int) -> BudgetRule:
    return BudgetRule(rule_type=RuleType.SINGLE_TRANSACTION_LIMIT, limit_cents=limit, active=True)


def blocked(merchant: str, active: bool = True) -> BudgetRule:
    return BudgetRule(rule_type=RuleType.BLOCKED_MERCHANT, merchant=merchant, active=active)


GROCERY_40 = Proposal(merchant="Whole Foods Market", amount_cents=4000, category="groceries")


@pytest.mark.parametrize(
    ("proposal", "rules", "spend", "expected"),
    [
        # No rules at all -> approve.
        (GROCERY_40, [], {}, Action.AUTO_APPROVE),
        # Under the single-transaction limit -> approve; exactly at it -> approve.
        (GROCERY_40, [single_limit(5000)], {}, Action.AUTO_APPROVE),
        (GROCERY_40, [single_limit(4000)], {}, Action.AUTO_APPROVE),
        # One cent over the single limit -> human.
        (GROCERY_40, [single_limit(3999)], {}, Action.NEEDS_HUMAN),
        # Category cap: existing spend + this purchase vs the cap.
        (GROCERY_40, [cap("groceries", 10000)], {"groceries": 6000}, Action.AUTO_APPROVE),
        (GROCERY_40, [cap("groceries", 10000)], {"groceries": 6001}, Action.NEEDS_HUMAN),
        # Cap for a different category doesn't apply.
        (GROCERY_40, [cap("dining", 100)], {"dining": 99999}, Action.AUTO_APPROVE),
        # Category match is case-insensitive.
        (GROCERY_40, [cap("Groceries", 1000)], {}, Action.NEEDS_HUMAN),
        # Blocked merchant: case-insensitive substring match.
        (GROCERY_40, [blocked("whole foods")], {}, Action.AUTO_BLOCK),
        (GROCERY_40, [blocked("Trader Joe")], {}, Action.AUTO_APPROVE),
        # Block wins over needs-human when both trigger.
        (GROCERY_40, [single_limit(1), blocked("WHOLE FOODS")], {}, Action.AUTO_BLOCK),
        # Inactive rules are ignored.
        (GROCERY_40, [blocked("whole foods", active=False)], {}, Action.AUTO_APPROVE),
        (GROCERY_40, [cap("groceries", 1, active=False)], {}, Action.AUTO_APPROVE),
    ],
)
def test_evaluate_table(proposal, rules, spend, expected):
    assert evaluate(proposal, rules, spend).action is expected


@pytest.mark.parametrize("amount", [0, -500])
def test_non_positive_amount_is_blocked(amount):
    p = Proposal(merchant="X", amount_cents=amount, category="misc")
    decision = evaluate(p, [], {})
    assert decision.action is Action.AUTO_BLOCK
    assert "amount" in decision.reason.lower()


def test_reason_explains_every_violation():
    rules = [single_limit(1000), cap("groceries", 2000)]
    decision = evaluate(GROCERY_40, rules, {"groceries": 0})
    assert decision.action is Action.NEEDS_HUMAN
    assert "$40.00" in decision.reason
    assert "$10.00" in decision.reason  # single limit
    assert "$20.00" in decision.reason  # category cap


def test_approve_reason_is_present():
    assert evaluate(GROCERY_40, [], {}).reason


def test_empty_blocked_merchant_rule_never_matches_everything():
    # An empty string is a substring of every name; it must not block all purchases.
    assert evaluate(GROCERY_40, [blocked("")], {}).action is Action.AUTO_APPROVE


def test_rule_with_missing_limit_is_ignored():
    rule = BudgetRule(rule_type=RuleType.SINGLE_TRANSACTION_LIMIT, limit_cents=None, active=True)
    assert evaluate(GROCERY_40, [rule], {}).action is Action.AUTO_APPROVE
