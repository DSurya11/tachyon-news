import { createContext, useContext, useState, type ReactNode } from 'react'

/**
 * Display currency for prices. `native` shows each listing in its own currency
 * (NVDA in USD, RELIANCE.NS in INR); USD / INR convert server-side at stored daily
 * FX rates. Index levels (NIFTY, SPX) are points and are never converted.
 */
export type CurrencyView = 'native' | 'USD' | 'INR'

const KEY = 'tsn.currency'
const Ctx = createContext<{ currency: CurrencyView; setCurrency: (c: CurrencyView) => void }>({ currency: 'native', setCurrency: () => {} })

function saved(): CurrencyView {
  try {
    const v = localStorage.getItem(KEY)
    return v === 'USD' || v === 'INR' ? v : 'native'
  } catch { return 'native' }
}

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, set] = useState<CurrencyView>(saved)
  const setCurrency = (c: CurrencyView) => {
    try { localStorage.setItem(KEY, c) } catch { /* private mode */ }
    set(c)
  }
  return <Ctx.Provider value={{ currency, setCurrency }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useCurrency = () => useContext(Ctx)

// eslint-disable-next-line react-refresh/only-export-components
export const CURRENCY_LABEL: Record<CurrencyView, string> = { native: 'Local', USD: 'US dollar', INR: 'Indian rupee' }
