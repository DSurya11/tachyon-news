import { Search, Trophy, X } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import { AnimatedShinyText } from '@/components/ui/animated-shiny-text'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Empty } from '@/components/app/Empty'
import { PageHeader } from '@/components/app/PageHeader'
import { StoryRow } from '@/components/app/StoryRow'
import { useNewsPages, useSummary } from '@/hooks/queries'
import { rangeLabel, useRange } from '@/hooks/use-range'
import { etDayKey } from '@/lib/format'
import type { Article } from '@/lib/types'
import { cn } from '@/lib/utils'

const EVENTS = ['earnings', 'merger', 'macro', 'regulatory', 'product', 'personnel', 'legal', 'other']
const ALL = '__all'

function Segmented<T extends string>({ value, onChange, options, id }: { value: T; onChange: (v: T) => void; options: { v: T; label: ReactNode }[]; id: string }) {
  return (
    <div role="radiogroup" className="relative inline-flex h-9 rounded-lg border bg-surface p-0.5">
      {options.map((o) => (
        <button key={o.v} type="button" role="radio" aria-checked={value === o.v} onClick={() => onChange(o.v)}
          className={cn('relative flex items-center gap-1.5 rounded-md px-3 text-[13px] font-medium transition-colors',
            value === o.v ? 'text-foreground' : 'text-muted-foreground hover:text-foreground')}>
          {value === o.v && <motion.span layoutId={id} className="seg-thumb absolute inset-0 rounded-md" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
          <span className="relative flex items-center gap-1.5">{o.label}</span>
        </button>
      ))}
    </div>
  )
}

function dayLabel(key: string) {
  const today = etDayKey(new Date().toISOString())
  const yest = etDayKey(new Date(Date.now() - 86400e3).toISOString())
  const pretty = new Date(`${key}T12:00:00Z`).toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', timeZone: 'UTC' })
  return key === today ? `Today, ${pretty}` : key === yest ? `Yesterday, ${pretty}` : pretty
}

const PAGE = 100 // stories per server page

/** A value that follows `value` after it stops changing for `ms` (search-as-you-type). */
function useDebounced<T>(value: T, ms = 300) {
  const [v, setV] = useState(value)
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t) }, [value, ms])
  return v
}

