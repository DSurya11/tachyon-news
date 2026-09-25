/* Mock data — mirrors the backend response shapes so the UI works with no server. */
(function () {
  'use strict';

  var QUOTES = {
    AAPL:  { price: 232.11, pct_change:  2.34 },
    TSM:   { price: 205.11, pct_change:  3.10 },
    NVDA:  { price: 138.47, pct_change:  4.12 },
    AMD:   { price: 149.22, pct_change: -2.15 },
    MSFT:  { price: 421.66, pct_change: -1.28 },
    META:  { price: 578.90, pct_change:  0.85 },
    GOOGL: { price: 178.34, pct_change:  1.02 },
    JPM:   { price: 245.88, pct_change:  1.65 },
    GS:    { price: 542.19, pct_change: -0.72 },
    WFC:   { price:  68.14, pct_change: -1.85 },
    BAC:   { price:  44.02, pct_change: -1.10 },
    TLT:   { price:  92.30, pct_change:  0.45 },
    SPY:   { price: 588.11, pct_change:  0.32 },
    XOM:   { price: 118.45, pct_change:  2.20 },
    CVX:   { price: 158.90, pct_change:  1.55 },
    OXY:   { price:  52.14, pct_change:  2.88 },
    TSLA:  { price: 342.10, pct_change: -3.45 },
    LLY:   { price: 812.45, pct_change:  5.20 },
    NVO:   { price: 108.22, pct_change: -0.90 },
    UNH:   { price: 528.11, pct_change: -4.20 },
    AMZN:  { price: 218.90, pct_change:  2.05 },
    NKE:   { price:  72.10, pct_change: -6.85 }
  };

  // minutes = age of the story at page load
  var NEWS = {
    Technology: [
      { id: 1, minutes: 18, source_name: 'Bloomberg', event_type: 'product', sentiment: 'bullish',
        headline: 'Apple Unveils Next-Gen Silicon With 40% Performance Gain, Shares Rally in Pre-Market',
        one_line: 'M4 Ultra chip beats industry benchmarks by wide margin; analysts raise price targets.',
        tickers: ['AAPL', 'TSM'] },
      { id: 2, minutes: 34, source_name: 'Reuters', event_type: 'earnings', sentiment: 'bullish',
        headline: 'NVIDIA Beats Q3 Estimates, Data Center Revenue Doubles YoY',
        one_line: 'Blackwell platform demand outstrips supply; guidance raised across all segments.',
        tickers: ['NVDA', 'AMD'] },
      { id: 3, minutes: 51, source_name: 'Financial Times', event_type: 'regulatory', sentiment: 'bearish',
        headline: 'Microsoft Cloud Division Faces Antitrust Probe in EU',
        one_line: 'Regulators scrutinize Azure bundling practices; potential fines could reach billions.',
        tickers: ['MSFT'] },
      { id: 4, minutes: 62, source_name: 'The Information', event_type: 'product', sentiment: 'neutral',
        headline: 'Meta Rolls Out AI Assistant to 3B Users, Ad Revenue Model Under Watch',
        one_line: 'Free tier launches globally; monetization strategy remains ambiguous.',
        tickers: ['META', 'GOOGL'] }
    ],
    Financials: [
      { id: 5, minutes: 24, source_name: 'WSJ', event_type: 'earnings', sentiment: 'bullish',
        headline: 'JPMorgan Posts Record Trading Revenue on Volatility Surge',
        one_line: 'Fixed income desk drives beat; buyback authorization increased to $30B.',
        tickers: ['JPM', 'GS'] },
      { id: 6, minutes: 64, source_name: 'Bloomberg', event_type: 'rating', sentiment: 'bearish',
        headline: 'Goldman Sachs Downgrades Regional Bank Sector on CRE Exposure',
        one_line: 'Commercial real estate write-downs seen accelerating into Q4.',
        tickers: ['GS', 'WFC', 'BAC'] },
      { id: 7, minutes: 68, source_name: 'Reuters', event_type: 'macro', sentiment: 'bullish',
        headline: 'Fed Signals Extended Pause as Inflation Cools to 2.4%',
        one_line: 'Dot plot suggests no cuts before Q2; yields dip across the curve.',
        tickers: ['TLT', 'SPY'] }
    ],
    Energy: [
      { id: 8, minutes: 39, source_name: 'Bloomberg', event_type: 'm&a', sentiment: 'bullish',
        headline: 'Exxon Announces $60B Permian Basin Acquisition',
        one_line: 'Largest US oil deal of the decade; production capacity to grow 25%.',
        tickers: ['XOM', 'CVX'] },
      { id: 9, minutes: 65, source_name: 'Financial Times', event_type: 'macro', sentiment: 'bullish',
        headline: 'OPEC+ Extends Production Cuts Through Mid-2026',
        one_line: 'Brent crude jumps 3%; Saudi voluntary cuts remain in place.',
        tickers: ['XOM', 'CVX', 'OXY'] },
      { id: 10, minutes: 125, source_name: 'The Verge', event_type: 'product', sentiment: 'neutral',
        headline: 'Tesla Powerwall Sales Cannibalize Traditional Utilities in Texas',
        one_line: 'Grid operators warn of demand destruction as home batteries proliferate.',
        tickers: ['TSLA'] }
    ],
    Healthcare: [
      { id: 11, minutes: 28, source_name: 'STAT News', event_type: 'clinical', sentiment: 'bullish',
        headline: 'Eli Lilly GLP-1 Successor Shows 30% Weight Loss in Phase 3',
        one_line: 'Oral formulation eliminates injection barrier; TAM expansion likely.',
        tickers: ['LLY', 'NVO'] },
      { id: 12, minutes: 66, source_name: 'Reuters', event_type: 'regulatory', sentiment: 'bearish',
        headline: 'UnitedHealth Faces Class Action Over Algorithm-Denied Claims',
        one_line: 'DOJ investigation expands; MA rebates under scrutiny.',
        tickers: ['UNH'] }
    ],
    Consumer: [
      { id: 13, minutes: 46, source_name: 'CNBC', event_type: 'earnings', sentiment: 'bullish',
        headline: 'Amazon Prime Day Sets Record With $14.2B in Sales',
        one_line: 'AWS-powered logistics show margin expansion; retail comps up 12%.',
        tickers: ['AMZN'] },
      { id: 14, minutes: 67, source_name: 'WSJ', event_type: 'guidance', sentiment: 'bearish',
        headline: 'Nike Warns of Weak China Demand, Cuts FY Guidance',
        one_line: 'Greater China revenue down 9%; peers Adidas and Lululemon also slide.',
        tickers: ['NKE'] }
    ]
  };

  var T0 = Date.now(); // stable timestamps so silent auto-refresh doesn't re-render the feed

  // Deterministic PRNG so sparklines are stable between reloads
  function hash(s) { var h = 2166136261; for (var i = 0; i < s.length; i++) { h = Math.imul(h ^ s.charCodeAt(i), 16777619); } return h >>> 0; }
  function rng(seed) {
    return function () {
      seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
      var t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  window.MOCK = {
    hasQuote: function (sym) { return !!QUOTES[sym]; },

    health: function () {
      return {
        status: 'ok',
        last_scrape_at: new Date(Date.now() - 4 * 60000).toISOString(),
        items_found: 150,
        errors: 2,
        readiness: 87
      };
    },

    news: function (sector) {
      return (NEWS[sector] || []).map(function (a) {
        var o = {}; for (var k in a) o[k] = a[k];
        o.published_at = new Date(T0 - a.minutes * 60000).toISOString();
        delete o.minutes;
        return o;
      });
    },

    quote: function (sym) {
      var q = QUOTES[sym];
      if (!q) throw new Error('no mock quote for ' + sym);
      return { symbol: sym, price: q.price, pct_change: q.pct_change, stale: false };
    },

    candles: function (sym) {
      var q = QUOTES[sym];
      if (!q) throw new Error('no mock candles for ' + sym);
      var r = rng(hash(sym)), n = 30, dir = q.pct_change >= 0 ? 1 : -1;
      var w = [], x = 0, i;
      for (i = 0; i < n; i++) { x += (r() - 0.5) * 2; w.push(x + dir * (i / (n - 1)) * 6); }
      var last = w[n - 1];
      return {
        symbol: sym,
        candles: w.map(function (v) { return +(q.price * (1 + (v - last) * 0.01)).toFixed(2); })
      };
    }
  };
})();
