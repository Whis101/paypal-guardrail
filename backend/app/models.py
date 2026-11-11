"""Database tables.

Money is always stored as integer cents: floats can't represent values like
$0.10 exactly, and rounding drift in a spending-limit product is a real bug.
"""

import enum
from datetime import UTC, datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class TxStatus(str, enum.Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    AUTO_APPROVED = "AUTO_APPROVED"
    AUTO_BLOCKED = "AUTO_BLOCKED"
    APPROVED_BY_HUMAN = "APPROVED_BY_HUMAN"
    DENIED_BY_HUMAN = "DENIED_BY_HUMAN"
    CAPTURED = "CAPTURED"
    CAPTURE_FAILED = "CAPTURE_FAILED"


class RuleType(str, enum.Enum):
    CATEGORY_MONTHLY_CAP = "CATEGORY_MONTHLY_CAP"
    SINGLE_TRANSACTION_LIMIT = "SINGLE_TRANSACTION_LIMIT"
    BLOCKED_MERCHANT = "BLOCKED_MERCHANT"


class Decision(str, enum.Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"


def str_enum(enum_cls: type[enum.Enum]) -> Enum:
    # native_enum=False -> plain VARCHAR column, readable in any SQLite browser.
    return Enum(enum_cls, native_enum=False, length=32)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    triggered_at: Mapped[datetime] = mapped_column(default=utcnow)
    prompt_used: Mapped[str] = mapped_column(Text)
    raw_llm_output: Mapped[str | None] = mapped_column(Text)

    transactions: Mapped[list["Transaction"]] = relationship(back_populates="agent_run")


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)
    agent_run_id: Mapped[int | None] = mapped_column(ForeignKey("agent_runs.id"))

    merchant_raw: Mapped[str] = mapped_column(String(200))
    merchant_normalized: Mapped[str | None] = mapped_column(String(200))
    amount_cents: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    category: Mapped[str | None] = mapped_column(String(64))
    item_description: Mapped[str | None] = mapped_column(Text)

    status: Mapped[TxStatus] = mapped_column(str_enum(TxStatus))
    decision_reason: Mapped[str | None] = mapped_column(Text)

    paypal_order_id: Mapped[str | None] = mapped_column(String(64))
    paypal_capture_id: Mapped[str | None] = mapped_column(String(64))
    paypal_status: Mapped[str | None] = mapped_column(String(32))

    agent_run: Mapped[AgentRun | None] = relationship(back_populates="transactions")
    approval_decisions: Mapped[list["ApprovalDecision"]] = relationship(
        back_populates="transaction"
    )


class BudgetRule(Base):
    __tablename__ = "budget_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    rule_type: Mapped[RuleType] = mapped_column(str_enum(RuleType))
    category: Mapped[str | None] = mapped_column(String(64))
    merchant: Mapped[str | None] = mapped_column(String(200))
    limit_cents: Mapped[int | None]
    period: Mapped[str] = mapped_column(String(16), default="MONTHLY")
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=utcnow)


class ApprovalDecision(Base):
    """Kept separate from Transaction so every human decision is an audit-trail row."""

    __tablename__ = "approval_decisions"

    id: Mapped[int] = mapped_column(primary_key=True)
    transaction_id: Mapped[int] = mapped_column(ForeignKey("transactions.id"))
    decided_by: Mapped[str] = mapped_column(String(100))
    decision: Mapped[Decision] = mapped_column(str_enum(Decision))
    decided_at: Mapped[datetime] = mapped_column(default=utcnow)
    note: Mapped[str | None] = mapped_column(Text)

    transaction: Mapped[Transaction] = relationship(back_populates="approval_decisions")
