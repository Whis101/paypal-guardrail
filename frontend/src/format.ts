import type { RuleType, TransactionStatus } from './types'

export function formatMoney(cents: number | null | undefined, currency = 'USD'): string {
  if (cents == null) return '—'
  return (cents / 100).toLocaleString('en-US', { style: 'currency', currency })
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

export type StatusTone = 'good' | 'warn' | 'bad'

export const STATUS_META: Record<TransactionStatus, { label: string; tone: StatusTone }> = {
  CAPTURED: { label: 'Captured', tone: 'good' },
  AUTO_APPROVED: { label: 'Auto-approved', tone: 'good' },
  APPROVED_BY_HUMAN: { label: 'Approved', tone: 'good' },
  PENDING_APPROVAL: { label: 'Needs approval', tone: 'warn' },
  AUTO_BLOCKED: { label: 'Blocked', tone: 'bad' },
  DENIED_BY_HUMAN: { label: 'Denied', tone: 'bad' },
  CAPTURE_FAILED: { label: 'Charge failed', tone: 'bad' },
}

export function statusMeta(status: string): { label: string; tone: StatusTone } {
  return STATUS_META[status as TransactionStatus] ?? { label: status, tone: 'warn' }
}

export const RULE_TYPE_LABELS: Record<RuleType, string> = {
  CATEGORY_MONTHLY_CAP: 'Category monthly cap',
  SINGLE_TRANSACTION_LIMIT: 'Single purchase limit',
  BLOCKED_MERCHANT: 'Blocked merchant',
}

export function paypalActivityUrl(captureId: string | null | undefined): string | null {
  return captureId ? `https://www.sandbox.paypal.com/activity/payment/${encodeURIComponent(captureId)}` : null
}
