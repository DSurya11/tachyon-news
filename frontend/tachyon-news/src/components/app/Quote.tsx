import { useInView } from 'motion/react'
import { useEffect, useRef, useState } from 'react'
import { useQuote } from '@/hooks/use-quote'
import { fmtPct, tone } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Money } from './Money'

/** Washes green/red briefly when the value changes between refreshes. */
function useTick(value?: number) {
  const prev = useRef<number | undefined>(undefined)
  const [cls, setCls] = useState('')
  useEffect(() => {
    if (value != null && prev.current != null && value !== prev.current) {
      setCls(value > prev.current ? 'tick-up' : 'tick-down')
      const t = setTimeout(() => setCls(''), 1200)
      prev.current = value
      return () => clearTimeout(t)
    }
    prev.current = value
  }, [value])
  return cls
}

/** Where a quote's number comes from, for tooltips: live/close, and any currency conversion. */
// eslint-disable-next-line react-refresh/only-export-components
export function quoteNote(q: import('@/lib/types').Quote) {
  const src = q.stale ? `Last close${q.as_of ? ` · ${q.as_of}` : ''}` : 'Live'
  if (q.fx_rate && q.native_currency && q.currency) {
    // Quote the rate the readable way round: 1 USD = 95.97 INR, not 1 INR = 0.0104 USD.
    const pair = q.fx_rate >= 1 ? `1 ${q.native_currency} = ${q.fx_rate.toFixed(2)} ${q.currency}` : `1 ${q.currency} = ${(1 / q.fx_rate).toFixed(2)} ${q.native_currency}`
    return `${src} · converted from ${q.native_currency} at ${pair}${q.fx_as_of ? ` (${q.fx_as_of} rate)` : ''}`
  }
  if (q.fx_unavailable) return `${src} · shown in ${q.currency}: no exchange rate available`
  if (q.unit === 'pts') return `${src} · index points (not a currency)`
  return src
}

/** Price + % change, fetched lazily when scrolled into view. */
export function QuoteText({ symbol, showPrice = true, className }: { symbol: string; showPrice?: boolean; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '200px' })
  const { data: q, isLoading } = useQuote(symbol, inView)
  const tick = useTick(q?.price)
  return (
    <span ref={ref} className={cn('num inline-flex items-baseline gap-2 whitespace-nowrap', className)}
      title={q ? quoteNote(q) : undefined}>
      {isLoading || !inView ? <span className="h-3 w-14 animate-pulse rounded bg-muted" /> : q ? (
        <>
          {showPrice && <Money value={q.price} currency={q.currency} unit={q.unit} className={cn('px-0.5', tick)} />}
          <span className={tone(q.pct_change)}>{fmtPct(q.pct_change)}</span>
        </>
      ) : <span className="text-muted-foreground">—</span>}
    </span>
  )
}
