(function () {
  'use strict';

  var cfg = window.APP_CONFIG, API = window.API;

  var SECTORS = [
    { key: 'Technology', color: '#4d9fff' },
    { key: 'Financials', color: '#00ff9d' },
    { key: 'Energy',     color: '#ffb020' },
    { key: 'Healthcare', color: '#a78bfa' },
    { key: 'Consumer',   color: '#ff3355' }
  ];

  // TradingView needs EXCHANGE:SYMBOL. Anything not listed falls back to NASDAQ.
  var EXCHANGE = {
    AAPL: 'NASDAQ', NVDA: 'NASDAQ', MSFT: 'NASDAQ', META: 'NASDAQ', GOOGL: 'NASDAQ',
    AMD: 'NASDAQ', AMZN: 'NASDAQ', TSLA: 'NASDAQ', TLT: 'NASDAQ',
    TSM: 'NYSE', JPM: 'NYSE', GS: 'NYSE', WFC: 'NYSE', BAC: 'NYSE', XOM: 'NYSE',
    CVX: 'NYSE', OXY: 'NYSE', LLY: 'NYSE', NVO: 'NYSE', UNH: 'NYSE', NKE: 'NYSE',
    SPY: 'AMEX'
  };

  var ICON_CLOCK = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>';
  var ICON_UP = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 7h10v10"/><path d="M7 17 17 7"/></svg>';
  var ICON_DOWN = '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m7 7 10 10"/><path d="M17 7v10H7"/></svg>';

  var state = { sector: 'ALL', query: '', groups: null, sig: '', busy: false };
  var $ = function (s) { return document.querySelector(s); };
  var feed = $('#feed'), chipsEl = $('#chips'), banner = $('#banner');
  var observer = null, uid = 0;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function rel(iso) {
    var m = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
    if (m < 60) return m + 'm';
    var h = Math.floor(m / 60);
    return h < 24 ? h + 'h' : Math.floor(h / 24) + 'd';
  }

  /* ---------- clock ---------- */
  function tick() {
    var d = new Date(), p = function (n) { return (n < 10 ? '0' : '') + n; };
    $('#clock').textContent = p(d.getUTCHours()) + ':' + p(d.getUTCMinutes()) + ':' + p(d.getUTCSeconds()) + ' UTC';
  }

  /* ---------- sparkline ---------- */
  function sparkline(vals, up, noAnim) {
    var w = 64, h = 22, min = Math.min.apply(null, vals), max = Math.max.apply(null, vals), rng = (max - min) || 1;
    var pts = vals.map(function (v, i) { return [i / (vals.length - 1) * w, h - (v - min) / rng * h]; });
    var line = pts.map(function (p) { return p[0].toFixed(1) + ',' + p[1].toFixed(1); }).join(' ');
    var len = 0, i;
    for (i = 1; i < pts.length; i++) len += Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    var c = up ? '#00ff9d' : '#ff3355', id = 'sg' + (++uid), last = pts[pts.length - 1];
    return '<svg class="spark" width="64" height="22" aria-hidden="true">' +
      '<defs><linearGradient id="' + id + '" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="' + c + '" stop-opacity=".35"/><stop offset="1" stop-color="' + c + '" stop-opacity="0"/></linearGradient></defs>' +
      '<polyline points="0,' + h + ' ' + line + ' ' + w + ',' + h + '" fill="url(#' + id + ')" stroke="none"/>' +
      '<polyline' + (noAnim ? '' : ' class="draw"') + ' points="' + line + '" fill="none" stroke="' + c + '" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" style="--dash:' + Math.ceil(len) + 'px"/>' +
      '<circle cx="' + last[0] + '" cy="' + last[1].toFixed(1) + '" r="1.8" fill="' + c + '"><animate attributeName="r" values="1.8;2.6;1.8" dur="2s" repeatCount="indefinite"/></circle></svg>';
  }

  /* ---------- ticker badge (lazy) ---------- */
  function badgeHTML(sym) {
    return '<button class="tb" type="button" data-sym="' + esc(sym) + '" aria-label="Open ' + esc(sym) + ' chart">' +
      '<span class="sym">' + esc(sym) + '</span><span class="skel" style="width:110px"></span></button>';
  }

  function fillBadge(el, sym, q, candles, noAnim) {
    var up = q.pct_change >= 0, cls = up ? 'up' : 'down';
    el.title = q.stale ? 'Delayed quote' : '';
    el.innerHTML = '<span class="sym">' + esc(sym) + '</span>' +
      '<span class="px ' + cls + '">' + Number(q.price).toFixed(2) + '</span>' +
      '<span class="chg ' + cls + '">' + (up ? ICON_UP : ICON_DOWN) + Math.abs(q.pct_change).toFixed(2) + '%</span>' +
      (candles && candles.length > 1 ? sparkline(candles, up, noAnim) : '');
    el.setAttribute('data-loaded', '1');
  }

  function loadBadge(el, noAnim) {
    var sym = el.getAttribute('data-sym');
    return Promise.all([API.quote(sym), API.candles(sym).catch(function () { return []; })])
      .then(function (r) { fillBadge(el, sym, r[0], r[1], noAnim); })
      .catch(function () {
        el.innerHTML = '<span class="sym">' + esc(sym) + '</span><span class="dim">n/a</span>';
        el.setAttribute('data-loaded', '1');
      });
  }

  function observeBadges() {
    if (observer) observer.disconnect();
    var els = feed.querySelectorAll('.tb[data-sym]');
    if (!('IntersectionObserver' in window)) { Array.prototype.forEach.call(els, function (el) { loadBadge(el); }); return; }
    observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (e.isIntersecting) { observer.unobserve(e.target); loadBadge(e.target); }
      });
    }, { rootMargin: '200px' });
    Array.prototype.forEach.call(els, function (el) { observer.observe(el); });
  }

  function refreshBadges() {
    API.clearCache();
    Array.prototype.forEach.call(feed.querySelectorAll('.tb[data-loaded]'), function (el) { loadBadge(el, true); });
  }

  /* ---------- feed rendering ---------- */
  function cardHTML(a, i) {
    var sent = String(a.sentiment || 'neutral').toLowerCase();
    return '<article class="card" style="animation-delay:' + (i * 40) + 'ms"><div class="in">' +
      '<div class="meta"><span class="src"><i></i><span>' + esc(a.source_name) + '</span></span>' +
      '<span class="age">' + ICON_CLOCK + esc(rel(a.published_at)) + '</span></div>' +
      '<h3>' + esc(a.headline) + '</h3>' +
      '<p>' + esc(a.one_line) + '</p>' +
      '<div class="tags"><span class="tag">' + esc(a.event_type) + '</span><span class="tag ' + esc(sent) + '">' + esc(sent) + '</span></div>' +
      '<div class="tbs">' + (a.tickers || []).map(badgeHTML).join('') + '</div>' +
      '</div></article>';
  }

  function sectionHTML(s, n, arts) {
    return '<section class="sec"><div class="sechead"><div class="l">' +
      '<span class="n">' + (n < 10 ? '0' : '') + n + '</span>' +
      '<h2 style="color:' + s.color + '">' + esc(s.key) + '</h2>' +
      '<span class="cnt">// ' + arts.length + ' ' + (arts.length === 1 ? 'STORY' : 'STORIES') + '</span></div>' +
      '<div class="rule" style="background:linear-gradient(90deg,' + s.color + ',transparent)"></div></div>' +
      '<div class="grid">' + arts.map(cardHTML).join('') + '</div></section>';
  }

  function skeletonHTML() {
    var card = '<article class="card skeleton"><div class="in"><span class="skel" style="width:40%"></span><span class="skel" style="width:90%;height:16px"></span><span class="skel" style="width:70%"></span><span class="skel" style="width:30%"></span></div></article>';
    return '<section class="sec"><div class="grid">' + card + card + '</div></section>';
  }

  function matches(a, q) {
    return [a.headline, a.one_line, a.source_name, a.event_type, (a.tickers || []).join(' ')].join(' ').toLowerCase().indexOf(q) !== -1;
  }

  function renderFeed() {
    var q = state.query.trim().toLowerCase(), html = [], total = 0;
    SECTORS.forEach(function (s) {
      if (state.sector !== 'ALL' && state.sector !== s.key) return;
      var arts = (state.groups && state.groups[s.key]) || [];
      if (q) arts = arts.filter(function (a) { return matches(a, q); });
      if (!arts.length) return;
      total += arts.length;
      html.push(sectionHTML(s, html.length + 1, arts));
    });
    feed.innerHTML = html.length ? html.join('') : '<div class="empty">NO STORIES MATCH' + (q ? ' "' + esc(state.query.trim()) + '"' : '') + '</div>';
    $('#foot-count').textContent = 'TERMINAL.STOCK.NEWS // ' + total + ' STORIES LIVE';
    observeBadges();
  }

  function renderChips() {
    var items = ['ALL'].concat(SECTORS.map(function (s) { return s.key; }));
    chipsEl.innerHTML = items.map(function (k) {
      return '<button class="chip' + (state.sector === k ? ' active' : '') + '" type="button" data-sector="' + k + '">' + k.toUpperCase() + '</button>';
    }).join('');
  }

  /* ---------- header: health + tape ---------- */
  function loadHealth() {
    return API.health().then(function (h) {
      $('#p-last').textContent = h.last_scrape_at ? rel(h.last_scrape_at) : '--';
      $('#p-items').textContent = h.items_found != null ? h.items_found : '--';
      $('#p-err').textContent = h.errors != null ? h.errors : '--';
      var r = h.readiness;
      $('#ready-pct').textContent = r != null ? Math.round(r) + '%' : 'n/a';
      $('#ready-bar').style.width = (r != null ? Math.max(0, Math.min(100, r)) : 0) + '%';
    });
  }

  function loadTape() {
    return Promise.all(cfg.TAPE_SYMBOLS.map(function (s) { return API.quote(s).catch(function () { return null; }); }))
      .then(function (qs) {
        var items = qs.filter(Boolean).map(function (q) {
          var up = q.pct_change >= 0, c = up ? 'up' : 'down';
          return '<div class="mi"><b>' + esc(q.symbol) + '</b><span class="' + c + '">' + Number(q.price).toFixed(2) + '</span>' +
            '<span class="' + c + '">' + (up ? '+' : '-') + Math.abs(q.pct_change).toFixed(2) + '%</span></div>';
        }).join('');
        $('#tape').innerHTML = items + items; // duplicated for a seamless loop
      });
  }

  /* ---------- refresh cycle ---------- */
  function refresh(silent) {
    if (state.busy) return Promise.resolve();
    state.busy = true;
    API.beginCycle();
    API.clearCache();
    var btn = $('#refresh');
    if (!silent) btn.classList.add('spin');

    return Promise.all([
      API.news(SECTORS.map(function (s) { return s.key; })),
      loadHealth().catch(function () {}),
      loadTape().catch(function () {})
    ]).then(function (r) {
      var groups = r[0], sig = JSON.stringify(groups), changed = sig !== state.sig;
      state.groups = groups; state.sig = sig;
      if (changed || !silent) renderFeed(); else refreshBadges();
      banner.hidden = !(API.live && API.usingFallback);
      if (!banner.hidden) banner.textContent = 'API UNREACHABLE // SHOWING MOCK DATA';
    }).catch(function (e) {
      banner.hidden = false;
      banner.textContent = 'FAILED TO LOAD FEED // ' + (e && e.message ? e.message : 'unknown error');
      if (!state.groups) feed.innerHTML = '<div class="empty">Could not load stories. Check API_URL in js/config.js, then press REFRESH.</div>';
    }).then(function () {
      state.busy = false;
      btn.classList.remove('spin');
    });
  }

  /* ---------- TradingView modal ---------- */
  var tvPromise = null, lastFocus = null;
  function loadTV() {
    if (window.TradingView) return Promise.resolve();
    if (!tvPromise) {
      tvPromise = new Promise(function (res, rej) {
        var s = document.createElement('script');
        s.src = 'https://s3.tradingview.com/tv.js';
        s.onload = res;
        s.onerror = function () { tvPromise = null; rej(new Error('tv.js failed')); };
        document.head.appendChild(s);
      });
    }
    return tvPromise;
  }

  function openChart(sym, opener) {
    var modal = $('#modal'), chart = $('#tradingview_chart');
    lastFocus = opener || null;
    $('#modal-title').textContent = sym + ' // CHART';
    chart.innerHTML = '<div class="empty" style="border:0;padding-top:200px">LOADING CHART…</div>';
    modal.hidden = false;
    $('#modal-close').focus();
    loadTV().then(function () {
      chart.innerHTML = '';
      new window.TradingView.widget({
        symbol: EXCHANGE[sym] ? EXCHANGE[sym] + ':' + sym : sym,
        width: '100%', height: 500, theme: 'dark', style: '1', locale: 'en',
        enable_publishing: false, allow_symbol_change: true,
        container_id: 'tradingview_chart'
      });
    }).catch(function () {
      chart.innerHTML = '<div class="empty" style="border:0;padding-top:200px">CHART FAILED TO LOAD // CHECK YOUR CONNECTION</div>';
    });
  }

  function closeChart() {
    $('#modal').hidden = true;
    $('#tradingview_chart').innerHTML = '';
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  /* ---------- events ---------- */
  chipsEl.addEventListener('click', function (e) {
    var b = e.target.closest('.chip[data-sector]');
    if (!b) return;
    state.sector = b.getAttribute('data-sector');
    renderChips();
    renderFeed();
  });

  $('#search').addEventListener('input', function (e) { state.query = e.target.value; renderFeed(); });
  $('#refresh').addEventListener('click', function () { refresh(false); });

  feed.addEventListener('click', function (e) {
    var b = e.target.closest('.tb[data-sym]');
    if (b) openChart(b.getAttribute('data-sym'), b);
  });

  feed.addEventListener('mousemove', function (e) {
    var card = e.target.closest('.card');
    if (!card) return;
    var r = card.getBoundingClientRect();
    card.style.setProperty('--x', (e.clientX - r.left) + 'px');
    card.style.setProperty('--y', (e.clientY - r.top) + 'px');
  });

  $('#modal-close').addEventListener('click', closeChart);
  $('#modal').addEventListener('click', function (e) { if (e.target.id === 'modal') closeChart(); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !$('#modal').hidden) closeChart(); });

  /* ---------- boot ---------- */
  tick(); setInterval(tick, 1000);
  renderChips();
  feed.innerHTML = skeletonHTML() + skeletonHTML();
  refresh(false);
  setInterval(function () { refresh(true); }, cfg.REFRESH_MS || 15000);
})();
