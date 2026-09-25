/* API layer: real backend when APP_CONFIG.API_URL is set, otherwise mock data. */
(function () {
  'use strict';

  var cfg = window.APP_CONFIG, M = window.MOCK;
  var base = (cfg.API_URL || '').replace(/\/+$/, '');
  var live = !!base;
  var quoteCache = {}, candleCache = {};

  var API = { live: live, usingFallback: false };

  function get(path) {
    return fetch(base + path, { headers: { Accept: 'application/json' } }).then(function (r) {
      if (!r.ok) throw new Error(r.status + ' ' + path);
      return r.json();
    });
  }
  function fellBack(err) {
    API.usingFallback = true;
    if (window.console) console.warn('[api] falling back to mock:', err && err.message || err);
  }

  API.beginCycle = function () { API.usingFallback = false; };
  API.clearCache = function () { quoteCache = {}; candleCache = {}; };

  API.health = function () {
    if (!live) return Promise.resolve(M.health());
    return get('/health').catch(function (e) { fellBack(e); return M.health(); });
  };

  // Returns { Technology: [...], Financials: [...], ... }
  API.news = function (sectors) {
    return Promise.all(sectors.map(function (s) {
      if (!live) return Promise.resolve(M.news(s));
      return get('/news?sector=' + encodeURIComponent(s))
        .then(function (d) { return d.articles || []; })
        .catch(function (e) { fellBack(e); return M.news(s); });
    })).then(function (lists) {
      var out = {};
      sectors.forEach(function (s, i) { out[s] = lists[i]; });
      return out;
    });
  };

  API.quote = function (sym) {
    if (!quoteCache[sym]) {
      quoteCache[sym] = !live ? Promise.resolve(M.quote(sym))
        : get('/quote/' + encodeURIComponent(sym)).catch(function (e) {
            if (M.hasQuote(sym)) { fellBack(e); return M.quote(sym); }
            throw e;
          });
    }
    return quoteCache[sym];
  };

  API.candles = function (sym) {
    if (!candleCache[sym]) {
      candleCache[sym] = (!live ? Promise.resolve(M.candles(sym))
        : get('/candles/' + encodeURIComponent(sym) + '?days=30').catch(function (e) {
            if (M.hasQuote(sym)) { fellBack(e); return M.candles(sym); }
            throw e;
          })).then(function (d) { return d.candles || []; });
    }
    return candleCache[sym];
  };

  window.API = API;
})();
