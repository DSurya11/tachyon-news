/* Reusable HTML fragments + DOM hydration for live quotes and sparklines. */
import { api } from './api.js';
import { sparkline } from './charts.js';
import { state } from './store.js';
import { ago, dirClass, esc, fmtDateTime, fmtPct, fmtPrice, sectorColor } from './util.js';

export const icon = {
  star: (on) => `<svg viewBox="0 0 24 24" width="15" height="15" aria-hidden="true"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z" fill="${on ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>`,
  close: '<svg viewBox="0 0 24 24" width="16" height="16" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
  ext: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  check: '<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true"><path d="m5 12 5 5L20 7" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  arrow: '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
  overview: '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><rect x="3" y="3" width="7" height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="14" y="3" width="7" height="5" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="14" y="12" width="7" height="9" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/><rect x="3" y="16" width="7" height="5" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.8"/></svg>',
  feed: '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M4 6h16M4 12h16M4 18h10" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  brief: '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="M6 3h9l4 4v14H6z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/><path d="M9 11h7M9 15h7M9 7h3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>',
  watchlist: '<svg viewBox="0 0 24 24" width="17" height="17" aria-hidden="true"><path d="m12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2L12 17.3 6.4 20.2l1.1-6.2L3 9.6l6.2-.9z" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linejoin="round"/></svg>',
};

export const sentTag = (s) => {
  const v = ['bullish', 'bearish'].includes(s) ? s : 'neutral';
  return `<span class="tag sent-${v}">${v}</span>`;
};

export const eventTag = (e) => (e ? `<span class="tag">${esc(e)}</span>` : '');

export const verifiedTag = (a) =>
  a.verified
    ? `<span class="tag verified" title="Evidence quote and every number were found in the article text">${icon.check}verified</span>`
    : '';

export const sectorLabel = (s) =>
  `<span class="sector-label"><i style="background:${sectorColor(s)}"></i>${esc(s || 'Macro & Markets')}</span>`;

/** Ticker chip; live quote filled in by hydrate(). */
export const tickerChip = (sym) =>
  `<button type="button" class="tchip" data-action="open-ticker" data-sym="${esc(sym)}" data-quote="${esc(sym)}">
     <b>${esc(sym)}</b><span class="q-pct mono"></span></button>`;

export function articleRow(a, { density = state.feedDensity, selected = false, fresh = false } = {}) {
  const sent = ['bullish', 'bearish'].includes(a.sentiment) ? a.sentiment : 'neutral';
  return `<article class="row s-${sent}${selected ? ' selected' : ''}${fresh ? ' fresh' : ''}" data-row="${a.id}"
      data-action="open-article" data-id="${a.id}" tabindex="-1" aria-selected="${selected}">
    <div class="row-time mono" title="${esc(fmtDateTime(a.published_at))}">${esc(ago(a.published_at))}</div>
    <div class="row-body">
      <h3 class="row-title">${esc(a.headline)}</h3>
      ${density === 'compact' || !a.one_line ? '' : `<p class="row-sub">${esc(a.one_line)}</p>`}
      <div class="row-meta">
        <span class="src">${esc(a.source_name || '')}</span>
        ${sectorLabel(a.sector)}
        ${sentTag(a.sentiment)}${eventTag(a.event_type)}${verifiedTag(a)}
      </div>
    </div>
    <div class="row-tickers">${(a.tickers || []).slice(0, 4).map(tickerChip).join('')}</div>
  </article>`;
}

export const skeletonRows = (n = 6) =>
  Array.from({ length: n }, () => `<div class="row skeleton"><span class="sk w20"></span><div class="row-body">
    <span class="sk w80"></span><span class="sk w60"></span><span class="sk w30"></span></div></div>`).join('');

export const emptyState = (title, body = '', action = '') =>
  `<div class="empty"><div class="empty-title">${esc(title)}</div>${body ? `<p>${body}</p>` : ''}${action}</div>`;

export const starButton = (sym) => {
  const on = state.watchlist.has(sym);
  return `<button type="button" class="star${on ? ' on' : ''}" data-action="toggle-watch" data-sym="${esc(sym)}"
    aria-pressed="${on}" aria-label="${on ? 'Remove' : 'Add'} ${esc(sym)} ${on ? 'from' : 'to'} watchlist"
    title="${on ? 'Remove from' : 'Add to'} watchlist (S)">${icon.star(on)}</button>`;
};

function fillQuotes(els, quotes) {
  for (const el of els) {
    const q = quotes.get(el.dataset.quote || el.dataset.price);
    if (el.dataset.quote) {
      const pct = el.querySelector('.q-pct');
      if (pct) {
        pct.textContent = q ? fmtPct(q.pct_change) : '';
        pct.className = `q-pct mono ${q ? dirClass(q.pct_change) : ''}`;
      }
      if (q) el.title = `${q.symbol} ${fmtPrice(q.price)} (${fmtPct(q.pct_change)})${q.stale ? ' · last close' : ''}`;
    } else {
      el.innerHTML = q
        ? `<span class="px">${fmtPrice(q.price)}</span><span class="chg ${dirClass(q.pct_change)}">${fmtPct(q.pct_change)}</span>`
        : '<span class="dim">n/a</span>';
      if (q?.stale) el.title = `Last close${q.as_of ? ` (${q.as_of})` : ''}`;
    }
  }
}

async function loadQuotesInto(els) {
  if (!els.length) return;
  const syms = [...new Set(els.map((el) => el.dataset.quote || el.dataset.price))];
  fillQuotes(els, await api.quotes(syms));
}

/* Ticker chips can number in the hundreds (feed, sources), so their quotes load
   lazily: only chips scrolled into view are fetched, batched into one request. */
const observed = new Set();
const pending = new Set();
let flushTimer;
const chipObserver = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    chipObserver.unobserve(e.target);
    observed.delete(e.target);
    pending.add(e.target);
  }
  clearTimeout(flushTimer);
  flushTimer = setTimeout(() => {
    const els = [...pending].filter((el) => el.isConnected);
    pending.clear();
    loadQuotesInto(els);
  }, 100);
}, { rootMargin: '200px 0px' });

function observeChips(root) {
  for (const el of observed) {
    if (!el.isConnected) { chipObserver.unobserve(el); observed.delete(el); }
  }
  for (const el of root.querySelectorAll('[data-quote]')) {
    observed.add(el);
    chipObserver.observe(el);
  }
}

/**
 * Fill live data inside `root`: [data-price] cells and [data-spark] sparklines now
 * (a handful per view), [data-quote] ticker chips lazily as they scroll into view.
 */
export async function hydrate(root) {
  if (!root) return;
  observeChips(root);
  await Promise.all([
    loadQuotesInto([...root.querySelectorAll('[data-price]')]),
    ...[...root.querySelectorAll('[data-spark]')].map(async (el) => {
      const d = await api.candles(el.dataset.spark);
      el.innerHTML = sparkline(d.candles || [], { width: +(el.dataset.w || 72), height: +(el.dataset.h || 22) });
    }),
  ]);
}
