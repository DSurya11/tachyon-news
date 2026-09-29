/* Demo data shaped exactly like the API — used offline or when the API is unreachable. */
import { byPick, bySector, byTicker, tally } from './stats'
import type { Article, ArticleDetail, Candles, Chart, Span, Health, NewsFilters, NewsPage, Quote, Report, ReportSummary, Summary, Window } from './types'



const QUOTES: Record<string, [number, number]> = {
  SPY: [588.11, 0.32], QQQ: [512.4, 0.61], DIA: [431.2, -0.12], IWM: [224.9, 0.84], AAPL: [232.11, 2.34],
  TSM: [205.11, 3.1], NVDA: [138.47, 4.12], AMD: [149.22, -2.15], MSFT: [421.66, -1.28], META: [578.9, 0.85],
  GOOGL: [178.34, 1.02], AMZN: [218.9, 2.05], TSLA: [342.1, -3.45], JPM: [245.88, 1.65], GS: [542.19, -0.72],
  BAC: [44.02, -1.1], XOM: [118.45, 2.2], CVX: [158.9, 1.55], LLY: [812.45, 5.2], UNH: [528.11, -4.2],
  NKE: [72.1, -6.85], TLT: [92.3, 0.45], WMT: [83.2, 0.4],
};

const T0 = Date.now();
const S = (id: number, mins: number, sector: string, sentiment: Article['sentiment'], event: string, tickers: string[], source: string, headline: string, oneLine: string, verified = true, market: Article['market'] = 'global'): Article => ({
  id, headline, source_name: source, url: null, canonical_url: null,
  published_at: new Date(T0 - mins * 60e3).toISOString(),
  trading_day: new Date(T0).toISOString().slice(0, 10),
  status: verified ? 'verified' : 'extracted', verified, noise_tags: [],
  event_type: event, sentiment, one_line: oneLine, tickers, sector, sectors: [sector], market,
  top_pick: PICKS[id] ? { rank: PICKS[id][0], why: PICKS[id][1], trading_day: new Date(T0).toISOString().slice(0, 10) } : null,
});

// Demo "top picks": article id → [rank, why].
const PICKS: Record<number, [number, string]> = {
  2: [1, 'Data-center demand resets the AI capex debate'],
  7: [2, 'Supply discipline keeps crude above $90'],
  15: [3, 'Banks lead India’s rally as credit growth holds up'],
  6: [4, 'Tougher capital rules could cap bank buybacks'],
  12: [5, 'Patience from the Fed pushes out rate cuts'],
};

const ARTICLES = [
  S(1, 18, 'Technology', 'bullish', 'product', ['AAPL', 'TSM'], 'Bloomberg', 'Apple unveils next-gen silicon with 40% performance gain', 'New chip beats benchmarks by a wide margin; analysts lift targets.'),
  S(2, 34, 'Technology', 'bullish', 'earnings', ['NVDA', 'AMD'], 'Reuters', 'NVIDIA beats Q3 estimates as data-center revenue doubles', 'Blackwell demand outstrips supply; guidance raised across segments.'),
  S(3, 51, 'Technology', 'bearish', 'regulatory', ['MSFT'], 'Financial Times', 'Microsoft cloud unit faces EU antitrust probe', 'Regulators scrutinise Azure bundling; fines could reach billions.'),
  S(4, 62, 'Communication Services', 'neutral', 'product', ['META', 'GOOGL'], 'The Information', 'Meta rolls out AI assistant to 3B users', 'Free tier launches globally; monetisation still unclear.', false),
  S(5, 75, 'Financials', 'bullish', 'earnings', ['JPM'], 'WSJ', 'JPMorgan tops estimates on trading and investment banking', 'Markets revenue up 18%; net interest income guidance reaffirmed.'),
  S(6, 96, 'Financials', 'bearish', 'regulatory', ['BAC', 'GS'], 'Reuters', 'Fed signals tougher capital rules for big banks', 'Proposal would lift requirements for the largest lenders.'),
  S(7, 130, 'Energy', 'bullish', 'macro', ['XOM', 'CVX'], 'Bloomberg', 'Oil climbs as OPEC+ extends supply cuts', 'Brent tops $90 after the group keeps output curbs into next year.'),
  S(8, 160, 'Health Care', 'bullish', 'product', ['LLY'], 'STAT', 'Eli Lilly obesity drug wins broader approval', 'Label expansion opens a large new patient population.'),
  S(9, 190, 'Health Care', 'bearish', 'legal', ['UNH'], 'Reuters', 'UnitedHealth faces DOJ probe over billing practices', 'Investigation centres on Medicare Advantage coding.'),
  S(10, 240, 'Consumer Discretionary', 'bearish', 'earnings', ['NKE'], 'CNBC', 'Nike cuts outlook as China demand weakens', 'Revenue guide lowered; inventory clean-up to weigh on margins.'),
  S(11, 300, 'Consumer Discretionary', 'bearish', 'personnel', ['TSLA'], 'Bloomberg', 'Tesla loses another senior executive', 'Departure adds to a string of leadership changes.', false),
  S(12, 420, 'Macro & Markets', 'neutral', 'macro', [], 'Reuters', 'Fed holds rates steady, signals patience', 'Policymakers see inflation cooling but want more evidence.'),
  S(13, 600, 'Consumer Staples', 'bullish', 'earnings', ['WMT'], 'Bloomberg', 'Walmart raises full-year forecast on grocery strength', 'E-commerce growth accelerates for a third quarter.'),
  S(14, 900, 'Macro & Markets', 'bearish', 'macro', ['TLT'], 'FT', 'Treasury yields jump after hot jobs report', 'Payrolls beat forecasts, pushing out rate-cut expectations.'),
  S(15, 45, 'Financials', 'bullish', 'macro', ['HDFCBANK.NS', 'ICICIBANK.NS'], 'Economic Times', 'Sensex, Nifty climb as private banks extend gains', 'Bank stocks lead a broad rally on steady credit growth.', true, 'india'),
  S(16, 140, 'Technology', 'bearish', 'earnings', ['INFY.NS'], 'Mint', 'Infosys trims revenue guidance on client caution', 'Deal wins stay strong but discretionary spending slows.', true, 'india'),
  S(17, 260, 'Macro & Markets', 'neutral', 'macro', [], 'Business Standard', 'Rupee steadies as RBI steps in near record low', 'Central bank dollar sales cap the slide against the dollar.', false, 'india'),
];

