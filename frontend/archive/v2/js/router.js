/*
  Hash router. URLs are shareable and the back button works:
    #/overview
    #/feed?sector=Technology&sent=bearish&verified=1&q=fed
    #/brief                 #/brief/2026-09-28
    #/watchlist
  Any view can carry an inspector:  ?a=<article id>  or  ?t=<ticker>
*/
import { emit } from './store.js';

export const VIEWS = ['overview', 'feed', 'brief', 'watchlist'];

export function parseRoute(hash = location.hash) {
  const raw = hash.replace(/^#\/?/, '');
  const [path, qs = ''] = raw.split('?');
  const [view, param] = path.split('/');
  return {
    view: VIEWS.includes(view) ? view : 'overview',
    param: param ? decodeURIComponent(param) : null,
    query: new URLSearchParams(qs),
  };
}

export let route = parseRoute();

export function href({ view = route.view, param = null, query } = {}) {
  const qs = query instanceof URLSearchParams ? query.toString() : new URLSearchParams(query || {}).toString();
  return `#/${view}${param ? `/${encodeURIComponent(param)}` : ''}${qs ? `?${qs}` : ''}`;
}

/** Navigate by patching the current route. `null` query values delete the key. */
export function navigate({ view, param, query = {}, replace = false, keepQuery = true } = {}) {
  const nextView = view ?? route.view;
  const q = new URLSearchParams(keepQuery && nextView === route.view ? route.query : '');
  // Inspector params survive view changes; filters do not.
  if (nextView !== route.view) {
    for (const k of ['a', 't']) if (route.query.has(k)) q.set(k, route.query.get(k));
  }
  for (const [k, v] of Object.entries(query)) {
    if (v == null || v === '' || v === false) q.delete(k);
    else q.set(k, String(v));
  }
  const url = href({ view: nextView, param: param === undefined ? (nextView === route.view ? route.param : null) : param, query: q });
  if (url === location.hash) return;
  if (replace) history.replaceState(null, '', url);
  else history.pushState(null, '', url);
  handleChange();
}

let currentHash = location.hash;

function handleChange() {
  // Back/forward fires both popstate and hashchange — handle each URL once.
  if (location.hash === currentHash) return;
  currentHash = location.hash;
  const prev = route;
  route = parseRoute();
  emit('route', { prev, route });
}

window.addEventListener('hashchange', handleChange);
window.addEventListener('popstate', handleChange);
