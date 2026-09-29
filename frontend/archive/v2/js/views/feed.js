import { articleRow, emptyState, hydrate, skeletonRows } from '../components.js';
import { navigate, route } from '../router.js';
import { state } from '../store.js';
import { $, EVENT_TYPES, debounce, esc, sectorStats } from '../util.js';

const WINDOWS = { '': 'Any time', '1h': 'Last hour', '6h': 'Last 6 hours', '24h': 'Last 24 hours' };
const WINDOW_MS = { '1h': 3600e3, '6h': 6 * 3600e3, '24h': 86400e3 };

export function feedFilters(q = route.query) {
  return {
    q: (q.get('q') || '').trim(),
    sector: q.get('sector') || '',
    sent: q.get('sent') || '',
    event: q.get('event') || '',
    verified: q.get('verified') === '1',
    win: q.get('win') || '',
  };
}

export function filterArticles(articles, f) {
  const needle = f.q.toLowerCase();
  const since = WINDOW_MS[f.win] ? Date.now() - WINDOW_MS[f.win] : 0;
  return articles.filter((a) =>
    (!f.sector || a.sector === f.sector || (a.sectors || []).includes(f.sector)) &&
    (!f.sent || a.sentiment === f.sent) &&
    (!f.event || a.event_type === f.event) &&
    (!f.verified || a.verified) &&
    (!since || new Date(a.published_at).getTime() >= since) &&
    (!needle || [a.headline, a.one_line, a.source_name, a.sector, (a.tickers || []).join(' ')]
      .join(' ').toLowerCase().includes(needle)));
}

function dayKey(iso) {
  return new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(new Date(iso));
}

function dayLabel(key) {
  const today = dayKey(new Date().toISOString());
  const yesterday = dayKey(new Date(Date.now() - 86400e3).toISOString());
  const pretty = new Date(`${key}T12:00:00Z`).toLocaleDateString('en-US', { weekday: 'long', month: 'short', day: 'numeric', timeZone: 'UTC' });
  return key === today ? `Today · ${pretty}` : key === yesterday ? `Yesterday · ${pretty}` : pretty;
}

const seg = (name, value, current, label) =>
  `<button type="button" class="seg-btn${current === value ? ' on' : ''}" data-filter="${name}" data-value="${esc(value)}"
    aria-pressed="${current === value}">${label}</button>`;

function toolbar(f, total, shown) {
  const sectors = sectorStats(state.articles);
  return `<div class="toolbar" role="search">
    <label class="field grow"><span class="sr">Search stories</span>
      <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><circle cx="11" cy="11" r="7" fill="none" stroke="currentColor" stroke-width="2"/><path d="m20 20-4-4" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>
      <input id="feed-q" type="search" placeholder="Filter stories, tickers, sources…" value="${esc(f.q)}" autocomplete="off" spellcheck="false">
    </label>
    <div class="seg" role="group" aria-label="Sentiment">
      ${seg('sent', '', f.sent, 'All')}${seg('sent', 'bullish', f.sent, '<i class="dot bull"></i>Bull')}
      ${seg('sent', 'neutral', f.sent, '<i class="dot neu"></i>Neutral')}${seg('sent', 'bearish', f.sent, '<i class="dot bear"></i>Bear')}
    </div>
    <label class="select"><span class="sr">Sector</span><select data-filter="sector">
      <option value="">All sectors</option>
      ${sectors.map((s) => `<option value="${esc(s.name)}"${s.name === f.sector ? ' selected' : ''}>${esc(s.name)} (${s.count})</option>`).join('')}
    </select></label>
    <label class="select"><span class="sr">Event type</span><select data-filter="event">
      <option value="">All events</option>
      ${EVENT_TYPES.map((e) => `<option value="${e}"${e === f.event ? ' selected' : ''}>${e}</option>`).join('')}
    </select></label>
    <label class="select"><span class="sr">Time window</span><select data-filter="win">
      ${Object.entries(WINDOWS).map(([k, v]) => `<option value="${k}"${k === f.win ? ' selected' : ''}>${v}</option>`).join('')}
    </select></label>
    <label class="toggle"><input type="checkbox" data-filter="verified"${f.verified ? ' checked' : ''}><span>Verified only</span></label>
    <div class="seg" role="group" aria-label="Density">
      <button type="button" class="seg-btn${state.feedDensity === 'comfortable' ? ' on' : ''}" data-action="density" data-value="comfortable" title="Comfortable">☰</button>
      <button type="button" class="seg-btn${state.feedDensity === 'compact' ? ' on' : ''}" data-action="density" data-value="compact" title="Compact">≡</button>
    </div>
  </div>
  <div class="toolbar-status muted"><span class="mono">${shown}</span> of <span class="mono">${total}</span> stories
    ${Object.values(f).some(Boolean) ? '<button type="button" class="link" data-action="clear-filters">Clear filters</button>' : ''}
    <span class="hint">j / k to move · Enter to open</span></div>`;
}

