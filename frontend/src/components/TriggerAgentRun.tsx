import { useState } from 'react'
import { api } from '../api/client'
import { formatMoney } from '../format'
import type { Transaction } from '../types'
import PaypalLink from './PaypalLink'
import StatusBadge from './StatusBadge'

interface Props {
  onComplete?: (tx: Transaction) => void
}

export default function TriggerAgentRun({ onComplete }: Props) {
  const [mandate, setMandate] = useState('')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<Transaction | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function run() {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      const tx = await api.runAgent(mandate)
      setResult(tx)
      onComplete?.(tx)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="card run-card">
      <h2>Run shopping agent</h2>
      <p className="muted">
        The agent proposes a purchase, Claude classifies it, and your budget rules decide: auto-approve (real
        PayPal sandbox charge), block, or ask you.
      </p>
      <label className="field">
        <span>Mandate (optional)</span>
        <textarea
          value={mandate}
          onChange={(e) => setMandate(e.target.value)}
          placeholder="Restock household essentials for a family of four"
          rows={3}
          disabled={running}
        />
      </label>
      <button className="btn btn-primary btn-lg" onClick={run} disabled={running}>
        {running ? (
          <>
            <span className="spinner" aria-hidden="true" /> Agent is shopping…
          </>
        ) : (
          'Run shopping agent'
        )}
      </button>
      {running && <p className="muted small">This takes 5–15 seconds (two LLM calls + PayPal).</p>}
      {error && <div className="alert alert-error">{error}</div>}
      {result && (
        <div className="result">
          <div className="result-head">
            <div>
              <div className="result-merchant">{result.merchant_raw}</div>
              {result.item_description && <div className="muted">{result.item_description}</div>}
            </div>
            <div className="result-amount">{formatMoney(result.amount_cents, result.currency)}</div>
          </div>
          <dl className="result-grid">
            <dt>Status</dt>
            <dd>
              <StatusBadge status={result.status} />
            </dd>
            <dt>Category</dt>
            <dd>{result.category ?? '—'}</dd>
            <dt>Why</dt>
            <dd>{result.decision_reason ?? '—'}</dd>
            <dt>PayPal order</dt>
            <dd>
              <PaypalLink orderId={result.paypal_order_id} captureId={result.paypal_capture_id} />
            </dd>
          </dl>
        </div>
      )}
    </section>
  )
}
