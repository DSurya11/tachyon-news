import { splitBar } from '../charts.js';
import { emptyState, hydrate, starButton } from '../components.js';
import { state } from '../store.js';
import { ago, esc, tickerStats } from '../util.js';

export function renderWatchlist(root) {
  const stats = new Map(tickerStats(state.articles).map((t) => [t.symbol, t]));
  const syms = [...state.watchlist].sort();

  if (!syms.length) {
    const suggestions = tickerStats(state.articles).slice(0, 8);
    root.innerHTML = `<section class="view"><header class="view-head"><div><h1>Watchlist</h1>
      <p class="muted">Star tickers to track their price, 30-day trend and news in one place. Stored in this browser.</p></div></header>
      ${emptyState('Your watchlist is empty', 'Press the ☆ on any ticker — or start with what the news is talking about:',
        `<div class="suggest">${suggestions.map((t) => `<span class="suggest-item"><b class="mono">${esc(t.symbol)}</b>
          <span class="muted">${t.count} stories</span>${starButton(t.symbol)}</span>`).join('')}</div>`)}
    </section>`;
    return;
  }

  root.innerHTML = `<section class="view"><header class="view-head"><div><h1>Watchlist</h1>
    <p class="muted">${syms.length} ticker${syms.length === 1 ? '' : 's'} · click a row for chart and news</p></div></header>
    <div class="panel flush"><table class="table watch">
      <thead><tr><th>Ticker</th><th class="num">Price</th><th>30 days</th><th class="num">Stories · 3d</th><th>Sentiment</th><th>Latest headline</th><th></th></tr></thead>
      <tbody>${syms.map((sym) => {
        const t = stats.get(sym);
        return `<tr data-action="open-ticker" data-sym="${esc(sym)}" tabindex="0">
          <td><b class="mono big">${esc(sym)}</b></td>
          <td class="num mono quote-cell" data-price="${esc(sym)}"><span class="sk w60"></span></td>
          <td data-spark="${esc(sym)}" data-w="110" data-h="28"></td>
          <td class="num mono">${t ? t.count : 0}</td>
          <td>${t ? splitBar(t, { thin: true }) : '<span class="muted">—</span>'}</td>
          <td class="clip">${t ? `<span class="muted mono">${esc(ago(t.latest.published_at))}</span> ${esc(t.latest.headline)}` : '<span class="muted">No recent stories</span>'}</td>
          <td>${starButton(sym)}</td></tr>`;
      }).join('')}</tbody></table></div></section>`;
  hydrate(root);
}
