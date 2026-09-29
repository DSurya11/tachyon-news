/*
  Data access. Talks to the FastAPI backend; if it is unreachable (or no API
  URL is configured) everything is served from the demo dataset and
  `api.demo` is set so the UI can say so.
*/
import config from './config.js';
import { mock } from './mock.js';

const base = (config.API_URL || '').replace(/\/+$/, '');

class HttpError extends Error {
  constructor(status, path) {
    super(`${status} ${path}`);
    this.status = status;
  }
}

async function get(path) {
  const res = await fetch(base + path, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new HttpError(res.status, path);
  return res.json();
}

const quoteCache = new Map(); // symbol → {at, value|null}
const candleCache = new Map(); // symbol → Promise
const articleCache = new Map(); // id → Promise
const tickerNewsCache = new Map(); // symbol → {at, promise}

export const api = {
  demo: !base,

  /** Call once at boot: decides live vs demo mode. */
  async probe() {
    if (!base) return false;
    try {
      await get('/health');
      this.demo = false;
    } catch (err) {
      // A 503 means the API is up but its DB is down — still "live", health will say so.
      this.demo = !(err instanceof HttpError);
    }
    return !this.demo;
  },

  async health() {
    if (this.demo) return mock.health();
    try {
      return await get('/health');
    } catch (err) {
      if (err instanceof HttpError && err.status === 503) return { status: 'error', database: 'unreachable' };
      throw err;
    }
  },

  async news() {
    if (this.demo) return mock.news().articles;
    const d = await get(`/news?days=${config.NEWS_DAYS}&limit=${config.NEWS_LIMIT}`);
    return d.articles || [];
  },

  tickerNews(sym) {
    const hit = tickerNewsCache.get(sym);
    if (hit && Date.now() - hit.at < config.REFRESH_MS) return hit.promise;
    const promise = this.demo
      ? Promise.resolve(mock.tickerNews(sym).articles)
      : get(`/news?ticker=${encodeURIComponent(sym)}&days=30&limit=50`).then((d) => d.articles || []);
    tickerNewsCache.set(sym, { at: Date.now(), promise });
    promise.catch(() => tickerNewsCache.delete(sym));
    return promise;
  },

  article(id) {
    if (!articleCache.has(id)) {
      const p = this.demo
        ? Promise.resolve(mock.article(id))
        : get(`/news/${encodeURIComponent(id)}`).catch((e) => (e.status === 404 ? null : Promise.reject(e)));
      articleCache.set(id, p);
      p.catch(() => articleCache.delete(id));
    }
    return articleCache.get(id);
  },

  async reports() {
    if (this.demo) return mock.reports().reports;
    return (await get('/reports?limit=60')).reports || [];
  },

  /** Latest report, or a specific trading day. Resolves null when none exists. */
  async report(day) {
    if (this.demo) return mock.report();
    try {
      return await get(day ? `/reports/${day}` : '/reports/latest');
    } catch (err) {
      if (err.status === 404) return null;
      throw err;
    }
  },

  /** Batch quotes with a short client cache. Returns Map symbol → quote|null. */
  async quotes(symbols) {
    const now = Date.now();
    const want = [...new Set(symbols.filter(Boolean))];
    const missing = want.filter((s) => {
      const c = quoteCache.get(s);
      return !c || now - c.at > config.QUOTE_TTL_MS;
    });
    for (let i = 0; i < missing.length; i += 50) {
      const chunk = missing.slice(i, i + 50);
      let rows;
      if (this.demo) {
        rows = chunk.map((s) => mock.quote(s) || { symbol: s, error: 'n/a' });
      } else {
        try {
          rows = (await get(`/quotes?symbols=${chunk.map(encodeURIComponent).join(',')}`)).data || [];
        } catch {
          rows = [];
        }
      }
      for (const r of rows) quoteCache.set(r.symbol, { at: now, value: r.error ? null : r });
      for (const s of chunk) if (!quoteCache.has(s)) quoteCache.set(s, { at: now, value: null });
    }
    return new Map(want.map((s) => [s, quoteCache.get(s)?.value ?? null]));
  },

  quoteCached: (sym) => quoteCache.get(sym)?.value ?? null,

  candles(sym) {
    if (!candleCache.has(sym)) {
      const p = this.demo
        ? Promise.resolve(mock.candles(sym))
        : get(`/candles/${encodeURIComponent(sym)}?days=30`).catch(() => ({ dates: [], candles: [] }));
      candleCache.set(sym, p);
    }
    return candleCache.get(sym);
  },

  clearCaches() {
    quoteCache.clear();
    tickerNewsCache.clear();
  },
};
