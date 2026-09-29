import { ChevronDown, Globe2 } from 'lucide-react'
import { motion } from 'motion/react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { MARKET_LABEL, useMarket, type MarketView } from '@/hooks/use-market'
import { cn } from '@/lib/utils'

const OPTIONS: { v: MarketView; short: string }[] = [
  { v: 'all', short: 'All' },
  { v: 'global', short: 'International' },
  { v: 'india', short: 'India' },
]

/** All markets / International (Finviz) / India. A segmented control on wide screens, a menu on phones. */
export function MarketSwitch() {
  const { market, setMarket } = useMarket()
  return (
    <>
      <div role="radiogroup" aria-label="Market" className="relative hidden h-9 shrink-0 items-center rounded-lg border bg-surface p-0.5 md:inline-flex">
        {OPTIONS.map((o) => (
          <button key={o.v} type="button" role="radio" aria-checked={market === o.v} onClick={() => setMarket(o.v)}
            className={cn('relative h-full rounded-md px-3 text-[13px] font-medium transition-colors',
              market === o.v ? 'text-foreground' : 'text-muted-foreground hover:text-foreground')}>
            {market === o.v && <motion.span layoutId="market-pill" className="seg-thumb absolute inset-0 rounded-md" transition={{ type: 'spring', stiffness: 500, damping: 38 }} />}
            <span className="relative">{o.short}</span>
          </button>
        ))}
      </div>

      <DropdownMenu>
        <DropdownMenuTrigger aria-label={`Market: ${MARKET_LABEL[market]}`}
          className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg border bg-surface px-2.5 text-[13px] font-medium md:hidden">
          <Globe2 className="hidden size-4 text-muted-foreground min-[400px]:block" strokeWidth={1.75} />
          {OPTIONS.find((o) => o.v === market)?.short}
          <ChevronDown className="size-3.5 text-muted-foreground" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-44">
          <DropdownMenuLabel className="text-xs text-muted-foreground">Market</DropdownMenuLabel>
          <DropdownMenuRadioGroup value={market} onValueChange={(v) => setMarket(v as MarketView)}>
            {OPTIONS.map((o) => <DropdownMenuRadioItem key={o.v} value={o.v}>{MARKET_LABEL[o.v]}</DropdownMenuRadioItem>)}
          </DropdownMenuRadioGroup>
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}
