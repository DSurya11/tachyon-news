import { ArrowLeft, ArrowUpRight, BadgeCheck, CircleAlert, ExternalLink, LineChart, Newspaper, TrendingUp, X } from 'lucide-react'
import { animate, AnimatePresence, motion, useAnimate, useReducedMotion, type PanInfo } from 'motion/react'
import { Dialog as DialogPrimitive } from 'radix-ui'
import { lazy, Suspense, useCallback, useId, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from 'react'
import { Link } from 'react-router-dom'
import { NumberTicker } from '@/components/ui/number-ticker'
import { useArticle, useChart, useReaction, useReport, useTickerNews } from '@/hooks/queries'
import { useRange, type Range } from '@/hooks/use-range'
import { PanelIndexContext, panelKey, takeOrigin, useInspector, type Origin, type Panel } from '@/hooks/use-inspector'
import { useQuote } from '@/hooks/use-quote'
import { displaySymbol, fmtDateTime, fmtPct, hostOf, priceDigits, safeUrl, tone, tradingViewSymbol, yahooSymbol } from '@/lib/format'
import type { Span } from '@/lib/types'
import { keyboardFocusReturn } from '@/lib/focus'
import { cn } from '@/lib/utils'
import { inline } from '@/lib/markdown'
import { Money } from './Money'
import { PricedIn } from './PricedIn'
import { quoteNote } from './Quote'
import { WordsReveal } from './Reveal'
import { SentimentBadge, SplitBar } from './Sentiment'
import { Star } from './Star'
import { StoryRow } from './StoryRow'
import { TickerChip } from './TickerChip'

const PriceChart = lazy(() => import('./PriceChart').then((m) => ({ default: m.PriceChart })))

const stagger = { hidden: {}, show: { transition: { staggerChildren: 0.05, delayChildren: 0.12 } } }
const item = { hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0, transition: { duration: 0.4, ease: [0.16, 1, 0.3, 1] as const } } }
// One spring for every move in the workspace, so panels travel together.
const spring = { type: 'spring', stiffness: 360, damping: 36, mass: 0.9 } as const
const EASE_OUT = [0.22, 1, 0.36, 1] as const
const RADIUS = 'round 16px'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <motion.section variants={item} className="space-y-2.5">
      <h4 className="text-xs font-medium text-muted-foreground">{title}</h4>
      {children}
    </motion.section>
  )
}

// ─── Panel bodies ────────────────────────────────────────────────────────────────

/** Only once there's a meter to show (none in demo mode, or for stories without priced tickers). */
function PricedInSection({ id }: { id: number }) {
  const { data } = useReaction(id)
  return data?.tickers.length ? <Section title="Priced in?"><PricedIn id={id} /></Section> : null
}

