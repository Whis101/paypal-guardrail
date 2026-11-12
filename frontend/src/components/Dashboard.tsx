import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { formatMoney } from '../format'
import type { Summary } from '../types'
import TriggerAgentRun from './TriggerAgentRun'

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(() => {
    api
      .summary()
      .then((s) => {
        setSummary(s)
        setError(null)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  useEffect(load, [load])

  const counts = summary?.counts_by_status ?? {}
  const blocked = (counts.AUTO_BLOCKED ?? 0) + (counts.DENIED_BY_HUMAN ?? 0)
  const spend = Object.entries(summary?.month_spend_by_category ?? {}).sort((a, b) => b[1] - a[1])
  const maxSpend = spend.length ? spend[0][1] : 0

  return (
    <div className="stack">
      <TriggerAgentRun onComplete={load} />

      {error && <div className="alert alert-error">Could not load summary: {error}</div>}

      <div className="tiles">
        <div className="tile tile-good">
          <div className="tile-label">Total captured</div>
          <div className="tile-value">{summary ? formatMoney(summary.total_captured_cents) : '—'}</div>
        </div>
        <div className="tile tile-warn">
          <div className="tile-label">Waiting for approval</div>
          <div className="tile-value">{summary ? (counts.PENDING_APPROVAL ?? 0) : '—'}</div>
        </div>
        <div className="tile tile-bad">
          <div className="tile-label">Blocked / denied</div>
          <div className="tile-value">{summary ? blocked : '—'}</div>
        </div>
      </div>

      <section className="card">
        <h3>Spend this month by category</h3>
        {spend.length === 0 ? (
          <p className="muted">No spend yet this month.</p>
        ) : (
          <ul className="spend-list">
            {spend.map(([cat, cents]) => (
              <li key={cat}>
                <span className="spend-cat">{cat}</span>
                <span className="spend-bar">
                  <span style={{ width: `${maxSpend ? (cents / maxSpend) * 100 : 0}%` }} />
                </span>
                <span className="spend-amt">{formatMoney(cents)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
