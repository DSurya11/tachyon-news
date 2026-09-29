import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { BlurFade } from '@/components/ui/blur-fade'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Cite } from '@/components/app/Cite'
import { Empty } from '@/components/app/Empty'
import { ReadingProgress } from '@/components/app/ReadingProgress'
import { StoryRow } from '@/components/app/StoryRow'
import { WordsReveal } from '@/components/app/Reveal'
import { useArticlesByIds, useReport, useReports } from '@/hooks/queries'
import { ago, fmtDateTime, fmtDay } from '@/lib/format'
import { renderMarkdown } from '@/lib/markdown'
import { cn } from '@/lib/utils'

function useActiveSection(ids: string[]) {
  const [active, setActive] = useState<string | null>(null)
  useEffect(() => {
    const els = ids.map((id) => document.getElementById(id)).filter(Boolean) as HTMLElement[]
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) if (e.isIntersecting) setActive(e.target.id)
    }, { rootMargin: '-15% 0px -70% 0px' })
    els.forEach((el) => io.observe(el))
    return () => io.disconnect()
  }, [ids.join('|')]) // eslint-disable-line react-hooks/exhaustive-deps
  return active
}

export default function Brief() {
  const { day } = useParams()
  const navigate = useNavigate()
  const { data: report, isLoading } = useReport(day)
  const { data: history = [] } = useReports()
  // The brief's own sources, however old: not limited to the chosen time range.
  const { data: sources = [] } = useArticlesByIds(report?.article_ids)
  const byId = new Map(sources.map((a) => [a.id, a]))

  const rendered = report ? renderMarkdown(report.content, (id) => <Cite id={id} local={byId.get(id)} />) : null
  const headings = rendered?.headings ?? []
  const active = useActiveSection([...headings.map((h) => h.id), 'sources'])

  if (isLoading) {
    return <div className="mx-auto max-w-3xl space-y-4 pt-6">{[40, 80, 100, 95, 90, 60].map((w, i) => <div key={i} className="h-4 animate-pulse rounded bg-muted" style={{ width: `${w}%` }} />)}</div>
  }
  if (!report || !rendered) {
    return <div className="pt-10"><Empty title={day ? `No brief for ${fmtDay(day)}` : 'No brief yet'}>Briefs are written once enough stories for the trading day have been extracted and verified.</Empty></div>
  }

  return (
    <div className="relative">
      <ReadingProgress />

      <header className="mx-auto max-w-[1080px] border-b pb-8">
        <div className="flex flex-wrap items-center justify-between gap-3 text-[13px] text-muted-foreground">
          <span>Daily brief · US trading day</span>
          {history.length > 1 && (
            <Select value={report.trading_day} onValueChange={(v) => navigate(`/brief/${v}`)}>
              <SelectTrigger aria-label="Choose a day" className="h-8 w-[210px] text-[13px]"><SelectValue /></SelectTrigger>
              <SelectContent>{history.map((h) => <SelectItem key={h.trading_day} value={h.trading_day}>{fmtDay(h.trading_day, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}</SelectItem>)}</SelectContent>
            </Select>
          )}
        </div>
        <WordsReveal key={report.trading_day} text={fmtDay(report.trading_day)}
          className="mt-5 font-serif text-[40px] leading-[1.05] font-medium tracking-[-0.02em] sm:text-[56px]" />
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-muted-foreground">
          Written {fmtDateTime(report.created_at)} ({ago(report.created_at)} ago), from{' '}
          {report.article_ids.length} verified and extracted stories. Every claim links to its source — hover a number to preview it.
        </p>
      </header>

      <div className="mx-auto grid max-w-[1080px] gap-12 pt-10 lg:grid-cols-[minmax(0,1fr)_200px]">
        <BlurFade delay={0.15}>
          <article className={cn(
            'font-serif text-[19px] leading-[1.72] text-foreground/90',
            '[&_h2]:mt-12 [&_h2]:mb-3 [&_h2]:scroll-mt-24 [&_h2]:font-sans [&_h2]:text-[22px] [&_h2]:font-semibold [&_h2]:tracking-tight [&_h2]:text-foreground [&_h2:first-child]:mt-0',
            '[&_h3]:mt-8 [&_h3]:mb-2 [&_h3]:font-sans [&_h3]:text-[17px] [&_h3]:font-semibold [&_h3]:text-foreground',
            '[&_p]:my-4 [&_p]:max-w-[68ch] [&_ul]:my-4 [&_ul]:max-w-[66ch] [&_ul]:list-disc [&_ul]:pl-6 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:pl-6 [&_li]:my-2 [&_li]:pl-1 [&_li::marker]:text-muted-foreground',
            '[&_strong]:font-semibold [&_strong]:text-foreground [&_hr]:my-10 [&_blockquote]:border-l-2 [&_blockquote]:pl-5 [&_blockquote]:italic',
            '[&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:font-mono [&_code]:text-[0.85em] [&_a]:underline [&_a]:underline-offset-4',
            // drop cap on the opening paragraph
            '[&>p:first-of-type]:first-letter:float-left [&>p:first-of-type]:first-letter:mt-1 [&>p:first-of-type]:first-letter:mr-3 [&>p:first-of-type]:first-letter:text-[64px] [&>p:first-of-type]:first-letter:leading-[0.8] [&>p:first-of-type]:first-letter:font-medium [&>p:first-of-type]:first-letter:text-foreground',
          )} id="brief-body">
            {rendered.nodes}
          </article>
        </BlurFade>

        <nav aria-label="Sections" className="hidden lg:block">
          <div className="sticky top-24 space-y-1 border-l">
            <div className="px-4 pb-2 text-xs text-muted-foreground">On this page</div>
            {[...headings, { id: 'sources', text: 'Sources' }].map((h) => (
              <a key={h.id} href={`#${h.id}`} onClick={(e) => { e.preventDefault(); document.getElementById(h.id)?.scrollIntoView({ behavior: 'smooth' }) }}
                className={cn('relative -ml-px block border-l px-4 py-1 text-[13px] transition-colors',
                  active === h.id ? 'border-foreground text-foreground' : 'border-transparent text-muted-foreground hover:text-foreground')}>
                {h.text}
              </a>
            ))}
          </div>
        </nav>
      </div>

      <section id="sources" className="mx-auto mt-16 max-w-[1080px] scroll-mt-24">
        <div className="flex items-baseline justify-between border-b pb-3">
          <h2 className="text-[15px] font-semibold">Sources</h2>
          <span className="text-xs text-muted-foreground">{report.article_ids.length} articles informed this brief</span>
        </div>
        <div className="divide-y">{sources.map((a) => <StoryRow key={a.id} article={a} compact />)}</div>
        <p className="pt-10 pb-4 text-center text-xs text-muted-foreground">Written by AI from extracted news. It can be wrong. Not investment advice.</p>
      </section>
    </div>
  )
}
