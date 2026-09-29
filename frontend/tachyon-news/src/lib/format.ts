const ET = 'America/New_York'

// Intl formatters are expensive to build; these run once per row, so build each one once.
const DATETIME_ET = new Intl.DateTimeFormat('en-US', { timeZone: ET, month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
const DAYKEY_ET = new Intl.DateTimeFormat('en-CA', { timeZone: ET })
const CLOCK_ET = new Intl.DateTimeFormat('en-US', { timeZone: ET, hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
const dayFormats = new Map<string, Intl.DateTimeFormat>()
const amountFormats = new Map<string, Intl.NumberFormat>()

/**
 * A price amount for display (no currency code — see <Money>). INR uses Indian digit
 * grouping (1,19,760.00); sub-1 prices (small coins) keep enough decimals to mean something.
 */
export const priceDigits = (n: number) => {
  const abs = Math.abs(n)
  return abs >= 1 || abs === 0 ? 2 : abs >= 0.01 ? 4 : 6
}

/** "BTC-USD" → "BTC", "RELIANCE.NS" → "RELIANCE"; the full symbol is still shown where it matters. */
export const displaySymbol = (s: string) => s.replace(/\.(NS|BO)$|-USD$/, '')

/*
  Our symbols follow Yahoo's style (RELIANCE.NS, BRK.B, BTC-USD) with short index names
  (NIFTY, SPX; see pipeline/symbols.py). TradingView and Yahoo each want their own form.
*/
const INDEX_LINKS: Record<string, { tv: string; yahoo: string }> = {
  NIFTY: { tv: 'NSE:NIFTY', yahoo: '^NSEI' },
  BANKNIFTY: { tv: 'NSE:BANKNIFTY', yahoo: '^NSEBANK' },
  SENSEX: { tv: 'BSE:SENSEX', yahoo: '^BSESN' },
  SPX: { tv: 'SP:SPX', yahoo: '^GSPC' },
  DJI: { tv: 'DJ:DJI', yahoo: '^DJI' },
  NDX: { tv: 'NASDAQ:NDX', yahoo: '^NDX' },
  IXIC: { tv: 'NASDAQ:IXIC', yahoo: '^IXIC' },
  VIX: { tv: 'CBOE:VIX', yahoo: '^VIX' },
  NIKKEI: { tv: 'TVC:NI225', yahoo: '^N225' },
  HSI: { tv: 'TVC:HSI', yahoo: '^HSI' },
  DAX: { tv: 'XETR:DAX', yahoo: '^GDAXI' },
  FTSE: { tv: 'TVC:UKX', yahoo: '^FTSE' },
  KOSPI: { tv: 'TVC:KOSPI', yahoo: '^KS11' },
  SSEC: { tv: 'SSE:000001', yahoo: '000001.SS' },
}

// Commodities that news-derived symbols write like coins (XAU-USD, BRENT-USD).
const TV_COMMODITIES: Record<string, string> = {
  XAU: 'OANDA:XAUUSD', XAG: 'OANDA:XAGUSD', GOLD: 'OANDA:XAUUSD', SILVER: 'OANDA:XAGUSD',
  BRENT: 'TVC:UKOIL', WTI: 'TVC:USOIL', OIL: 'TVC:USOIL',
}

/** TradingView's symbol: NSE:JIOFIN, NSE:M&M, NSE:BAJAJ_AUTO (TradingView writes - as _), BSE:…, CRYPTO:BTCUSD. */
export function tradingViewSymbol(s: string): string {
  if (INDEX_LINKS[s]) return INDEX_LINKS[s].tv
  const india = /^(.+)\.(NS|BO)$/.exec(s)
  if (india) return `${india[2] === 'NS' ? 'NSE' : 'BSE'}:${india[1].replace(/-/g, '_')}`
  const coin = /^([A-Z0-9]+)-USD$/.exec(s)
  if (coin) return TV_COMMODITIES[coin[1]] ?? `CRYPTO:${coin[1]}USD`
  return s // US listings: TradingView finds the exchange itself
}

/** Yahoo Finance's symbol: indices as ^…, US share classes with a dash (BRK-B); .NS/.BO unchanged. */
export function yahooSymbol(s: string): string {
  if (INDEX_LINKS[s]) return INDEX_LINKS[s].yahoo
  return /^[A-Z]+\.[A-KM-SUW-Z]$/.test(s) ? s.replace('.', '-') : s
}

export function fmtAmount(n: number, currency?: string | null, precisionOf?: number) {
  const digits = priceDigits(precisionOf ?? n)
  const locale = currency === 'INR' ? 'en-IN' : 'en-US'
  const key = `${locale}:${digits}`
  let f = amountFormats.get(key)
  if (!f) amountFormats.set(key, (f = new Intl.NumberFormat(locale, { minimumFractionDigits: digits, maximumFractionDigits: digits })))
  return f.format(n)
}

export const fmtPct = (n?: number | null, sign = true) =>
  n == null || Number.isNaN(+n) ? '—' : `${sign && n > 0 ? '+' : ''}${(+n).toFixed(2)}%`

export const tone = (n?: number | null) => (n == null ? 'text-muted-foreground' : n > 0 ? 'text-up' : n < 0 ? 'text-down' : 'text-muted-foreground')

export function ago(iso?: string | null) {
  if (!iso) return '—'
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000)
  if (s < 60) return 'now'
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h`
  return `${Math.floor(h / 24)}d`
}

export const fmtDateTime = (iso?: string | null) =>
  iso ? `${DATETIME_ET.format(new Date(iso))} ET` : '—'

export function fmtDay(day?: string | null, opts: Intl.DateTimeFormatOptions = { weekday: 'long', month: 'long', day: 'numeric' }) {
  if (!day) return '—'
  const [y, m, d] = day.split('-').map(Number)
  const key = JSON.stringify(opts)
  let f = dayFormats.get(key)
  if (!f) dayFormats.set(key, (f = new Intl.DateTimeFormat('en-US', { ...opts, timeZone: 'UTC' })))
  return f.format(new Date(Date.UTC(y, m - 1, d, 12)))
}

export const etDayKey = (iso: string) => DAYKEY_ET.format(new Date(iso))

export function etClock(d = new Date()) {
  return CLOCK_ET.format(d)
}

export const hostOf = (url?: string | null) => {
  try { return url ? new URL(url).hostname.replace(/^www\./, '') : '' } catch { return '' }
}

export const safeUrl = (u?: string | null) => (u && /^https?:\/\//i.test(u) ? u : null)
