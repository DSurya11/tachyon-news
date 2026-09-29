/* Right-hand inspector: article details or a ticker profile. */
import { api } from './api.js';
import { priceChart, splitBar } from './charts.js';
import {
  articleRow, emptyState, eventTag, hydrate, icon, sectorLabel, sentTag, skeletonRows, starButton, tickerChip, verifiedTag,
} from './components.js';
import { href, navigate, route } from './router.js';
import { state } from './store.js';
import {
  $, dirClass, esc, fmtDateTime, fmtPct, fmtPrice, hostOf, safeUrl, tickerStats,
} from './util.js';

const panel = () => $('#inspector');
let token = 0; // discards responses for an inspector that was closed or replaced

const head = (label, extra = '') => `<header class="insp-head">
  <span class="eyebrow">${esc(label)}</span>
  <div class="insp-actions">${extra}
    <button type="button" class="icon-btn" data-action="close-inspector" aria-label="Close details (Esc)" title="Close (Esc)">${icon.close}</button>
  </div></header>`;

function extractionBlock(ext) {
  if (!ext) return '';
  const facts = (ext.key_facts || []).filter(Boolean);
  const numbers = (ext.numbers || []).filter((n) => n && n.value);
  return `
    ${facts.length ? `<section class="insp-sec"><h4>Key facts</h4><ul class="facts">${facts.map((f) => `<li>${esc(f)}</li>`).join('')}</ul></section>` : ''}
    ${numbers.length ? `<section class="insp-sec"><h4>Numbers</h4><table class="table nums">${numbers.map((n) =>
      `<tr><td class="mono num">${esc(n.value)}${n.unit ? ` <span class="muted">${esc(n.unit)}</span>` : ''}</td><td>${esc(n.context || '')}</td></tr>`).join('')}</table></section>` : ''}
    ${ext.evidence ? `<section class="insp-sec"><h4>Evidence</h4><blockquote class="evidence">${esc(ext.evidence)}</blockquote></section>` : ''}
    ${ext.model_used ? `<p class="muted small">Extracted by <span class="mono">${esc(ext.model_used)}</span></p>` : ''}`;
}

