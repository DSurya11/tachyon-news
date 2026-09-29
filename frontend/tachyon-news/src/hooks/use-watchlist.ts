import { useSyncExternalStore } from 'react'

const KEY = 'tsn.watchlist'
const listeners = new Set<() => void>()
let cache: string[] = read()

function read(): string[] {
  try { return JSON.parse(localStorage.getItem(KEY) || '[]') } catch { return [] }
}

function write(next: string[]) {
  cache = next
  try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* private mode */ }
  listeners.forEach((l) => l())
}

window.addEventListener('storage', (e) => {
  if (e.key === KEY) { cache = read(); listeners.forEach((l) => l()) }
})

export function useWatchlist() {
  const list = useSyncExternalStore((cb) => { listeners.add(cb); return () => listeners.delete(cb) }, () => cache)
  return {
    list,
    has: (s: string) => list.includes(s),
    toggle: (s: string) => {
      const on = !cache.includes(s)
      write(on ? [...cache, s].sort() : cache.filter((x) => x !== s))
      return on
    },
  }
}
