/*
  API client. Data calls carry the session's bearer token; a 401 ends the session
  (the app then shows sign-in). If the backend is unreachable (or no URL is configured)
  data calls are served from the demo dataset and `api.demo` is true, so the UI can say so.
*/
import { config } from './config'
import { mock } from './mock'
import { session } from './session'
import type { Article, ArticleDetail, AuthConfig, AuthResult, Candles, Chart, Reaction, Span, Health, Market, NewsFilters, NewsPage, Quote, Report, ReportSummary, Summary, User, Window } from './types'

export class HttpError extends Error {
  status: number
  constructor(status: number, path: string, detail?: string) {
    super(detail || `${status} ${path}`)
    this.status = status
  }
}

function headers(json = false): HeadersInit {
  const h: Record<string, string> = { Accept: 'application/json' }
  if (json) h['Content-Type'] = 'application/json'
  if (session.token) h.Authorization = `Bearer ${session.token}`
  return h
}

async function fail(res: Response, path: string): Promise<never> {
  let detail: string | undefined
  try { detail = (await res.json())?.detail } catch { /* not JSON */ }
  throw new HttpError(res.status, path, typeof detail === 'string' ? detail : undefined)
}

async function get<T>(path: string): Promise<T> {
  const res = await fetch(config.apiUrl + path, { headers: headers() })
  if (res.status === 401 && session.token) session.set(null) // expired or revoked: back to sign-in
  if (!res.ok) await fail(res, path)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(config.apiUrl + path, { method: 'POST', headers: headers(true), body: body === undefined ? undefined : JSON.stringify(body) })
  if (!res.ok) await fail(res, path)
  return (res.status === 204 ? undefined : await res.json()) as T
}

// Components that show whether data is live (the demo banner) subscribe here, so a switch to
// sample data mid-session is visible — it used to happen silently after the boot-time check.
const modeListeners = new Set<() => void>()
export function onModeChange(listener: () => void) {
  modeListeners.add(listener)
  return () => { modeListeners.delete(listener) }
}
function setDemo(demo: boolean) {
  if (api.demo === demo) return
  api.demo = demo
  modeListeners.forEach((l) => l())
}

/** Run a live call; on a network failure (API down) switch to demo data for the session. */
async function live<T>(fn: () => Promise<T>, fallback: () => T): Promise<T> {
  if (api.demo) return fallback()
  try {
    return await fn()
  } catch (err) {
    if (err instanceof HttpError) throw err
    setDemo(true)
    return fallback()
  }
}

/** Query string for a time window plus extra parameters (empty / false values are left out). */
function qs(w: Window, extra: Record<string, string | number | boolean | undefined | null> = {}): string {
  const p = new URLSearchParams()
  if (w.since) p.set('since', w.since)
  if (w.until) p.set('until', w.until)
  for (const [k, v] of Object.entries(extra)) if (v !== undefined && v !== null && v !== '' && v !== false) p.set(k, String(v))
  return p.toString()
}

const quoteCache = new Map<string, { at: number; value: Quote | null }>() // key: `${currency}:${symbol}`
const QUOTE_TTL = 60_000

