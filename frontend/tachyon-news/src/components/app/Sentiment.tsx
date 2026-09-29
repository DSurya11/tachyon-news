import { cn } from '@/lib/utils'
import type { Sentiment as S } from '@/lib/types'

const LABEL: Record<S, string> = { bullish: 'Bullish', bearish: 'Bearish', neutral: 'Neutral' }
export const norm = (s?: string | null): S => (s === 'bullish' || s === 'bearish' ? s : 'neutral')

export function SentimentBadge({ value, className }: { value?: string | null; className?: string }) {
  const s = norm(value)
  return (
    <span className={cn('inline-flex items-center gap-1.5 text-xs font-medium',
      s === 'bullish' && 'text-up', s === 'bearish' && 'text-down', s === 'neutral' && 'text-muted-foreground', className)}>
      <SentimentGlyph value={s} />
      {LABEL[s]}
    </span>
  )
}

export function SentimentGlyph({ value, className }: { value?: string | null; className?: string }) {
  const s = norm(value)
  if (s === 'neutral') return <span aria-hidden className={cn('inline-block h-[2px] w-2 rounded-full bg-current', className)} />
  return (
    <svg viewBox="0 0 8 8" className={cn('size-2', className)} aria-hidden>
      <path d={s === 'bullish' ? 'M4 1 7.5 7h-7z' : 'M4 7 .5 1h7z'} fill="currentColor" />
    </svg>
  )
}

/** 100%-stacked bull / neutral / bear bar. */
export function SplitBar({ bullish, neutral, bearish, className }: { bullish: number; neutral: number; bearish: number; className?: string }) {
  const total = bullish + neutral + bearish || 1
  return (
    <div className={cn('flex h-1.5 w-full gap-px overflow-hidden rounded-full bg-muted', className)}
      role="img" aria-label={`${bullish} bullish, ${neutral} neutral, ${bearish} bearish`}>
      <span className="h-full bg-up transition-[width] duration-700" style={{ width: `${(bullish / total) * 100}%` }} />
      <span className="h-full bg-flat/40 transition-[width] duration-700" style={{ width: `${(neutral / total) * 100}%` }} />
      <span className="h-full bg-down transition-[width] duration-700" style={{ width: `${(bearish / total) * 100}%` }} />
    </div>
  )
}
