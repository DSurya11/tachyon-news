import type { Article, Sentiment } from './types'

export interface Tally { count: number; bullish: number; neutral: number; bearish: number; verified: number; net: number }

export function tally(items: Article[]): Tally {
  const t = { count: items.length, bullish: 0, neutral: 0, bearish: 0, verified: 0, net: 0 }
  for (const a of items) {
    const s: Sentiment = a.sentiment === 'bullish' || a.sentiment === 'bearish' ? a.sentiment : 'neutral'
    t[s] += 1
    if (a.verified) t.verified += 1
  }
  t.net = t.count ? (t.bullish - t.bearish) / t.count : 0
  return t
}

export function bySector(articles: Article[]) {
  const groups = new Map<string, Article[]>()
  for (const a of articles) {
    const k = a.sector || 'Macro & Markets'
    groups.set(k, [...(groups.get(k) ?? []), a])
  }
  return [...groups.entries()]
    .map(([name, items]) => ({ name, ...tally(items) }))
    .sort((x, y) => y.count - x.count || x.name.localeCompare(y.name))
}

export function byTicker(articles: Article[]) {
  const map = new Map<string, Article[]>()
  for (const a of articles) for (const s of a.tickers ?? []) map.set(s, [...(map.get(s) ?? []), a])
  return [...map.entries()]
    .map(([symbol, items]) => ({ symbol, latest: items[0], sector: items[0].sector, ...tally(items) }))
    .sort((x, y) => y.count - x.count || x.symbol.localeCompare(y.symbol))
}

export const moodWord = (net: number) =>
  net >= 0.12 ? 'Risk-on' : net >= 0.04 ? 'Leaning bullish' : net <= -0.12 ? 'Risk-off' : net <= -0.04 ? 'Leaning bearish' : 'Balanced'

/** Top picks first by the day they were picked (newest), then by the writer's rank. */
export function byPick(a: Article, b: Article) {
  const pa = a.top_pick!, pb = b.top_pick!
  return pa.trading_day === pb.trading_day ? pa.rank - pb.rank : pa.trading_day < pb.trading_day ? 1 : -1
}
