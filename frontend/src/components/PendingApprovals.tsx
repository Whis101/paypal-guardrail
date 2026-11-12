import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { formatDate, formatMoney } from '../format'
import type { Decision, Transaction } from '../types'
import PaypalLink from './PaypalLink'
import StatusBadge from './StatusBadge'

export default function PendingApprovals() {
  const [pending, setPending] = useState<Transaction[] | null>(null)
  const [busyId, setBusyId] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [decided, setDecided] = useState<Transaction[]>([])

  const load = useCallback(() => {
    api
      .pendingApprovals()
      .then(setPending)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  useEffect(load, [load])

  async function decide(tx: Transaction, decision: Decision) {
    setBusyId(tx.id)
    setError(null)
    try {
      const updated = await api.decide(tx.id, decision)
      setDecided((d) => [updated, ...d])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setBusyId(null)
      load()
    }
  }

  return (
    <div className="stack">
      <div className="toolbar">
        <h2>Approvals</h2>
        <button className="btn" onClick={load}>
          Refresh
        </button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      {decided.length > 0 && (
        <section className="card">
          <h3>Just decided</h3>
          <ul className="decided-list">
            {decided.map((t) => (
              <li key={t.id}>
                <strong>{t.merchant_raw}</strong>
                <span>{formatMoney(t.amount_cents, t.currency)}</span>
                <StatusBadge status={t.status} />
                <PaypalLink orderId={t.paypal_order_id} captureId={t.paypal_capture_id} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {pending === null ? (
        !error && <p className="muted">Loading…</p>
      ) : pending.length === 0 ? (
        <div className="empty">No purchases waiting for you.</div>
      ) : (
        <div className="approval-grid">
          {pending.map((tx) => {
            const busy = busyId === tx.id
            return (
              <article key={tx.id} className="card approval-card">
                <div className="result-head">
                  <div>
                    <div className="result-merchant">{tx.merchant_raw}</div>
                    {tx.item_description && <div className="muted">{tx.item_description}</div>}
                  </div>
                  <div className="result-amount">{formatMoney(tx.amount_cents, tx.currency)}</div>
                </div>
                <div className="meta">
                  <span className="chip">{tx.category ?? 'uncategorized'}</span>
                  <span className="muted small">{formatDate(tx.created_at)}</span>
                </div>
                {tx.decision_reason && <p className="reason">{tx.decision_reason}</p>}
                <div className="actions">
                  <button
                    className="btn btn-approve"
                    disabled={busyId !== null}
                    onClick={() => decide(tx, 'APPROVE')}
                  >
                    {busy && <span className="spinner" aria-hidden="true" />} Approve &amp; charge
                  </button>
                  <button className="btn btn-deny" disabled={busyId !== null} onClick={() => decide(tx, 'DENY')}>
                    Deny
                  </button>
                </div>
              </article>
            )
          })}
        </div>
      )}
    </div>
  )
}