function StoryPanel({ id }: { id: number }) {
  const { data: full, isLoading } = useArticle(id)
  const { data: report } = useReport()
  const a = full
  if (!a) return <div className="p-6 text-sm text-muted-foreground">{isLoading ? 'Loading…' : 'Story not found.'}</div>
  const url = safeUrl(a.url)
  const ext = full?.extraction
  const cited = report?.article_ids?.includes(id)
  const facts = (ext?.key_facts ?? []).filter(Boolean)
  const numbers = (ext?.numbers ?? []).filter((n) => n?.value)
  return (
    <motion.div key={id} variants={stagger} initial="hidden" animate="show" className="mx-auto max-w-[680px] space-y-6 p-6 sm:p-8">
      <motion.div variants={item} className="space-y-3">
        <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/80">{a.source_name}</span>
          <span>{fmtDateTime(a.published_at)}</span>
        </div>
        <WordsReveal as="h2" text={a.headline} delay={0.18} className="text-xl leading-snug font-semibold tracking-tight text-balance sm:text-2xl" />
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <SentimentBadge value={a.sentiment} />
          <span>{a.sector}</span>
          {a.event_type && <span className="capitalize">{a.event_type}</span>}
        </div>
      </motion.div>

      {a.one_line && (
        <motion.p variants={item} className="font-serif text-[17px] leading-relaxed text-foreground/90">{a.one_line}</motion.p>
      )}

      <motion.div variants={item} className={cn('flex gap-3 rounded-lg border p-3 text-[13px] leading-relaxed',
        a.verified ? 'bg-surface' : 'border-dashed')}>
        {a.verified
          ? <BadgeCheck className="mt-0.5 size-4 shrink-0 text-up" strokeWidth={1.75} />
          : <CircleAlert className="mt-0.5 size-4 shrink-0 text-muted-foreground" strokeWidth={1.75} />}
        <span className="text-muted-foreground">
          {a.verified
            ? <><span className="font-medium text-foreground">Verified.</span> The model's evidence quote and every extracted number were found in the article text.</>
            : <><span className="font-medium text-foreground">Not fully verified.</span> A quote or number couldn't be matched to the article, or only the headline was available.</>}
        </span>
      </motion.div>

      {cited && (
        <motion.div variants={item}>
          <Link to="/brief" className="group flex items-center justify-between rounded-lg border px-3 py-2.5 text-[13px] font-medium transition-colors hover:border-foreground/35">
            Cited in today's brief
            <ArrowUpRight className="size-4 text-muted-foreground transition-transform group-hover:-translate-y-0.5 group-hover:translate-x-0.5" />
          </Link>
        </motion.div>
      )}

      {a.tickers.length > 0 && (
        <Section title="Tickers · open beside this story"><div className="flex flex-wrap gap-1.5">{a.tickers.map((t) => <TickerChip key={t} symbol={t} />)}</div></Section>
      )}
      {a.tickers.length > 0 && <PricedInSection id={id} />}
      {facts.length > 0 && (
        <Section title="Key facts">
          <ul className="space-y-2">{facts.map((f, i) => (
            <li key={i} className="flex gap-2.5 text-[13.5px] leading-relaxed"><span className="mt-2 size-1 shrink-0 rounded-full bg-foreground/50" /><span>{inline(f, () => null, `f${i}`)}</span></li>
          ))}</ul>
        </Section>
      )}
      {numbers.length > 0 && (
        <Section title="Numbers">
          <div className="divide-y rounded-lg border">{numbers.map((n, i) => (
            <div key={i} className="flex items-baseline justify-between gap-4 px-3 py-2 text-[13px]">
              <span className="num font-medium">{n.value}{n.unit && !String(n.value).trim().endsWith(n.unit.trim()) ? <span className="ml-1 text-muted-foreground">{n.unit}</span> : null}</span>
              <span className="text-right text-muted-foreground">{n.context}</span>
            </div>
          ))}</div>
        </Section>
      )}
      {ext?.evidence && (
        <Section title="Evidence">
          <blockquote className="border-l-2 border-foreground/20 pl-4 font-serif text-[15.5px] leading-relaxed text-foreground/85 italic">“{ext.evidence}”</blockquote>
        </Section>
      )}
      {url && (
        <motion.a variants={item} href={url} target="_blank" rel="noopener noreferrer"
          className="flex h-10 items-center justify-center gap-2 rounded-lg bg-foreground text-sm font-medium text-background transition-opacity hover:opacity-90">
          Read on {hostOf(url) || 'source'} <ExternalLink className="size-3.5" />
        </motion.a>
      )}
    </motion.div>
  )
}

/*
  The ticker chip that was clicked flies into this panel's title: a copy of the title starts on
  top of the chip and springs into place (transform only), then hands over to the real title.
  The copy lives on <body>, so the new panel's unfolding clip never hides it mid-flight.
*/
function useChipFlight(title: React.RefObject<HTMLHeadingElement | null>, text: string, from: Origin | null) {
  const reduce = useReducedMotion()
  useLayoutEffect(() => {
    const el = title.current
    if (!el || !from?.chip || reduce) return
    const to = el.getBoundingClientRect(), f = from.rect
    const ghost = document.createElement('div')
    ghost.textContent = text
    ghost.className = 'pointer-events-none fixed z-[60] origin-left text-3xl font-semibold tracking-tight text-foreground'
    Object.assign(ghost.style, { left: `${to.left}px`, top: `${to.top}px`, height: `${to.height}px`, lineHeight: `${to.height}px`, whiteSpace: 'nowrap' })
    document.body.appendChild(ghost)
    // Deliberate DOM write: hide the real title (no re-render) while its copy flies in.
    // eslint-disable-next-line react-hooks/immutability
    el.style.opacity = '0'
    const scale = Math.max(Math.min(f.height / to.height, 1), 0.3)
    const flight = animate(ghost,
      { x: [f.left - to.left, 0], y: [f.top + f.height / 2 - (to.top + to.height / 2), 0], scale: [scale, 1] },
      { type: 'spring', stiffness: 240, damping: 28 })
    const land = () => { el.style.opacity = ''; ghost.remove() }
    flight.then(land)
    return () => { flight.stop(); land() }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
}

const SPANS: { key: Span; label: string; long: string }[] = [
  { key: '1d', label: '1D', long: '1 day' }, { key: '5d', label: '5D', long: '5 days' }, { key: '1m', label: '1M', long: '1 month' },
  { key: '3m', label: '3M', long: '3 months' }, { key: '6m', label: '6M', long: '6 months' }, { key: '1y', label: '1Y', long: '1 year' },
  { key: '5y', label: '5Y', long: '5 years' },
]

/** The chart span closest to the top bar's range, so a panel opens on the period being read about. */
function spanFor(r: Range): Span {
  const days = r.key === 'custom' && r.from && r.to ? (Date.parse(r.to) - Date.parse(r.from)) / 86400e3 + 1
    : ({ '1h': 1, '6h': 1, '12h': 1, '24h': 1, '3d': 7, '7d': 7, '30d': 30, '90d': 91, '1y': 365, all: 1826 } as Record<string, number>)[r.key] ?? 30
  return days <= 1 ? '1d' : days <= 7 ? '5d' : days <= 31 ? '1m' : days <= 92 ? '3m' : days <= 183 ? '6m' : days <= 366 ? '1y' : '5y'
}

function SpanPicker({ value, onChange }: { value: Span; onChange: (s: Span) => void }) {
  const id = useId() // several stock panels can be open side by side: each thumb slides on its own
  return (
    <div role="radiogroup" aria-label="Chart span" className="inline-flex h-8 rounded-lg border bg-surface p-0.5">
      {SPANS.map((o) => {
        const on = value === o.key
        return (
          <button key={o.key} type="button" role="radio" aria-checked={on} aria-label={o.long} onClick={() => onChange(o.key)}
            className={cn('relative rounded-md px-2.5 text-[12px] font-medium transition-colors', on ? 'text-foreground' : 'text-muted-foreground hover:text-foreground')}>
            {on && <motion.span layoutId={`span-${id}`} className="seg-thumb absolute inset-0 rounded-md" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
            <span className="num relative">{o.label}</span>
          </button>
        )
      })}
    </div>
  )
}

function TickerPanel({ symbol, from }: { symbol: string; from: Origin | null }) {
  const title = useRef<HTMLHeadingElement>(null)
  useChipFlight(title, displaySymbol(symbol), from)
  const { range } = useRange()
  const [picked, setPicked] = useState<Span | null>(null)
  const span = picked ?? spanFor(range)
  const meta = SPANS.find((o) => o.key === span)!
  const { data: q } = useQuote(symbol)
  const { data: c, isFetching } = useChart(symbol, span)
  const { news: page, counts } = useTickerNews(symbol, span)
  const news = page?.articles ?? []
  const shown = c?.span === span ? c : undefined // keepPreviousData: don't label last span's numbers with this one
  const closes = shown?.candles ?? []
  const base = shown?.base ?? closes[0]
  // 1D: the quote's own day change (official close to now), so the panel never shows two numbers for it.
  const chg = span === '1d' && q ? q.pct_change : closes.length > 1 && base ? ((closes[closes.length - 1] - base) / base) * 100 : null
  const t = counts ?? { bullish: 0, neutral: 0, bearish: 0, count: 0 }
  return (
    <motion.div key={symbol} variants={stagger} initial="hidden" animate="show" className="mx-auto max-w-[760px] space-y-6 p-6 sm:p-8">
      {/* Not part of the stagger when the title arrives by flight: it must be visible to land. */}
      <motion.div variants={from?.chip ? undefined : item} className="space-y-3">
        <div className="flex items-center gap-2">
          <h2 ref={title} className="min-w-0 truncate text-3xl font-semibold tracking-tight" title={symbol}>{displaySymbol(symbol)}</h2>
          {displaySymbol(symbol) !== symbol && <span className="num rounded border px-1.5 py-px text-[11px] text-muted-foreground">{symbol}</span>}
          <Star symbol={symbol} className="ml-auto" />
        </div>
        {q ? (
          <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
            <span className="num flex items-baseline gap-1.5 text-[28px] leading-none font-medium">
              <NumberTicker value={q.price} startValue={c?.currency === q.currency && closes[0] ? closes[0] : q.price * 0.95}
                decimalPlaces={priceDigits(q.price)} locale={q.currency === 'INR' ? 'en-IN' : 'en-US'} className="num text-foreground" />
              {(q.currency ?? q.unit) && <span className="text-sm font-normal text-muted-foreground">{q.currency ?? q.unit}</span>}
            </span>
            <span className={cn('num text-sm', tone(q.change))}>
              <Money value={q.change} currency={q.currency} unit={q.unit} signed precisionOf={q.price} /> ({fmtPct(q.pct_change)})
            </span>
          </div>
        ) : null}
        <p className="text-xs leading-relaxed text-muted-foreground">{q ? quoteNote(q) : 'No market data for this symbol — it may not trade under this code.'}</p>
      </motion.div>

      <motion.div variants={item} className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <SpanPicker value={span} onChange={setPicked} />
          <span className={cn('text-[11.5px] text-muted-foreground transition-opacity', isFetching && 'opacity-50')}>
            {shown?.source === 'stored' ? 'Stored daily closes (live history unavailable)' : shown?.intraday ? (span === '1d' ? `${shown.extended ? 'Incl. pre-market & after hours' : 'Latest session'} · dashed line: previous close` : '15-minute bars') : ''}
          </span>
        </div>
        <Suspense fallback={<div className="h-56 animate-pulse rounded-lg bg-muted" />}>
          {shown ? <PriceChart dates={shown.dates} closes={closes} currency={shown.currency} unit={shown.unit} intraday={shown.intraday} base={shown.base} span={span} />
            : <div className="h-56 animate-pulse rounded-lg bg-muted" />}
        </Suspense>
      </motion.div>

      <motion.div variants={item} className="grid grid-cols-[1fr_1.5fr_0.8fr] divide-x rounded-lg border text-[13px]">
        <div className="p-3"><div className="text-xs text-muted-foreground">{meta.label} change</div><div className={cn('num mt-1 font-medium', tone(chg))}>{fmtPct(chg)}</div></div>
        <div className="p-3"><div className="text-xs text-muted-foreground">{meta.label} range</div><div className="num mt-1 font-medium leading-snug">{closes.length ? <><Money value={Math.min(...closes)} currency={shown?.currency} unit={shown?.unit} /><br /><Money value={Math.max(...closes)} currency={shown?.currency} unit={shown?.unit} /></> : '—'}</div></div>
        <div className="p-3"><div className="text-xs text-muted-foreground">Stories · {meta.label}</div><div className="num mt-1 font-medium">{page ? page.total.toLocaleString() : '—'}</div></div>
      </motion.div>

      {t.count > 0 && (
        <Section title={`News sentiment · ${meta.long}`}>
          <SplitBar {...t} className="h-2" />
          <div className="num flex justify-between text-xs text-muted-foreground"><span className="text-up">{t.bullish} bullish</span><span>{t.neutral} neutral</span><span className="text-down">{t.bearish} bearish</span></div>
        </Section>
      )}

      <motion.div variants={item} className="flex flex-wrap gap-2">
        <a href={`https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tradingViewSymbol(symbol))}`} target="_blank" rel="noopener noreferrer"
          className="inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-[13px] font-medium transition-colors hover:border-foreground/35">
          <LineChart className="size-4" strokeWidth={1.75} /> TradingView
        </a>
        <a href={`https://finance.yahoo.com/quote/${encodeURIComponent(yahooSymbol(symbol))}`} target="_blank" rel="noopener noreferrer"
          className="inline-flex h-9 items-center gap-2 rounded-lg border px-3 text-[13px] font-medium transition-colors hover:border-foreground/35">
          Yahoo Finance <ExternalLink className="size-3.5" />
        </a>
      </motion.div>

      <Section title={`News · ${meta.long}${page && page.total > news.length ? ` · newest ${news.length} of ${page.total.toLocaleString()}` : ''} · open beside this chart`}>
        <div className="-mx-6 divide-y border-y sm:-mx-8">
          {news.length ? news.map((n) => <StoryRow key={n.id} article={n} compact />) : <div className="px-6 py-6 text-sm text-muted-foreground">{page ? `No stories in the last ${meta.long}.` : 'Loading…'}</div>}
        </div>
      </Section>
    </motion.div>
  )
}

// ─── Workspace ───────────────────────────────────────────────────────────────────

const MIN_PANEL_PX = 360 // narrowest readable panel (phone width; every panel is built to fit it)
const GAP_PX = 12

/** As many side-by-side panels as fit at a readable width: 1 on phones, then 2–4. */
function useColumns() {
  const get = () => {
    const w = window.innerWidth
    if (w < 768) return 1
    return Math.min(4, Math.max(2, Math.floor((w - 64 + GAP_PX) / (MIN_PANEL_PX + GAP_PX))))
  }
  return useSyncExternalStore((cb) => {
    window.addEventListener('resize', cb)
    return () => window.removeEventListener('resize', cb)
  }, get, () => 1)
}

function usePanelLabel(p: Panel) {
  const { data: story } = useArticle(p.kind === 'a' ? p.id : null)
  return p.kind === 't' ? displaySymbol(p.sym) : (story?.headline ?? 'Story')
}

/** A collapsed panel: a slim labelled tab that brings it (and what followed it) back. */
function PanelTab({ panel, onOpen }: { panel: Panel; onOpen: () => void }) {
  const label = usePanelLabel(panel)
  const Icon = panel.kind === 'a' ? Newspaper : TrendingUp
  return (
    <motion.button layout="position" type="button" onClick={onOpen} title={label} transition={spring}
      initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -12 }}
      className="flex w-11 shrink-0 flex-col items-center gap-3 overflow-hidden rounded-xl border bg-popover py-4 text-muted-foreground transition-colors hover:border-foreground/35 hover:text-foreground">
      <Icon className="size-4 shrink-0" strokeWidth={1.75} />
      <span className="max-h-[60vh] truncate text-[12.5px] font-medium [writing-mode:vertical-rl]">{label}</span>
    </motion.button>
  )
}

function PanelFrame({ panel, index, focused, isFirst, total, mobile, basis, onClose, onBack, ref: popRef }: {
  panel: Panel; index: number; focused: boolean; isFirst: boolean; total: number; mobile: boolean
  /** The panel's width (CSS), so the row can stay put and centre its panels. */
  basis: string
  onClose: () => void; onBack: () => void
  /** From AnimatePresence (popLayout): it needs the element to lift a closing panel out of the row. */
  ref?: React.Ref<HTMLElement>
}) {
  const [ref, animatePanel] = useAnimate<HTMLElement>()
  // One element, two owners: our entrance animations and AnimatePresence's popLayout.
  const setRef = useCallback((el: HTMLElement | null) => {
    ;(ref as { current: HTMLElement | null }).current = el
    if (typeof popRef === 'function') popRef(el)
    else if (popRef) (popRef as React.RefObject<HTMLElement | null>).current = el
  }, [ref, popRef])
  const reduce = useReducedMotion()
  const label = usePanelLabel(panel)
  const [origin] = useState(takeOrigin)

  /*
    Entrance, run before first paint. Nothing is ever scaled (text and charts stay crisp): the
    panel is drawn at its final size and revealed with a clip — out of the row or chip that was
    clicked for a new stack, or unfolding from its left edge beside the previous panel. Clip,
    opacity and transform all run in the browser's animation engine, off React's render loop.
  */
  useLayoutEffect(() => {
    const el = ref.current
    if (!el || reduce) return
    const r = el.getBoundingClientRect()
    let run
    if (mobile) {
      run = isFirst
        ? animatePanel(el, { y: [48, 0], opacity: [0, 1] }, { duration: 0.45, ease: EASE_OUT })
        : animatePanel(el, { x: ['100%', '0%'] }, spring)
    } else if (isFirst && origin) {
      const o = origin.rect
      const clamp = (v: number, max: number) => Math.min(Math.max(v, 0), Math.max(max, 0))
      const top = clamp(o.top - r.top, r.height - 12), bottom = clamp(r.bottom - o.bottom, r.height - top - 12)
      const left = clamp(o.left - r.left, r.width - 12), right = clamp(r.right - o.right, r.width - left - 12)
      run = animatePanel(el,
        { clipPath: [`inset(${top}px ${right}px ${bottom}px ${left}px round 10px)`, `inset(0px 0px 0px 0px ${RADIUS})`] },
        { duration: 0.62, ease: EASE_OUT })
    } else if (isFirst) {
      run = animatePanel(el, { opacity: [0, 1], y: [18, 0] }, { duration: 0.42, ease: EASE_OUT })
    } else {
      run = animatePanel(el,
        { clipPath: [`inset(0px 100% 0px 0px ${RADIUS})`, `inset(0px 0% 0px 0px ${RADIUS})`] },
        { duration: 0.55, ease: EASE_OUT })
    }
    // Fully opaque throughout: the clip does the revealing (a see-through panel mid-reveal
    // showed the page behind through its text). Drop the clip once open for the shadow.
    run.then(() => { el.style.clipPath = '' })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (focused) ref.current?.focus({ preventScroll: true }) }, [focused, ref])

  const onDragEnd = (_: unknown, info: PanInfo) => { if (info.offset.x > 90 || info.velocity.x > 500) onBack() }

  return (
    // layout="position": when panels are added or removed, each one glides to its new place and
    // takes its new width at once. A full layout animation would scale the content to fake the
    // size change, stretching text and charts to twice their width mid-move.
    <motion.section ref={setRef} layout="position" tabIndex={-1} aria-label={label} style={{ flex: `0 1 ${basis}` }}
      transition={spring}
      // Closing folds the panel shut towards its right edge (a clip, never a scale).
      exit={reduce ? { opacity: 0 } : mobile
        ? { x: '100%', transition: { duration: 0.28, ease: [0.4, 0, 1, 1] } }
        : { clipPath: [`inset(0px 0px 0px 0% ${RADIUS})`, `inset(0px 0px 0px 100% ${RADIUS})`], opacity: [1, 0],
            transition: { duration: 0.32, ease: [0.4, 0, 1, 1] } }}
      drag={mobile && total > 1 ? 'x' : false} dragConstraints={{ left: 0, right: 0 }} dragElastic={{ left: 0, right: 0.6 }} onDragEnd={onDragEnd}
      className={cn('relative flex min-w-0 flex-col overflow-hidden bg-popover outline-none',
        mobile ? 'h-full' : 'rounded-2xl border shadow-2xl shadow-black/25')}>
      {/* One neutral light glides along the newest panel's top edge as it arrives (a small
          transform-only element; a full-border beam cost ~40% frame time on large panels). */}
      {focused && !mobile && !reduce && <span aria-hidden className="panel-arrive"><i /></span>}
      <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3 text-xs text-muted-foreground">
        {mobile && total > 1 && (
          <button type="button" onClick={onBack} aria-label="Back" className="grid size-8 place-items-center rounded-md hover:text-foreground">
            <ArrowLeft className="size-4" strokeWidth={1.75} />
          </button>
        )}
        {panel.kind === 'a' ? <Newspaper className="ml-1 size-3.5" strokeWidth={1.75} /> : <TrendingUp className="ml-1 size-3.5" strokeWidth={1.75} />}
        <span className="min-w-0 truncate">{panel.kind === 'a' ? 'Story' : 'Stock'}{mobile && total > 1 ? ` · ${index + 1} of ${total}` : ''}</span>
        <button type="button" onClick={onClose} aria-label={`Close ${label}`}
          className="group/x ml-auto grid size-8 place-items-center rounded-md transition-colors hover:text-foreground">
          <X className="size-4 transition-transform duration-300 group-hover/x:rotate-90" strokeWidth={1.75} />
        </button>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
        <PanelIndexContext.Provider value={index}>
          {panel.kind === 'a' ? <StoryPanel id={panel.id} /> : <TickerPanel symbol={panel.sym} from={origin} />}
        </PanelIndexContext.Provider>
      </div>
    </motion.section>
  )
}

/*
  The inspector workspace: stories and tickers open in a centred panel that grows out of what
  was clicked. Opening something from inside a panel adds a panel beside it — as many columns
  as fit at a readable width (2–4; one on phones) — and older panels collapse into
  tabs on the left. Esc or a panel's × closes one panel; clicking the backdrop closes them all;
  the browser's Back steps back one panel. On phones panels are full screen: swipe right or
  press ← to go back.
*/
export function Inspector() {
  const { stack, close, closeAt, keepThrough } = useInspector()
  const columns = useColumns()
  const mobile = columns === 1
  const open = stack.length > 0
  const visibleFrom = Math.max(0, stack.length - columns)
  const hidden = stack.slice(0, visibleFrom)
  const visible = stack.slice(visibleFrom)
  // Panel width follows how many are showing, so one story isn't lost in a huge frame. The row
  // itself is full width and never moves: a closing panel folds away exactly where it stands
  // while the others glide to their new places (it used to drift across them).
  const basis = mobile ? '100%'
    : visible.length === 1 ? 'min(760px, 100%)'
    : visible.length === 2 ? 'calc((min(1360px, 100%) - 12px) / 2)'
    : `calc((100% - ${hidden.length ? 44 + GAP_PX : 0}px - ${(visible.length - 1) * GAP_PX}px) / ${visible.length})`
  const lastIndex = stack.length - 1

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(o) => { if (!o) close() }}>
      <AnimatePresence>
        {open && (
          <DialogPrimitive.Portal forceMount>
            <DialogPrimitive.Overlay asChild forceMount>
              <motion.div className="fixed inset-0 z-50 bg-background/60 [background-image:radial-gradient(ellipse_at_center,transparent_30%,color-mix(in_oklch,var(--background)_55%,transparent)_100%)]"
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: 0.2 }} />
            </DialogPrimitive.Overlay>
            <DialogPrimitive.Content forceMount aria-describedby={undefined}
              onCloseAutoFocus={keyboardFocusReturn()}
              onEscapeKeyDown={(e) => { e.preventDefault(); closeAt(lastIndex) }}
              onPointerDown={(e) => { if (e.target === e.currentTarget) close() }}
              className={cn('fixed inset-0 z-50 flex items-center justify-center outline-none', mobile ? 'p-0' : 'p-4 lg:p-8')}>
              <DialogPrimitive.Title className="sr-only">Details</DialogPrimitive.Title>
              <div
                // relative: a closing panel is lifted out (position: absolute) exactly where it stood.
                className={cn('relative flex h-full w-full justify-center', mobile ? '' : 'max-h-[920px] gap-3')}
                onPointerDown={(e) => { if (e.target === e.currentTarget) close() }}>
                <AnimatePresence initial={false} propagate>
                  {/* Phones show one panel at full width; the header's back arrow walks the stack instead. */}
                  {!mobile && hidden.map((p, i) => <PanelTab key={panelKey(p)} panel={p} onOpen={() => keepThrough(i)} />)}
                </AnimatePresence>
                <AnimatePresence mode="popLayout" propagate>
                  {visible.map((p, j) => {
                    const index = visibleFrom + j
                    return (
                      <PanelFrame key={panelKey(p)} panel={p} index={index} total={stack.length} mobile={mobile}
                        isFirst={stack.length === 1} focused={index === lastIndex} basis={basis}
                        onClose={() => closeAt(index)} onBack={() => closeAt(lastIndex)} />
                    )
                  })}
                </AnimatePresence>
              </div>
            </DialogPrimitive.Content>
          </DialogPrimitive.Portal>
        )}
      </AnimatePresence>
    </DialogPrimitive.Root>
  )
}
