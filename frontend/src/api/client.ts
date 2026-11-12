import type { Decision, Health, NewRule, Rule, Summary, Transaction } from '../types'

const BASE: string = import.meta.env.VITE_API_BASE_URL ?? ''

function detailFrom(body: unknown, fallback: string): string {
  if (body && typeof body === 'object' && 'detail' in body) {
    const detail = (body as { detail: unknown }).detail
    if (typeof detail === 'string') return detail
    // FastAPI 422 validation errors: detail is a list of {loc, msg}
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join('; ')
    }
  }
  return fallback
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  })
  if (!res.ok) {
    let body: unknown = null
    try {
      body = await res.json()
    } catch {
      // non-JSON error body
    }
    throw new Error(detailFrom(body, `${res.status} ${res.statusText || 'Request failed'}`))
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  health: () => request<Health>('/api/health'),
  runAgent: (mandate: string) =>
    request<Transaction>('/api/agent/run', {
      method: 'POST',
      body: JSON.stringify(mandate.trim() ? { mandate: mandate.trim() } : {}),
    }),
  transactions: () => request<Transaction[]>('/api/transactions'),
  pendingApprovals: () => request<Transaction[]>('/api/approvals/pending'),
  decide: (id: number, decision: Decision, note?: string) =>
    request<Transaction>(`/api/approvals/${id}/decision`, {
      method: 'POST',
      body: JSON.stringify(note ? { decision, note } : { decision }),
    }),
  rules: () => request<Rule[]>('/api/rules'),
  createRule: (rule: NewRule) =>
    request<Rule>('/api/rules', { method: 'POST', body: JSON.stringify(rule) }),
  setRuleActive: (id: number, active: boolean) =>
    request<Rule>(`/api/rules/${id}`, { method: 'PATCH', body: JSON.stringify({ active }) }),
  deleteRule: (id: number) => request<void>(`/api/rules/${id}`, { method: 'DELETE' }),
  summary: () => request<Summary>('/api/summary'),
}