const REPORT = `## Market Overview

Chip stocks led risk appetite as **NVIDIA** beat estimates [2] and Apple unveiled faster silicon [1], while regulatory pressure on big tech and banks lingered [3][6]. Oil strength lifted energy names [7].

## Technology

NVIDIA's data-center revenue doubled year over year [2]; the EU is probing Azure bundling practices [3].

- Apple claims a 40% performance gain for its new chips [1].
- AMD trades lower despite sector strength [2].

## Financials

JPMorgan beat on trading revenue [5], but proposed capital rules weigh on the largest banks [6].

## What to Watch

- Guidance commentary from AI suppliers [2].
- Timeline for the EU Azure decision [3].
- OPEC+ compliance and crude inventories [7].`;

function rng(seed: number) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const inWindow = (a: Article, w: Window) => {
  const t = a.published_at ? new Date(a.published_at).getTime() : NaN
  return (!w.since || t >= new Date(w.since).getTime()) && (!w.until || t < new Date(w.until).getTime())
}
const counts = (items: Article[]) => { const { count, bullish, neutral, bearish, verified } = tally(items); return { count, bullish, neutral, bearish, verified } }

/** Mirrors GET /news filtering and paging for the demo dataset. */
function newsPage(w: Window, f: NewsFilters, page: number, limit: number, ticker?: string): NewsPage {
  const needle = (f.q ?? '').toLowerCase()
  let rows = ARTICLES.filter((a) => inWindow(a, w) &&
    (!ticker || a.tickers.includes(ticker)) &&
    (!f.market || (a.market ?? 'global') === f.market) &&
    (!f.sector || a.sector === f.sector || a.sectors?.includes(f.sector)) &&
    (!f.sentiment || f.sentiment.split(',').includes(a.sentiment ?? 'neutral')) &&
    (!f.event || a.event_type === f.event) &&
    (!f.verifiedOnly || a.verified) &&
    (!f.picks || a.top_pick) &&
    (!needle || [a.headline, a.one_line, a.source_name].join(' ').toLowerCase().includes(needle)))
  if (f.picks) rows = [...rows].sort(byPick)
  const start = (page - 1) * limit
  return { page, total: rows.length, has_more: rows.length > start + limit, articles: rows.slice(start, start + limit).map((a) => ({ ...a })) }
}

/** Mirrors GET /summary for the demo dataset. */
function summary(w: Window, market: Article['market'] | undefined, symbols: string[], top = 30): Summary {
  const rows = ARTICLES.filter((a) => inWindow(a, w) && (!market || (a.market ?? 'global') === market))
  const tickers = byTicker(rows)
  const chosen = [...new Set([...tickers.slice(0, top).map((t) => t.symbol), ...symbols])]
  const start = w.since ? new Date(w.since).getTime() : Math.min(...rows.map((a) => new Date(a.published_at!).getTime()), T0)
  const end = w.until ? new Date(w.until).getTime() : Date.now()
  const span = end - start
  const unit = span <= 2 * 3600e3 ? '5min' : span <= 12 * 3600e3 ? '15min' : span <= 72 * 3600e3 ? 'hour' : span <= 400 * 86400e3 ? 'day' : 'week'
  const step = { '5min': 300e3, '15min': 900e3, hour: 3600e3, day: 86400e3, week: 7 * 86400e3 }[unit]
  const first = Math.floor(start / step) * step
  const buckets = Array.from({ length: Math.min(2000, Math.floor((end - first) / step) + 1) }, (_, i) => ({ t: new Date(first + i * step).toISOString(), bullish: 0, neutral: 0, bearish: 0 }))
  for (const a of rows) {
    const b = buckets[Math.floor((new Date(a.published_at!).getTime() - first) / step)]
    if (b) b[a.sentiment === 'bullish' || a.sentiment === 'bearish' ? a.sentiment : 'neutral'] += 1
  }
  return {
    since: w.since, until: w.until, ...counts(rows),
    sectors: bySector(rows).map(({ name, count, bullish, neutral, bearish, verified }) => ({ name, count, bullish, neutral, bearish, verified })),
    tickers: chosen.map((sym) => {
      const t = tickers.find((x) => x.symbol === sym)
      return t
        ? { symbol: sym, count: t.count, bullish: t.bullish, neutral: t.neutral, bearish: t.bearish, verified: t.verified,
            latest: { id: t.latest.id, headline: t.latest.headline, published_at: t.latest.published_at } }
        : { symbol: sym, count: 0, bullish: 0, neutral: 0, bearish: 0, verified: 0, latest: null }
    }),
    timeline: { unit, buckets },
    picks: rows.filter((a) => a.top_pick).length,
  }
}

