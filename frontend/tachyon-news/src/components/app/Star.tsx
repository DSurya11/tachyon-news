import { Star as StarIcon } from 'lucide-react'
import { motion } from 'motion/react'
import { toast } from 'sonner'
import { useWatchlist } from '@/hooks/use-watchlist'
import { cn } from '@/lib/utils'

export function Star({ symbol, className }: { symbol: string; className?: string }) {
  const { has, toggle } = useWatchlist()
  const on = has(symbol)
  return (
    <button type="button" aria-pressed={on} aria-label={`${on ? 'Remove' : 'Add'} ${symbol} ${on ? 'from' : 'to'} watchlist`}
      onClick={(e) => {
        e.stopPropagation()
        const added = toggle(symbol)
        toast(added ? `${symbol} added to watchlist` : `${symbol} removed from watchlist`)
      }}
      className={cn('grid size-8 place-items-center rounded-md text-muted-foreground transition-colors hover:text-foreground', on && 'text-signal hover:text-signal', className)}>
      <motion.span key={String(on)} initial={on ? { scale: 0.3, rotate: -60 } : false} animate={{ scale: 1, rotate: 0 }}
        transition={{ type: 'spring', stiffness: 500, damping: 14 }}>
        <StarIcon className="size-4" fill={on ? 'currentColor' : 'none'} strokeWidth={1.75} />
      </motion.span>
    </button>
  )
}
