/* Small pure helpers: escaping, formatting, time, market clock, derived stats. */

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ESC[c]);

export const safeUrl = (u) => (/^https?:\/\//i.test(u || '') ? u : null);

export function hostOf(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; }
}

/* ---------- numbers ---------- */
export const fmtPrice = (n) =>
  n == null || Number.isNaN(+n) ? '—' : (+n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const fmtPct = (n, sign = true) =>
  n == null || Number.isNaN(+n) ? '—' : `${sign && n > 0 ? '+' : ''}${(+n).toFixed(2)}%`;
export const fmtInt = (n) => (n == null ? '—' : (+n).toLocaleString('en-US'));
export const dirClass = (n) => (n > 0 ? 'up' : n < 0 ? 'down' : 'flat');

/* ---------- time ---------- */
export function ago(iso) {
  if (!iso) return '—';
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return 'now';
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
}

const ET = 'America/New_York';
const etParts = (d) =>
  Object.fromEntries(
    new Intl.DateTimeFormat('en-US', {
      timeZone: ET, hour12: false, weekday: 'short', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).formatToParts(d).map((p) => [p.type, p.value]),
  );

export function etClock(d = new Date()) {
  const p = etParts(d);
  return `${p.hour === '24' ? '00' : p.hour}:${p.minute}:${p.second} ET`;
}

export function fmtDateTime(iso) {
  if (!iso) return '—';
  return new Intl.DateTimeFormat('en-US', {
    timeZone: ET, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit',
  }).format(new Date(iso)) + ' ET';
}

export function fmtDay(isoDay) {
  if (!isoDay) return '—';
  const [y, m, d] = isoDay.split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d, 12)).toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC',
  });
}

const WEEKDAY = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
const OPEN = 9 * 60 + 30, CLOSE = 16 * 60, PRE = 4 * 60, POST = 20 * 60;

/** NYSE session state in New York time (exchange holidays are not modelled). */
export function marketStatus(now = new Date()) {
  const p = etParts(now);
  const dow = WEEKDAY[p.weekday];
  const mins = (+p.hour % 24) * 60 + +p.minute;
  const weekday = dow >= 1 && dow <= 5;
  const dur = (m) => (m >= 60 ? `${Math.floor(m / 60)}h ${m % 60}m` : `${m}m`);

  if (weekday && mins >= OPEN && mins < CLOSE) return { state: 'open', label: 'Market open', detail: `closes in ${dur(CLOSE - mins)}` };
  if (weekday && mins >= PRE && mins < OPEN) return { state: 'pre', label: 'Pre-market', detail: `opens in ${dur(OPEN - mins)}` };
  if (weekday && mins >= CLOSE && mins < POST) return { state: 'post', label: 'After hours', detail: 'closed 4:00 PM ET' };
  let days = 0;
  let d = dow;
  if (!(weekday && mins < OPEN)) { d = (d + 1) % 7; days = 1; }
  while (d === 0 || d === 6) { d = (d + 1) % 7; days += 1; }
  const next = days === 0 ? 'today' : days === 1 ? 'tomorrow' : Object.keys(WEEKDAY)[d];
  return { state: 'closed', label: 'Market closed', detail: `opens ${next} 9:30 ET` };
}

/* ---------- derived stats ---------- */
export const SENTIMENTS = ['bullish', 'neutral', 'bearish'];
export const EVENT_TYPES = ['earnings', 'merger', 'macro', 'regulatory', 'product', 'personnel', 'legal', 'other'];

export const SECTOR_COLORS = {
  'Technology': '#5aa9ff', 'Financials': '#22d39a', 'Energy': '#ffb547', 'Health Care': '#a78bfa',
  'Consumer Discretionary': '#ff5470', 'Consumer Staples': '#ff8a5c', 'Industrials': '#7dd3fc',
  'Communication Services': '#f472b6', 'Materials': '#d4b13d', 'Real Estate': '#5eead4',
  'Utilities': '#94a3b8', 'ETF': '#cbd5e1', 'Macro & Markets': '#fbbf24',
};
export const sectorColor = (s) => SECTOR_COLORS[s] || '#8d98a9';

function tally(items) {
  const t = { count: items.length, bullish: 0, neutral: 0, bearish: 0, verified: 0 };
  for (const a of items) {
    t[a.sentiment in t ? a.sentiment : 'neutral'] += 1;
    if (a.verified) t.verified += 1;
  }
  t.net = t.count ? (t.bullish - t.bearish) / t.count : 0; // -1 … +1
  return t;
}

export function sectorStats(articles) {
  const groups = new Map();
  for (const a of articles) {
    const k = a.sector || 'Macro & Markets';
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(a);
  }
  return [...groups.entries()]
    .map(([name, items]) => ({ name, ...tally(items) }))
    .sort((x, y) => y.count - x.count || x.name.localeCompare(y.name));
}

export function tickerStats(articles) {
  const map = new Map();
  for (const a of articles) {
    for (const sym of a.tickers || []) {
      if (!map.has(sym)) map.set(sym, { symbol: sym, items: [], sector: a.sector });
      map.get(sym).items.push(a);
    }
  }
  return [...map.values()]
    .map((t) => ({ symbol: t.symbol, sector: t.sector, latest: t.items[0], ...tally(t.items) }))
    .sort((x, y) => y.count - x.count || x.symbol.localeCompare(y.symbol));
}

export const overallStats = (articles) => tally(articles);

/** Hourly buckets for the last `hours` hours, oldest first. */
export function hourlyBuckets(articles, hours = 48) {
  const now = Date.now();
  const start = now - hours * 3600e3;
  const buckets = Array.from({ length: hours }, (_, i) => ({
    t: new Date(start + i * 3600e3), bullish: 0, neutral: 0, bearish: 0,
  }));
  for (const a of articles) {
    const t = new Date(a.published_at).getTime();
    if (!(t >= start && t <= now)) continue;
    const i = Math.min(hours - 1, Math.floor((t - start) / 3600e3));
    buckets[i][a.sentiment in buckets[i] ? a.sentiment : 'neutral'] += 1;
  }
  return buckets;
}

export function debounce(fn, ms) {
  let id;
  return (...args) => { clearTimeout(id); id = setTimeout(() => fn(...args), ms); };
}