const hash = (s: string) => [...s].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261) >>> 0;

export const mock = {
  health: (): Health => ({
    status: 'ok', database: 'ok', last_scrape_at: new Date(T0 - 4 * 60e3).toISOString(), last_scrape_status: 'done',
    items_found: 90, errors: 0, articles_24h: ARTICLES.length, latest_report_day: ARTICLES[0].trading_day,
    days_with_data: 12, readiness: 20,
  }),
  articles: (): Article[] => ARTICLES.map((a) => ({ ...a })),
  newsPage,
  summary,
  article: (id: number): ArticleDetail | null => {
    const a = ARTICLES.find((x) => x.id === +id)
    if (!a) return null
    return {
      ...a,
      extraction: {
        event_type: a.event_type, sentiment: a.sentiment, tickers: a.tickers, one_line: a.one_line,
        key_facts: [a.one_line ?? ''], numbers: [], evidence: a.verified ? a.one_line : null,
      },
    }
  },
  reports: (): ReportSummary[] => [{ trading_day: ARTICLES[0].trading_day!, created_at: new Date(T0 - 20 * 60e3).toISOString() }],
  report: (): Report => ({
    id: 1, trading_day: ARTICLES[0].trading_day!, content: REPORT, article_ids: [1, 2, 3, 5, 6, 7],
    created_at: new Date(T0 - 20 * 60e3).toISOString(),
    top_picks: Object.entries(PICKS).map(([id, [rank, why]]) => ({ id: +id, rank, why })),
  }),
  quote: (sym: string): Quote | null => {
    const q = QUOTES[sym]
    if (!q) return null
    return { symbol: sym, price: q[0], change: (q[0] * q[1]) / 100, pct_change: q[1], stale: false, source: 'demo', currency: 'USD', native_currency: 'USD' }
  },
  candles: (sym: string): Candles => {
    const q = QUOTES[sym]
    if (!q) return { symbol: sym, dates: [], candles: [] }
    const r = rng(hash(sym))
    const n = 30, dir = q[1] >= 0 ? 1 : -1
    const walk: number[] = []
    let x = 0
    for (let i = 0; i < n; i++) { x += (r() - 0.5) * 2; walk.push(x + dir * (i / (n - 1)) * 6) }
    const last = walk[n - 1]
    const dates = walk.map((_, i) => new Date(T0 - (n - 1 - i) * 86400e3).toISOString().slice(0, 10))
    return { symbol: sym, currency: 'USD', dates, candles: walk.map((v) => +(q[0] * (1 + (v - last) * 0.01)).toFixed(2)) }
  },
  chart: (sym: string, span: Span): Chart => {
    const q = QUOTES[sym]
    const empty: Chart = { symbol: sym, span, source: 'demo', intraday: false, base: null, dates: [], candles: [] }
    if (!q) return empty
    const [n, step, intraday] = ({ '1d': [78, 300e3, true], '5d': [130, 900e3, true], '1m': [21, 86400e3, false], '3m': [63, 86400e3, false],
      '6m': [126, 86400e3, false], '1y': [251, 86400e3, false], '5y': [261, 7 * 86400e3, false] } as const)[span]
    const r = rng(hash(sym + span)), dir = q[1] >= 0 ? 1 : -1
    const walk: number[] = []
    let x = 0
    for (let i = 0; i < n; i++) { x += (r() - 0.5) * 2; walk.push(x + dir * (i / (n - 1)) * 6) }
    const last = walk[n - 1], scale = span === '1d' ? 0.002 : span === '5y' ? 0.04 : 0.01
    const candles = walk.map((v) => +(q[0] * (1 + (v - last) * scale)).toFixed(2))
    const dates = walk.map((_, i) => { const d = new Date(T0 - (n - 1 - i) * step).toISOString(); return intraday ? d : d.slice(0, 10) })
    const base = span === '1d' ? +(q[0] / (1 + q[1] / 100)).toFixed(2) : candles[0]
    return { symbol: sym, span, source: 'demo', intraday, base, currency: 'USD', dates, candles }
  },
}
