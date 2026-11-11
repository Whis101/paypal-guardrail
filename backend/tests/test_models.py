from sqlalchemy import select

from app.models import (
    AgentRun,
    ApprovalDecision,
    BudgetRule,
    Decision,
    RuleType,
    Transaction,
    TxStatus,
)


def test_transaction_round_trip_with_relationships(db_session):
    run = AgentRun(prompt_used="buy groceries", raw_llm_output="Whole Foods, $42.17")
    tx = Transaction(
        agent_run=run,
        merchant_raw="WHOLEFDS #123",
        amount_cents=4217,
        category="groceries",
        status=TxStatus.PENDING_APPROVAL,
    )
    tx.approval_decisions.append(
        ApprovalDecision(decided_by="dave", decision=Decision.APPROVE, note="fine")
    )
    db_session.add(run)
    db_session.commit()
    db_session.expunge_all()  # force a real reload from the DB below

    loaded = db_session.scalars(select(Transaction)).one()
    assert loaded.amount_cents == 4217 and isinstance(loaded.amount_cents, int)
    assert loaded.status is TxStatus.PENDING_APPROVAL
    assert loaded.currency == "USD"
    assert loaded.created_at is not None
    assert loaded.agent_run.prompt_used == "buy groceries"
    assert loaded.agent_run.transactions[0].id == loaded.id
    assert loaded.approval_decisions[0].decision is Decision.APPROVE
    assert loaded.approval_decisions[0].transaction.id == loaded.id


def test_budget_rule_defaults(db_session):
    db_session.add(
        BudgetRule(rule_type=RuleType.CATEGORY_MONTHLY_CAP, category="dining", limit_cents=20000)
    )
    db_session.commit()
    db_session.expunge_all()

    rule = db_session.scalars(select(BudgetRule)).one()
    assert rule.rule_type is RuleType.CATEGORY_MONTHLY_CAP
    assert rule.period == "MONTHLY"
    assert rule.active is True
