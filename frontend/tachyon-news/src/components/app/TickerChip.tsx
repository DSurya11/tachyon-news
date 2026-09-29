import { memo, useRef } from 'react'
import { useInspectorActions } from '@/hooks/use-inspector'
import { useQuote } from '@/hooks/use-quote'
import { useSeenOnce } from '@/hooks/use-seen'
import { displaySymbol, fmtAmount, fmtPct, tone } from '@/lib/format'
import { cn } from '@/lib/utils'

/** Ticker with its day move; the quote is fetched only once the chip scrolls near the viewport. */
export const TickerChip = memo(function TickerChip({ symbol, className }: { symbol: string; className?: string }) {
  const ref = useRef<HTMLButtonElement>(null)
  const seen = useSeenOnce(ref)
  const { data: q, isFetched } = useQuote(symbol, seen)
  const { openTicker } = useInspectorActions()
  return (
    <button ref={ref} type="button"
      onClick={(e) => { e.stopPropagation(); openTicker(symbol) }}
      className={cn('num inline-flex h-6 items-center gap-1.5 rounded-md border bg-surface px-1.5 text-[11.5px] font-medium',
        'transition-[border-color,transform] duration-200 hover:-translate-y-px hover:border-foreground/40', className)}
      title={q ? `${symbol} ${fmtAmount(q.price, q.currency)} ${q.currency ?? q.unit ?? ''}`.trim() : symbol}>
      <span>{displaySymbol(symbol)}</span>
      {/* The move's width is reserved until the quote arrives, so the chip — and the row it wraps
          in — never grows while the page is being scrolled (that made the page jump back). */}
      {q ? <span className={cn('text-[11px]', tone(q.pct_change))}>{fmtPct(q.pct_change)}</span>
        : !isFetched && <span aria-hidden className="invisible text-[11px]">+0.00%</span>}
    </button>
  )
})
