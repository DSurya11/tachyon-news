import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import { useArticle } from '@/hooks/queries'
import type { Article } from '@/lib/types'
import { useInspector } from '@/hooks/use-inspector'
import { ago } from '@/lib/format'

/** An inline source citation: hover to preview, click to open the story. */
export function Cite({ id, local }: { id: number; local?: Article }) {
  const { openArticle } = useInspector()
  return (
    <HoverCard openDelay={120} closeDelay={60}>
      <HoverCardTrigger asChild>
        <button type="button" onClick={() => openArticle(id)}
          className="num mx-[1px] inline-flex h-[18px] min-w-[22px] -translate-y-[2px] items-center justify-center rounded-[5px] border bg-muted px-1 align-middle text-[10.5px] font-medium text-muted-foreground transition-colors hover:border-foreground/30 hover:text-foreground">
          {id}
        </button>
      </HoverCardTrigger>
      <HoverCardContent className="w-80 p-4" side="top">
        <CitePreview id={id} local={local} />
      </HoverCardContent>
    </HoverCard>
  )
}

function CitePreview({ id, local }: { id: number; local?: { headline: string; source_name: string | null; published_at: string | null; one_line: string | null } }) {
  const { data, isLoading } = useArticle(local ? null : id)
  const a = local ?? data
  if (!a) return <div className="text-sm text-muted-foreground">{isLoading ? 'Loading source…' : `Source #${id}`}</div>
  return (
    <div className="space-y-1.5">
      <div className="text-xs text-muted-foreground">{a.source_name} · {ago(a.published_at)} ago</div>
      <div className="text-sm leading-snug font-medium">{a.headline}</div>
      {a.one_line && <div className="text-[13px] leading-relaxed text-muted-foreground">{a.one_line}</div>}
      <div className="pt-1 text-xs text-muted-foreground">Click to open</div>
    </div>
  )
}
