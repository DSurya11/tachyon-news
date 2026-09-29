import { RefreshCw, Search } from 'lucide-react'
import { useIsFetching, useQueryClient } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { cn } from '@/lib/utils'
import { Logo } from './Logo'
import { MarketStatus } from './MarketStatus'
import { CurrencySwitch } from './CurrencySwitch'
import { MarketSwitch } from './MarketSwitch'
import { RangePicker } from './RangePicker'
import { UserMenu } from './UserMenu'

export function Topbar({ onSearch }: { onSearch: () => void }) {
  const qc = useQueryClient()
  const fetching = useIsFetching() > 0
  const mac = /Mac|iPhone|iPad/.test(navigator.userAgent)
  return (
    // Solid, not backdrop-blur: a blurred sticky bar re-blurs everything scrolling under it every frame.
    <div className="sticky top-0 z-30 border-b bg-background">
      {/* Phones: two rows (logo, search, account; then the filters) so nothing pushes the page sideways. */}
      <div className="flex flex-wrap items-center gap-2 px-4 py-2.5 sm:h-14 sm:flex-nowrap sm:gap-3 sm:px-6 sm:py-0">
        <div className="lg:hidden"><Logo compact /></div>
        <button type="button" onClick={onSearch}
          className="flex h-9 min-w-0 flex-1 items-center gap-2.5 rounded-lg border bg-surface px-3 text-[13px] text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground sm:max-w-sm">
          <Search className="size-4 shrink-0" strokeWidth={1.75} />
          <span className="flex-1 truncate text-left"><span className="sm:hidden">Search</span><span className="hidden sm:inline">Search tickers, sectors, stories…</span></span>
          <kbd className="num hidden rounded border bg-background px-1.5 py-0.5 text-[10.5px] sm:inline">{mac ? '⌘K' : 'Ctrl K'}</kbd>
        </button>
        <div className="order-last flex w-full min-w-0 items-center gap-1.5 overflow-x-auto [scrollbar-width:none] sm:order-none sm:w-auto sm:gap-3 sm:overflow-visible">
          <RangePicker />
          <MarketSwitch />
          <CurrencySwitch />
          <div className="ml-auto shrink-0 sm:hidden"><MarketStatus /></div>
        </div>
        <div className="ml-auto flex shrink-0 items-center gap-1.5 sm:gap-2">
          <div className="hidden sm:block"><MarketStatus /></div>
          <button type="button" aria-label="Refresh data" title="Refresh"
            onClick={() => { api.clearQuoteCache(); qc.invalidateQueries() }}
            className="hidden size-9 place-items-center rounded-lg text-muted-foreground transition-colors hover:text-foreground sm:grid">
            <RefreshCw className={cn('size-4', fetching && 'animate-spin')} strokeWidth={1.75} />
          </button>
          <UserMenu />
        </div>
      </div>
    </div>
  )
}
