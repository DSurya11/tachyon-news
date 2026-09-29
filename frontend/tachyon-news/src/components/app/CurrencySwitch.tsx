import { ChevronDown } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuLabel, DropdownMenuRadioGroup, DropdownMenuRadioItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { CURRENCY_LABEL, useCurrency, type CurrencyView } from '@/hooks/use-currency'

const OPTIONS: { v: CurrencyView; code: string; hint: string }[] = [
  { v: 'native', code: 'Local', hint: 'Each listing in its own currency' },
  { v: 'USD', code: 'USD', hint: 'Converted at the daily rate' },
  { v: 'INR', code: 'INR', hint: 'Converted at the daily rate' },
]

/** Display currency for every price. Index levels stay in points whatever is chosen. */
export function CurrencySwitch() {
  const { currency, setCurrency } = useCurrency()
  const current = OPTIONS.find((o) => o.v === currency)!
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label={`Currency: ${CURRENCY_LABEL[currency]}`}
        className="num flex h-9 shrink-0 items-center gap-1.5 rounded-lg border bg-surface px-2.5 text-[12.5px] font-medium transition-[border-color] hover:border-foreground/30">
        {current.code}
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-64">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Show prices in</DropdownMenuLabel>
        <DropdownMenuRadioGroup value={currency} onValueChange={(v) => setCurrency(v as CurrencyView)}>
          {OPTIONS.map((o) => (
            <DropdownMenuRadioItem key={o.v} value={o.v} className="py-1.5">
              <span className="flex flex-col">
                <span className="text-[13px] font-medium">{CURRENCY_LABEL[o.v]}{o.v !== 'native' && <span className="num ml-1.5 text-muted-foreground">{o.code}</span>}</span>
                <span className="text-[11.5px] text-muted-foreground">{o.hint}</span>
              </span>
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
        <DropdownMenuSeparator />
        <p className="px-2 py-1.5 text-[11.5px] leading-relaxed text-muted-foreground">
          Index levels (NIFTY, S&amp;P 500) are points and are never converted. % change is always the listing's own move.
        </p>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
