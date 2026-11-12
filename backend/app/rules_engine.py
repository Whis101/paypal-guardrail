"""The guardrail decision core: a pure function from (proposal, rules, spend) to a Decision.

"Pure" means no database, network or clock access inside `evaluate()`. All inputs are
passed in, so every approve/block/ask-a-human case is a one-line unit test, and the
same function can be reused anywhere (API, batch re-check, what-if simulation).
"""

import enum
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.models import BudgetRule, RuleType


class Action(str, enum.Enum):
    AUTO_APPROVE = "AUTO_APPROVE"
    AUTO_BLOCK = "AUTO_BLOCK"
    NEEDS_HUMAN = "NEEDS_HUMAN"


@dataclass(frozen=True)
class Proposal:
    merchant: str
    amount_cents: int
    category: str


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


def fmt_cents(cents: int) -> str:
    return f"${cents / 100:,.2f}"


def evaluate(
    proposal: Proposal,
    rules: Iterable[BudgetRule],
    month_spend_by_category: Mapping[str, int],
) -> Decision:
    """Severity order: AUTO_BLOCK beats NEEDS_HUMAN beats AUTO_APPROVE."""
    if proposal.amount_cents <= 0:
        return Decision(Action.AUTO_BLOCK, "Invalid amount: must be greater than zero.")

    merchant = proposal.merchant.casefold()
    category = proposal.category.casefold()
    # Normalise spend keys too, so "Groceries" and "groceries" are one bucket.
    spend = {k.casefold(): v for k, v in month_spend_by_category.items()}
    amount = fmt_cents(proposal.amount_cents)

    blocks: list[str] = []
    escalations: list[str] = []

    for rule in rules:
        if not rule.active:
            continue

        if rule.rule_type is RuleType.BLOCKED_MERCHANT:
            needle = (rule.merchant or "").strip().casefold()
            if needle and needle in merchant:
                blocks.append(f"Merchant '{proposal.merchant}' is on the blocked list.")

        elif rule.rule_type is RuleType.SINGLE_TRANSACTION_LIMIT:
            if rule.limit_cents is not None and proposal.amount_cents > rule.limit_cents:
                escalations.append(
                    f"{amount} exceeds the single-purchase limit of {fmt_cents(rule.limit_cents)}."
                )

        elif rule.rule_type is RuleType.CATEGORY_MONTHLY_CAP:
            applies = (
                rule.limit_cents is not None
                and bool(rule.category)
                and rule.category.casefold() == category
            )
            projected = spend.get(category, 0) + proposal.amount_cents
            if applies and projected > rule.limit_cents:
                escalations.append(
                    f"{amount} would bring '{proposal.category}' spend this month to "
                    f"{fmt_cents(projected)}, over the {fmt_cents(rule.limit_cents)} cap."
                )

    if blocks:
        return Decision(Action.AUTO_BLOCK, " ".join(blocks))
    if escalations:
        return Decision(Action.NEEDS_HUMAN, " ".join(escalations))
    return Decision(Action.AUTO_APPROVE, f"{amount} at '{proposal.merchant}' is within all rules.")
