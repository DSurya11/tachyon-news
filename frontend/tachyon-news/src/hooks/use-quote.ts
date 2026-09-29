/*
  Per-symbol quotes with request batching (DataLoader-style): every useQuote() call made
  within the same 40 ms window is merged into one /quotes request. Combined with
  `enabled: inView`, only quotes that are actually on screen are fetched.
*/
import { useQuery } from '@tanstack/react-query'
import { useCurrency } from '@/hooks/use-currency'
import { api } from '@/lib/api'
import { config } from '@/lib/config'
import type { Quote } from '@/lib/types'

// currency → symbol → waiting callers
let pending = new Map<string, Map<string, ((q: Quote | null) => void)[]>>()
let timer: ReturnType<typeof setTimeout> | null = null

function load(sym: string, currency: string): Promise<Quote | null> {
  return new Promise((resolve) => {
    const group = pending.get(currency) ?? new Map()
    group.set(sym, [...(group.get(sym) ?? []), resolve])
    pending.set(currency, group)
    if (!timer) {
      timer = setTimeout(() => {
        const batches = pending
        pending = new Map()
        timer = null
        for (const [ccy, batch] of batches) {
          api.quotes([...batch.keys()], ccy)
            .catch(() => new Map<string, Quote | null>())
            .then((result) => { for (const [s, resolvers] of batch) resolvers.forEach((r) => r(result.get(s) ?? null)) })
        }
      }, 40)
    }
  })
}

export function useQuote(sym: string | null | undefined, enabled = true) {
  const { currency } = useCurrency()
  return useQuery({
    queryKey: ['quote', currency, sym],
    queryFn: () => load(sym!, currency),
    enabled: !!sym && enabled,
    staleTime: 55_000,
    refetchInterval: config.refreshMs,
    refetchIntervalInBackground: false,
  })
}
