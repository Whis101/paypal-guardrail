"""Business workflows: they glue Claude, the rules engine, the DB and PayPal together.

Routers stay thin (parse HTTP in, serialize HTTP out); everything that matters
happens here, where it is testable without HTTP.
"""

from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.llm import classify, generate_proposal
from app.models import (
    AgentRun,
    ApprovalDecision,
    BudgetRule,
    Decision,
    RuleType,
    Transaction,
    TxStatus,
)
from app.paypal_client import PayPalError
from app.rules_engine import Action, Proposal, evaluate

# Money that has actually left (or is leaving) the account counts toward caps.
SPENT_STATUSES = (TxStatus.CAPTURED, TxStatus.AUTO_APPROVED, TxStatus.APPROVED_BY_HUMAN)


class NotFound(LookupError):
    pass


class AlreadyDecided(RuntimeError):
    pass


def _month_bounds(now: datetime) -> tuple[datetime, datetime]:
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    end = start.replace(year=start.year + 1, month=1) if start.month == 12 else start.replace(
        month=start.month + 1
    )
    return start, end


def month_spend_by_category(db: Session, now: datetime | None = None) -> dict[str, int]:
    start, end = _month_bounds(now or datetime.now(UTC))
    rows = db.execute(
        select(Transaction.category, func.sum(Transaction.amount_cents))
        .where(
            Transaction.status.in_(SPENT_STATUSES),
            Transaction.created_at >= start,
            Transaction.created_at < end,
        )
        .group_by(Transaction.category)
    ).all()
    return {cat or "other": int(total) for cat, total in rows}


def _charge(tx: Transaction, paypal) -> None:
    """Attempt the real PayPal charge; record the outcome on tx instead of raising."""
    try:
        result = paypal.charge_vault(
            tx.amount_cents, f"{tx.merchant_raw}: {tx.item_description or ''}".strip()
        )
    except PayPalError as e:
        tx.status = TxStatus.CAPTURE_FAILED
        tx.decision_reason = f"{tx.decision_reason or ''} Charge failed: {e}".strip()
        return
    tx.paypal_order_id = result.order_id
    tx.paypal_capture_id = result.capture_id
    tx.paypal_status = result.status
    tx.status = TxStatus.CAPTURED if result.status == "COMPLETED" else TxStatus.CAPTURE_FAILED


def run_agent_once(db: Session, llm_client, paypal, mandate: str | None) -> Transaction:
    """Agent proposes -> Claude classifies -> rules decide -> maybe charge. Raises LLMError."""
    proposal_text = generate_proposal(llm_client, mandate)
    c = classify(llm_client, proposal_text)

    rules = db.scalars(select(BudgetRule)).all()
    decision = evaluate(
        Proposal(merchant=c.merchant, amount_cents=c.amount_cents, category=c.category),
        rules,
        month_spend_by_category(db),
    )

    run = AgentRun(prompt_used=(mandate or "").strip() or "(default mandate)",
                   raw_llm_output=proposal_text)
    tx = Transaction(
        agent_run=run,
        merchant_raw=c.merchant[:200],
        merchant_normalized=c.merchant.strip().lower()[:200],
        amount_cents=c.amount_cents,
        category=c.category,
        item_description=c.item_description,
        decision_reason=decision.reason,
        status={
            Action.AUTO_APPROVE: TxStatus.AUTO_APPROVED,
            Action.AUTO_BLOCK: TxStatus.AUTO_BLOCKED,
            Action.NEEDS_HUMAN: TxStatus.PENDING_APPROVAL,
        }[decision.action],
    )
    db.add(run)
    db.commit()  # persist the decision before touching money

    if tx.status is TxStatus.AUTO_APPROVED:
        _charge(tx, paypal)
        db.commit()
    db.refresh(tx)
    return tx


def decide(db: Session, tx_id: int, decision: Decision, note: str | None, paypal,
           decided_by: str = "demo-user") -> Transaction:
    tx = db.get(Transaction, tx_id)
    if tx is None:
        raise NotFound(tx_id)

    new_status = (TxStatus.APPROVED_BY_HUMAN if decision is Decision.APPROVE
                  else TxStatus.DENIED_BY_HUMAN)
    # Atomic compare-and-set: only one request can move a row out of PENDING_APPROVAL,
    # so a double-click or a replayed request can never charge twice.
    claimed = db.execute(
        update(Transaction)
        .where(Transaction.id == tx_id, Transaction.status == TxStatus.PENDING_APPROVAL)
        .values(status=new_status)
    ).rowcount
    if claimed != 1:
        db.rollback()
        raise AlreadyDecided(tx_id)

    tx.approval_decisions.append(
        ApprovalDecision(decided_by=decided_by, decision=decision, note=note)
    )
    db.commit()
    db.refresh(tx)

    if decision is Decision.APPROVE:
        _charge(tx, paypal)
        db.commit()
        db.refresh(tx)
    return tx


def summary(db: Session) -> dict:
    counts = dict(
        db.execute(select(Transaction.status, func.count()).group_by(Transaction.status)).all()
    )
    total = db.scalar(
        select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(
            Transaction.status == TxStatus.CAPTURED
        )
    )
    return {
        "month_spend_by_category": month_spend_by_category(db),
        "counts_by_status": {s.value: n for s, n in counts.items()},
        "total_captured_cents": int(total),
    }


DEFAULT_RULES = [
    {"rule_type": RuleType.SINGLE_TRANSACTION_LIMIT, "limit_cents": 15_000},
    {"rule_type": RuleType.CATEGORY_MONTHLY_CAP, "category": "groceries", "limit_cents": 60_000},
    {"rule_type": RuleType.CATEGORY_MONTHLY_CAP, "category": "electronics", "limit_cents": 20_000},
    {"rule_type": RuleType.CATEGORY_MONTHLY_CAP, "category": "gift_cards", "limit_cents": 1},
    {"rule_type": RuleType.BLOCKED_MERCHANT, "merchant": "casino"},
]


def seed_default_rules(db: Session) -> None:
    """Give a fresh install sensible demo rules; never touches an existing rule set."""
    if db.scalar(select(func.count()).select_from(BudgetRule)):
        return
    db.add_all(BudgetRule(**r) for r in DEFAULT_RULES)
    db.commit()
