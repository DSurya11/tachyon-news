/* Demo data shaped exactly like the API, used offline or when the API is unreachable. */

const QUOTES = {
  SPY: [588.11, 0.32], QQQ: [512.4, 0.61], DIA: [431.2, -0.12], IWM: [224.9, 0.84], AAPL: [232.11, 2.34],
  TSM: [205.11, 3.1], NVDA: [138.47, 4.12], AMD: [149.22, -2.15], MSFT: [421.66, -1.28], META: [578.9, 0.85],
  GOOGL: [178.34, 1.02], AMZN: [218.9, 2.05], TSLA: [342.1, -3.45], JPM: [245.88, 1.65], GS: [542.19, -0.72],
  BAC: [44.02, -1.1], XOM: [118.45, 2.2], CVX: [158.9, 1.55], LLY: [812.45, 5.2], UNH: [528.11, -4.2],
  NKE: [72.1, -6.85], TLT: [92.3, 0.45], WMT: [83.2, 0.4],
};

const T0 = Date.now();
const S = (id, mins, sector, sentiment, event, tickers, source, headline, oneLine, verified = true) => ({
  id, headline, source_name: source, url: null, canonical_url: null,
  published_at: new Date(T0 - mins * 60e3).toISOString(),
  trading_day: new Date(T0).toISOString().slice(0, 10),
  status: verified ? 'verified' : 'extracted', verified, noise_tags: [],
  event_type: event, sentiment, one_line: oneLine, tickers, sector, sectors: [sector],
});

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

function rng(seed) {
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const hash = (s) => [...s].reduce((h, c) => Math.imul(h ^ c.charCodeAt(0), 16777619), 2166136261) >>> 0;

export const mock = {
  health: () => ({
    status: 'ok', database: 'ok', last_scrape_at: new Date(T0 - 4 * 60e3).toISOString(), last_scrape_status: 'done',
    items_found: 90, errors: 0, articles_24h: ARTICLES.length, latest_report_day: ARTICLES[0].trading_day,
    days_with_data: 12, readiness: 20,
  }),
  news: () => ({ page: 1, limit: 200, has_more: false, articles: ARTICLES.map((a) => ({ ...a })) }),
  tickerNews: (sym) => ({ articles: ARTICLES.filter((a) => a.tickers.includes(sym)) }),
  article: (id) => {
    const a = ARTICLES.find((x) => x.id === +id);
    if (!a) return null;
    return {
      ...a,
      extraction: {
        event_type: a.event_type, sentiment: a.sentiment, tickers: a.tickers, one_line: a.one_line,
        key_facts: [a.one_line], numbers: [], evidence: a.verified ? a.one_line : null, model_used: 'demo',
      },
    };
  },
  reports: () => ({ reports: [{ trading_day: ARTICLES[0].trading_day, created_at: new Date(T0 - 20 * 60e3).toISOString(), provider: 'demo' }] }),
  report: () => ({
    id: 1, trading_day: ARTICLES[0].trading_day, content: REPORT, article_ids: [1, 2, 3, 5, 6, 7],
    provider: 'demo', created_at: new Date(T0 - 20 * 60e3).toISOString(),
  }),
  quote: (sym) => {
    const q = QUOTES[sym];
    if (!q) return null;
    return { symbol: sym, price: q[0], change: (q[0] * q[1]) / 100, pct_change: q[1], stale: false, source: 'demo' };
  },
  candles: (sym) => {
    const q = QUOTES[sym];
    if (!q) return { symbol: sym, dates: [], candles: [] };
    const r = rng(hash(sym));
    const n = 30, dir = q[1] >= 0 ? 1 : -1;
    const walk = [];
    let x = 0;
    for (let i = 0; i < n; i++) { x += (r() - 0.5) * 2; walk.push(x + dir * (i / (n - 1)) * 6); }
    const last = walk[n - 1];
    const dates = walk.map((_, i) => new Date(T0 - (n - 1 - i) * 86400e3).toISOString().slice(0, 10));
    return { symbol: sym, dates, candles: walk.map((v) => +(q[0] * (1 + (v - last) * 0.01)).toFixed(2)) };
  },
};
