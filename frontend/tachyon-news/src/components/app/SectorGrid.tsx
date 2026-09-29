import { Link } from 'react-router-dom'
import { MagicCard } from '@/components/ui/magic-card'
import { cn } from '@/lib/utils'
import { SplitBar } from './Sentiment'

interface SectorStat { name: string; count: number; bullish: number; neutral: number; bearish: number; net: number }

export function SectorGrid({ sectors }: { sectors: SectorStat[] }) {
  const max = Math.max(1, ...sectors.map((s) => s.count))
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
      {sectors.map((s) => {
        const bias = s.net >= 0.05 ? 'Bullish' : s.net <= -0.05 ? 'Bearish' : 'Mixed'
        return (
          <Link key={s.name} to={{ pathname: '/wire', search: `?sector=${encodeURIComponent(s.name)}` }} className="rounded-xl">
            <MagicCard className="rounded-xl" gradientSize={180} gradientOpacity={0}
              gradientFrom="var(--foreground)" gradientTo="var(--muted-foreground)">
              <div className="flex h-full flex-col gap-3 p-4">
                <div className="flex items-start justify-between gap-2">
                  <span className="text-[13px] leading-tight font-medium">{s.name}</span>
                  <span className={cn('text-[11px]', bias === 'Bullish' && 'text-up', bias === 'Bearish' && 'text-down', bias === 'Mixed' && 'text-muted-foreground')}>{bias}</span>
                </div>
                <div className="flex items-end justify-between gap-2">
                  <span className="num text-2xl font-medium tracking-tight">{s.count}</span>
                  <span className="mb-1 h-1 flex-1 max-w-20 overflow-hidden rounded-full bg-muted">
                    <span className="block h-full rounded-full bg-foreground/60" style={{ width: `${(s.count / max) * 100}%` }} />
                  </span>
                </div>
                <SplitBar {...s} />
              </div>
            </MagicCard>
          </Link>
        )
      })}
    </div>
  )
}
