# Devpost submission: Guardrail

## Tagline
Spending limits for AI shopping agents: Claude classifies every purchase, your rules
decide, and PayPal Vault charges only what's allowed.

## Inspiration
Agentic commerce is coming: AI agents that reorder groceries, book travel, renew
subscriptions. The missing piece isn't the agent. It's the **guardrail**. People want
to delegate spending without giving an LLM an unlimited wallet.

## What it does
An autonomous shopping agent (Claude Haiku 5.5) proposes a purchase in free text. A
second Claude call, constrained to a JSON schema, extracts merchant, amount and category,
treating the agent's text as untrusted. A deterministic rules engine checks it against
your budget rules (per-purchase limits, monthly category caps, blocked merchants) and:

- **approves**: a real PayPal sandbox charge via **Vault + merchant-initiated Orders v2**
  (no buyer redirect, because the buyer pre-authorized the wallet once)
- **blocks**: never reaches PayPal
- **escalates**: lands in an approval queue, where one click charges or denies it

Every decision carries a plain-English reason, and every human decision is an audit row.
The transactions view is an AG Grid with status badges, quick filter, sorting, and
links to the PayPal sandbox capture.

## How we built it
- **PayPal**: OAuth2 client credentials → Vault v3 setup token → buyer approval →
  payment token (vault id). Each approved purchase is `POST /v2/checkout/orders` with
  `payment_source.paypal.vault_id` and `stored_credential {payment_initiator: MERCHANT,
  usage: SUBSEQUENT}`. That order completes with the capture inline, and we handle the
  explicit `/capture` shape too. A unique `PayPal-Request-Id` on every POST gives idempotency.
- **AI**: Anthropic Python SDK, `claude-haiku-5-5`. Call 1 generates the proposal.
  Call 2 uses `messages.parse` with a Pydantic model (structured outputs) whose category is a
  closed enum, so the rules engine only gets validated, typed data.
- **Backend**: FastAPI, SQLAlchemy 2, SQLite. Money is integer cents end to end.
  Approvals use an atomic compare-and-set UPDATE, so a double click can't double-charge.
- **Frontend**: React + TypeScript + Vite, AG Grid Community.
- **Testing**: TDD with pytest, 66 tests. The rules engine has a table-driven suite.
  The Claude and PayPal clients are tested against injected fakes that assert the exact
  request payloads. API tests run the full flow with dependency overrides.

## Challenges
- The original sandbox app lacked the Vault scope (403s). Printing the `scope` field
  from the OAuth response diagnosed it, and a fresh app with "Save payment methods" fixed it.
- Vault setup tokens expire if they aren't approved promptly.
- Vaulted CAPTURE orders return `COMPLETED` straight from create, so a naive
  create-then-capture flow fails. The client handles both shapes.

## What's next
Per-agent budgets and API keys, time-window rules (no purchases after midnight),
anomaly detection on merchant drift, webhooks for refunds/disputes, and an MCP server
so any agent framework can call Guardrail as its payment tool.

## AI tools used
- **Claude Haiku 5.5 (Anthropic API)**, at runtime: the shopping agent's purchase proposals,
  and structured-output extraction/classification of each proposal.
- **Claude Code (Claude Opus 5.5)**, during development: pair-programming, test-first
  implementation, code review, and documentation drafting.

## Built with
python, fastapi, sqlalchemy, sqlite, anthropic, claude, paypal-rest-api, paypal-vault,
react, typescript, vite, ag-grid, pytest

---

## Demo video script (target 2:30, hard limit 3:00)

**0:00–0:20 Problem.** "AI agents can now shop for us. But would you hand one your
card with no limits? Guardrail is the spending policy layer between an AI agent and PayPal."

**0:20–0:45 Setup.** Show the Rules tab: $150 per-purchase limit, grocery and
electronics monthly caps, gift cards need approval, casino blocked. "These are my rules.
The agent can't change them."

**0:45–1:25 Auto-approve.** Dashboard → type a mandate ("restock pantry basics") →
Run. Point at: the agent's merchant/amount, Claude's category, the green **Captured**
badge, the reason, and the PayPal order id. Cut to the sandbox business **Activity** page
showing the payment. "No checkout page, no buyer redirect. It's a merchant-initiated
charge against a PayPal Vault token the buyer approved once."

**1:25–2:05 Escalate → human.** Run with a pricier mandate (e.g. "buy a new
laptop for school"). It lands as **Needs approval** with the reason ("exceeds the
$150.00 single-purchase limit"). Go to the Approvals tab → Approve → it captures. Show
Deny on another one → nothing is charged.

**2:05–2:25 Grid + how.** Transactions tab (AG Grid): filter "captured", sort by
amount. "Two Claude calls: one proposes, one is a schema-constrained classifier that
treats the agent's text as untrusted. A deterministic, unit-tested rules engine decides."

**2:25–2:35 Close.** "Guardrail: let agents spend, safely. Built with PayPal Vault,
Claude, and AG Grid."
