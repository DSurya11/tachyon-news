/*
  Configuration.

  API_URL
    served from localhost / 127.0.0.1  -> http://localhost:8080 (the `make up` backend)
    deployed anywhere else             -> PROD_API_URL (set this before deploying)
    ?api=<url> in the page URL overrides both (handy for testing)
    ?demo=1 forces the built-in demo data
*/
const PROD_API_URL = ''; // e.g. "https://stock-news-api.onrender.com"

const params = new URLSearchParams(location.search);
const isLocal = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname);

export default {
  API_URL: params.get('demo') ? '' : params.get('api') || (isLocal ? 'http://localhost:8080' : PROD_API_URL),
  // The pipeline runs hourly; a minute is plenty and keeps free-tier quotas safe.
  REFRESH_MS: 60_000,
  NEWS_DAYS: 3,
  NEWS_LIMIT: 200,
  QUOTE_TTL_MS: 60_000,
  TAPE_SYMBOLS: ['SPY', 'QQQ', 'DIA', 'IWM', 'AAPL', 'NVDA', 'MSFT', 'AMZN', 'META', 'GOOGL', 'TSLA', 'AMD', 'JPM', 'XOM', 'TLT'],
};
