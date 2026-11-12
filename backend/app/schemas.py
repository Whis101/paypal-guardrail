"""Pydantic request/response shapes: the HTTP contract, validated at the edge."""

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.llm import MAX_MANDATE_CHARS
from app.models import Decision, RuleType, TxStatus

MAX_LIMIT_CENTS = 10_000_000  # $100k sanity ceiling


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    agent_run_id: int | None
    merchant_raw: str
    amount_cents: int
    currency: str
    category: str | None
    item_description: str | None
    status: TxStatus
    decision_reason: str | None
    paypal_order_id: str | None
    paypal_capture_id: str | None
    paypal_status: str | None


class AgentRunIn(BaseModel):
    mandate: str | None = Field(default=None, max_length=MAX_MANDATE_CHARS)


class DecisionIn(BaseModel):
    decision: Decision
    note: str | None = Field(default=None, max_length=1000)


class RuleIn(BaseModel):
    rule_type: RuleType
    category: str | None = Field(default=None, max_length=64)
    merchant: str | None = Field(default=None, max_length=200)
    limit_cents: int | None = Field(default=None, gt=0, le=MAX_LIMIT_CENTS)

    @model_validator(mode="after")
    def check_fields_for_type(self) -> Self:
        self.category = (self.category or "").strip().lower() or None
        self.merchant = (self.merchant or "").strip() or None
        if self.rule_type is RuleType.CATEGORY_MONTHLY_CAP and not (
            self.category and self.limit_cents
        ):
            raise ValueError("CATEGORY_MONTHLY_CAP needs category and limit_cents")
        if self.rule_type is RuleType.SINGLE_TRANSACTION_LIMIT and not self.limit_cents:
            raise ValueError("SINGLE_TRANSACTION_LIMIT needs limit_cents")
        if self.rule_type is RuleType.BLOCKED_MERCHANT and not self.merchant:
            raise ValueError("BLOCKED_MERCHANT needs merchant")
        return self


class RulePatch(BaseModel):
    active: bool


class RuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rule_type: RuleType
    category: str | None
    merchant: str | None
    limit_cents: int | None
    active: bool
    created_at: datetime


class SummaryOut(BaseModel):
    month_spend_by_category: dict[str, int]
    counts_by_status: dict[str, int]
    total_captured_cents: int
