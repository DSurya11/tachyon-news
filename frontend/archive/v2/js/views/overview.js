import { netTint, sentimentBars, splitBar } from '../charts.js';
import { articleRow, emptyState, hydrate, icon, skeletonRows, starButton } from '../components.js';
import { firstParagraph, renderMarkdown } from '../markdown.js';
import { href } from '../router.js';
import { state } from '../store.js';
import {
  ago, esc, fmtDay, fmtInt, hourlyBuckets, marketStatus, overallStats, sectorColor, sectorStats, tickerStats,
} from '../util.js';

function kpi(label, value, sub = '', extra = '') {
  return `<div class="kpi"><div class="kpi-label">${esc(label)}</div>
    <div class="kpi-value mono">${value}</div>${sub ? `<div class="kpi-sub">${sub}</div>` : ''}${extra}</div>`;
}

function briefTeaser() {
  const r = state.latestReport;
  if (!r) {
    return `<article class="panel teaser">${emptyState('No daily brief yet',
      'The pipeline writes one once enough stories have been extracted for the trading day.')}</article>`;
  }
  const { html } = renderMarkdown(firstParagraph(r.content));
  const cited = (r.article_ids || []).length;
  return `<article class="panel teaser">
    <header class="panel-head"><h2><span class="eyebrow">Daily brief</span>${esc(fmtDay(r.trading_day))}</h2>
      <span class="muted mono">${esc(ago(r.created_at))} ago${r.provider ? ` · ${esc(r.provider)}` : ''}</span></header>
    <div class="teaser-body prose">${html}</div>
    <footer class="panel-foot"><span class="muted">${cited} sources cited</span>
      <a class="btn primary" href="${href({ view: 'brief' })}">Read the full brief ${icon.arrow}</a></footer>
  </article>`;
}

function heatmap(sectors) {
  if (!sectors.length) return emptyState('No sector data yet');
  const max = Math.max(...sectors.map((s) => s.count));
  return `<div class="heatmap">${sectors.map((s) => {
    const weight = 1 + Math.round((s.count / max) * 5);
    const bias = s.net >= 0.05 ? 'bullish' : s.net <= -0.05 ? 'bearish' : 'mixed';
    return `<a class="heat" style="flex-grow:${weight};background:${netTint(s.net)}" href="${href({ view: 'feed', query: { sector: s.name } })}"
        title="${esc(`${s.name}: ${s.count} stories — ${s.bullish} bullish, ${s.neutral} neutral, ${s.bearish} bearish`)}">
      <span class="heat-name"><i style="background:${sectorColor(s.name)}"></i>${esc(s.name)}</span>
      <span class="heat-count mono">${s.count}</span>
      <span class="heat-bias ${bias}">${bias}</span>
    </a>`;
  }).join('')}</div>`;
}

function movers(tickers) {
  if (!tickers.length) return emptyState('No tickers mentioned yet');
  return `<table class="table movers">
    <thead><tr><th>Ticker</th><th class="num">Mentions</th><th>Sentiment</th><th class="num">Price</th><th>30d</th><th></th></tr></thead>
    <tbody>${tickers.map((t) => `<tr data-action="open-ticker" data-sym="${esc(t.symbol)}" tabindex="0">
      <td><b class="mono">${esc(t.symbol)}</b></td>
      <td class="num mono">${t.count}</td>
      <td>${splitBar(t, { thin: true })}</td>
      <td class="num mono quote-cell" data-price="${esc(t.symbol)}"><span class="sk w60"></span></td>
      <td class="spark-cell" data-spark="${esc(t.symbol)}" data-w="80"></td>
      <td>${starButton(t.symbol)}</td></tr>`).join('')}</tbody></table>`;
}

export function renderOverview(root) {
  if (!state.loaded) {
    root.innerHTML = `<section class="view"><div class="kpis">${'<div class="kpi skeleton"><span class="sk w60"></span><span class="sk w30"></span></div>'.repeat(5)}</div>
      <div class="panel">${skeletonRows(5)}</div></section>`;
    return;
  }
  const arts = state.articles;
  const day = arts.filter((a) => Date.now() - new Date(a.published_at).getTime() < 86400e3);
  const all = overallStats(arts);
  const d24 = overallStats(day);
  const sectors = sectorStats(arts);
  const tickers = tickerStats(arts).slice(0, 12);
  const verifiedPct = all.count ? Math.round((all.verified / all.count) * 100) : 0;
  const netLabel = all.net >= 0.05 ? 'Risk-on' : all.net <= -0.05 ? 'Risk-off' : 'Mixed';
  const mkt = marketStatus();
  const top = arts.filter((a) => a.verified).slice(0, 8);

  root.innerHTML = `<section class="view overview">
    <header class="view-head">
      <div><h1>Market overview</h1>
        <p class="muted">Last ${arts.length ? Math.round((Date.now() - new Date(arts[arts.length - 1].published_at)) / 3600e3) : 0} hours of wire news, extracted and evidence-checked · ${esc(mkt.label.toLowerCase())}, ${esc(mkt.detail)}</p></div>
    </header>

    <div class="kpis">
      ${kpi('Stories · 24h', fmtInt(d24.count), `${fmtInt(all.count)} in the last ${arts.length ? '3 days' : '—'}`)}
      ${kpi('Verified', `${verifiedPct}<small>%</small>`, 'quotes & numbers found in source')}
      ${kpi('Mood · 24h', `<span class="${d24.net >= 0.05 ? 'up' : d24.net <= -0.05 ? 'down' : ''}">${netLabel}</span>`,
        `${d24.bullish} bull · ${d24.neutral} neutral · ${d24.bearish} bear`, splitBar(d24))}
      ${kpi('Active sectors', fmtInt(sectors.length), sectors[0] ? `busiest: ${esc(sectors[0].name)}` : '')}
      ${kpi('Most mentioned', tickers[0] ? `<a href="#" data-action="open-ticker" data-sym="${esc(tickers[0].symbol)}">${esc(tickers[0].symbol)}</a>` : '—',
        tickers[0] ? `${tickers[0].count} stories` : '')}
    </div>

    <div class="grid-2">
      ${briefTeaser()}
      <article class="panel">
        <header class="panel-head"><h2><span class="eyebrow">Sentiment flow</span>Stories per hour · 48h</h2>
          <span class="legend"><i class="bull"></i>bullish <i class="neu"></i>neutral <i class="bear"></i>bearish</span></header>
        ${sentimentBars(hourlyBuckets(arts, 48))}
      </article>
    </div>

    <div class="grid-2 wide-right">
      <article class="panel">
        <header class="panel-head"><h2><span class="eyebrow">Sector heatmap</span>Size = volume · colour = net sentiment</h2></header>
        ${heatmap(sectors)}
      </article>
      <article class="panel">
        <header class="panel-head"><h2><span class="eyebrow">In the news</span>Most-mentioned tickers</h2></header>
        ${movers(tickers)}
      </article>
    </div>

    <article class="panel">
      <header class="panel-head"><h2><span class="eyebrow">Latest</span>Verified stories</h2>
        <a class="btn ghost" href="${href({ view: 'feed', query: { verified: 1 } })}">Open feed ${icon.arrow}</a></header>
      <div class="rows">${top.length ? top.map((a) => articleRow(a, { density: 'compact' })).join('') : emptyState('No verified stories yet')}</div>
    </article>
  </section>`;
  hydrate(root);
}
