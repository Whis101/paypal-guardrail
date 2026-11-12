import { statusMeta } from '../format'

export default function StatusBadge({ status }: { status: string }) {
  const { label, tone } = statusMeta(status)
  return (
    <span className={`badge badge-${tone}`} title={status}>
      {label}
    </span>
  )
}
