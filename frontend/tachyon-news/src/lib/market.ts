/*
  Exchange sessions, each in its own time zone. Exchange holidays are not modelled.

    NYSE  09:30–16:00 ET   (pre-market from 04:00, after-hours to 20:00)
    NSE   09:15–15:30 IST  (pre-open 09:00–09:15; no after-hours trading)
*/
export type Session = 'open' | 'pre' | 'post' | 'closed'
export type Exchange = 'NYSE' | 'NSE'

interface Hours { tz: string; zone: string; open: number; close: number; pre: number; post: number; preLabel: string }

const HM = (h: number, m = 0) => h * 60 + m
const HOURS: Record<Exchange, Hours> = {
  NYSE: { tz: 'America/New_York', zone: 'ET', open: HM(9, 30), close: HM(16), pre: HM(4), post: HM(20), preLabel: 'Pre-market' },
  NSE: { tz: 'Asia/Kolkata', zone: 'IST', open: HM(9, 15), close: HM(15, 30), pre: HM(9), post: HM(15, 30), preLabel: 'Pre-open' },
}

const WEEKDAY: Record<string, number> = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 }
const DAY_NAMES = Object.keys(WEEKDAY)
const partsFmt = new Map<string, Intl.DateTimeFormat>()
const clockFmt = new Map<string, Intl.DateTimeFormat>()

function local(tz: string, now: Date) {
  let f = partsFmt.get(tz)
  if (!f) partsFmt.set(tz, (f = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false })))
  const p = Object.fromEntries(f.formatToParts(now).map((x) => [x.type, x.value]))
  return { dow: WEEKDAY[p.weekday], mins: (+p.hour % 24) * 60 + +p.minute }
}

const clock = (m: number) => `${Math.floor(m / 60) % 12 || 12}:${String(m % 60).padStart(2, '0')} ${m >= 720 ? 'PM' : 'AM'}`
const dur = (m: number) => (m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`)

export interface MarketState { exchange: Exchange; state: Session; label: string; detail: string; zone: string }

export function marketStatus(exchange: Exchange = 'NYSE', now = new Date()): MarketState {
  const h = HOURS[exchange]
  const { dow, mins } = local(h.tz, now)
  const weekday = dow >= 1 && dow <= 5
  const base = { exchange, zone: h.zone }
  if (weekday && mins >= h.open && mins < h.close) return { ...base, state: 'open', label: 'Open', detail: `Closes in ${dur(h.close - mins)}` }
  if (weekday && mins >= h.pre && mins < h.open) return { ...base, state: 'pre', label: h.preLabel, detail: `Opens in ${dur(h.open - mins)}` }
  if (weekday && mins >= h.close && mins < h.post) return { ...base, state: 'post', label: 'After hours', detail: `Closed at ${clock(h.close)} ${h.zone}` }
  let days = 0
  let d = dow
  if (!(weekday && mins < h.open)) { d = (d + 1) % 7; days = 1 }
  while (d === 0 || d === 6) { d = (d + 1) % 7; days += 1 }
  const when = days === 0 ? 'today' : days === 1 ? 'tomorrow' : DAY_NAMES[d]
  return { ...base, state: 'closed', label: 'Closed', detail: `Opens ${when} ${clock(h.open)} ${h.zone}` }
}

/** The exchanges a market view is about. */
export const exchangesFor = (market: 'all' | 'global' | 'india'): Exchange[] =>
  market === 'india' ? ['NSE'] : market === 'global' ? ['NYSE'] : ['NYSE', 'NSE']

export function exchangeClock(exchange: Exchange, now = new Date()) {
  const tz = HOURS[exchange].tz
  let f = clockFmt.get(tz)
  if (!f) clockFmt.set(tz, (f = new Intl.DateTimeFormat('en-US', { timeZone: tz, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })))
  return `${f.format(now)} ${HOURS[exchange].zone}`
}
