import type { ReactNode } from 'react'
import { WordsReveal } from './Reveal'

export function PageHeader({ kicker, title, children, actions }: { kicker?: ReactNode; title: string; children?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 pb-6">
      <div className="min-w-0 max-w-3xl">
        {kicker && <div className="mb-2 text-[13px] text-muted-foreground">{kicker}</div>}
        <WordsReveal key={title} text={title} className="text-[28px] leading-[1.15] font-semibold tracking-[-0.025em] text-balance sm:text-[32px]" />
        {children && <div className="mt-2 text-[15px] leading-relaxed text-muted-foreground">{children}</div>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  )
}
