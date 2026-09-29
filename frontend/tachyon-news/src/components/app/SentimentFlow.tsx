import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import type { Summary } from '@/lib/types'

type Timeline = Summary['timeline']

const bucketLabel = (t: string, unit: Timeline['unit']) =>
  unit === '5min' || unit === '15min'
    ? new Date(t).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }) + ' ET'
    : unit === 'hour'
    ? new Date(t).toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric' }) + ' ET'
    : new Date(t).toLocaleDateString('en-US', { timeZone: 'UTC', month: 'short', day: 'numeric', ...(unit === 'week' ? { year: '2-digit' } : {}) })

/** Stacked sentiment per hour, day or week — whatever the API chose for the range's length. */
export function SentimentFlow({ timeline, className = 'h-44' }: { timeline: Timeline; className?: string }) {
  const data = timeline.buckets.map((b) => ({ ...b, label: (timeline.unit === 'week' ? 'Week of ' : '') + bucketLabel(b.t, timeline.unit) }))
  const tickEvery = Math.max(0, Math.ceil(data.length / 6) - 1)
  return (
    <div className={`w-full ${className}`}>
      <ResponsiveContainer>
        <BarChart data={data} barCategoryGap={2} margin={{ top: 4, right: 0, left: 0, bottom: 0 }}>
          <XAxis dataKey="label" interval={tickEvery} tickLine={false} axisLine={false}
            tick={{ fontSize: 11, fill: 'var(--muted-foreground)' }} />
          <Tooltip cursor={{ fill: 'var(--accent)' }}
            content={({ active, payload }) => {
              if (!active || !payload?.length) return null
              const p = payload[0].payload as (typeof data)[number]
              const total = p.bullish + p.neutral + p.bearish
              return (
                <div className="rounded-lg border bg-popover px-3 py-2 text-xs shadow-lg">
                  <div className="font-medium">{p.label}</div>
                  <div className="num mt-1 space-y-0.5 text-muted-foreground">
                    <div>{total} stories</div>
                    <div><span className="text-up">{p.bullish} bullish</span> · {p.neutral} neutral · <span className="text-down">{p.bearish} bearish</span></div>
                  </div>
                </div>
              )
            }} />
          <Bar dataKey="bearish" stackId="s" fill="var(--down)" animationDuration={900} />
          <Bar dataKey="neutral" stackId="s" fill="var(--flat)" fillOpacity={0.35} animationDuration={900} />
          <Bar dataKey="bullish" stackId="s" fill="var(--up)" radius={[2, 2, 0, 0]} animationDuration={900} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
