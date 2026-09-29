/* Boot, data refresh, routing, global interactions. */
import { api } from './api.js';
import { splitBar } from './charts.js';
import { icon } from './components.js';
import config from './config.js';
import { closeInspector, refreshInspector, syncInspector } from './inspector.js';
import { closeOverlays, openChart, openHelp, openPalette, overlayOpen, wireOverlayBackdrops } from './overlays.js';
import { href, navigate, route } from './router.js';
import { on, setArticles, setDensity, setTheme, state, toggleWatch } from './store.js';
import { $, $$, ago, dirClass, esc, etClock, fmtPct, fmtPrice, marketStatus, sectorColor, sectorStats } from './util.js';
import { loadBrief, renderBrief } from './views/brief.js';
import { moveSelection, renderFeed } from './views/feed.js';
import { renderOverview } from './views/overview.js';
import { renderWatchlist } from './views/watchlist.js';

const main = $('#main');
const VIEW_RENDERERS = { overview: renderOverview, feed: renderFeed, brief: renderBrief, watchlist: renderWatchlist };
const NAV = [
  { view: 'overview', label: 'Overview', short: 'Overview', key: '1' },
  { view: 'feed', label: 'Feed', short: 'Feed', key: '2' },
  { view: 'brief', label: 'Daily brief', short: 'Brief', key: '3' },
  { view: 'watchlist', label: 'Watchlist', short: 'Watchlist', key: '4' },
];

/* ───────────── toasts & banner ───────────── */

export function toast(message, kind = 'info') {
  const el = document.createElement('div');
  el.className = `toast ${kind}`;
  el.textContent = message;
  $('#toasts').appendChild(el);
  setTimeout(() => el.classList.add('out'), 3200);
  setTimeout(() => el.remove(), 3700);
}

function setBanner(html) {
  const b = $('#banner');
  b.hidden = !html;
  b.innerHTML = html || '';
}

/* ───────────── chrome: rail, tab bar, tape, clock ───────────── */

function navCount(view) {
  if (view === 'feed') return state.loaded ? state.articles.length : '';
  if (view === 'watchlist') return state.watchlist.size || '';
  if (view === 'brief') return state.latestReport ? '●' : '';
  return '';
}

function renderRail() {
  const sectors = state.loaded ? sectorStats(state.articles) : [];
  const activeSector = route.view === 'feed' ? route.query.get('sector') : null;
  const h = state.health;
  const status = !h ? 'unknown' : h.status === 'ok' ? 'ok' : h.status === 'degraded' ? 'warn' : 'err';
  const readiness = h?.readiness ?? null;

  $('#rail').innerHTML = `
    <div class="rail-nav">${NAV.map((n) => `<a class="nav-item${route.view === n.view ? ' on' : ''}" href="${href({ view: n.view })}"
        ${route.view === n.view ? 'aria-current="page"' : ''} data-nav="${n.view}">
        ${icon[n.view]}<span>${n.label}</span><span class="nav-count mono">${navCount(n.view)}</span></a>`).join('')}</div>

    <div class="rail-section">
      <div class="rail-title"><span>Sectors</span><span class="muted">3 days</span></div>
      ${sectors.length ? sectors.map((s) => `<a class="sector-item${activeSector === s.name ? ' on' : ''}"
          href="${href({ view: 'feed', query: { sector: s.name } })}" title="${esc(`${s.bullish} bullish · ${s.neutral} neutral · ${s.bearish} bearish`)}">
          <span class="sector-top"><i style="background:${sectorColor(s.name)}"></i><span class="sector-name">${esc(s.name)}</span>
          <span class="mono muted">${s.count}</span></span>${splitBar(s, { thin: true })}</a>`).join('')
        : '<div class="rail-skel">' + '<span class="sk w80"></span>'.repeat(6) + '</div>'}
    </div>

    <div class="rail-section pipeline">
      <div class="rail-title"><span>Pipeline</span><span class="status-dot ${status}" title="API status: ${esc(h?.status || 'unknown')}"></span></div>
      <dl class="kv">
        <dt>Last scrape</dt><dd class="mono">${h?.last_scrape_at ? `${esc(ago(h.last_scrape_at))} ago` : '—'}</dd>
        <dt>Stories · 24h</dt><dd class="mono">${h?.articles_24h ?? '—'}</dd>
        <dt>Latest brief</dt><dd class="mono">${esc(h?.latest_report_day || '—')}</dd>
      </dl>
      <div class="readiness" title="Days of extracted coverage toward the ${esc(String(h?.days_with_data ?? 0))}/${60}-day readiness goal">
        <div class="readiness-top"><span class="muted">Data readiness</span><span class="mono">${readiness == null ? '—' : `${Math.round(readiness)}%`}</span></div>
        <div class="meter"><i style="width:${Math.max(0, Math.min(100, readiness || 0))}%"></i></div>
      </div>
      ${api.demo ? '<p class="muted small">Demo data — API not connected.</p>' : ''}
    </div>
    <p class="rail-foot muted small">Not investment advice. Data may be delayed.</p>`;
}

