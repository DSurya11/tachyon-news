import { fmtAmount } from '@/lib/format'
import { cn } from '@/lib/utils'

/**
 * A price with its currency code after the number ("1,19,760.00 INR", "83,238.41 USD").
 * `currency` null means the value isn't money (index points) — then `unit` ("pts") is shown.
 */
export function Money({ value, currency, unit, signed, precisionOf, className }: {
  value: number | null | undefined
  currency?: string | null
  unit?: string | null
  signed?: boolean
  /** Take the decimal places from this number (a change uses its price's precision). */
  precisionOf?: number
  className?: string
}) {
  if (value == null || Number.isNaN(value)) return <span className={className}>—</span>
  const label = currency ?? unit ?? null
  return (
    <span className={cn('whitespace-nowrap', className)}>
      {signed && value > 0 ? '+' : ''}{fmtAmount(value, currency, precisionOf)}
      {label && <span className="ml-1 text-[0.78em] font-normal tracking-normal text-muted-foreground">{label}</span>}
    </span>
  )
}
