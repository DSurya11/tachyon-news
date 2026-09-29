import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export function Stat({ label, children, footer, className }: { label: string; children: ReactNode; footer?: ReactNode; className?: string }) {
  return (
    <div className={cn('flex min-w-0 flex-col justify-between gap-3 rounded-xl border bg-card p-4 shadow-(--shadow-card)', className)}>
      <div className="text-[13px] text-muted-foreground">{label}</div>
      <div className="text-[28px] leading-none font-medium tracking-tight">{children}</div>
      {footer && <div className="min-w-0 text-xs text-muted-foreground">{footer}</div>}
    </div>
  )
}

export function Card({ title, aside, children, className }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn('relative min-w-0 overflow-hidden rounded-xl border bg-card shadow-(--shadow-card)', className)}>
      {(title || aside) && (
        <header className="flex items-center justify-between gap-3 px-5 pt-4 pb-2">
          <h2 className="text-[14px] font-medium">{title}</h2>
          {aside && <div className="text-xs text-muted-foreground">{aside}</div>}
        </header>
      )}
      {children}
    </section>
  )
}
