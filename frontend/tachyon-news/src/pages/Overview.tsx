import { ArrowRight, Trophy } from 'lucide-react'
import { motion } from 'motion/react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { BlurFade } from '@/components/ui/blur-fade'
import { BorderBeam } from '@/components/ui/border-beam'
import { NumberTicker } from '@/components/ui/number-ticker'
import { Empty } from '@/components/app/Empty'
import { PageHeader } from '@/components/app/PageHeader'
import { PipelineBeams } from '@/components/app/PipelineBeams'
import { QuoteText } from '@/components/app/Quote'
import { SectorGrid } from '@/components/app/SectorGrid'
import { SplitBar } from '@/components/app/Sentiment'
import { SentimentFlow } from '@/components/app/SentimentFlow'
import { Card, Stat } from '@/components/app/Stat'
import { StoryRow } from '@/components/app/StoryRow'
import { TickerSpark } from '@/components/app/TickerSpark'
import { useHealth, useNewsPages, useReport, useSummary } from '@/hooks/queries'
import { useInspector } from '@/hooks/use-inspector'
import { ago, fmtDay } from '@/lib/format'
import { exchangesFor, marketStatus } from '@/lib/market'
import { useMarket } from '@/hooks/use-market'
import { PRESETS, rangeId, rangeLabel, rangePhrase, rangeShort, useRange, type Range } from '@/hooks/use-range'
import { firstParagraph, renderMarkdown } from '@/lib/markdown'
import { moodWord } from '@/lib/stats'
import type { Counts } from '@/lib/types'
import { Cite } from '@/components/app/Cite'
import { cn } from '@/lib/utils'

const LEAD: Record<string, string> = {
  'Risk-on': 'Risk appetite is back',
  'Leaning bullish': 'Markets lean bullish',
  Balanced: 'A two-sided tape',
  'Leaning bearish': 'Markets turn cautious',
  'Risk-off': 'A risk-off tone takes hold',
}

function headline(mood: string, sector?: string, ticker?: string) {
  const lead = LEAD[mood] ?? 'The day on the wire'
  if (sector && ticker) return `${lead} as ${sector} leads the conversation`
  return lead
}

const net = (c: Counts) => (c.count ? (c.bullish - c.bearish) / c.count : 0)

