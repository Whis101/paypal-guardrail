import { useEffect, useState } from 'react'
import { api } from './api/client'
import type { Health } from './types'
import Dashboard from './components/Dashboard'
import PendingApprovals from './components/PendingApprovals'
import BudgetRulesEditor from './components/BudgetRulesEditor'
import TransactionsTable from './components/TransactionsTable'
import './App.css'

const TABS = ['Dashboard', 'Approvals', 'Rules', 'Transactions'] as const
type Tab = (typeof TABS)[number]

function HealthBadges() {
  const [health, setHealth] = useState<Health | null>(null)
  const [down, setDown] = useState(false)

  useEffect(() => {
    api
      .health()
      .then(setHealth)
      .catch(() => setDown(true))
  }, [])

  if (down) return <span className="hbadge hbadge-bad">Backend offline</span>
  if (!health) return <span className="hbadge">Checking…</span>
  return (
    <>
      <span className={`hbadge ${health.vault_configured ? 'hbadge-good' : 'hbadge-bad'}`}>
        {health.vault_configured ? 'Vault connected' : 'Vault not configured'}
      </span>
      <span className={`hbadge ${health.llm_configured ? 'hbadge-good' : 'hbadge-bad'}`}>
        {health.llm_configured ? 'LLM configured' : 'LLM not configured'}
      </span>
    </>
  )
}

export default function App() {
  const [tab, setTab] = useState<Tab>('Dashboard')

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="logo" aria-hidden="true">
            ◆
          </span>
          <div>
            <h1>Guardrail</h1>
            <p className="tagline">Spending limits for AI shopping agents</p>
          </div>
        </div>
        <div className="health">
          <HealthBadges />
        </div>
      </header>

      <nav className="tabs" role="tablist">
        {TABS.map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`tab ${tab === t ? 'tab-active' : ''}`}
            onClick={() => setTab(t)}
          >
            {t}
          </button>
        ))}
      </nav>

      {/* Each tab remounts on selection, so it always refetches fresh data. */}
      <main className="main">
        {tab === 'Dashboard' && <Dashboard />}
        {tab === 'Approvals' && <PendingApprovals />}
        {tab === 'Rules' && <BudgetRulesEditor />}
        {tab === 'Transactions' && <TransactionsTable />}
      </main>
    </div>
  )
}
