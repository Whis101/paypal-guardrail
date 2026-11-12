# Guardrail: spending limits for AI shopping agents

AI agents are starting to buy things on our behalf. Nobody wants to hand one an
unlimited wallet. **Guardrail** sits between an autonomous shopping agent and
PayPal. Every purchase the agent proposes is classified by Claude, checked against
budget rules you set, and then:

- **auto-approved**: charged immediately through a real **PayPal Vault merchant-initiated
  payment**, with no buyer redirect and no human in the loop
- **auto-blocked**: never reaches PayPal (blocked merchants, invalid amounts)
- **escalated**: parked in an approval queue. One click from you charges it, or denies it.

```
 Claude Haiku 5.5            Claude Haiku 5.5              pure Python             PayPal sandbox
┌──────────────┐  free text ┌──────────────────┐  typed  ┌──────────────┐ approve ┌───────────────────┐
│ Shopping     │──────────▶│ Classifier        │───────▶│ Rules engine │───────▶│ Orders v2 + Vault │
│ agent        │            │ (structured JSON) │        │              │        │ MERCHANT-initiated│
└──────────────┘            └──────────────────┘        └──────┬───────┘        └───────────────────┘
                                                               │ needs human / block
                                                               ▼
                                                     Approval queue (React UI) ──approve──▶ PayPal
```

## Why it's built this way

- **The agent is never trusted about its own purchase.** A second, schema-constrained
  Claude call (structured outputs) extracts merchant, amount in integer cents and
  category from the agent's free text. It treats that text as untrusted data. The
  rules engine only ever sees validated, typed fields.
- **Decisions are deterministic and explainable.** The rules engine is a pure
  function with a table of unit tests. An LLM proposes; code decides. Every decision
  stores a human-readable reason.
- **Real money movement for autonomous agents.** A one-time PayPal Vault approval
  stores the buyer's consent as a payment token. After that, each approved purchase is
  an Orders v2 call with `stored_credential.payment_initiator = MERCHANT`: the
  standard pattern for charges made while the buyer isn't present.
- **Safe by construction.** Money is stored as integer cents (never floats). Each
  PayPal POST carries a unique `PayPal-Request-Id` idempotency key. Approvals use an
  atomic compare-and-set, so a double click can't charge twice. The decision is
  committed *before* any money moves.

## Tech

FastAPI · SQLAlchemy 2 + SQLite · Anthropic Python SDK (Claude Haiku 5.5, structured outputs) ·
PayPal REST (OAuth2 client credentials, Vault v3, Orders v2) · React + TypeScript + Vite ·
AG Grid (transactions table) · pytest + Ruff

## Run it locally

Prerequisites: Python 3.12+, Node 20+, a PayPal developer account, an Anthropic API key.

### 1. Configure

```bash
cp .env.example .env    # then fill in the values (repo root)
```

- `PAYPAL_CLIENT_ID` / `PAYPAL_CLIENT_SECRET`: a **sandbox** REST app at
  developer.paypal.com → Apps & Credentials, with **Vault / "Save payment methods"**
  enabled. (If vault calls return 403, create a fresh app with that option ticked.)
- `ANTHROPIC_API_KEY`: from console.anthropic.com.
- `PAYPAL_VAULT_ID`: produced in step 3.

### 2. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                       # 66 tests, no network needed
uvicorn app.main:app --reload   # http://localhost:8000/docs
```

### 3. One-time PayPal Vault approval (the "buyer grants the agent a wallet" step)

```bash
cd backend
python scripts/vault_poc.py create-setup-token
#  -> open the printed approve link (incognito), log in as your sandbox PERSONAL account, approve
python scripts/vault_poc.py create-payment-token <setup_token_id>
#  -> copy the printed vault id into .env as PAYPAL_VAULT_ID, restart uvicorn
```

Setup tokens expire quickly if they aren't approved. If you get a 404, just create a new one.

### 4. Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:5173 (proxies /api to :8000)
```

Click **Run shopping agent**. Default rules are seeded on first start: a $150
single-purchase limit, monthly caps on groceries and electronics, gift cards always
need approval, and "casino" merchants are blocked. Edit them in the **Rules** tab. Captured
payments show up in your sandbox business account under Activity.

## API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/agent/run` | Agent proposes → classify → decide → maybe charge |
| GET | `/api/transactions` | All transactions, newest first |
| GET | `/api/approvals/pending` | The human-approval queue |
| POST | `/api/approvals/{id}/decision` | `APPROVE` (charges via PayPal) or `DENY` |
| GET/POST/PATCH/DELETE | `/api/rules[/{id}]` | Budget rules |
| GET | `/api/summary` | Month spend by category, counts, captured total |
| GET | `/api/health` | DB / Vault / LLM configuration status |

## Project layout

```
backend/app/
  rules_engine.py   pure decision function (the guardrail core)
  llm.py            Claude agent + structured-output classifier
  paypal_client.py  OAuth2 + vaulted merchant-initiated charge
  services.py       workflows: run agent, human decision, month spend
  routers/api.py    thin HTTP layer
frontend/src/       React UI, AG Grid transactions table
```

## License

MIT, see [LICENSE](LICENSE).