export default function Overview() {
  const { range } = useRange()
  // Everything below is computed by the API for the chosen range, so any range size is cheap.
  const { data: summary, isLoading, dataUpdatedAt } = useSummary()
  // "How today's brief was made" is about today's brief, whatever range is chosen.
  const { data: today } = useSummary({ at: { key: '24h' }, top: 0 })
  const { data: health } = useHealth()
  const { data: report } = useReport()
  const { data: pickPages } = useNewsPages({ picks: true }, 6)
  const { data: verifiedPages } = useNewsPages({ verifiedOnly: true }, 6)
  const { openTicker } = useInspector()
  const { market } = useMarket()

  if (isLoading && !summary) return <OverviewSkeleton />

  const all: Counts = summary ?? { count: 0, bullish: 0, neutral: 0, bearish: 0, verified: 0 }
  const d24: Counts = today ?? all
  const sectors = (summary?.sectors ?? []).map((s) => ({ ...s, net: net(s) }))
  const tickers = summary?.tickers ?? []
  const verifiedPct = all.count ? Math.round((all.verified / all.count) * 100) : 0
  const mood = moodWord(net(all))
  const sessions = exchangesFor(market).map((x) => marketStatus(x)).map((s) => `${s.exchange} ${s.label.toLowerCase()}`).join(' · ')
  const top = tickers[0]
  const picks = pickPages?.pages[0]?.articles ?? []
  const pickTotal = summary?.picks ?? 0
  const latestVerified = verifiedPages?.pages[0]?.articles ?? []
  const span = rangeShort(range)

  return (
    <div className="space-y-6">
      <PageHeader kicker={<span>{sessions} · {fmtDay(report?.trading_day ?? new Date().toISOString().slice(0, 10))}</span>}
        title={headline(mood, sectors[0]?.name, top?.symbol)}>
        {all.count.toLocaleString()} stories crossed the wire {rangePhrase(range)}. Every one was read, summarised and checked against its source
        {dataUpdatedAt ? (ago(new Date(dataUpdatedAt).toISOString()) === 'now' ? ' — updated just now.' : ` — updated ${ago(new Date(dataUpdatedAt).toISOString())} ago.`) : '.'}
      </PageHeader>

      <BlurFade delay={0.05} inView>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat label={`Stories, ${span}`} footer={`${sectors.length} sectors · ${tickers.length ? `${tickers.length}+ tickers` : 'no tickers'}`}>
            <NumberTicker value={all.count} className="num text-foreground" />
          </Stat>
          <Stat label="Verified against source" footer="Quote and numbers matched to the article">
            <span className="num"><NumberTicker value={verifiedPct} className="num text-foreground" /><span className="text-muted-foreground">%</span></span>
          </Stat>
          <Stat label={`Mood, ${span}`} footer={<><SplitBar {...all} className="mb-2" /><span className="num"><span className="text-up">{all.bullish}</span> up · {all.neutral} flat · <span className="text-down">{all.bearish}</span> down</span></>}>
            <span className={cn(net(all) >= 0.04 && 'text-up', net(all) <= -0.04 && 'text-down')}>{mood}</span>
          </Stat>
          <Stat label="Most discussed" footer={top ? <QuoteText symbol={top.symbol} /> : undefined}>
            {top ? <button type="button" className="num hover:underline" onClick={() => openTicker(top.symbol)}>{top.symbol}</button> : '—'}
          </Stat>
        </div>
      </BlurFade>

      <div className="grid gap-3 lg:grid-cols-3">
        <BlurFade delay={0.1} inView className="lg:col-span-2">
          <Card className="h-full" title="Today's brief" aside={report ? `${fmtDay(report.trading_day, { month: 'short', day: 'numeric' })} · written ${ago(report.created_at)} ago` : undefined}>
            {report ? (
              <div className="flex h-[calc(100%-44px)] flex-col px-5 pb-5">
                <div className="flex-1 font-serif text-[17.5px] leading-[1.7] text-foreground/90 [&_p]:line-clamp-6">
                  {renderMarkdown(firstParagraph(report.content), (id) => <Cite id={id} />).nodes}
                </div>
                <div className="mt-4 flex items-center justify-between border-t pt-4">
                  <span className="text-xs text-muted-foreground">{report.article_ids.length} sources cited</span>
                  <Link to="/brief" className="group inline-flex h-9 items-center gap-2 rounded-lg bg-foreground px-4 text-[13px] font-medium text-background transition-opacity hover:opacity-90">
                    Read the brief <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
                  </Link>
                </div>
              </div>
            ) : <div className="p-5"><Empty title="No brief yet">It's written once enough stories for the trading day are verified.</Empty></div>}
            {report && <BorderBeam duration={10} />}
          </Card>
        </BlurFade>

        <BlurFade delay={0.15} inView>
          <Card className="h-full" title="How today's brief was made" aside="live">
            <div className="px-5 pb-5">
              <PipelineBeams scraped={Math.max(health?.articles_24h ?? 0, d24.count)} extracted={d24.count} verified={d24.verified} cited={report?.article_ids.length ?? 0}
                briefLabel={report ? fmtDay(report.trading_day, { month: 'short', day: 'numeric' }) : '—'} />
              <p className="mt-4 text-[13px] leading-relaxed text-muted-foreground">
                Headlines are pulled from the wire every hour. An LLM reads each article, a verifier checks its quote and numbers
                against the original text, and the brief cites only what survived.
              </p>
            </div>
          </Card>
        </BlurFade>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <BlurFade delay={0.05} inView className="lg:col-span-2">
          <SentimentCard />
        </BlurFade>
        <BlurFade delay={0.1} inView>
          <Card className="h-full" title="In the news" aside="by mentions">
            <div className="divide-y pb-1">
              {tickers.slice(0, 7).map((t, i) => (
                <div key={t.symbol} role="button" tabIndex={0} onClick={() => openTicker(t.symbol)} onKeyDown={(e) => e.key === 'Enter' && openTicker(t.symbol)}
                  className="hover-row cursor-pointer outline-none">
                  <div className="hover-body grid grid-cols-[18px_52px_1fr_auto] items-center gap-3 px-5 py-2.5">
                  <span className="num text-xs text-muted-foreground">{i + 1}</span>
                  <span className="num text-[13px] font-medium"><span className="hover-title">{t.symbol}</span></span>
                  <TickerSpark symbol={t.symbol} width={72} height={22} />
                  <span className="text-right text-[12px]"><QuoteText symbol={t.symbol} showPrice={false} /><span className="block text-[11px] text-muted-foreground">{t.count} stories</span></span>
                  </div>
                </div>
              ))}
              {!tickers.length && <div className="p-5"><Empty title="No tickers yet" /></div>}
            </div>
          </Card>
        </BlurFade>
      </div>

      <BlurFade delay={0.05} inView>
        <Card title="Sectors" aside="size of the conversation · net sentiment">
          <div className="px-5 pb-5"><SectorGrid sectors={sectors} /></div>
        </Card>
      </BlurFade>

      <BlurFade delay={0.05} inView>
        {picks.length ? (
          <Card title={<span className="flex items-center gap-2"><Trophy className="size-4 text-signal" strokeWidth={2} />Top picks</span>}
            aside={<Link to="/wire?view=top" className="hover:text-foreground">All {pickTotal} picks →</Link>}>
            <div className="divide-y border-t">
              {picks.map((a) => <StoryRow key={a.id} article={a} compact showPick />)}
            </div>
          </Card>
        ) : (
          <Card title="Latest verified" aside={<Link to="/wire?verified=1" className="hover:text-foreground">All stories →</Link>}>
            <div className="divide-y border-t">
              {latestVerified.map((a) => <StoryRow key={a.id} article={a} compact />)}
            </div>
          </Card>
        )}
      </BlurFade>
    </div>
  )
}

const CHART_SPANS = ['1h', '6h', '12h', '24h', '7d', '30d', '1y', 'all'] as const
const SPAN_LABEL: Record<(typeof CHART_SPANS)[number], string> = { '1h': '1H', '6h': '6H', '12h': '12H', '24h': '24H', '7d': '7D', '30d': '1M', '1y': '1Y', all: 'All' }
const BAR_SIZE: Record<string, string> = { '5min': '5-minute', '15min': '15-minute', hour: 'hourly', day: 'daily', week: 'weekly' }

/** Sentiment over time, with its own span (1 hour … all time); follows the top-bar range until one is picked. */
function SentimentCard() {
  const { range } = useRange()
  const [span, setSpan] = useState<Range | null>(null)
  const shown = span ?? range
  const { data } = useSummary({ at: shown, top: 0 })
  // A span longer than the database is drawn from the first story; say so rather than look broken.
  const first = data?.timeline.buckets[0]?.t
  const hours = PRESETS.find((p) => p.key === shown.key)?.hours
  const partial = Boolean(hours && first && Date.now() - Date.parse(first) < hours * 3600e3 * 0.9)
  const legend = <span className="flex items-center gap-3"><Legend c="bg-up" l="Bullish" /><Legend c="bg-flat/40" l="Neutral" /><Legend c="bg-down" l="Bearish" /></span>
  return (
    <Card className="flex h-full flex-col" title="Sentiment over time" aside={legend}>
      <div className="flex flex-wrap items-center gap-2 px-5 pb-2">
        <div role="radiogroup" aria-label="Chart span" className="inline-flex h-8 rounded-lg border bg-surface p-0.5">
          {CHART_SPANS.map((k) => {
            const on = rangeId(shown) === k
            return (
              <button key={k} type="button" role="radio" aria-checked={on} aria-label={PRESETS.find((p) => p.key === k)?.label} onClick={() => setSpan({ key: k })}
                className={cn('relative rounded-md px-2.5 text-[12px] font-medium transition-colors', on ? 'text-foreground' : 'text-muted-foreground hover:text-foreground')}>
                {on && <motion.span layoutId="chart-span" className="seg-thumb absolute inset-0 rounded-md" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
                <span className="num relative">{SPAN_LABEL[k]}</span>
              </button>
            )
          })}
        </div>
        <span className="text-[11.5px] text-muted-foreground">
          {data ? `${BAR_SIZE[data.timeline.unit]} bars · ${data.count.toLocaleString()} stories` : ''}
          {!CHART_SPANS.some((k) => k === rangeId(shown)) && ` · ${rangeLabel(shown)}`}
          {partial && first && ` · stories start ${fmtDay(first.slice(0, 10), { month: 'short', day: 'numeric' })}`}
        </span>
        {span && rangeId(span) !== rangeId(range) && (
          <button type="button" onClick={() => setSpan(null)} className="ml-auto text-[11.5px] text-muted-foreground hover:text-foreground">Match top bar</button>
        )}
      </div>
      <div className="flex min-h-[258px] flex-1 flex-col px-3 pb-4">{data && <SentimentFlow timeline={data.timeline} className="min-h-[258px] flex-1" />}</div>
    </Card>
  )
}

function Legend({ c, l }: { c: string; l: string }) {
  return <span className="flex items-center gap-1.5"><span className={cn('size-2 rounded-[2px]', c)} />{l}</span>
}

function OverviewSkeleton() {
  return (
    <div className="space-y-6">
      <div className="space-y-3 pb-6"><div className="h-4 w-40 animate-pulse rounded bg-muted" /><div className="h-8 w-2/3 animate-pulse rounded bg-muted" /><div className="h-4 w-1/2 animate-pulse rounded bg-muted" /></div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">{Array.from({ length: 4 }, (_, i) => <div key={i} className="h-32 animate-pulse rounded-xl border bg-card" />)}</div>
      <div className="grid gap-3 lg:grid-cols-3"><div className="h-72 animate-pulse rounded-xl border bg-card lg:col-span-2" /><div className="h-72 animate-pulse rounded-xl border bg-card" /></div>
    </div>
  )
}
