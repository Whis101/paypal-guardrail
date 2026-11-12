"""HTTP routes. Thin by design: validate input, call a service, shape the output."""

import anthropic
from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select

from app import services
from app.db import DbSession
from app.deps import LLMClient, PayPal
from app.llm import LLMError
from app.models import BudgetRule, Transaction, TxStatus
from app.schemas import (
    AgentRunIn,
    DecisionIn,
    RuleIn,
    RuleOut,
    RulePatch,
    SummaryOut,
    TransactionOut,
)

router = APIRouter(prefix="/api")


@router.post("/agent/run")
def run_agent(body: AgentRunIn, db: DbSession, llm: LLMClient, paypal: PayPal) -> TransactionOut:
    try:
        tx = services.run_agent_once(db, llm, paypal, body.mandate)
    except LLMError as e:
        raise HTTPException(502, str(e)) from e
    except anthropic.APIError as e:
        # Don't echo provider internals to the browser; the type name is enough.
        raise HTTPException(502, f"Claude API error ({type(e).__name__}).") from e
    return TransactionOut.model_validate(tx)


@router.get("/transactions")
def list_transactions(db: DbSession) -> list[TransactionOut]:
    rows = db.scalars(select(Transaction).order_by(Transaction.id.desc()).limit(500))
    return [TransactionOut.model_validate(t) for t in rows]


@router.get("/approvals/pending")
def pending(db: DbSession) -> list[TransactionOut]:
    rows = db.scalars(
        select(Transaction)
        .where(Transaction.status == TxStatus.PENDING_APPROVAL)
        .order_by(Transaction.id)
    )
    return [TransactionOut.model_validate(t) for t in rows]


@router.post("/approvals/{tx_id}/decision")
def decide(tx_id: int, body: DecisionIn, db: DbSession, paypal: PayPal) -> TransactionOut:
    try:
        tx = services.decide(db, tx_id, body.decision, body.note, paypal)
    except services.NotFound as e:
        raise HTTPException(404, "Transaction not found.") from e
    except services.AlreadyDecided as e:
        raise HTTPException(409, "Transaction is not awaiting approval.") from e
    return TransactionOut.model_validate(tx)


@router.get("/rules")
def list_rules(db: DbSession) -> list[RuleOut]:
    return [RuleOut.model_validate(r) for r in db.scalars(select(BudgetRule).order_by(BudgetRule.id))]


@router.post("/rules", status_code=201)
def create_rule(body: RuleIn, db: DbSession) -> RuleOut:
    rule = BudgetRule(**body.model_dump())
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return RuleOut.model_validate(rule)


def _get_rule(db, rule_id: int) -> BudgetRule:
    rule = db.get(BudgetRule, rule_id)
    if rule is None:
        raise HTTPException(404, "Rule not found.")
    return rule


@router.patch("/rules/{rule_id}")
def patch_rule(rule_id: int, body: RulePatch, db: DbSession) -> RuleOut:
    rule = _get_rule(db, rule_id)
    rule.active = body.active
    db.commit()
    db.refresh(rule)
    return RuleOut.model_validate(rule)


@router.delete("/rules/{rule_id}", status_code=204)
def delete_rule(rule_id: int, db: DbSession) -> Response:
    db.delete(_get_rule(db, rule_id))
    db.commit()
    return Response(status_code=204)


@router.get("/summary")
def get_summary(db: DbSession) -> SummaryOut:
    return SummaryOut(**services.summary(db))