function renderTabbar() {
  $('#tabbar').innerHTML = NAV.map((n) => `<a class="tab${route.view === n.view ? ' on' : ''}" href="${href({ view: n.view })}"
    ${route.view === n.view ? 'aria-current="page"' : ''}>${icon[n.view]}<span>${n.short}</span></a>`).join('');
}

async function renderTape() {
  const quotes = await api.quotes(config.TAPE_SYMBOLS);
  const items = config.TAPE_SYMBOLS.map((s) => quotes.get(s)).filter(Boolean)
    .map((q) => `<button type="button" class="tape-item" data-action="open-ticker" data-sym="${esc(q.symbol)}">
      <b>${esc(q.symbol)}</b><span class="mono">${fmtPrice(q.price)}</span><span class="mono ${dirClass(q.pct_change)}">${fmtPct(q.pct_change)}</span></button>`)
    .join('');
  $('#tape').innerHTML = items ? items + items : ''; // doubled for a seamless loop
  $('#tape').parentElement.hidden = !items;
}

function tickClock() {
  $('#clock').textContent = etClock();
}

function renderMarketPill() {
  const m = marketStatus();
  const pill = $('#market-pill');
  pill.className = `market-pill ${m.state}`;
  pill.innerHTML = `<i></i><span>${esc(m.label)}</span><span class="muted">${esc(m.detail)}</span>`;
}

/* ───────────── views ───────────── */

function renderView() {
  VIEW_RENDERERS[route.view](main);
  document.title = `${NAV.find((n) => n.view === route.view).label} — Tachyon News`;
}

const viewKey = (r) => {
  const q = new URLSearchParams(r.query);
  q.delete('a');
  q.delete('t');
  return `${r.view}|${r.param || ''}|${q.toString()}`;
};

function markSelection() {
  const a = route.query.get('a');
  for (const row of $$('.row[data-row]')) {
    const on = row.dataset.row === a;
    row.classList.toggle('selected', on);
    row.setAttribute('aria-selected', String(on));
  }
}

on('route', ({ prev }) => {
  closeOverlays();
  if (viewKey(prev) !== viewKey(route)) {
    if (route.view === 'brief' && (prev.view !== 'brief' || prev.param !== route.param)) loadBrief();
    renderView();
    if (prev.view !== route.view) main.scrollTop = 0;
    renderRail();
    renderTabbar();
  } else {
    markSelection();
  }
  syncInspector();
});

on('articles', ({ fresh }) => {
  renderRail();
  if (route.view !== 'brief') renderView();
  if (fresh > 0) toast(`${fresh} new ${fresh === 1 ? 'story' : 'stories'}`, 'info');
});

on('brief', () => { if (route.view === 'brief') renderView(); });
on('density', () => { if (route.view === 'feed') renderView(); });
on('watchlist', ({ sym, added }) => {
  for (const b of $$(`.star[data-sym="${CSS.escape(sym)}"]`)) {
    b.classList.toggle('on', added);
    b.setAttribute('aria-pressed', String(added));
    b.innerHTML = icon.star(added);
  }
  if (route.view === 'watchlist') renderView();
  renderRail();
  toast(added ? `${sym} added to watchlist` : `${sym} removed from watchlist`, added ? 'ok' : 'info');
});

/* ───────────── data ───────────── */

let refreshing = false;

async function refresh({ manual = false } = {}) {
  if (refreshing) return;
  refreshing = true;
  $('[data-action="refresh"]').classList.add('spinning');
  if (manual) api.clearCaches();
  try {
    const [news, health, report] = await Promise.allSettled([api.news(), api.health(), api.report()]);
    if (health.status === 'fulfilled') state.health = health.value;
    if (report.status === 'fulfilled') {
      const changed = report.value?.created_at !== state.latestReport?.created_at;
      state.latestReport = report.value;
      if (changed && route.view === 'brief' && !route.param) { state.report = report.value; state.reports = []; loadBrief(); }
    }
    if (news.status === 'fulfilled') setArticles(news.value);
    else throw news.reason;
    state.error = null;
    setBanner(api.demo
      ? `Showing <b>demo data</b> — the API at <span class="mono">${esc(config.API_URL || '(not configured)')}</span> is not reachable. Start it with <span class="mono">make up</span>.`
      : state.health?.status === 'error' ? 'The API is up but its database is unreachable — showing the last data received.' : '');
    renderTape();
    if (manual) { refreshInspector(); toast('Data refreshed', 'ok'); }
  } catch (err) {
    state.error = err;
    setBanner(`Could not refresh data (${esc(err.message || 'network error')}). Retrying automatically.`);
    if (!state.loaded) renderView();
  } finally {
    refreshing = false;
    $('[data-action="refresh"]').classList.remove('spinning');
    renderRail();
  }
}

/* ───────────── interactions ───────────── */

