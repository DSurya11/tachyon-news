import { useId } from 'react'
import { Area, AreaChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { fmtDay } from '@/lib/format'
import type { Span } from '@/lib/types'
import { Money } from './Money'

/** A bar's time: clock time for intraday spans, the exchange's date (with the year on long spans) otherwise. */
function when(d: string, intraday: boolean, span?: Span) {
  if (intraday) return new Date(d).toLocaleString(undefined, { weekday: span === '5d' ? 'short' : undefined, hour: 'numeric', minute: '2-digit' })
  const long = span === '1y' || span === '5y'
  return fmtDay(d.slice(0, 10), long ? { month: 'short', day: 'numeric', year: 'numeric' } : { month: 'short', day: 'numeric' })
}

export function PriceChart({ dates, closes, currency, unit, intraday = false, base, span }: {
  dates: string[]; closes: number[]; currency?: string | null; unit?: string | null
  intraday?: boolean; base?: number | null; span?: Span
}) {
  // Unique per chart: two charts side by side in the inspector must not share a gradient.
  const fillId = `pc-fill-${useId().replace(/:/g, '')}`
  if (closes.length < 2) {
    return <div className="grid h-56 place-items-center rounded-lg border border-dashed text-sm text-muted-foreground">No price history for this span</div>
  }
  const data = closes.map((c, i) => ({ d: dates[i], c }))
  const from = base ?? closes[0]
  const up = closes[closes.length - 1] >= from
  const color = up ? 'var(--up)' : 'var(--down)'
  // 1D is measured from the previous close: draw it, and keep it in view.
  const prevClose = span === '1d' && base ? base : null
  const lo = Math.min(...closes, prevClose ?? Infinity), hi = Math.max(...closes, prevClose ?? -Infinity), pad = (hi - lo) * 0.12 || 1
  return (
    // The line and fill sweep in left to right (.chart-reveal in index.css): a clip animation the
    // browser runs by itself, timed to start once the panel has opened. Recharts' own drawing ran
    // on the busy main thread while the panel animated, so it stalled and the chart popped in whole.
    <div className="chart-reveal h-56 w-full" key={`${span}-${dates[0]}-${closes.length}`}>
      <ResponsiveContainer>
        <AreaChart data={data} margin={{ top: 8, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={fillId} x1="0" x2="0" y1="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.22} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="d" hide />
          <YAxis domain={[lo - pad, hi + pad]} hide />
          {prevClose != null && <ReferenceLine y={prevClose} stroke="var(--muted-foreground)" strokeDasharray="3 4" strokeOpacity={0.6} ifOverflow="extendDomain" />}
          <Tooltip
            cursor={{ stroke: 'var(--muted-foreground)', strokeWidth: 1, strokeDasharray: '3 3' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as { d: string; c: number }
              const chg = ((p.c - from) / from) * 100
              return (
                <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
                  <Money value={p.c} currency={currency} unit={unit} className="num block text-sm font-medium" />
                  <div className="num text-muted-foreground">
                    <span className={chg >= 0 ? 'text-up' : 'text-down'}>{chg >= 0 ? '+' : ''}{chg.toFixed(2)}%</span> · {when(p.d, intraday, span)}
                  </div>
                </div>
              )
            }} />
          <Area type="monotone" dataKey="c" stroke={color} strokeWidth={1.75} fill={`url(#${fillId})`}
            isAnimationActive={false} activeDot={{ r: 3.5, strokeWidth: 0, fill: color }} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
