import { useState, useSyncExternalStore, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Empty } from '@/components/app/Empty'
import { PageHeader } from '@/components/app/PageHeader'
import { StoryRow } from '@/components/app/StoryRow'
import { api, HttpError, onModeChange } from '@/lib/api'
import type { AskResult } from '@/lib/types'

const EXAMPLES = [
  'Bank stocks with negative news this week, and how they moved',
  'What happened with Nvidia recently?',
  'Indian stocks with merger news in the last month',
]

const STOPPED: Record<AskResult['stopped'], string> = {
  answered: '',
  step_limit: 'It ran out of steps before finishing.',
  token_budget: 'It used its token budget before finishing.',
  error: 'The model service failed.',
}

/**
 * Ask the news: one question, answered by an agent from Tachyon's own stories and prices
 * (backend/ask.py). The stories it relies on are listed under the answer, as on the wire;
 * code checks that each came from its searches and that its percentages came from the data.
 */
export default function Ask() {
  const demo = useSyncExternalStore(onModeChange, () => api.demo)
  const [question, setQuestion] = useState('')
  const [asked, setAsked] = useState('')
  const [result, setResult] = useState<AskResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(e?: FormEvent, text = question) {
    e?.preventDefault()
    const q = text.trim()
    if (q.length < 3 || busy) return
    setBusy(true); setError(null); setAsked(q)
    try {
      setResult(await api.ask(q))
    } catch (err) {
      setResult(null)
      setError(err instanceof HttpError ? err.message : 'Could not reach the API.')
    } finally {
      setBusy(false)
    }
  }

  const tools = result?.steps.filter((s) => s.kind === 'tool') ?? []

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader kicker="Agent" title="Ask the news">
        Questions about the stories and prices in this database. Every story it cites is listed under the answer.
      </PageHeader>

      {demo ? (
        <Empty title="Ask needs the live API">Sample data has no agent behind it.</Empty>
      ) : (
        <>
          <form onSubmit={submit} className="space-y-2">
            <Textarea
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void submit() } }}
              maxLength={300}
              rows={2}
              placeholder="e.g. Bank stocks with negative news this week, and how they moved"
              aria-label="Your question"
            />
            <div className="flex items-center justify-between gap-3">
              <span className="num text-xs text-muted-foreground">{question.length}/300</span>
              <Button type="submit" disabled={busy || question.trim().length < 3}>{busy ? 'Working…' : 'Ask'}</Button>
            </div>
          </form>

          {!result && !busy && !error && (
            <div className="mt-6 space-y-1">
              <div className="text-xs text-muted-foreground">Try</div>
              {EXAMPLES.map((ex) => (
                <button key={ex} type="button" onClick={() => { setQuestion(ex); void submit(undefined, ex) }}
                  className="hover-row block w-full rounded-lg px-3 py-2 text-left text-[14px]">{ex}</button>
              ))}
            </div>
          )}

          {busy && <p className="mt-6 text-sm text-muted-foreground">Searching the stories… usually 10 to 40 seconds on the free models.</p>}
          {error && <p className="mt-6 text-sm text-down">{error}</p>}

          {result && !busy && (
            <section className="mt-8">
              <div className="text-xs text-muted-foreground">{asked}</div>
              <p className="mt-2 whitespace-pre-line text-[15px] leading-relaxed">{result.answer}</p>
              {STOPPED[result.stopped] && <p className="mt-2 text-sm text-muted-foreground">{STOPPED[result.stopped]}</p>}
              {result.unchecked.length > 0 && (
                <p className="mt-2 text-sm text-signal">Not found in the data, check before relying on: {result.unchecked.join(', ')}</p>
              )}

              {result.stories.length > 0 && (
                <div className="mt-6 border-t">
                  <div className="divide-y">{result.stories.map((a) => <StoryRow key={a.id} article={a} compact />)}</div>
                </div>
              )}

              <details className="mt-6 text-xs text-muted-foreground">
                <summary className="cursor-pointer">
                  How it answered: {tools.length} tool call{tools.length === 1 ? '' : 's'} · <span className="num">{result.seconds.toFixed(1)} s</span> · <span className="num">{result.tokens.toLocaleString()}</span> tokens{result.cached ? ' · repeated question, stored answer' : ''}
                </summary>
                <ol className="mt-2 space-y-1">
                  {tools.map((s, i) => (
                    <li key={i} className="num break-all">{s.failed ? '✗ ' : ''}{s.tool}({s.arguments})</li>
                  ))}
                </ol>
              </details>
              <p className="pt-8 text-center text-xs text-muted-foreground">Written by AI from extracted news. It can be wrong. Not investment advice.</p>
            </section>
          )}
        </>
      )}
    </div>
  )
}
