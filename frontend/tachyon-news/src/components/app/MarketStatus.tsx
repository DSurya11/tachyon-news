import { useEffect, useState } from 'react'
import { useMarket } from '@/hooks/use-market'
import { exchangeClock, exchangesFor, marketStatus, type MarketState } from '@/lib/market'
import { cn } from '@/lib/utils'

function Dot({ m }: { m: MarketState }) {
  return (
    <span className={cn('live-dot size-1.5 shrink-0 rounded-full',
      m.state === 'open' && 'bg-up text-up', (m.state === 'pre' || m.state === 'post') && 'bg-signal text-signal',
      m.state === 'closed' && 'bg-muted-foreground text-muted-foreground [animation:none]')} />
  )
}

/**
 * Session status for the exchanges in view: NSE for India, NYSE for International,
 * both for All markets — each with its own hours and time zone.
 */
export function MarketStatus() {
  const { market } = useMarket()
  const [now, setNow] = useState(() => new Date())
  useEffect(() => { const t = setInterval(() => setNow(new Date()), 1000); return () => clearInterval(t) }, [])
  const states = exchangesFor(market).map((x) => marketStatus(x, now))

  if (states.length === 1) {
    const m = states[0]
    return (
      <div className="flex items-center gap-3 text-[12.5px]" title={`${m.exchange} · ${m.detail}`}>
        <span className="flex items-center gap-2">
          <Dot m={m} />
          <span className="hidden font-medium sm:inline">{m.exchange} {m.label.toLowerCase()}</span>
          <span className="hidden text-muted-foreground xl:inline">{m.detail}</span>
        </span>
        <span className="num hidden text-muted-foreground lg:inline">{exchangeClock(m.exchange, now)}</span>
      </div>
    )
  }
  return (
    <div className="flex items-center gap-2.5 text-[12.5px] sm:gap-3">
      {states.map((m) => (
        <span key={m.exchange} className="flex items-center gap-1.5" title={`${m.exchange} ${m.label.toLowerCase()} · ${m.detail} · ${exchangeClock(m.exchange, now)}`}>
          <Dot m={m} />
          <span className="font-medium">{m.exchange}</span>
          <span className="hidden text-muted-foreground sm:inline">{m.label.toLowerCase()}</span>
        </span>
      ))}
    </div>
  )
}
