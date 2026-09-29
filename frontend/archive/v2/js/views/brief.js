import { api } from '../api.js';
import { articleRow, emptyState, hydrate, skeletonRows } from '../components.js';
import { renderMarkdown } from '../markdown.js';
import { navigate, route } from '../router.js';
import { emit, state } from '../store.js';
import { ago, esc, fmtDateTime, fmtDay } from '../util.js';

let loadingDay;
let spy;

/** Load the report for the current route (latest, or #/brief/<day>). */
export async function loadBrief() {
  const day = route.param || null;
  const key = day || 'latest';
  if (loadingDay === key) return;
  loadingDay = key;
  state.report = undefined; // loading
  emit('brief');
  try {
    const [report, reports] = await Promise.all([
      !day && state.latestReport ? state.latestReport : api.report(day),
      state.reports.length ? state.reports : api.reports(),
    ]);
    state.report = report;
    state.reports = reports;
  } catch (err) {
    state.report = null;
    state.error = err;
  } finally {
    loadingDay = null;
  }
  emit('brief');
}

function sources(report) {
  const ids = report.article_ids || [];
  const known = ids.map((id) => state.byId.get(id)).filter(Boolean);
  const missing = ids.length - known.length;
  return `<section class="panel sources" id="sources">
    <header class="panel-head"><h2><span class="eyebrow">Sources</span>${ids.length} articles informed this brief</h2></header>
    <div class="rows">${known.map((a) => articleRow(a, { density: 'compact' })).join('')}</div>
    ${missing ? `<p class="muted small">${missing} older source${missing === 1 ? '' : 's'} not in the current 3-day window — click a citation to open it.</p>` : ''}
  </section>`;
}

export function renderBrief(root) {
  spy?.disconnect();
  const r = state.report;
  if (r === undefined) {
    root.innerHTML = `<section class="view"><header class="view-head"><h1>Daily brief</h1></header>
      <div class="panel prose">${skeletonRows(4)}</div></section>`;
    return;
  }
  if (!r) {
    root.innerHTML = `<section class="view"><header class="view-head"><h1>Daily brief</h1></header>
      ${emptyState(route.param ? `No brief for ${fmtDay(route.param)}` : 'No daily brief yet',
        'Briefs are written by the pipeline once enough stories for the trading day have been extracted and verified.')}</section>`;
    return;
  }

  const { html, headings } = renderMarkdown(r.content);
  const history = state.reports || [];
  root.innerHTML = `<section class="view brief">
    <header class="view-head">
      <div><span class="eyebrow">Daily brief · trading day</span><h1>${esc(fmtDay(r.trading_day))}</h1>
        <p class="muted">Written ${esc(fmtDateTime(r.created_at))} (${esc(ago(r.created_at))} ago)${r.provider ? ` by <b>${esc(r.provider)}</b>` : ''}
          · ${(r.article_ids || []).length} sources · every claim links to its source article</p></div>
      ${history.length > 1 ? `<label class="select"><span class="sr">Choose a day</span><select id="brief-day">
        ${history.map((h) => `<option value="${esc(h.trading_day)}"${h.trading_day === r.trading_day ? ' selected' : ''}>${esc(fmtDay(h.trading_day))}</option>`).join('')}
      </select></label>` : ''}
    </header>
    <div class="brief-layout">
      <article class="panel prose brief-body" id="brief-body">${html}</article>
      <nav class="toc" aria-label="Brief sections">
        <div class="eyebrow">Sections</div>
        ${headings.map((h) => `<a href="#" data-action="toc" data-target="${esc(h.id)}">${esc(h.text)}</a>`).join('')}
        <a href="#" data-action="toc" data-target="sources">Sources</a>
      </nav>
    </div>
    ${sources(r)}
    <p class="disclaimer muted small">AI-generated from extracted news; may contain errors. Not investment advice.</p>
  </section>`;

  root.querySelector('#brief-day')?.addEventListener('change', (e) =>
    navigate({ view: 'brief', param: e.target.value, keepQuery: false }));

  // Scroll-spy: highlight the section being read.
  const links = new Map([...root.querySelectorAll('.toc a')].map((a) => [a.dataset.target, a]));
  spy = new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue;
      links.forEach((a) => a.classList.remove('on'));
      links.get(e.target.id)?.classList.add('on');
    }
  }, { root, rootMargin: '0px 0px -70% 0px' });
  root.querySelectorAll('#brief-body h2[id], #sources').forEach((h) => spy.observe(h));
  hydrate(root);
}
