import { ArrowUpRight, BadgeCheck, Trophy } from 'lucide-react'
import { memo } from 'react'
import { useInspectorActions } from '@/hooks/use-inspector'
import { useMarket } from '@/hooks/use-market'
import { ago, fmtDateTime } from '@/lib/format'
import type { Article } from '@/lib/types'
import { cn } from '@/lib/utils'
import { norm, SentimentGlyph } from './Sentiment'
import { TickerChip } from './TickerChip'

interface Props {
  article: Article
  compact?: boolean
  selected?: boolean
  fresh?: boolean
  /** Top-picks view: lead with the rank and the writer's one-line reason. */
  showPick?: boolean
}

/*
  Memoised: the wire renders hundreds of these, and they only change when their own
  article / selection does. They open the inspector through stable context actions,
  so URL changes elsewhere don't re-render them.
*/
export const StoryRow = memo(function StoryRow({ article: a, compact, selected, fresh, showPick }: Props) {
  const { openArticle } = useInspectorActions()
  const { market } = useMarket() // tag rows only when markets are mixed
  const s = norm(a.sentiment)
  const pick = a.top_pick
  const lead = showPick && pick
  return (
    <div role="button" tabIndex={0} data-row={a.id} aria-selected={selected}
      onClick={() => openArticle(a.id)}
      onKeyDown={(e) => { if (e.key === 'Enter') openArticle(a.id) }}
      className={cn('hover-row group @container relative cursor-pointer outline-none',
        // The wire's long list: off-screen rows skip layout and paint until scrolled near. Their
        // placeholder height is the measured typical row height at each width, so the page barely
        // changes length as rows render. Short compact lists render normally: no shifting at all.
        !compact && '[content-visibility:auto] [contain-intrinsic-size:auto_210px] sm:[contain-intrinsic-size:auto_165px] md:[contain-intrinsic-size:auto_138px] xl:[contain-intrinsic-size:auto_108px]',
        selected && 'shadow-[inset_0_0_0_1px_color-mix(in_oklch,var(--foreground)_22%,transparent)]', fresh && 'row-fresh')}>
      {/* sentiment rule; grows on hover */}
      <span aria-hidden className={cn('absolute inset-y-3 left-0 w-[2px] origin-center rounded-full transition-transform duration-300 group-hover:scale-y-[1.35]',
        s === 'bullish' && 'bg-up', s === 'bearish' && 'bg-down', s === 'neutral' && 'bg-border')} />
      <div className={cn('hover-body grid grid-cols-[44px_minmax(0,1fr)] gap-x-4 px-4 @2xl:grid-cols-[52px_minmax(0,1fr)_auto]', compact ? 'py-3' : 'py-4')}>
        <div className="num pt-0.5 text-xs text-muted-foreground" title={fmtDateTime(a.published_at)}>
          {lead
            ? <span className="block font-serif text-[26px] leading-none font-medium text-foreground tabular-nums">{String(pick.rank).padStart(2, '0')}</span>
            : ago(a.published_at)}
          {lead && <span className="mt-1.5 block">{ago(a.published_at)}</span>}
          {fresh && <span className="mt-1 block text-[10px] font-medium text-signal">New</span>}
        </div>
        <div className="min-w-0">
          <h3 className="text-[14.5px] leading-snug font-medium text-balance">
            <span className="hover-title">{a.headline}</span>
            <ArrowUpRight className="ml-1 inline size-3.5 -translate-x-1 text-muted-foreground opacity-0 transition-all group-hover:translate-x-0 group-hover:opacity-100" />
          </h3>
          {lead && pick.why && (
            <p className="mt-1.5 font-serif text-[15px] leading-snug text-foreground/85 italic">{pick.why}</p>
          )}
          {!compact && !lead && a.one_line && <p className="mt-1 line-clamp-2 text-[13.5px] leading-relaxed text-muted-foreground">{a.one_line}</p>}
          <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
            <span className="font-medium text-foreground/80">{a.source_name}</span>
            {market === 'all' && (
              <span className="num rounded-sm border px-1 py-px text-[10px] font-medium tracking-wider text-foreground/70">{a.market === 'india' ? 'INDIA' : 'INTL'}</span>
            )}
            <span>{a.sector}</span>
            <span className={cn('inline-flex items-center gap-1', s === 'bullish' && 'text-up', s === 'bearish' && 'text-down')}>
              <SentimentGlyph value={s} />{s}
            </span>
            {a.event_type && a.event_type !== 'other' && <span className="capitalize">{a.event_type}</span>}
            {a.verified && (
              <span className="inline-flex items-center gap-1 text-foreground/70" title="Quote and numbers matched to the article text">
                <BadgeCheck className="size-3.5" strokeWidth={1.75} />Verified
              </span>
            )}
            {pick && !lead && (
              <span className="inline-flex items-center gap-1 font-medium text-signal" title={pick.why}>
                <Trophy className="size-3.5" strokeWidth={1.75} />Top pick
              </span>
            )}
          </div>
        </div>
        {a.tickers.length > 0 && (
          <div className="col-start-2 mt-2.5 flex flex-wrap items-start gap-1 @2xl:col-start-3 @2xl:mt-0 @2xl:max-w-[210px] @2xl:justify-end">
            {a.tickers.slice(0, 3).map((t) => <TickerChip key={t} symbol={t} />)}
          </div>
        )}
      </div>
    </div>
  )
})
