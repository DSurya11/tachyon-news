import { Search } from 'lucide-react'
import { useState } from 'react'
import { BlurFade } from '@/components/ui/blur-fade'
import { Input } from '@/components/ui/input'
import { MagicCard } from '@/components/ui/magic-card'
import { Empty } from '@/components/app/Empty'
import { PageHeader } from '@/components/app/PageHeader'
import { QuoteText } from '@/components/app/Quote'
import { SplitBar } from '@/components/app/Sentiment'
import { Star } from '@/components/app/Star'
import { TickerSpark } from '@/components/app/TickerSpark'
import { useSummary } from '@/hooks/queries'
import { rangePhrase, rangeShort, useRange } from '@/hooks/use-range'
import { useInspector } from '@/hooks/use-inspector'
import { useWatchlist } from '@/hooks/use-watchlist'
import { ago } from '@/lib/format'
import type { TickerSummary } from '@/lib/types'

/** Tickers in the news that aren't on the watchlist yet, each with a star to add it. */
function AddTickers({ tickers, watched, phrase }: { tickers: TickerSummary[]; watched: string[]; phrase: string }) {
  const [q, setQ] = useState('')
  const query = q.trim().toUpperCase()
  const candidates = tickers.filter((t) => !watched.includes(t.symbol) && (!query || t.symbol.includes(query)))
  const shown = candidates.slice(0, query ? 24 : 12)
  return (
    <div className="space-y-3">
      <div className="relative max-w-xs">
        <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" strokeWidth={1.75} />
        <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Find a ticker in the news" aria-label="Find a ticker" className="pl-9" />
      </div>
      {shown.length ? (
        <div className="flex flex-wrap gap-2">
          {shown.map((t) => (
            <span key={t.symbol} className="flex items-center gap-1 rounded-lg border bg-card py-0.5 pr-0.5 pl-3 text-[13px]">
              <span className="num font-medium">{t.symbol}</span><span className="num text-xs text-muted-foreground">{t.count}</span><Star symbol={t.symbol} />
            </span>
          ))}
        </div>
      ) : (
        <p className="text-[13px] text-muted-foreground">{query ? `No ticker matching "${query}" ${phrase}.` : 'You follow every ticker in the news.'}</p>
      )}
    </div>
  )
}

export default function Watchlist() {
  const { list } = useWatchlist()
  const { range } = useRange()
  const { data: summary } = useSummary({ symbols: list, top: 200 })
  const { openTicker } = useInspector()
  const tickers = summary?.tickers ?? []
  const stats = new Map(tickers.map((t) => [t.symbol, t]))

  return (
    <div>
      <PageHeader kicker={list.length ? `${list.length} ${list.length === 1 ? 'ticker' : 'tickers'}` : 'Your tickers'} title="Watchlist">
        Price, 30-day trend and what the wire is saying — for the names you care about. Saved in this browser.
      </PageHeader>

      {!list.length ? (
        <Empty title="Nothing here yet" action={<div className="mx-auto max-w-2xl text-left"><AddTickers tickers={tickers} watched={list} phrase={rangePhrase(range)} /></div>}>
          Star any ticker to follow it. These are the most discussed right now:
        </Empty>
      ) : (<>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {list.map((sym, i) => {
            const t = stats.get(sym)
            return (
              <BlurFade key={sym} delay={0.04 * i} inView>
                <div role="button" tabIndex={0} onClick={() => openTicker(sym)} onKeyDown={(e) => e.key === 'Enter' && openTicker(sym)} className="cursor-pointer rounded-xl">
                  <MagicCard className="rounded-xl" gradientSize={220} gradientOpacity={0}
                    gradientFrom="var(--foreground)" gradientTo="var(--muted-foreground)">
                    <div className="space-y-4 p-5">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="num text-xl font-semibold tracking-tight">{sym}</div>
                          <QuoteText symbol={sym} className="mt-1 text-[13px]" />
                        </div>
                        <Star symbol={sym} />
                      </div>
                      <TickerSpark symbol={sym} width={300} height={56} />
                      <div className="grid grid-cols-[auto_1fr] items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                        <span>Stories, {rangeShort(range)}</span>
                        <span className="num text-right text-foreground">{t?.count ?? 0}</span>
                        <span>Sentiment</span>
                        {t?.count ? <SplitBar {...t} /> : <span className="text-right">—</span>}
                      </div>
                      <p className="line-clamp-2 min-h-[2.6em] border-t pt-3 text-[13px] leading-snug">
                        {t?.latest ? <><span className="num mr-1.5 text-xs text-muted-foreground">{t.latest.published_at ? ago(t.latest.published_at) : ''}</span>{t.latest.headline}</> : <span className="text-muted-foreground">No stories {rangePhrase(range)}.</span>}
                      </p>
                    </div>
                  </MagicCard>
                </div>
              </BlurFade>
            )
          })}
        </div>
        <section className="mt-10 border-t pt-6">
          <h2 className="mb-3 text-[15px] font-semibold">Add more</h2>
          <AddTickers tickers={tickers} watched={list} phrase={rangePhrase(range)} />
        </section>
      </>)}
    </div>
  )
}
