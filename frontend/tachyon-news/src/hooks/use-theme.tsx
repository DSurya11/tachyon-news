import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

/** Two themes: dark (default) and light. index.html applies the saved one before first paint. */
export type Theme = 'light' | 'dark'
const KEY = 'tsn.theme'
const THEME_COLOR: Record<Theme, string> = { dark: '#0f0e0d', light: '#f2f0eb' }

const Ctx = createContext<{ theme: Theme; resolved: Theme; setTheme: (t: Theme) => void }>({
  theme: 'dark', resolved: 'dark', setTheme: () => {},
})

function saved(): Theme {
  try { return localStorage.getItem(KEY) === 'light' ? 'light' : 'dark' } catch { return 'dark' }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(saved)

  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark')
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', THEME_COLOR[theme])
  }, [theme])

  const setTheme = (t: Theme) => {
    try { localStorage.setItem(KEY, t) } catch { /* private mode */ }
    setThemeState(t)
  }
  // `resolved` is kept so callers don't care whether a theme is derived.
  return <Ctx.Provider value={{ theme, resolved: theme, setTheme }}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export const useTheme = () => useContext(Ctx)
