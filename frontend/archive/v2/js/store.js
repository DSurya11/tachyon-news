/* Application state + a tiny event bus. Views read state and re-render on events. */

const listeners = new Map();

export function on(event, fn) {
  if (!listeners.has(event)) listeners.set(event, new Set());
  listeners.get(event).add(fn);
  return () => listeners.get(event).delete(fn);
}

export function emit(event, payload) {
  for (const fn of listeners.get(event) || []) fn(payload);
}

function load(key, fallback) {
  try {
    const v = localStorage.getItem(key);
    return v == null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}

function save(key, value) {
  try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ }
}

export const state = {
  loaded: false,
  articles: [],          // newest first
  byId: new Map(),
  seenIds: new Set(),    // ids already shown once — anything else is "new"
  freshIds: new Set(),   // ids that arrived in the latest refresh
  health: null,
  report: null,          // the report currently displayed in the Brief view
  latestReport: null,
  reports: [],
  lastUpdated: null,
  error: null,
  watchlist: new Set(load('tsn.watchlist', [])),
  feedDensity: load('tsn.density', 'comfortable'),
};

export function setArticles(list) {
  const firstLoad = !state.loaded;
  state.articles = list;
  state.byId = new Map(list.map((a) => [a.id, a]));
  state.freshIds = firstLoad ? new Set() : new Set(list.filter((a) => !state.seenIds.has(a.id)).map((a) => a.id));
  for (const a of list) state.seenIds.add(a.id);
  state.loaded = true;
  state.lastUpdated = new Date();
  emit('articles', { fresh: state.freshIds.size });
}

export function toggleWatch(sym) {
  const has = state.watchlist.has(sym);
  if (has) state.watchlist.delete(sym);
  else state.watchlist.add(sym);
  save('tsn.watchlist', [...state.watchlist]);
  emit('watchlist', { sym, added: !has });
  return !has;
}

export function setDensity(d) {
  state.feedDensity = d;
  save('tsn.density', d);
  emit('density');
}

export function setTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', theme === 'light' ? '#f4f6f9' : '#07090c');
  try { localStorage.setItem('tsn.theme', theme); } catch { /* ignore */ }
  emit('theme', theme);
}
