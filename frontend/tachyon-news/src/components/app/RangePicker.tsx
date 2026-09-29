import { CalendarRange, Check, ChevronDown } from 'lucide-react'
import { Popover } from 'radix-ui'
import { useState } from 'react'
import { PRESETS, rangeLabel, rangeShort, useRange } from '@/hooks/use-range'
import { useTheme } from '@/hooks/use-theme'
import { keyboardFocusReturn } from '@/lib/focus'
import { cn } from '@/lib/utils'

const localDay = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const daysAgo = (n: number) => { const d = new Date(); d.setDate(d.getDate() - n); return localDay(d) }

/**
  The time range every page follows: presets from the last 24 hours (the default) to all time,
  or a custom from–to range of whole days. A popover rather than a menu, so the date inputs
  keep normal keyboard behaviour.
*/
export function RangePicker() {
  const { range, setRange } = useRange()
  const { resolved } = useTheme()
  const [open, setOpen] = useState(false)
  const today = localDay(new Date())
  const [from, setFrom] = useState(range.from ?? daysAgo(6))
  const [to, setTo] = useState(range.to ?? today)
  const valid = Boolean(from && to && from <= to && to <= today)

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger aria-label={`Time range: ${rangeLabel(range)}`}
        className="flex h-9 shrink-0 items-center gap-1.5 rounded-lg border bg-surface px-2.5 text-[12.5px] font-medium transition-[border-color] hover:border-foreground/30">
        <CalendarRange className="hidden size-3.5 text-muted-foreground min-[400px]:block" strokeWidth={1.75} />
        <span className="hidden md:inline">{rangeLabel(range)}</span>
        <span className="md:hidden">{rangeShort(range)}</span>
        <ChevronDown className="size-3.5 text-muted-foreground" />
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content align="start" sideOffset={6} onCloseAutoFocus={keyboardFocusReturn()}
          className="z-50 w-64 origin-(--radix-popover-content-transform-origin) rounded-lg bg-popover p-1 text-popover-foreground shadow-md ring-1 ring-foreground/10 duration-100 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95">
          <div className="px-2 py-1.5 text-xs text-muted-foreground">Show news from</div>
          <div role="radiogroup" aria-label="Time range">
            {PRESETS.map((p) => {
              const on = range.key === p.key
              return (
                <button key={p.key} type="button" role="radio" aria-checked={on}
                  onClick={() => { setRange({ key: p.key }); setOpen(false) }}
                  className={cn('flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-[13px] transition-colors',
                    on ? 'font-medium text-foreground' : 'text-muted-foreground hover:text-foreground')}>
                  {p.label}
                  {on && <Check className="size-3.5" strokeWidth={2} />}
                </button>
              )
            })}
          </div>

          <div className="mx-1 my-1 border-t" />
          <form className="space-y-2 px-2 pt-1 pb-2" onSubmit={(e) => {
            e.preventDefault()
            if (!valid) return
            setRange({ key: 'custom', from, to })
            setOpen(false)
          }}>
            <div className="flex items-center justify-between text-xs">
              <span className={cn(range.key === 'custom' ? 'font-medium text-foreground' : 'text-muted-foreground')}>Custom range</span>
              {range.key === 'custom' && <Check className="size-3.5" strokeWidth={2} />}
            </div>
            <div className="grid grid-cols-2 gap-2" style={{ colorScheme: resolved }}>
              <label className="space-y-1 text-[11px] text-muted-foreground">From
                <input type="date" value={from} max={to || today} onChange={(e) => setFrom(e.target.value)}
                  className="num h-8 w-full rounded-md border bg-surface px-1.5 text-[12px] text-foreground outline-none focus:border-foreground/30" />
              </label>
              <label className="space-y-1 text-[11px] text-muted-foreground">To
                <input type="date" value={to} min={from} max={today} onChange={(e) => setTo(e.target.value)}
                  className="num h-8 w-full rounded-md border bg-surface px-1.5 text-[12px] text-foreground outline-none focus:border-foreground/30" />
              </label>
            </div>
            <button type="submit" disabled={!valid}
              className="h-8 w-full rounded-md bg-foreground text-[12.5px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-40">
              Apply
            </button>
          </form>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  )
}
