/*
  TACHYON NEWS // Stock News — configuration

  API_URL
    Served from localhost  -> http://localhost:8080 (the `make up` backend)
    Deployed               -> set PROD_API_URL below to your Render URL
    ""                     -> built-in mock data only (works offline)
  If the backend can't be reached, the page falls back to mock data and
  shows a warning banner.
*/
(function () {
  'use strict';

  var PROD_API_URL = ''; // e.g. "https://stock-news-api.onrender.com"
  var isLocal = /^(localhost|127\.0\.0\.1|\[::1\])$/.test(location.hostname) || location.protocol === 'file:';

  window.APP_CONFIG = {
    API_URL: isLocal ? 'http://localhost:8080' : PROD_API_URL,
    // The pipeline runs hourly; polling faster than once a minute only burns quota.
    REFRESH_MS: 60000,
    // Feed window and size
    NEWS_DAYS: 3,
    NEWS_LIMIT: 200,
    // Symbols shown in the scrolling tape under the header
    TAPE_SYMBOLS: ['SPY', 'QQQ', 'AAPL', 'NVDA', 'MSFT', 'AMZN', 'META', 'GOOGL', 'TSM', 'AMD', 'JPM', 'GS', 'XOM', 'TLT']
  };
})();
