import { useReaction } from '@/hooks/queries'
import { displaySymbol, fmtPct, tone } from '@/lib/format'
import type { PricedVerdict, ReactionHistory, TickerReaction } from '@/lib/types'
import { cn } from '@/lib/utils'

const BENCH_NAME = { SPX: 'S&P 500', NIFTY: 'Nifty 50' } as const
const SESSION = { pre: ' (pre-market)', post: ' (after hours)', regular: '' } as const

// History, not advice: each label says how the move compares with what similar stories saw.
const VERDICT: Record<PricedVerdict, string> = {
  mostly: 'Most of the usual move has happened',
  partly: 'Part of the usual move has happened',
  little: 'Little of the usual move so far',
  against: 'Moving against what similar stories saw',
  usually_small: 'Similar stories barely moved stocks',
}

// Large studies of US news: hard-number news keeps drifting, story-driven news tends to reverse.
const PRIOR: Record<string, string> = {
  earnings: 'Across large studies of US news, hard-number stories like earnings tend to keep drifting for weeks after the first day.',
  product: 'Across large studies of US news, story-driven news like launches tends to give back part of its first-day move.',
  personnel: 'Across large studies of US news, story-driven news like leadership changes tends to give back part of its first-day move.',
  other: 'Across large studies of US news, most of the first-day move fades over the following weeks.',
}

function TickerLine({ t }: { t: TickerReaction }) {
  const bench = t.benchmark ? BENCH_NAME[t.benchmark] : null
  return (
    <div className="space-y-1.5 px-3 py-2.5">
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-[13px]">
        <span className="num font-medium">{displaySymbol(t.symbol)}</span>
        {t.move_pct != null && (
          <>
            <span><span className={cn('num font-medium', tone(t.move_pct))}>{fmtPct(t.move_pct)}</span> <span className="text-muted-foreground">since the headline{SESSION[t.session ?? 'regular']}</span></span>
            {t.excess_pct != null && bench && (
              <span className="text-muted-foreground">
                <span className={cn('num', tone(t.excess_pct))}>{fmtPct(t.excess_pct)}</span> beyond the {bench} ({fmtPct(t.bench_move_pct)})
              </span>
            )}
          </>
        )}
      </div>
      {t.verdict && <div className="text-[12px] font-medium text-foreground/80">{VERDICT[t.verdict]}</div>}
    </div>
  )
}

function History({ h }: { h: ReactionHistory }) {
  const group = `${h.event_type}${h.sentiment ? ` · ${h.sentiment}` : ''}`
  if (!h.horizon) {
    const p = h.progress['1d']
    return (
      <div className="space-y-2 text-[12.5px] leading-relaxed text-muted-foreground">
        <p>
          <span className="font-medium text-foreground/80">Building history</span> for {group} stories: {p.n} with a next-day outcome so far,
          from {p.days} trading {p.days === 1 ? 'day' : 'days'}. What similar stories saw appears at {h.needed} from at least {h.needed_days} different days.
        </p>
        {PRIOR[h.event_type] && <p>{PRIOR[h.event_type]}</p>}
      </div>
    )
  }
  const by = h.horizon === '5d' ? 'five sessions later' : 'the next session'
  return (
    <div className="space-y-1.5 text-[12.5px] leading-relaxed text-muted-foreground">
      <p>
        <span className="font-medium text-foreground/80">Similar stories</span> ({group}, {h.n}): by {by} the stock was{' '}
        <span className="num text-foreground">{fmtPct(h.p25)}</span> to <span className="num text-foreground">{fmtPct(h.p75)}</span> beyond the market,
        median <span className={cn('num', tone(h.median))}>{fmtPct(h.median)}</span> (<span className="num">{fmtPct(h.day0_median)}</span> on the first day).
      </p>
      {h.kept_going != null && (
        <p>The first-day move kept going in <span className="num text-foreground">{h.kept_going}%</span> of them and faded in <span className="num text-foreground">{100 - h.kept_going}%</span>.</p>
      )}
    </div>
  )
}

/** "Already moved X% since this headline; news like this usually fades or keeps going." */
export function PricedIn({ id }: { id: number }) {
  const { data } = useReaction(id)
  if (!data || !data.tickers.length) return null
  // Only tickers that have traded since the headline: the rest have nothing to say yet.
  const moved = data.tickers.filter((t) => t.traded && t.move_pct != null)
  return (
    <div className="space-y-3">
      {moved.length > 0 && <div className="divide-y rounded-lg border">{moved.map((t) => <TickerLine key={t.symbol} t={t} />)}</div>}
      {data.history && <History h={data.history} />}
      <p className="text-[11px] text-muted-foreground/80">
        {data.approximate ? 'This story has only a date, so it counts from the previous close. ' : ''}
        History, not a forecast. Not investment advice.
      </p>
    </div>
  )
}
