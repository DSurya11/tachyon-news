import { Moon, Sun } from 'lucide-react'
import { motion } from 'motion/react'
import { NavLink, useLocation } from 'react-router-dom'
import { useHealth, useReport, useSummary } from '@/hooks/queries'
import { rangeShort, useRange } from '@/hooks/use-range'
import { useTheme, type Theme } from '@/hooks/use-theme'
import { useWatchlist } from '@/hooks/use-watchlist'
import { api } from '@/lib/api'
import { ago } from '@/lib/format'
import { NAV } from '@/lib/nav'
import { cn } from '@/lib/utils'
import { Logo } from './Logo'
import { SplitBar } from './Sentiment'



const isActive = (path: string, to: string) => (to === '/' ? path === '/' : path.startsWith(to))

function ThemeSwitch() {
  const { theme, setTheme } = useTheme()
  const opts: { v: Theme; icon: typeof Sun; label: string }[] = [
    { v: 'dark', icon: Moon, label: 'Dark' }, { v: 'light', icon: Sun, label: 'Light' },
  ]
  return (
    <div role="radiogroup" aria-label="Theme" className="relative flex rounded-lg border bg-background p-0.5">
      {opts.map(({ v, icon: Icon, label }) => (
        <button key={v} type="button" role="radio" aria-checked={theme === v} aria-label={label} title={label} onClick={() => setTheme(v)}
          className={cn('relative grid h-7 flex-1 place-items-center rounded-md text-muted-foreground transition-colors hover:text-foreground', theme === v && 'text-foreground')}>
          {theme === v && <motion.span layoutId="theme-pill" className="seg-thumb absolute inset-0 rounded-md" transition={{ type: 'spring', stiffness: 500, damping: 36 }} />}
          <span className="relative flex items-center gap-1.5 text-[12px] font-medium"><Icon className="size-3.5" strokeWidth={1.75} />{label}</span>
        </button>
      ))}
    </div>
  )
}

export function Sidebar() {
  const { pathname, search } = useLocation()
  const { data: summary } = useSummary()
  const { range } = useRange()
  const { data: health } = useHealth()
  const { data: report } = useReport()
  const { list } = useWatchlist()
  const sectors = summary?.sectors ?? []
  const activeSector = pathname.startsWith('/wire') ? new URLSearchParams(search).get('sector') : null
  const counts: Record<string, string | number> = { '/wire': summary?.count ? summary.count.toLocaleString() : '', '/watchlist': list.length || '', '/brief': report ? 'New' : '' }
  const status = !health ? 'bg-muted-foreground' : health.status === 'ok' ? 'bg-up' : health.status === 'degraded' ? 'bg-signal' : 'bg-down'

  return (
    <aside className="sticky top-0 hidden h-dvh w-[248px] shrink-0 flex-col border-r bg-sidebar lg:flex">
      <div className="px-5 pt-5 pb-6"><NavLink to="/" aria-label="Tachyon News home"><Logo /></NavLink></div>

      <nav className="space-y-0.5 px-3" aria-label="Primary">
        {NAV.map(({ to, label, icon: Icon }) => {
          const on = isActive(pathname, to)
          return (
            <NavLink key={to} to={to} className={cn('relative flex h-9 items-center gap-2.5 rounded-lg px-3 text-[13.5px] font-medium transition-colors',
              on ? 'text-foreground' : 'text-muted-foreground hover:text-foreground')}>
              {on && <motion.span layoutId="nav-pill" className="seg-thumb absolute inset-0 rounded-lg" transition={{ type: 'spring', stiffness: 520, damping: 38 }} />}
              <Icon className="relative size-4" strokeWidth={1.75} />
              <span className="relative">{label}</span>
              {counts[to] ? <span className={cn('num relative ml-auto text-[11px]', to === '/brief' ? 'text-signal' : 'text-muted-foreground')}>{counts[to]}</span> : null}
            </NavLink>
          )
        })}
      </nav>

      <div className="mt-7 min-h-0 flex-1 overflow-y-auto px-3 scrollbar-thin">
        <div className="flex items-baseline justify-between px-3 pb-2 text-xs text-muted-foreground"><span>Sectors</span><span>{rangeShort(range)}</span></div>
        <div className="space-y-0.5">
          {sectors.map((s) => (
            <NavLink key={s.name} to={`/wire?sector=${encodeURIComponent(s.name)}`}
              className={cn('hover-row group block rounded-lg px-3 py-2', activeSector === s.name && 'seg-thumb')}>
              <div className="flex items-center justify-between gap-2 text-[13px]">
                <span className={cn('truncate transition-colors', activeSector === s.name ? 'text-foreground' : 'text-foreground/75 group-hover:text-foreground')}><span className="hover-title">{s.name}</span></span>
                <span className="num text-[11px] text-muted-foreground">{s.count}</span>
              </div>
              <SplitBar {...s} className="mt-1.5 h-1" />
            </NavLink>
          ))}
          {summary && !sectors.length && <p className="px-3 text-[12.5px] text-muted-foreground">No stories in this range.</p>}
          {!summary && Array.from({ length: 7 }, (_, i) => <div key={i} className="mx-3 my-3 h-3 animate-pulse rounded bg-muted" />)}
        </div>
      </div>

      <div className="space-y-3 border-t p-4">
        <div className="flex items-center justify-between text-xs">
          <span className="flex items-center gap-2 font-medium"><span className={cn('size-1.5 rounded-full', status)} />Pipeline</span>
          <span className="text-muted-foreground">{health?.last_scrape_at ? `scraped ${ago(health.last_scrape_at)} ago` : api.demo ? 'demo data' : '—'}</span>
        </div>
        <ThemeSwitch />
      </div>
    </aside>
  )
}

export function MobileNav() {
  const { pathname } = useLocation()
  return (
    <nav aria-label="Views" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t bg-background pb-[env(safe-area-inset-bottom)] lg:hidden">
      {NAV.map(({ to, short, icon: Icon }) => {
        const on = isActive(pathname, to)
        return (
          <NavLink key={to} to={to} className={cn('relative flex flex-col items-center gap-1 py-2.5 text-[11px] font-medium', on ? 'text-foreground' : 'text-muted-foreground')}>
            {on && <motion.span layoutId="tab-dot" className="absolute top-0 h-0.5 w-8 rounded-full bg-foreground" />}
            <Icon className="size-[18px]" strokeWidth={1.75} />{short}
          </NavLink>
        )
      })}
    </nav>
  )
}