/*
  The wire for the chosen range. Filters, search and paging run on the server, so the page
  stays fast whatever the range — the whole history can be browsed without downloading it.
*/
export default function Wire() {
  const { range } = useRange()
  const [params, setParams] = useSearchParams()
  const top = params.get('view') === 'top'
  const q = params.get('q') ?? ''
  const sector = params.get('sector') ?? ''
  const sent = params.get('sent') ?? ''
  const event = params.get('event') ?? ''
  const verified = params.get('verified') === '1'
  const density = params.get('density') === 'compact'
  const selected = params.get('a')

  const set = (patch: Record<string, string | null>, replace = false) => {
    const next = new URLSearchParams(params)
    for (const [k, v] of Object.entries(patch)) if (!v) next.delete(k); else next.set(k, v)
    setParams(next, { replace })
  }

  // The search box updates the URL as you type; the server is asked once you pause.
  const [qInput, setQInput] = useState(q)
  const qSearch = useDebounced(qInput)
  useEffect(() => { if (qSearch !== q) set({ q: qSearch }, true) }, [qSearch]) // eslint-disable-line react-hooks/exhaustive-deps

  const { data: summary } = useSummary()
  const { data, isLoading, isFetching, hasNextPage, fetchNextPage, isFetchingNextPage } = useNewsPages(
    { q: q || undefined, sector: sector || undefined, sentiment: sent || undefined, event: event || undefined, verifiedOnly: verified, picks: top }, PAGE)
  const list = useMemo(() => data?.pages.flatMap((p) => p.articles) ?? [], [data])
  const total = data?.pages[0]?.total ?? 0
  const allCount = summary?.count ?? 0
  const pickCount = summary?.picks ?? 0
  const filterKey = [rangeLabel(range), top, q, sector, sent, event, verified].join('|')

  // "New" = arrived since this page was opened (or since the notice was dismissed).
  const [seen, setSeen] = useState<Set<number> | null>(null)
  if (seen === null && list.length) setSeen(new Set(list.map((a) => a.id))) // first data: everything counts as seen
  const fresh = useMemo(() => new Set(seen ? list.filter((a) => !seen.has(a.id)).map((a) => a.id) : []), [list, seen])

  // Older stories load from the server as the end of the list comes into view.
  const more = () => { if (hasNextPage && !isFetchingNextPage) fetchNextPage() }
  const sentinel = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const el = sentinel.current
    if (!el || !hasNextPage) return
    const io = new IntersectionObserver(([e]) => { if (e.isIntersecting && !isFetchingNextPage) fetchNextPage() }, { rootMargin: '800px' })
    io.observe(el)
    return () => io.disconnect()
  }, [hasNextPage, isFetchingNextPage, fetchNextPage, list.length])

  const groups = useMemo(() => {
    const g = new Map<string, Article[]>()
    for (const a of list) {
      // While the picks load, the previous (unpicked) rows are still on screen: group those by day too.
      const k = top && a.top_pick ? a.top_pick.trading_day : a.published_at ? etDayKey(a.published_at) : 'unknown'
      const bucket = g.get(k)
      if (bucket) bucket.push(a); else g.set(k, [a])
    }
    return [...g.entries()]
  }, [list, top])

  // j / k keyboard navigation through the visible list.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).closest('input, textarea, select, [role="dialog"]') || e.metaKey || e.ctrlKey) return
      if (e.key !== 'j' && e.key !== 'k') return
      const i = list.findIndex((a) => String(a.id) === selected)
      const next = list[Math.max(0, Math.min(list.length - 1, i === -1 ? 0 : i + (e.key === 'j' ? 1 : -1)))]
      if (next) {
        if (list.indexOf(next) >= list.length - 3) more()
        set({ a: String(next.id), t: null }, true)
        requestAnimationFrame(() => document.querySelector(`[data-row="${next.id}"]`)?.scrollIntoView({ block: 'nearest' }))
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  })

  const filtered = Boolean(q || sector || sent || event || verified)
  const sectors = summary?.sectors ?? []

  return (
    <div>
      <PageHeader kicker={top ? `Ranked by the writer of the daily brief · ${rangeLabel(range)}` : rangeLabel(range)} title={top ? 'Top picks' : 'The wire'}>
        {top
          ? <>The stories that matter most, most important first, each with a line on why. Switch back to <em>All stories</em> to read everything.</>
          : <>Every story the pipeline has read, newest first. Press <kbd className="num rounded border px-1 text-xs">j</kbd> and <kbd className="num rounded border px-1 text-xs">k</kbd> to move through them.</>}
      </PageHeader>

      {/* Solid background: backdrop-blur on a sticky bar re-blurs the list under it on every scroll frame. */}
      <div className="sticky top-(--topbar-h) z-20 -mx-4 mb-3 border-b bg-background px-4 py-3 sm:-mx-6 sm:px-6">
        <div className="flex flex-wrap items-center gap-2">
          <Segmented id="view-pill" value={top ? 'top' : 'all'} onChange={(v) => set({ view: v === 'top' ? 'top' : null })} options={[
            { v: 'all', label: <>All stories <span className="num text-xs text-muted-foreground">{allCount.toLocaleString()}</span></> },
            { v: 'top', label: <><Trophy className="size-3.5 text-signal" strokeWidth={2} />Top picks <span className="num text-xs text-muted-foreground">{pickCount}</span></> },
          ]} />
          <label className="relative flex h-9 min-w-[200px] flex-1 items-center">
            <Search className="pointer-events-none absolute left-3 size-4 text-muted-foreground" strokeWidth={1.75} />
            <input id="wire-q" value={qInput} onChange={(e) => setQInput(e.target.value)} placeholder="Search headlines, summaries and sources"
              className="h-9 w-full rounded-lg border bg-surface pr-3 pl-9 text-[13.5px] outline-none placeholder:text-muted-foreground focus:border-foreground/30" />
          </label>
          <Segmented id="sent-pill" value={sent} onChange={(v) => set({ sent: v })} options={[
            { v: '', label: 'All' },
            { v: 'bullish', label: <><span className="size-1.5 rounded-full bg-up" />Bullish</> },
            { v: 'neutral', label: 'Neutral' },
            { v: 'bearish', label: <><span className="size-1.5 rounded-full bg-down" />Bearish</> },
          ]} />
          <Select value={sector || ALL} onValueChange={(v) => set({ sector: v === ALL ? null : v })}>
            <SelectTrigger aria-label="Sector" className="h-9 w-[180px] bg-surface text-[13px]"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All sectors</SelectItem>
              {sectors.map((s) => <SelectItem key={s.name} value={s.name}>{s.name} <span className="num text-muted-foreground">{s.count}</span></SelectItem>)}
            </SelectContent>
          </Select>
          <Select value={event || ALL} onValueChange={(v) => set({ event: v === ALL ? null : v })}>
            <SelectTrigger aria-label="Event type" className="h-9 w-[130px] bg-surface text-[13px] capitalize"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All events</SelectItem>
              {EVENTS.map((e) => <SelectItem key={e} value={e} className="capitalize">{e}</SelectItem>)}
            </SelectContent>
          </Select>
          <label className="flex h-9 items-center gap-2 rounded-lg border bg-surface px-3 text-[13px]">
            <Switch checked={verified} onCheckedChange={(c) => set({ verified: c ? '1' : null })} aria-label="Verified only" />
            Verified only
          </label>
          <Segmented id="density-pill" value={density ? 'compact' : 'comfortable'} onChange={(v) => set({ density: v === 'compact' ? 'compact' : null }, true)}
            options={[{ v: 'comfortable', label: 'Comfortable' }, { v: 'compact', label: 'Compact' }]} />
        </div>
        <div className="mt-2.5 flex items-center gap-3 text-xs text-muted-foreground">
          <span><span className="num text-foreground">{total.toLocaleString()}</span> of <span className="num">{(top ? pickCount : allCount).toLocaleString()}</span> {top ? 'top picks' : 'stories'}{isFetching && !isFetchingNextPage && <span className="ml-2">updating…</span>}</span>
          {filtered && (
            <button type="button" onClick={() => { setQInput(''); setParams(new URLSearchParams({ ...(top ? { view: 'top' } : {}), ...(selected ? { a: selected } : {}) })) }}
              className="inline-flex items-center gap-1 font-medium text-foreground hover:underline"><X className="size-3" />Clear filters</button>
          )}
        </div>
      </div>

      <AnimatePresence>
        {fresh.size > 0 && !top && (
          <motion.button type="button" initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}
            onClick={() => { setSeen(new Set(list.map((a) => a.id))); window.scrollTo({ top: 0, behavior: 'smooth' }) }}
            className="mx-auto mb-3 flex rounded-full border bg-card px-4 py-1.5 text-[13px] shadow-sm">
            <AnimatedShinyText>{fresh.size} new {fresh.size === 1 ? 'story' : 'stories'} just arrived</AnimatedShinyText>
          </motion.button>
        )}
      </AnimatePresence>

      {isLoading && !list.length ? (
        <div className="space-y-2">{Array.from({ length: 8 }, (_, i) => <div key={i} className="h-20 animate-pulse rounded-xl border bg-card" />)}</div>
      ) : list.length === 0 ? (
        top && !pickCount
          ? <Empty title="No top picks yet">Each time the daily brief is written, its writer ranks the stories that matter most. They'll show up here after the next brief.</Empty>
          : <Empty title="Nothing matches these filters" action={<button type="button" onClick={() => { setQInput(''); setParams(new URLSearchParams(top ? { view: 'top' } : {})) }} className="text-sm font-medium underline">Clear filters</button>}>
              Try a wider time range (top bar) or fewer filters.
            </Empty>
      ) : (
        // One fade for the whole list (per-row motion + layout tracking was the main cost of opening this page).
        <motion.div key={filterKey} id="wire-rows" className="space-y-6"
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}>
          {groups.map(([key, items]) => (
            <section key={key}>
              <h2 className="flex items-baseline justify-between px-1 pb-2 text-[13px] font-medium">
                {top ? `Picked for ${dayLabel(key)}` : dayLabel(key)}<span className="num text-xs font-normal text-muted-foreground">{items.length}</span>
              </h2>
              <div className="divide-y overflow-hidden rounded-xl border bg-card shadow-(--shadow-card)">
                {items.map((a) => (
                  <StoryRow key={a.id} article={a} compact={density} selected={String(a.id) === selected} fresh={fresh.has(a.id)} showPick={top} />
                ))}
              </div>
            </section>
          ))}
          {hasNextPage && (
            <div ref={sentinel} className="flex justify-center py-2">
              <button type="button" onClick={more} disabled={isFetchingNextPage} className="text-[13px] font-medium text-muted-foreground hover:text-foreground">
                {isFetchingNextPage ? 'Loading older stories…' : <>Load older stories <span className="num">({(total - list.length).toLocaleString()} left)</span></>}
              </button>
            </div>
          )}
        </motion.div>
      )}
    </div>
  )
}
