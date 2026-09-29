/*
  The product, explained by its own live numbers: stories flow from the wire through
  body fetch, LLM extraction and source verification into the daily brief.
*/
import { BadgeCheck, BookOpenText, Cpu, FileText, Radio } from 'lucide-react'
import { useEffect, useRef, useState, type CSSProperties, type ReactNode, type RefObject } from 'react'
import { cn } from '@/lib/utils'

type Ref = RefObject<HTMLDivElement | null>

/**
 * Straight connectors between node centres, each with a short light that slides across.
 * The light moves with `transform` only (compositor), unlike an SVG dash or gradient.
 */
function Connectors({ container, nodes }: { container: Ref; nodes: Ref[] }) {
  const [segs, setSegs] = useState<{ x: number; y: number; w: number }[]>([])
  useEffect(() => {
    const box = container.current
    if (!box) return
    const measure = () => {
      const c = box.getBoundingClientRect()
      const rects = nodes.map((r) => r.current?.getBoundingClientRect())
      setSegs(rects.slice(0, -1).flatMap((a, i) => {
        const b = rects[i + 1]
        if (!a || !b) return []
        const x = a.right - c.left
        return [{ x, y: a.top - c.top + a.height / 2, w: b.left - c.left - x }]
      }))
    }
    measure()
    const ro = new ResizeObserver(measure)
    ro.observe(box)
    return () => ro.disconnect()
  }, [container, nodes])
  return segs.map((s, i) => (
    <div key={i} aria-hidden className="pipe-link" style={{ left: s.x, top: s.y, width: s.w, '--pipe-delay': `${i * 0.35}s` } as CSSProperties}>
      <i />
    </div>
  ))
}

function Node({ nodeRef, icon, label, value, emphasis }: { nodeRef: RefObject<HTMLDivElement | null>; icon: ReactNode; label: string; value: ReactNode; emphasis?: boolean }) {
  return (
    <div className="z-10 flex flex-col items-center gap-2 text-center">
      <div ref={nodeRef}
        className={cn('grid size-11 place-items-center rounded-xl border bg-card shadow-(--shadow-raised)',
          emphasis && 'border-foreground/25 bg-foreground text-background')}>
        {icon}
      </div>
      <div className="leading-tight">
        <div className="num text-sm font-medium">{value}</div>
        <div className="text-[11px] text-muted-foreground">{label}</div>
      </div>
    </div>
  )
}

export function PipelineBeams({ scraped, extracted, verified, cited, briefLabel }: { scraped: number; extracted: number; verified: number; cited: number; briefLabel: string }) {
  const container = useRef<HTMLDivElement>(null)
  const refs = [useRef<HTMLDivElement>(null), useRef<HTMLDivElement>(null), useRef<HTMLDivElement>(null), useRef<HTMLDivElement>(null), useRef<HTMLDivElement>(null)]
  const icon = 'size-[18px]'
  return (
    <div ref={container} className="relative flex items-start justify-between gap-2 px-1 py-2">
      <Node nodeRef={refs[0]} icon={<Radio className={icon} strokeWidth={1.75} />} label="Scraped, 24h" value={scraped} />
      <Node nodeRef={refs[1]} icon={<Cpu className={icon} strokeWidth={1.75} />} label="Extracted" value={extracted} />
      <Node nodeRef={refs[2]} icon={<BadgeCheck className={icon} strokeWidth={1.75} />} label="Verified" value={verified} />
      <Node nodeRef={refs[3]} icon={<FileText className={icon} strokeWidth={1.75} />} label="Cited" value={cited} />
      <Node nodeRef={refs[4]} icon={<BookOpenText className={icon} strokeWidth={1.75} />} label="Brief" value={briefLabel} emphasis />
      <Connectors container={container} nodes={refs} />
    </div>
  )
}
