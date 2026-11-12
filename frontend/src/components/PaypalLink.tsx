import { paypalActivityUrl } from '../format'

interface Props {
  orderId: string | null
  captureId: string | null
}

/** Order id, linked to the sandbox activity page once a capture exists. */
export default function PaypalLink({ orderId, captureId }: Props) {
  if (!orderId) return <span className="muted">—</span>
  const url = paypalActivityUrl(captureId)
  if (!url) return <code>{orderId}</code>
  return (
    <a href={url} target="_blank" rel="noopener noreferrer" title="Open in PayPal sandbox">
      <code>{orderId}</code> ↗
    </a>
  )
}
