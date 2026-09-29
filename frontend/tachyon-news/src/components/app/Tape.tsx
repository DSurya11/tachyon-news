import { Marquee } from '@/components/ui/marquee'
import { useQuotes } from '@/hooks/queries'
import { useInspector } from '@/hooks/use-inspector'
import { config } from '@/lib/config'
import { fmtPct, tone } from '@/lib/format'
import { cn } from '@/lib/utils'
import { Money } from './Money'

export function Tape() {
  const { data } = useQuotes(config.tape)
  const { openTicker } = useInspector()
  const quotes = config.tape.map((s) => data?.get(s)).filter((q): q is NonNullable<typeof q> => Boolean(q))
  if (!quotes.length) return <div className="h-9 border-b" />
  return (
    <div className="relative border-b bg-surface/60">
      <Marquee pauseOnHover repeat={3} className="py-0 [--duration:70s] [--gap:0rem]">
        {quotes.map((q) => (
          <button key={q.symbol} type="button" onClick={() => openTicker(q.symbol)}
            className="num flex h-9 items-center gap-2.5 border-r px-5 text-[12.5px] hover-row">
            <span className="font-medium"><span className="hover-title">{q.symbol}</span></span>
            <Money value={q.price} currency={q.currency} unit={q.unit} className="text-muted-foreground" />
            <span className={cn(tone(q.pct_change))}>{fmtPct(q.pct_change)}</span>
          </button>
        ))}
      </Marquee>
      <div className="pointer-events-none absolute inset-y-0 left-0 w-16 bg-gradient-to-r from-background to-transparent" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-16 bg-gradient-to-l from-background to-transparent" />
    </div>
  )
}
