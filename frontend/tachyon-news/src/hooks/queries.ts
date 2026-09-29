import { keepPreviousData, useInfiniteQuery, useQuery } from '@tanstack/react-query'
import { useCurrency } from '@/hooks/use-currency'
import { useMarket } from '@/hooks/use-market'
import { rangeId, useRange, windowOf, type Range } from '@/hooks/use-range'
import { api } from '@/lib/api'
import { config } from '@/lib/config'
import type { NewsFilters, Span, Window } from '@/lib/types'

const live = { refetchInterval: config.refreshMs, refetchIntervalInBackground: false }

/** Live vs demo — used only for the banner; data queries don't wait for it. */
export const useMode = () => useQuery({ queryKey: ['mode'], queryFn: () => api.probe(), staleTime: Infinity })

/**
  Aggregates for the chosen range and market, computed by the API (exact however large the
  range). `symbols` are always included in `tickers` (a watchlist); `at` pins a different range.
*/
export function useSummary({ symbols = [], top = 30, at }: { symbols?: string[]; top?: number; at?: Range } = {}) {
  const { market } = useMarket()
  const chosen = useRange().range
  const range = at ?? chosen
  const syms = [...new Set(symbols)].sort()
  return useQuery({
    queryKey: ['summary', rangeId(range), market, syms.join(','), top],
    queryFn: () => api.summary(windowOf(range), market === 'all' ? undefined : market, syms, top),
    placeholderData: keepPreviousData,
    ...live,
  })
}

/** Server-filtered, server-paged stories of the chosen range (the Wire and top picks). */
export function useNewsPages(filters: Omit<NewsFilters, 'market'>, pageSize = 100, enabled = true) {
  const { market } = useMarket()
  const { range } = useRange()
  const f: NewsFilters = { ...filters, market: market === 'all' ? undefined : market }
  return useInfiniteQuery({
    queryKey: ['news-pages', rangeId(range), JSON.stringify(f), pageSize],
    queryFn: ({ pageParam }) => api.newsPage(windowOf(range), f, pageParam, pageSize),
    initialPageParam: 1,
    getNextPageParam: (last) => (last.has_more ? last.page + 1 : undefined),
    placeholderData: keepPreviousData,
    enabled,
    ...live,
  })
}

/** Specific stories by id, whatever the range (a brief's sources). */
export function useArticlesByIds(ids: number[] = []) {
  return useQuery({ queryKey: ['articles', ids.join(',')], queryFn: () => api.articlesByIds(ids), enabled: ids.length > 0, staleTime: 5 * 60_000 })
}

export function useHealth() {
  return useQuery({ queryKey: ['health'], queryFn: () => api.health(), ...live })
}

export function useReport(day?: string | null) {
  return useQuery({ queryKey: ['report', day ?? 'latest'], queryFn: () => api.report(day), ...live })
}

export function useReports() {
  return useQuery({ queryKey: ['reports'], queryFn: () => api.reports(), staleTime: 5 * 60_000 })
}

/** The priced-in meter; refreshes while open, as the move since the headline changes. */
export function useReaction(id?: number | null) {
  return useQuery({ queryKey: ['reaction', id], queryFn: () => api.reaction(id!), enabled: id != null, staleTime: 60_000, refetchInterval: 120_000 })
}

export function useArticle(id?: number | null) {
  return useQuery({ queryKey: ['article', id], queryFn: () => api.article(id!), enabled: id != null, staleTime: 5 * 60_000 })
}

/** Calendar days each chart span covers (5 trading days ≈ a week), for the stories shown beside it. */
export const SPAN_DAYS: Record<Span, number> = { '1d': 1, '5d': 7, '1m': 30, '3m': 91, '6m': 182, '1y': 365, '5y': 1826 }
const spanWindow = (span: Span): Window => ({ since: new Date(Date.now() - SPAN_DAYS[span] * 86400e3).toISOString(), until: null })

/** A ticker's stories and exact sentiment counts over a chart span (every market). */
export function useTickerNews(sym: string | null | undefined, span: Span) {
  const news = useQuery({
    queryKey: ['ticker-news', sym, span], queryFn: () => api.tickerNews(sym!, spanWindow(span)),
    enabled: !!sym, staleTime: 60_000, placeholderData: keepPreviousData,
  })
  const counts = useQuery({
    queryKey: ['ticker-summary', sym, span], queryFn: () => api.summary(spanWindow(span), undefined, [sym!], 0),
    enabled: !!sym, staleTime: 60_000, placeholderData: keepPreviousData,
    select: (s) => s.tickers.find((t) => t.symbol === sym) ?? null,
  })
  return { news: news.data, counts: counts.data }
}

/** One span of the stock panel's chart; intraday spans refresh while open. */
export function useChart(sym: string | null | undefined, span: Span) {
  const { currency } = useCurrency()
  const intraday = span === '1d' || span === '5d'
  return useQuery({
    queryKey: ['chart', currency, sym, span], queryFn: () => api.chart(sym!, span, currency), enabled: !!sym,
    staleTime: intraday ? 60_000 : 30 * 60_000, refetchInterval: span === '1d' ? 120_000 : false,
    placeholderData: keepPreviousData,
  })
}

export function useQuotes(symbols: string[]) {
  const { currency } = useCurrency()
  const key = [...new Set(symbols)].sort()
  return useQuery({
    queryKey: ['quotes', currency, key.join(',')],
    queryFn: () => api.quotes(key, currency),
    enabled: key.length > 0,
    placeholderData: keepPreviousData,
    ...live,
  })
}

/** Daily closes. `inCurrency` converts (each day at its own rate); sparklines use native shape. */
export function useCandles(sym?: string | null, inCurrency = false) {
  const { currency } = useCurrency()
  const ccy = inCurrency ? currency : 'native'
  return useQuery({ queryKey: ['candles', ccy, sym], queryFn: () => api.candles(sym!, ccy), enabled: !!sym, staleTime: 30 * 60_000 })
}
