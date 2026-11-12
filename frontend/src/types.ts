export type TransactionStatus =
  | 'PENDING_APPROVAL'
  | 'AUTO_APPROVED'
  | 'AUTO_BLOCKED'
  | 'APPROVED_BY_HUMAN'
  | 'DENIED_BY_HUMAN'
  | 'CAPTURED'
  | 'CAPTURE_FAILED'

export interface Transaction {
  id: number
  created_at: string
  merchant_raw: string
  amount_cents: number
  currency: string
  category: string | null
  item_description: string | null
  status: TransactionStatus
  decision_reason: string | null
  paypal_order_id: string | null
  paypal_capture_id: string | null
  paypal_status: string | null
  agent_run_id: number | null
}

export type RuleType = 'CATEGORY_MONTHLY_CAP' | 'SINGLE_TRANSACTION_LIMIT' | 'BLOCKED_MERCHANT'

export interface Rule {
  id: number
  rule_type: RuleType
  category: string | null
  merchant: string | null
  limit_cents: number | null
  active: boolean
  created_at: string
}

export interface NewRule {
  rule_type: RuleType
  category?: string
  merchant?: string
  limit_cents?: number
}

export interface Health {
  status: string
  db: string
  vault_configured: boolean
  llm_configured: boolean
}

export interface Summary {
  month_spend_by_category: Record<string, number>
  counts_by_status: Record<string, number>
  total_captured_cents: number
}

export type Decision = 'APPROVE' | 'DENY'