const ACTIONS = {
  palette: () => openPalette(),
  refresh: () => refresh({ manual: true }),
  theme: () => setTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'),
  help: () => openHelp(),
  'open-article': (el) => navigate({ query: { a: el.dataset.id, t: null } }),
  'open-ticker': (el) => navigate({ query: { t: el.dataset.sym, a: null } }),
  'close-inspector': () => closeInspector(),
  'close-overlay': () => closeOverlays(),
  'toggle-watch': (el) => toggleWatch(el.dataset.sym),
  density: (el) => setDensity(el.dataset.value),
  'clear-filters': () => navigate({ view: 'feed', keepQuery: false }),
  'scroll-top': () => { main.scrollTo({ top: 0, behavior: 'smooth' }); state.freshIds.clear(); },
  'tv-chart': (el) => openChart(el.dataset.sym),
  toc: (el) => $(`#${CSS.escape(el.dataset.target)}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' }),
};

document.addEventListener('click', (e) => {
  const el = e.target.closest('[data-action]');
  if (!el || !ACTIONS[el.dataset.action]) return;
  if (el.tagName === 'A' && (e.metaKey || e.ctrlKey)) return; // let modified clicks open tabs
  if (el.dataset.action === 'open-article' && e.target.closest('a[href]:not([data-action]), button:not([data-action="open-article"])')) return;
  e.preventDefault();
  ACTIONS[el.dataset.action](el);
});

document.addEventListener('keydown', (e) => {
  // Enter/Space on focusable table rows
  if ((e.key === 'Enter' || e.key === ' ') && e.target.matches('tr[data-action]')) {
    e.preventDefault();
    ACTIONS[e.target.dataset.action]?.(e.target);
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    if (overlayOpen()) closeOverlays(); else openPalette();
    return;
  }
  if (e.key === 'Escape') {
    if (closeOverlays()) return;
    if (!$('#inspector').hidden) { closeInspector(); return; }
    if (document.activeElement?.id === 'feed-q') document.activeElement.blur();
    return;
  }
  const typing = e.target.closest('input, select, textarea, [contenteditable="true"]');
  if (typing || overlayOpen() || e.ctrlKey || e.metaKey || e.altKey) return;

  const k = e.key;
  const nav = NAV.find((n) => n.key === k);
  if (nav) { navigate({ view: nav.view, keepQuery: false }); return; }
  if (k === '/') { e.preventDefault(); if (route.view === 'feed') $('#feed-q')?.focus(); else openPalette(); return; }
  if (k === '?') { openHelp(); return; }
  if (k === 'r') { refresh({ manual: true }); return; }
  if (k === 't') { ACTIONS.theme(); return; }
  if (k === 's' && route.query.get('t')) { toggleWatch(route.query.get('t')); return; }
  if ((k === 'j' || k === 'k') && route.view === 'feed') { moveSelection(main, k === 'j' ? 1 : -1); }
});

/* Citation hover previews in the brief. */
const popover = $('#popover');
let popTimer;
document.addEventListener('pointerover', (e) => {
  const cite = e.target.closest('a.cite');
  if (!cite) return;
  clearTimeout(popTimer);
  popTimer = setTimeout(async () => {
    const id = +cite.dataset.id;
    const local = state.byId.get(id);
    const place = (a) => {
      if (!cite.isConnected || !cite.matches(':hover')) return;
      popover.innerHTML = a
        ? `<div class="pop-meta mono">[${id}] ${esc(a.source_name || '')} · ${esc(ago(a.published_at))} ago</div>
           <div class="pop-title">${esc(a.headline)}</div>${a.one_line ? `<div class="pop-sub">${esc(a.one_line)}</div>` : ''}
           <div class="pop-hint muted">Click to open</div>`
        : `<div class="pop-title">Source #${id}</div><div class="pop-hint muted">Click to open</div>`;
      popover.hidden = false;
      const r = cite.getBoundingClientRect();
      const w = Math.min(360, innerWidth - 24);
      popover.style.width = `${w}px`;
      popover.style.left = `${Math.max(12, Math.min(innerWidth - w - 12, r.left + r.width / 2 - w / 2))}px`;
      const below = r.bottom + 8;
      popover.style.top = `${below + popover.offsetHeight > innerHeight ? r.top - popover.offsetHeight - 8 : below}px`;
    };
    if (local) place(local);
    else api.article(id).then(place).catch(() => place(null));
  }, 120);
});
document.addEventListener('pointerout', (e) => {
  if (e.target.closest('a.cite')) { clearTimeout(popTimer); popover.hidden = true; }
});

/* ───────────── boot ───────────── */

async function boot() {
  const isMac = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent);
  $('#kbd-hint').textContent = isMac ? '⌘K' : 'Ctrl K';
  wireOverlayBackdrops();
  tickClock();
  renderMarketPill();
  setInterval(tickClock, 1000);
  setInterval(renderMarketPill, 30_000);

  renderRail();
  renderTabbar();
  renderView();
  syncInspector();

  await api.probe();
  if (route.view === 'brief') loadBrief();
  await refresh();

  setInterval(() => { if (!document.hidden) refresh(); }, config.REFRESH_MS);
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden && state.lastUpdated && Date.now() - state.lastUpdated > config.REFRESH_MS) refresh();
  });
}

boot();
