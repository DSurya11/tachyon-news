/* Command palette, keyboard help and the TradingView chart modal. */
import { icon } from './components.js';
import { navigate } from './router.js';
import { state } from './store.js';
import { $, ago, esc, sectorColor, sectorStats, tickerStats } from './util.js';

let lastFocus = null;

function openOverlay(el, html) {
  lastFocus = document.activeElement;
  el.innerHTML = html;
  el.hidden = false;
  document.body.classList.add('overlay-open');
}

export function closeOverlays() {
  let closed = false;
  for (const id of ['palette', 'help', 'chart-modal']) {
    const el = $(`#${id}`);
    if (!el.hidden) { el.hidden = true; el.innerHTML = ''; closed = true; }
  }
  document.body.classList.remove('overlay-open');
  if (closed && lastFocus?.focus) lastFocus.focus();
  return closed;
}

/** Close when the backdrop (not the dialog) is pressed. Call once at boot. */
export function wireOverlayBackdrops() {
  for (const id of ['palette', 'help', 'chart-modal']) {
    const el = $(`#${id}`);
    el.addEventListener('mousedown', (e) => { if (e.target === el) closeOverlays(); });
  }
}

export const overlayOpen = () => ['palette', 'help', 'chart-modal'].some((id) => !$(`#${id}`).hidden);

/* ───────────── command palette ───────────── */

const VIEW_ITEMS = [
  { kind: 'view', label: 'Overview', hint: 'Go to', run: () => navigate({ view: 'overview', keepQuery: false }) },
  { kind: 'view', label: 'Feed', hint: 'Go to', run: () => navigate({ view: 'feed', keepQuery: false }) },
  { kind: 'view', label: 'Daily brief', hint: 'Go to', run: () => navigate({ view: 'brief', param: null, keepQuery: false }) },
  { kind: 'view', label: 'Watchlist', hint: 'Go to', run: () => navigate({ view: 'watchlist', keepQuery: false }) },
];

function paletteItems(query) {
  const q = query.trim().toLowerCase();
  const items = [];
  const tickers = tickerStats(state.articles);
  const known = new Set(tickers.map((t) => t.symbol));
  for (const s of state.watchlist) if (!known.has(s)) tickers.push({ symbol: s, count: 0 });

  const tick = tickers
    .filter((t) => !q || t.symbol.toLowerCase().startsWith(q))
    .slice(0, q ? 6 : 5)
    .map((t) => ({ kind: 'ticker', label: t.symbol, hint: `${t.count} stories`, run: () => navigate({ query: { t: t.symbol, a: null } }) }));
  // Free-form symbol lookup for tickers not in the news; ranked after real matches.
  const upper = query.trim().toUpperCase();
  const lookup = /^[A-Z][A-Z0-9.-]{0,5}$/.test(upper) && !known.has(upper) && !state.watchlist.has(upper)
    ? [{ kind: 'ticker', label: upper, hint: 'Look up ticker', run: () => navigate({ query: { t: upper, a: null } }) }]
    : [];

  const sectors = sectorStats(state.articles)
    .filter((s) => !q || s.name.toLowerCase().includes(q))
    .slice(0, 4)
    .map((s) => ({ kind: 'sector', label: s.name, hint: `${s.count} stories`, color: sectorColor(s.name),
      run: () => navigate({ view: 'feed', keepQuery: false, query: { sector: s.name } }) }));

  const stories = q.length >= 2
    ? state.articles
      .filter((a) => `${a.headline} ${a.source_name}`.toLowerCase().includes(q))
      .slice(0, 6)
      .map((a) => ({ kind: 'story', label: a.headline, hint: `${a.source_name || ''} · ${ago(a.published_at)}`,
        run: () => navigate({ query: { a: a.id, t: null } }) }))
    : [];

  const views = VIEW_ITEMS.filter((v) => !q || v.label.toLowerCase().includes(q));
  items.push(...tick, ...sectors, ...stories, ...views, ...lookup);
  if (q.length >= 2) {
    items.push({ kind: 'search', label: `Search feed for “${query.trim()}”`, hint: 'Feed',
      run: () => navigate({ view: 'feed', keepQuery: false, query: { q: query.trim() } }) });
  }
  return items;
}