export const api = {
  demo: !config.apiUrl,

  /** Decide live vs demo once at boot. A 503 still counts as live (API up, DB down). */
  async probe(): Promise<boolean> {
    if (!config.apiUrl) return false
    try {
      await get('/health')
      setDemo(false)
    } catch (err) {
      setDemo(!(err instanceof HttpError))
    }
    return !this.demo
  },

  async health(): Promise<Health> {
    try {
      return await live(() => get<Health>('/health'), mock.health)
    } catch (err) {
      if (err instanceof HttpError && err.status === 503) return { status: 'error', database: 'unreachable' }
      throw err
    }
  },

  /** The newest stories in a range (at most NEWS_CAP_PAGES × 200): search, inspector, citations. */
  /** One server-filtered page of a range (the Wire, top picks). */
  newsPage: (w: Window, f: NewsFilters, page: number, limit = 100): Promise<NewsPage> =>
    live(() => get<NewsPage>(`/news?${qs(w, {
      q: f.q, sector: f.sector, sentiment: f.sentiment, event: f.event, market: f.market,
      verified_only: f.verifiedOnly, picks: f.picks, page, limit,
    })}`), () => mock.newsPage(w, f, page, limit)),

  /** Totals, sentiment, sectors, most-discussed tickers and the timeline for a range — computed by the API. */
  summary: (w: Window, market?: Market, symbols: string[] = [], top = 30): Promise<Summary> =>
    live(() => get<Summary>(`/summary?${qs(w, { market, symbols: symbols.join(','), top })}`),
      () => mock.summary(w, market, symbols, top)),

  /** Specific stories whatever the range (a brief's sources). */
  articlesByIds: (ids: number[]): Promise<Article[]> =>
    ids.length
      ? live(async () => {
          // 200 per request (the API's page limit), fetched together.
          const chunks = Array.from({ length: Math.ceil(Math.min(ids.length, 1000) / 200) }, (_, i) => ids.slice(i * 200, i * 200 + 200))
          const pages = await Promise.all(chunks.map((c) => get<NewsPage>(`/news?ids=${c.join(',')}&limit=200`)))
          return pages.flatMap((pg) => pg.articles ?? [])
        },
        () => mock.articles().filter((a) => ids.includes(a.id)))
      : Promise.resolve([]),

  /** A ticker's newest stories in a window (every market), with the exact total. */
  tickerNews: (sym: string, w: Window): Promise<NewsPage> =>
    live(() => get<NewsPage>(`/news?${qs(w, { ticker: sym, limit: 50 })}`),
      () => mock.newsPage(w, {}, 1, 50, sym)),

  async article(id: number): Promise<ArticleDetail | null> {
    try {
      return await live(() => get<ArticleDetail>(`/news/${id}`), () => mock.article(id))
    } catch (err) {
      if (err instanceof HttpError && err.status === 404) return null
      throw err
    }
  },

  reports: (): Promise<ReportSummary[]> => live(async () => (await get<{ reports: ReportSummary[] }>('/reports?limit=60')).reports ?? [], mock.reports),

  async report(day?: string | null): Promise<Report | null> {
    try {
      return await live(() => get<Report>(day ? `/reports/${day}` : '/reports/latest'), mock.report)
    } catch (err) {
      if (err instanceof HttpError && err.status === 404) return null
      throw err
    }
  },

  /** Batched quotes (50 per request) with a 60 s client cache, in the chosen display currency. */
  async quotes(symbols: string[], currency: string = 'native'): Promise<Map<string, Quote | null>> {
    const now = Date.now()
    const want = [...new Set(symbols.filter(Boolean))]
    const k = (s: string) => `${currency}:${s}`
    const missing = want.filter((s) => {
      const c = quoteCache.get(k(s))
      return !c || now - c.at > QUOTE_TTL
    })
    for (let i = 0; i < missing.length; i += 50) {
      const chunk = missing.slice(i, i + 50)
      let rows: (Quote | { symbol: string; error: string })[] = []
      // Demo data is never converted: it has no real exchange rates behind it.
      if (api.demo) rows = chunk.map((s) => mock.quote(s) ?? { symbol: s, error: 'n/a' })
      else {
        try {
          rows = (await get<{ data: typeof rows }>(`/quotes?currency=${currency}&symbols=${chunk.map(encodeURIComponent).join(',')}`)).data ?? []
        } catch {
          rows = []
        }
      }
      for (const r of rows) quoteCache.set(k(r.symbol), { at: now, value: 'error' in r ? null : r })
      for (const s of chunk) if (!quoteCache.has(k(s))) quoteCache.set(k(s), { at: now, value: null })
    }
    return new Map(want.map((s) => [s, quoteCache.get(k(s))?.value ?? null]))
  },

  async candles(sym: string, currency: string = 'native'): Promise<Candles> {
    try {
      return await live(() => get<Candles>(`/candles/${encodeURIComponent(sym)}?days=30&currency=${currency}`), () => mock.candles(sym))
    } catch {
      return { symbol: sym, dates: [], candles: [] }
    }
  },

  /** The priced-in meter for a story. Demo mode has no market history, so it has no meter. */
  reaction: (id: number): Promise<Reaction | null> =>
    live(() => get<Reaction>(`/news/${id}/reaction`), () => null),

  /** Price history for one span of the stock panel (fetched by the API from Yahoo). */
  async chart(sym: string, span: Span, currency: string = 'native'): Promise<Chart> {
    try {
      return await live(() => get<Chart>(`/chart/${encodeURIComponent(sym)}?span=${span}&currency=${currency}`), () => mock.chart(sym, span))
    } catch {
      return { symbol: sym, span, source: 'stored', intraday: false, base: null, dates: [], candles: [] }
    }
  },

  clearQuoteCache: () => quoteCache.clear(),

  // Accounts ------------------------------------------------------------------
  authConfig: () => get<AuthConfig>('/auth/config'),
  me: () => get<User>('/auth/me'),
  login: (email: string, password: string) => post<AuthResult>('/auth/login', { email, password }),
  signup: (email: string, password: string, name?: string) => post<AuthResult>('/auth/signup', { email, password, name }),
  google: (credential: string) => post<AuthResult>('/auth/google', { credential }),
  logout: () => post<void>('/auth/logout').catch(() => undefined),
}
