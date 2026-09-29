import { motion, MotionConfig } from 'motion/react'
import { lazy, Suspense, useEffect, useSyncExternalStore, type ComponentType } from 'react'
import { HashRouter, Navigate, Route, Routes, useLocation, useNavigate, useNavigationType } from 'react-router-dom'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { CommandMenu } from '@/components/app/CommandMenu'
import { useCommandMenu } from '@/hooks/use-command-menu'
import { Inspector } from '@/components/app/Inspector'
import { MobileNav, Sidebar } from '@/components/app/Nav'
import { Tape } from '@/components/app/Tape'
import { Topbar } from '@/components/app/Topbar'
import { Logo } from '@/components/app/Logo'
import { useMode } from '@/hooks/queries'
import { AuthProvider, useAuth } from '@/hooks/use-auth'
import { InspectorProvider } from '@/hooks/use-inspector'
import { CurrencyProvider } from '@/hooks/use-currency'
import { MarketProvider } from '@/hooks/use-market'
import { RangeProvider } from '@/hooks/use-range'
import { ThemeProvider, useTheme } from '@/hooks/use-theme'
import { api, onModeChange } from '@/lib/api'
import { config } from '@/lib/config'
import SignIn from '@/pages/SignIn'
/**
 * A route-level lazy component that renders synchronously once its code is loaded.
 * Plain React.lazy suspends on first render even when the module is already in memory,
 * and React then holds the fallback for its ~300 ms reveal throttle.
 */
function lazyPage(load: () => Promise<{ default: ComponentType }>) {
  let Loaded: ComponentType | null = null
  const preload = () => load().then((m) => { Loaded = m.default; return m })
  const Lazy = lazy(preload)
  const Page = () => (Loaded ? <Loaded /> : <Lazy />)
  return Object.assign(Page, { preload })
}

const Overview = lazyPage(() => import('@/pages/Overview'))
const Wire = lazyPage(() => import('@/pages/Wire'))
const Brief = lazyPage(() => import('@/pages/Brief'))
const Watchlist = lazyPage(() => import('@/pages/Watchlist'))

/** Fetch the other pages' code once the first one is up, so switching never waits on the network. */
function usePrefetchPages() {
  useEffect(() => {
    const idle = window.requestIdleCallback ?? ((cb: () => void) => window.setTimeout(cb, 1200))
    idle(() => [Overview, Wire, Brief, Watchlist].forEach((p) => void p.preload()))
  }, [])
}

function Hotkeys() {
  const navigate = useNavigate()
  const { resolved, setTheme } = useTheme()
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return
      if ((e.target as HTMLElement).closest('input, textarea, select, [contenteditable="true"], [role="dialog"]')) return
      const to = { '1': '/', '2': '/wire', '3': '/brief', '4': '/watchlist' }[e.key]
      if (to) navigate(to)
      if (e.key === 't') setTheme(resolved === 'dark' ? 'light' : 'dark')
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate, resolved, setTheme])
  return null
}

function DemoBanner() {
  const { isSuccess } = useMode()
  const demo = useSyncExternalStore(onModeChange, () => api.demo)
  if (!isSuccess || !demo) return null
  return (
    <div className="border-b bg-signal/10 px-4 py-2 text-[13px] sm:px-6">
      <span className="font-medium">Showing sample data.</span>{' '}
      <span className="text-muted-foreground">
        {config.apiUrl
          ? <>Can't reach your API at <span className="num">{config.apiUrl}</span> — the laptop may be off or asleep, or the browser blocked it (Chrome on a Tailscale device: allow "Local network access" for this site). Reload once it's back.</>
          : <>This build has no API address: set <span className="num">VITE_API_URL</span> and rebuild (on this laptop: <span className="num">make up</span>).</>}
      </span>
    </div>
  )
}

function Shell() {
  const location = useLocation()
  const { open, setOpen } = useCommandMenu()
  const section = location.pathname.split('/')[1] || 'overview'
  usePrefetchPages()
  useEffect(() => {
    const titles: Record<string, string> = { overview: 'Overview', wire: 'The wire', brief: 'Daily brief', watchlist: 'Watchlist' }
    document.title = `${titles[section] ?? 'Tachyon News'} — Tachyon News`
  }, [section])
  // Opening a page starts at its top; back/forward keeps the browser's own scroll restoration.
  const navigationType = useNavigationType()
  useEffect(() => {
    if (navigationType !== 'POP') window.scrollTo(0, 0)
  }, [location.pathname]) // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className="flex min-h-dvh">
      <Sidebar />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar onSearch={() => setOpen(true)} />
        <Tape />
        <DemoBanner />
        <main id="main" className="mx-auto w-full max-w-[1280px] flex-1 px-4 pt-8 pb-28 sm:px-6 lg:pb-16">
          {/* Enter-only transition: the new page starts immediately (no exit wait, no blur filter). */}
          <motion.div key={section}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.24, ease: [0.16, 1, 0.3, 1] }}>
              <Suspense fallback={<div className="h-[60vh]" />}>
              <Routes location={location}>
                <Route path="/" element={<Overview />} />
                <Route path="/wire" element={<Wire />} />
                <Route path="/brief" element={<Brief />} />
                <Route path="/brief/:day" element={<Brief />} />
                <Route path="/watchlist" element={<Watchlist />} />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
              </Suspense>
          </motion.div>
        </main>
      </div>
      <MobileNav />
      <Inspector />
      <CommandMenu open={open} setOpen={setOpen} />
      <Hotkeys />
      <Toaster position="bottom-right" />
    </div>
  )
}

const AUTH_PAGES = new Set(['/login', '/signup'])

/** Signed-out visitors only see sign-in / sign-up; after signing in they land where they were headed. */
function Gate() {
  const { status } = useAuth()
  const location = useLocation()
  const onAuthPage = AUTH_PAGES.has(location.pathname)

  if (status === 'checking') {
    return <div className="grid min-h-dvh place-items-center"><span className="animate-pulse"><Logo /></span></div>
  }
  if (status === 'signed-out') {
    if (onAuthPage) return <SignIn mode={location.pathname === '/signup' ? 'signup' : 'signin'} />
    const next = location.pathname + location.search
    return <Navigate replace to={next === '/' ? '/login' : `/login?next=${encodeURIComponent(next)}`} />
  }
  if (onAuthPage) return <Navigate replace to={new URLSearchParams(location.search).get('next') || '/'} />
  return <InspectorProvider><Shell /></InspectorProvider>
}

export default function App() {
  return (
    <ThemeProvider>
      <MotionConfig reducedMotion="user">
        <TooltipProvider delayDuration={200}>
          <HashRouter>
            <AuthProvider>
              <MarketProvider>
                <RangeProvider>
                  <CurrencyProvider>
                    <Gate />
                  </CurrencyProvider>
                </RangeProvider>
              </MarketProvider>
            </AuthProvider>
          </HashRouter>
        </TooltipProvider>
      </MotionConfig>
    </ThemeProvider>
  )
}