export function renderFeed(root) {
  if (!state.loaded) {
    root.innerHTML = `<section class="view"><header class="view-head"><h1>Feed</h1></header><div class="rows">${skeletonRows(10)}</div></section>`;
    return;
  }
  const f = feedFilters();
  const list = filterArticles(state.articles, f);
  const selected = route.query.get('a');

  const groups = new Map();
  for (const a of list) {
    const k = dayKey(a.published_at);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(a);
  }
  const fresh = [...state.freshIds].filter((id) => list.some((a) => a.id === id)).length;

  // Preserve the reader's position and the search caret across re-renders.
  const scroller = root;
  const active = document.activeElement;
  const typing = active?.id === 'feed-q' ? [active.selectionStart, active.selectionEnd] : null;
  const anchor = [...root.querySelectorAll('[data-row]')].find((el) => el.getBoundingClientRect().top >= root.getBoundingClientRect().top);
  const anchorId = anchor?.dataset.row;
  const anchorTop = anchor?.getBoundingClientRect().top;

  root.innerHTML = `<section class="view feed density-${state.feedDensity}">
    <header class="view-head"><div><h1>Feed</h1>
      <p class="muted">Every extracted story from the last 3 days, newest first.</p></div></header>
    ${toolbar(f, state.articles.length, list.length)}
    ${fresh ? `<button type="button" class="fresh-pill" data-action="scroll-top">▲ ${fresh} new ${fresh === 1 ? 'story' : 'stories'}</button>` : ''}
    <div class="rows" id="feed-rows">${
      list.length
        ? [...groups.entries()].map(([k, items]) => `<div class="group-head"><span>${esc(dayLabel(k))}</span><span class="mono">${items.length}</span></div>
          ${items.map((a) => articleRow(a, { selected: String(a.id) === selected, fresh: state.freshIds.has(a.id) })).join('')}`).join('')
        : emptyState('No stories match these filters', 'Try widening the time window or clearing filters.',
          '<button type="button" class="btn" data-action="clear-filters">Clear filters</button>')
    }</div>
  </section>`;

  if (anchorId) {
    const el = root.querySelector(`[data-row="${anchorId}"]`);
    if (el) scroller.scrollTop += el.getBoundingClientRect().top - anchorTop;
  }

  const input = $('#feed-q', root);
  if (typing) {
    input.focus({ preventScroll: true });
    input.setSelectionRange(...typing);
  }
  input.addEventListener('input', debounce(() => navigate({ query: { q: input.value.trim() }, replace: true }), 180));
  root.querySelectorAll('select[data-filter]').forEach((el) =>
    el.addEventListener('change', () => navigate({ query: { [el.dataset.filter]: el.value } })));
  root.querySelector('input[data-filter="verified"]').addEventListener('change', (e) =>
    navigate({ query: { verified: e.target.checked ? 1 : null } }));
  root.querySelectorAll('.seg-btn[data-filter]').forEach((b) =>
    b.addEventListener('click', () => navigate({ query: { [b.dataset.filter]: b.dataset.value } })));
  hydrate(root);
}

/** Move the keyboard selection in the feed by `delta` rows and open it. */
export function moveSelection(root, delta) {
  const rows = [...root.querySelectorAll('.row[data-row]')];
  if (!rows.length) return;
  const cur = rows.findIndex((r) => r.classList.contains('selected'));
  const next = rows[Math.max(0, Math.min(rows.length - 1, cur === -1 ? 0 : cur + delta))];
  navigate({ query: { a: next.dataset.row, t: null }, replace: true });
  next.scrollIntoView({ block: 'nearest' });
}
