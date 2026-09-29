import { createContext, useContext, useState, type ReactNode } from 'react'
import type { Article } from '@/lib/types'

/** Which markets the dashboard shows. Remembered per browser. */
export type MarketView = 'all' | 'global' | 'india'

const KEY = 'tsn.market'
const Ctx = createContext<{ market: MarketView; setMarket: (m: MarketView) => void }>({ market: 'all', setMarket: () => {} })

function saved(): MarketView {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'global' || v === 'india' ? v : 'all'
  } catch { return 'all' }
}

export function MarketProvider({ children }: { children: ReactNode }) {
  const [market, set] = useState<MarketView>(saved)
  const setMarket = (m: MarketView) => {
    try { localStorage.setItem(KEY, m) } catch { /* private mode */ }
    set(m)
  }
  return <Ctx.Provider value={{ market, setMarket }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useMarket = () => useContext(Ctx)

// eslint-disable-next-line react-refresh/only-export-components
export const inMarket = (a: Article, m: MarketView) => m === 'all' || (a.market ?? 'global') === m

// eslint-disable-next-line react-refresh/only-export-components
export const MARKET_LABEL: Record<MarketView, string> = { all: 'All markets', global: 'International', india: 'India' }
