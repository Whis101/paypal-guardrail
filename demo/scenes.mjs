// Narration script for the demo video. One entry per scene; `text` is what you say
// (and what appears as captions). Edit wording here, then re-run record + build.
export const SCENES = [
  {
    id: 'intro',
    text: "AI agents can now shop for us. But would you hand one your card with no limits? Guardrail is the spending policy layer between an AI shopping agent and PayPal.",
  },
  {
    id: 'rules',
    text: "First, I set the rules. A one hundred fifty dollar limit per purchase, monthly caps on groceries and electronics, gift cards always need my approval, and casinos are blocked. The agent can't change any of this.",
  },
  {
    id: 'run-small',
    text: "Now I let the agent shop. Claude proposes a purchase in plain language. A second Claude call, locked to a strict JSON schema, extracts the merchant, amount and category, and treats the agent's words as untrusted.",
  },
  {
    id: 'result-small',
    text: "It's within my rules, so Guardrail charges it right away through PayPal. No checkout page, no redirect. It's a merchant initiated payment against a PayPal Vault token I approved once.",
  },
  {
    id: 'run-big',
    text: "Now something bigger: a laptop for school. This breaks my rules, so nothing is charged. It goes to my approval queue, with a plain English reason.",
  },
  {
    id: 'approve',
    text: "In the approval queue, one click from me approves it, and PayPal captures the payment. A repeated click can never charge twice.",
  },
  {
    id: 'grid',
    text: "Every decision lands in an AG Grid audit trail that I can search, sort and filter, with links straight to the PayPal transaction.",
  },
  {
    id: 'outro',
    text: "Under the hood: FastAPI, Claude Haiku, a deterministic rules engine with sixty seven tests, and PayPal Vault with Orders v2. Guardrail. Let agents spend, safely.",
  },
];

// Speaking pace. Normal conversational speech is ~150 words/min; default is slower.
export const WPM = Number(process.env.WPM || 120);
export const COUNTDOWN_SECONDS = 5;

export const words = (t) => t.trim().split(/\s+/).length;
export const speechSeconds = (t) => (words(t) * 60) / WPM;
