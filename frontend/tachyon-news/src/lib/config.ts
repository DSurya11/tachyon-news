/*
  API location:
    ?api=<url>          explicit override (tests, previews)
    ?demo=1             built-in demo data
    VITE_API_URL        set at build time for production (e.g. your Render URL)
    localhost           http://localhost:8080 (the `make up` backend)
*/
const params = new URLSearchParams(window.location.search)
const isLocal = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(window.location.hostname)

export const config = {
  apiUrl: params.get('demo')
    ? ''
    : (params.get('api') ?? import.meta.env.VITE_API_URL ?? (isLocal ? 'http://localhost:8080' : '')).replace(/\/+$/, ''),
  refreshMs: 60_000,
  newsLimit: 200,
  tape: ['SPY', 'QQQ', 'DIA', 'IWM', 'AAPL', 'NVDA', 'MSFT', 'AMZN', 'META', 'GOOGL', 'TSLA', 'AMD', 'JPM', 'XOM', 'TLT'],
}
