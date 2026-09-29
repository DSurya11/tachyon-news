import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { api, HttpError } from '@/lib/api'
import { config } from '@/lib/config'
import { session } from '@/lib/session'
import type { AuthConfig, AuthResult, User } from '@/lib/types'

/**
 * checking   — validating a saved session with the API
 * signed-in  — `user` is set; data calls carry the token
 * signed-out — show sign-in (`offline` when the API can't be reached)
 * demo       — no API configured / `?demo=1`: the built-in demo data, no account needed
 */
export type AuthStatus = 'checking' | 'signed-in' | 'signed-out' | 'demo'

interface AuthState {
  status: AuthStatus
  user: User | null
  options: AuthConfig | null
  offline: boolean
  signIn: (email: string, password: string) => Promise<void>
  signUp: (email: string, password: string, name?: string) => Promise<void>
  signInWithGoogle: (credential: string) => Promise<void>
  signOut: () => Promise<void>
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const demo = !config.apiUrl
  const [status, setStatus] = useState<AuthStatus>(demo ? 'demo' : session.token ? 'checking' : 'signed-out')
  const [user, setUser] = useState<User | null>(null)
  const [options, setOptions] = useState<AuthConfig | null>(null)
  const [offline, setOffline] = useState(false)

  // Validate a saved session, and learn which sign-in methods the API offers. A network failure
  // (laptop asleep, phone between networks) is retried with backoff, and at once when the device
  // comes back online or the tab is shown again, so one blip doesn't strand you on sign-in.
  useEffect(() => {
    if (demo) return
    let alive = true
    let timer: ReturnType<typeof setTimeout> | undefined
    let failures = 0
    const retryLater = () => {
      clearTimeout(timer)
      timer = setTimeout(attempt, Math.min(30_000, 2_000 * 2 ** failures++))
    }
    function attempt() {
      clearTimeout(timer)
      api.authConfig()
        .then((c) => {
          if (!alive) return
          setOptions(c)
          setOffline(false)
          failures = 0
          if (!session.token) return
          api.me()
            .then((u) => { if (alive) { setUser(u); setStatus('signed-in') } })
            .catch((err) => {
              if (!alive) return
              if (err instanceof HttpError) { session.set(null); setStatus('signed-out') } else { setOffline(true); retryLater() }
            })
        })
        .catch((err) => {
          if (!alive || err instanceof HttpError) return
          setOffline(true)
          setStatus((st) => (st === 'checking' ? 'signed-out' : st))
          retryLater()
        })
    }
    const now = () => { if (document.visibilityState === 'visible') { failures = 0; attempt() } }
    attempt()
    window.addEventListener('online', now)
    document.addEventListener('visibilitychange', now)
    return () => {
      alive = false
      clearTimeout(timer)
      window.removeEventListener('online', now)
      document.removeEventListener('visibilitychange', now)
    }
  }, [demo])

  // A 401 anywhere (expired or revoked session) or a sign-out in another tab.
  useEffect(() => session.subscribe((token) => {
    if (token) return
    setUser(null)
    setStatus((s) => (s === 'demo' ? s : 'signed-out'))
    qc.clear()
  }), [qc])

  const accept = useCallback((r: AuthResult) => {
    qc.clear() // never show one account's cached data to another
    session.set(r.token)
    setUser(r.user)
    setStatus('signed-in')
  }, [qc])

  const value = useMemo<AuthState>(() => ({
    status, user, options, offline,
    signIn: async (email, password) => accept(await api.login(email, password)),
    signUp: async (email, password, name) => accept(await api.signup(email, password, name)),
    signInWithGoogle: async (credential) => accept(await api.google(credential)),
    signOut: async () => {
      await api.logout()
      session.set(null)
    },
  }), [status, user, options, offline, accept])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAuth() {
  const ctx = useContext(Ctx)
  if (!ctx) throw new Error('useAuth outside AuthProvider')
  return ctx
}
