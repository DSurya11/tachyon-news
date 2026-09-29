import { createContext, useContext, useState, type ReactNode } from 'react'
import type { Window } from '@/lib/types'

/*
  The dashboard's time range: one setting every page follows (Overview, Wire, sidebar,
  Watchlist, search). Default: the last 24 hours. Relative ranges are resolved to dates each
  time data is fetched, so "last 24 hours" keeps moving; custom ranges are whole local days.
  Remembered in this browser.
*/
export type RangeKey = '1h' | '6h' | '12h' | '24h' | '3d' | '7d' | '30d' | '90d' | '1y' | 'all' | 'custom'
export interface Range { key: RangeKey; from?: string; to?: string } // custom: YYYY-MM-DD, inclusive

export const PRESETS: { key: Exclude<RangeKey, 'custom'>; label: string; short: string; hours?: number }[] = [
  { key: '1h', label: 'Last hour', short: '1h', hours: 1 },
  { key: '6h', label: 'Last 6 hours', short: '6h', hours: 6 },
  { key: '12h', label: 'Last 12 hours', short: '12h', hours: 12 },
  { key: '24h', label: 'Last 24 hours', short: '24h', hours: 24 },
  { key: '3d', label: 'Last 3 days', short: '3 days', hours: 72 },
  { key: '7d', label: 'Last 7 days', short: '7 days', hours: 168 },
  { key: '30d', label: 'Last 30 days', short: '30 days', hours: 720 },
  { key: '90d', label: 'Last 90 days', short: '90 days', hours: 2160 },
  { key: '1y', label: 'Last 12 months', short: '12 months', hours: 8760 },
  { key: 'all', label: 'All time', short: 'All time' },
]

const KEY = 'tsn.range'
const DEFAULT: Range = { key: '24h' }
const localDay = (d: string) => new Date(`${d}T00:00:00`) // local midnight

/** The window (ISO datetimes) a range covers right now. */
export function windowOf(r: Range): Window {
  if (r.key === 'custom' && r.from && r.to) {
    const until = localDay(r.to)
    until.setDate(until.getDate() + 1) // "to" is inclusive
    return { since: localDay(r.from).toISOString(), until: until.toISOString() }
  }
  const p = PRESETS.find((x) => x.key === r.key)
  return { since: p?.hours ? new Date(Date.now() - p.hours * 3600e3).toISOString() : null, until: null }
}

const fmt = (d: string) => localDay(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })

export function rangeLabel(r: Range): string {
  if (r.key === 'custom' && r.from && r.to) return r.from === r.to ? fmt(r.from) : `${fmt(r.from)} – ${fmt(r.to)}`
  return PRESETS.find((x) => x.key === r.key)?.label ?? 'Last 24 hours'
}

export function rangeShort(r: Range): string {
  if (r.key === 'custom') return rangeLabel(r)
  return PRESETS.find((x) => x.key === r.key)?.short ?? '24h'
}

/** For sentences: "in the last 24 hours", "so far", "between Sep 1 and Sep 15". */
export function rangePhrase(r: Range): string {
  if (r.key === 'all') return 'so far'
  if (r.key === 'custom' && r.from && r.to) return r.from === r.to ? `on ${fmt(r.from)}` : `between ${fmt(r.from)} and ${fmt(r.to)}`
  return `in the ${rangeLabel(r).toLowerCase()}`
}

/** Stable query-key part. */
export const rangeId = (r: Range) => (r.key === 'custom' ? `custom:${r.from}:${r.to}` : r.key)

function read(): Range {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) || 'null') as Range | null
    if (v && (PRESETS.some((p) => p.key === v.key) || (v.key === 'custom' && v.from && v.to))) return v
  } catch { /* unreadable: default */ }
  return DEFAULT
}

const Ctx = createContext<{ range: Range; setRange: (r: Range) => void }>({ range: DEFAULT, setRange: () => {} })

export function RangeProvider({ children }: { children: ReactNode }) {
  const [range, set] = useState<Range>(read)
  const setRange = (r: Range) => {
    set(r)
    try { localStorage.setItem(KEY, JSON.stringify(r)) } catch { /* private mode */ }
  }
  return <Ctx.Provider value={{ range, setRange }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useRange = () => useContext(Ctx)