export async function showArticle(id) {
  const my = ++token;
  const el = panel();
  const cached = state.byId.get(+id);
  const renderBody = (a, full) => {
    const url = safeUrl(a.url);
    const cited = (state.latestReport?.article_ids || []).includes(+id);
    el.innerHTML = `${head('Story', url ? `<a class="icon-btn" href="${esc(url)}" target="_blank" rel="noopener noreferrer" aria-label="Open source article" title="Open source">${icon.ext}</a>` : '')}
    <div class="insp-body">
      <div class="insp-meta"><span class="src">${esc(a.source_name || '')}</span><span class="muted">${esc(fmtDateTime(a.published_at))}</span></div>
      <h2 class="insp-title">${esc(a.headline)}</h2>
      <div class="tags-row">${sectorLabel(a.sector)}${sentTag(a.sentiment)}${eventTag(a.event_type)}${verifiedTag(a)}</div>
      ${a.one_line ? `<p class="insp-lede">${esc(a.one_line)}</p>` : ''}
      ${cited ? `<a class="callout" href="${href({ view: 'brief' })}">${icon.brief}<span>Cited in today's brief</span>${icon.arrow}</a>` : ''}
      ${a.verified
        ? '<p class="note ok">✓ Verified — the model’s evidence quote and every extracted number were found in the article text.</p>'
        : a.status === 'extracted' ? '<p class="note">Not fully verified — the quote or a number could not be matched to the article text, or only the headline was available.</p>' : ''}
      ${(a.tickers || []).length ? `<section class="insp-sec"><h4>Tickers</h4><div class="chips">${a.tickers.map(tickerChip).join('')}</div></section>` : ''}
      ${full === undefined ? `<div class="insp-sec">${skeletonRows(2)}</div>` : extractionBlock(full?.extraction)}
      ${url ? `<a class="btn primary block" href="${esc(url)}" target="_blank" rel="noopener noreferrer">Read at ${esc(hostOf(url) || 'source')} ${icon.ext}</a>` : ''}
    </div>`;
    hydrate(el);
  };

  if (cached) renderBody(cached, undefined);
  else el.innerHTML = `${head('Story')}<div class="insp-body">${skeletonRows(3)}</div>`;

  try {
    const full = await api.article(id);
    if (my !== token) return;
    if (!full) {
      el.innerHTML = `${head('Story')}<div class="insp-body">${emptyState('Story not found')}</div>`;
      return;
    }
    renderBody({ ...full, ...(cached || {}) }, full);
  } catch {
    if (my !== token) return;
    if (cached) renderBody(cached, null);
    else el.innerHTML = `${head('Story')}<div class="insp-body">${emptyState('Could not load this story')}</div>`;
  }
}

export async function showTicker(sym) {
  const my = ++token;
  const el = panel();
  const local = tickerStats(state.articles).find((t) => t.symbol === sym);
  el.innerHTML = `${head('Ticker', starButton(sym))}
  <div class="insp-body">
    <div class="tk-head">
      <h2 class="tk-sym mono">${esc(sym)}</h2>
      <div class="tk-quote" id="tk-quote"><span class="sk w60"></span></div>
    </div>
    <div class="chart-box" id="tk-chart"><div class="sk chart-sk"></div></div>
    <div class="tk-stats" id="tk-stats"></div>
    <div class="tk-links">
      <button type="button" class="btn" data-action="tv-chart" data-sym="${esc(sym)}">Advanced chart</button>
      <a class="btn ghost" href="https://finance.yahoo.com/quote/${encodeURIComponent(sym.replace('.', '-'))}" target="_blank" rel="noopener noreferrer">Yahoo Finance ${icon.ext}</a>
      <a class="btn ghost" href="${href({ view: 'feed', query: { q: sym } })}">Filter feed</a>
    </div>
    <section class="insp-sec"><h4>News · 30 days</h4><div class="rows" id="tk-news">${skeletonRows(3)}</div></section>
  </div>`;

  const [quotes, candles, news] = await Promise.all([
    api.quotes([sym]),
    api.candles(sym),
    api.tickerNews(sym).catch(() => (local ? state.articles.filter((a) => (a.tickers || []).includes(sym)) : [])),
  ]);
  if (my !== token) return;

  const q = quotes.get(sym);
  $('#tk-quote', el).innerHTML = q
    ? `<span class="tk-price mono">${fmtPrice(q.price)}</span>
       <span class="tk-chg mono ${dirClass(q.pct_change)}">${q.change >= 0 ? '+' : ''}${fmtPrice(q.change)} (${fmtPct(q.pct_change)})</span>
       <span class="muted small">${q.stale ? `Last close${q.as_of ? ` · ${esc(q.as_of)}` : ''}` : 'Live · Finnhub'}</span>`
    : '<span class="muted">No quote available</span>';

  const closes = candles.candles || [];
  priceChart($('#tk-chart', el), candles.dates || [], closes);

  const sentiment = news.reduce((t, a) => { t[a.sentiment in t ? a.sentiment : 'neutral'] += 1; return t; },
    { bullish: 0, neutral: 0, bearish: 0 });
  const chg30 = closes.length > 1 ? ((closes[closes.length - 1] - closes[0]) / closes[0]) * 100 : null;
  $('#tk-stats', el).innerHTML = `
    <div><span class="muted">30d change</span><b class="mono ${dirClass(chg30)}">${fmtPct(chg30)}</b></div>
    <div><span class="muted">30d range</span><b class="mono">${closes.length ? `${fmtPrice(Math.min(...closes))} – ${fmtPrice(Math.max(...closes))}` : '—'}</b></div>
    <div><span class="muted">Stories · 30d</span><b class="mono">${news.length}</b></div>
    <div class="wide"><span class="muted">News sentiment</span>${splitBar(sentiment)}</div>`;

  const selected = route.query.get('a');
  $('#tk-news', el).innerHTML = news.length
    ? news.map((a) => articleRow(a, { density: 'compact', selected: String(a.id) === selected })).join('')
    : emptyState('No stories in the last 30 days');
}

/** Show / hide the inspector according to the current route. */
export function syncInspector() {
  const el = panel();
  const a = route.query.get('a');
  const t = route.query.get('t');
  const open = Boolean(a || t);
  el.hidden = !open;
  document.body.classList.toggle('inspecting', open);
  $('#scrim').hidden = !open;
  if (!open) { token++; return; }
  const key = a ? `a:${a}` : `t:${t}`;
  if (el.dataset.key === key) return;
  el.dataset.key = key;
  el.scrollTop = 0;
  if (a) showArticle(a); else showTicker(t);
}

export function refreshInspector() {
  delete panel().dataset.key;
  syncInspector();
}

export const closeInspector = () => navigate({ query: { a: null, t: null } });
