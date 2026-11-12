import { useCallback, useEffect, useState, type FormEvent } from 'react'
import { api } from '../api/client'
import { formatMoney, RULE_TYPE_LABELS } from '../format'
import type { NewRule, Rule, RuleType } from '../types'

const RULE_TYPES = Object.keys(RULE_TYPE_LABELS) as RuleType[]

function toCents(dollars: string): number | undefined {
  const n = parseFloat(dollars)
  return Number.isFinite(n) ? Math.round(n * 100) : undefined
}

function describe(rule: Rule): string {
  switch (rule.rule_type) {
    case 'CATEGORY_MONTHLY_CAP':
      return `${rule.category ?? '?'} capped at ${formatMoney(rule.limit_cents)} / month`
    case 'SINGLE_TRANSACTION_LIMIT':
      return `Any single purchase over ${formatMoney(rule.limit_cents)} needs approval`
    case 'BLOCKED_MERCHANT':
      return `Never buy from ${rule.merchant ?? '?'}`
    default:
      return ''
  }
}

export default function BudgetRulesEditor() {
  const [rules, setRules] = useState<Rule[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  const [ruleType, setRuleType] = useState<RuleType>('CATEGORY_MONTHLY_CAP')
  const [category, setCategory] = useState('')
  const [merchant, setMerchant] = useState('')
  const [limit, setLimit] = useState('')

  const load = useCallback(() => {
    api
      .rules()
      .then((r) => {
        setRules(r)
        setError(null)
      })
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
  }, [])

  useEffect(load, [load])

  async function act(fn: () => Promise<unknown>) {
    setError(null)
    try {
      await fn()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      load()
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault()
    setFormError(null)
    const body: NewRule = { rule_type: ruleType }
    if (ruleType === 'CATEGORY_MONTHLY_CAP') {
      body.category = category.trim()
      body.limit_cents = toCents(limit)
    } else if (ruleType === 'SINGLE_TRANSACTION_LIMIT') {
      body.limit_cents = toCents(limit)
    } else {
      body.merchant = merchant.trim()
    }
    setBusy(true)
    try {
      await api.createRule(body)
      setCategory('')
      setMerchant('')
      setLimit('')
      load()
    } catch (err) {
      setFormError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(false)
    }
  }

  const needsLimit = ruleType !== 'BLOCKED_MERCHANT'

  return (
    <div className="stack">
      <div className="toolbar">
        <h2>Budget rules</h2>
        <button className="btn" onClick={load}>
          Refresh
        </button>
      </div>
      {error && <div className="alert alert-error">{error}</div>}

      <section className="card">
        {rules === null ? (
          !error && <p className="muted">Loading…</p>
        ) : rules.length === 0 ? (
          <p className="muted">No rules yet. Every purchase will need your approval rules to decide.</p>
        ) : (
          <table className="rules-table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Rule</th>
                <th>Active</th>
                <th aria-label="Actions" />
              </tr>
            </thead>
            <tbody>
              {rules.map((r) => (
                <tr key={r.id} className={r.active ? '' : 'inactive'}>
                  <td>
                    <span className="chip">{RULE_TYPE_LABELS[r.rule_type] ?? r.rule_type}</span>
                  </td>
                  <td>{describe(r)}</td>
                  <td>
                    <label className="toggle">
                      <input
                        type="checkbox"
                        checked={r.active}
                        onChange={(e) => {
                          const active = e.target.checked
                          void act(() => api.setRuleActive(r.id, active))
                        }}
                      />
                      <span>{r.active ? 'On' : 'Off'}</span>
                    </label>
                  </td>
                  <td className="right">
                    <button
                      className="btn btn-small btn-deny"
                      onClick={() => {
                        if (window.confirm('Delete this rule?')) void act(() => api.deleteRule(r.id))
                      }}
                    >
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="card">
        <h3>Add a rule</h3>
        <form className="rule-form" onSubmit={submit}>
          <label className="field">
            <span>Rule type</span>
            <select value={ruleType} onChange={(e) => setRuleType(e.target.value as RuleType)}>
              {RULE_TYPES.map((t) => (
                <option key={t} value={t}>
                  {RULE_TYPE_LABELS[t]}
                </option>
              ))}
            </select>
          </label>
          {ruleType === 'CATEGORY_MONTHLY_CAP' && (
            <label className="field">
              <span>Category</span>
              <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. groceries" required />
            </label>
          )}
          {ruleType === 'BLOCKED_MERCHANT' && (
            <label className="field">
              <span>Merchant</span>
              <input value={merchant} onChange={(e) => setMerchant(e.target.value)} placeholder="e.g. Shady Deals Inc" required />
            </label>
          )}
          {needsLimit && (
            <label className="field">
              <span>Limit (USD)</span>
              <input
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="50.00"
                required
              />
            </label>
          )}
          <button className="btn btn-primary" type="submit" disabled={busy}>
            {busy ? 'Adding…' : 'Add rule'}
          </button>
        </form>
        {formError && <div className="alert alert-error">{formError}</div>}
      </section>
    </div>
  )
}