export function openPalette(initial = '') {
  const el = $('#palette');
  openOverlay(el, `<div class="palette" role="dialog" aria-modal="true" aria-label="Command palette">
    <div class="palette-input">
      <svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <input id="palette-q" type="text" placeholder="Ticker, sector, story or view…" autocomplete="off" spellcheck="false"
        role="combobox" aria-expanded="true" aria-controls="palette-list" value="${esc(initial)}">
      <kbd>Esc</kbd>
    </div>
    <ul class="palette-list" id="palette-list" role="listbox"></ul>
    <div class="palette-foot muted"><span><kbd>↑</kbd><kbd>↓</kbd> navigate</span><span><kbd>Enter</kbd> open</span></div>
  </div>`);
  const input = $('#palette-q', el);
  const list = $('#palette-list', el);
  let items = [];
  let active = 0;

  const draw = () => {
    items = paletteItems(input.value);
    active = Math.min(active, Math.max(0, items.length - 1));
    list.innerHTML = items.length
      ? items.map((it, i) => `<li role="option" id="pi-${i}" aria-selected="${i === active}" class="${i === active ? 'on' : ''}" data-i="${i}">
          <span class="pk ${it.kind}">${it.kind === 'sector' ? `<i style="background:${it.color}"></i>` : ''}${it.kind}</span>
          <span class="pl${it.kind === 'ticker' ? ' mono' : ''}">${esc(it.label)}</span><span class="ph muted">${esc(it.hint || '')}</span></li>`).join('')
      : '<li class="palette-empty muted">No matches</li>';
    input.setAttribute('aria-activedescendant', items.length ? `pi-${active}` : '');
    list.querySelector('.on')?.scrollIntoView({ block: 'nearest' });
  };
  const run = (i) => { const it = items[i]; if (!it) return; closeOverlays(); it.run(); };

  input.addEventListener('input', () => { active = 0; draw(); });
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { active = Math.min(items.length - 1, active + 1); draw(); e.preventDefault(); }
    else if (e.key === 'ArrowUp') { active = Math.max(0, active - 1); draw(); e.preventDefault(); }
    else if (e.key === 'Enter') { run(active); e.preventDefault(); }
  });
  list.addEventListener('click', (e) => { const li = e.target.closest('li[data-i]'); if (li) run(+li.dataset.i); });
  draw();
  input.focus();
}

/* ───────────── keyboard help ───────────── */

const SHORTCUTS = [
  ['Ctrl K  ·  /', 'Command palette / search'],
  ['1  2  3  4', 'Overview · Feed · Brief · Watchlist'],
  ['j  /  k', 'Next / previous story (feed)'],
  ['s', 'Star the open ticker'],
  ['r', 'Refresh data'],
  ['t', 'Toggle light / dark'],
  ['Esc', 'Close panel or dialog'],
  ['?', 'This help'],
];

export function openHelp() {
  const el = $('#help');
  openOverlay(el, `<div class="dialog" role="dialog" aria-modal="true" aria-labelledby="help-title">
    <header class="dialog-head"><h2 id="help-title">Keyboard shortcuts</h2>
      <button type="button" class="icon-btn" data-action="close-overlay" aria-label="Close">${icon.close}</button></header>
    <dl class="shortcuts">${SHORTCUTS.map(([k, d]) => `<dt>${k.split('  ').map((x) => `<kbd>${esc(x.trim())}</kbd>`).join(' ')}</dt><dd>${esc(d)}</dd>`).join('')}</dl>
  </div>`);
  el.querySelector('button').focus();
}

/* ───────────── TradingView modal ───────────── */

let tvPromise = null;
function loadTradingView() {
  if (window.TradingView) return Promise.resolve();
  tvPromise ??= new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = 'https://s3.tradingview.com/tv.js';
    s.onload = resolve;
    s.onerror = () => { tvPromise = null; reject(new Error('tv.js failed to load')); };
    document.head.appendChild(s);
  });
  return tvPromise;
}

export function openChart(sym) {
  const el = $('#chart-modal');
  openOverlay(el, `<div class="dialog wide" role="dialog" aria-modal="true" aria-labelledby="tv-title">
    <header class="dialog-head"><h2 id="tv-title" class="mono">${esc(sym)} · advanced chart</h2>
      <button type="button" class="icon-btn" data-action="close-overlay" aria-label="Close chart">${icon.close}</button></header>
    <div id="tv-chart" class="tv-chart"><div class="empty">Loading chart…</div></div>
  </div>`);
  el.querySelector('button').focus();
  loadTradingView().then(() => {
    if (el.hidden) return;
    $('#tv-chart').innerHTML = '';
    // eslint-disable-next-line no-new
    new window.TradingView.widget({
      symbol: sym, autosize: true, interval: 'D', timezone: 'America/New_York',
      theme: document.documentElement.dataset.theme === 'light' ? 'light' : 'dark',
      style: '1', locale: 'en', allow_symbol_change: true, container_id: 'tv-chart',
    });
  }).catch(() => {
    if (!el.hidden) $('#tv-chart').innerHTML = '<div class="empty">Chart failed to load — check your connection.</div>';
  });
}
