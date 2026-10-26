export type Sentiment = 'bullish' | 'bearish' | 'neutral'

export interface Article {
  id: number
  headline: string
  source_name: string | null
  url: string | null
  canonical_url: string | null
  published_at: string | null
  trading_day: string | null
  status: string
  verified: boolean
  noise_tags: string[]
  event_type: string | null
  sentiment: Sentiment | null
  one_line: string | null
  tickers: string[]
  sector: string
  sectors: string[]
  /** global = Finviz (US-listed & international), india = Indian publishers */
  market?: Market
  /** Set when the brief's writer ranked this story a must-read. */
  top_pick?: TopPick | null
}

export type Market = 'global' | 'india'

export interface TopPick {
  rank: number
  why: string
  trading_day: string
}

export interface Extraction {
  event_type: string | null
  sentiment: Sentiment | null
  tickers: string[] | null
  key_facts: string[] | null
  numbers: { value: string; unit?: string; context?: string }[] | null
  one_line: string | null
  evidence: string | null
}

export interface ArticleDetail extends Article {
  extraction: Extraction | null
}

export interface Health {
  status: 'ok' | 'degraded' | 'error'
  database: string
  last_scrape_at?: string | null
  last_scrape_status?: string | null
  items_found?: number
  errors?: number
  articles_24h?: number
  latest_report_day?: string | null
  days_with_data?: number
  readiness?: number
}

export interface Report {
  id: number
  trading_day: string
  content: string
  article_ids: number[]
  top_picks?: { id: number; rank: number; why: string }[]
  created_at: string
}

export interface ReportSummary {
  trading_day: string
  created_at: string
}

export interface Quote {
  symbol: string
  price: number
  change: number
  /** The listing's own move, in its own currency (not affected by FX). */
  pct_change: number
  stale: boolean
  source: string
  as_of?: string
  /** What `price` / `change` are in: ISO code ("USD", "INR", "GBp"), or null for index points. */
  currency?: string | null
  native_currency?: string | null
  unit?: 'pts'
  /** Set when converted: target units per 1 native unit, and the rate's date. */
  fx_rate?: number
  fx_as_of?: string | null
  /** Asked for another currency but no rate was available — values are in `currency`. */
  fx_unavailable?: boolean
}

export interface Candles {
  symbol: string
  dates: string[]
  candles: number[]
  currency?: string | null
  unit?: 'pts' | null
}

/** The priced-in meter for one story (GET /news/:id/reaction). Percentages are percent, not fractions. */
export type PricedVerdict = 'mostly' | 'partly' | 'little' | 'against' | 'usually_small'
export interface TickerReaction {
  symbol: string
  currency: string | null
  benchmark: 'SPX' | 'NIFTY' | null
  t0?: string
  t0_price?: number
  price?: number
  price_at?: string
  traded?: boolean
  session?: 'pre' | 'regular' | 'post'
  move_pct?: number | null
  bench_move_pct: number | null
  excess_pct: number | null
  verdict: PricedVerdict | null
}
export interface ReactionHistory {
  event_type: string
  sentiment: string | null
  needed: number
  needed_days: number
  progress: Record<'1d' | '5d', { n: number; days: number }>
  horizon: '1d' | '5d' | null
  n?: number
  p25?: number
  median?: number
  p75?: number
  day0_median?: number
  kept_going?: number | null
  moved_n?: number
}
export interface Reaction {
  article_id: number
  published_at: string | null
  approximate: boolean
  tickers: TickerReaction[]
  history: ReactionHistory | null
}

/** The stock panel's chart spans. */
export type Span = '1d' | '5d' | '1m' | '3m' | '6m' | '1y' | '5y'

/** One span of price history: intraday `dates` are timestamps; `base` is what the change is measured from. */
export interface Chart extends Candles {
  span: Span
  source: 'yahoo' | 'stored' | 'demo'
  intraday: boolean
  extended?: boolean
  base: number | null
}

export interface User {
  id: number
  email: string
  name: string | null
  has_password: boolean
  google: boolean
}

export interface AuthResult {
  token: string
  user: User
}

export interface AuthConfig {
  google_client_id: string | null
  password: boolean
  signup: boolean
}

// ── Time-range aggregates (/summary) and paged lists (/news) ─────────────────────
export interface Window { since: string | null; until: string | null }

export interface Counts { count: number; bullish: number; neutral: number; bearish: number; verified: number }
export interface SectorSummary extends Counts { name: string }
export interface TickerSummary extends Counts {
  symbol: string
  latest: { id: number; headline: string | null; published_at: string | null } | null
}
export interface TimelineBucket { t: string; bullish: number; neutral: number; bearish: number }
export interface Summary extends Counts {
  since: string | null
  until: string | null
  sectors: SectorSummary[]
  tickers: TickerSummary[]
  timeline: { unit: '5min' | '15min' | 'hour' | 'day' | 'week'; buckets: TimelineBucket[] }
  picks: number
}

export interface NewsFilters {
  q?: string
  sector?: string
  sentiment?: string
  event?: string
  verifiedOnly?: boolean
  picks?: boolean
  market?: Market
}
export interface NewsPage { page: number; total: number; has_more: boolean; articles: Article[] }

export interface AskStep { kind: 'model' | 'tool' | 'answer' | 'error'; tool?: string; arguments?: string; failed?: boolean; model?: string }
export interface AskResult {
  answer: string
  stories: Article[]
  stopped: 'answered' | 'step_limit' | 'token_budget' | 'error'
  total_matching: number | null
  unchecked: string[]
  steps: AskStep[]
  tokens: number
  seconds: number
  cached: boolean
}
