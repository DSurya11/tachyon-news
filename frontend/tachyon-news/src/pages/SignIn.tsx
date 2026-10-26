import { ArrowRight, BadgeCheck, Eye, EyeOff, LoaderCircle } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { Logo } from '@/components/app/Logo'
import { SentimentGlyph } from '@/components/app/Sentiment'
import { useAuth } from '@/hooks/use-auth'
import { useTheme } from '@/hooks/use-theme'
import { config } from '@/lib/config'
import { renderGoogleButton } from '@/lib/google'
import { mock } from '@/lib/mock'
import { cn } from '@/lib/utils'

type Mode = 'signin' | 'signup'

/* Left panel: the product, shown rather than described — a slow column of checked headlines. */
function WirePreview() {
  const rows = mock.articles()
  const col = [...rows, ...rows]
  return (
    <div className="relative h-full overflow-hidden [mask-image:linear-gradient(to_bottom,transparent,#000_14%,#000_86%,transparent)]">
      <div className="signin-wire space-y-2.5">
        {col.map((a, i) => (
          <div key={i} className="relative rounded-xl border bg-card px-4 py-3.5 shadow-(--shadow-card)">
            <span aria-hidden className={cn('absolute inset-y-3 left-0 w-[2px] rounded-full',
              a.sentiment === 'bullish' ? 'bg-up' : a.sentiment === 'bearish' ? 'bg-down' : 'bg-border')} />
            <div className="text-[13.5px] leading-snug font-medium">{a.headline}</div>
            <div className="mt-1.5 flex items-center gap-3 text-[11.5px] text-muted-foreground">
              <span className="font-medium text-foreground/75">{a.source_name}</span>
              <span className={cn('inline-flex items-center gap-1', a.sentiment === 'bullish' && 'text-up', a.sentiment === 'bearish' && 'text-down')}>
                <SentimentGlyph value={a.sentiment} />{a.sentiment}
              </span>
              {a.verified && <span className="inline-flex items-center gap-1"><BadgeCheck className="size-3.5" strokeWidth={1.75} />Verified</span>}
              {a.tickers[0] && <span className="num ml-auto rounded border bg-background px-1.5 py-px text-[10.5px] text-foreground/80">{a.tickers[0]}</span>}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

function Field({ label, children, hint }: { label: string; children: ReactNode; hint?: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-baseline justify-between text-[13px] font-medium">{label}{hint}</span>
      {children}
    </label>
  )
}

const input = 'h-11 w-full rounded-lg border bg-surface px-3.5 text-[14.5px] outline-none transition-[border-color,box-shadow] placeholder:text-muted-foreground/70 focus:border-foreground/40 focus:shadow-[0_0_0_3px_color-mix(in_oklch,var(--ring)_18%,transparent)]'

export default function SignIn({ mode }: { mode: Mode }) {
  const { signIn, signUp, signInWithGoogle, options, offline } = useAuth()
  const { resolved } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const next = new URLSearchParams(location.search).get('next') || '/'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')
  const [show, setShow] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const googleEl = useRef<HTMLDivElement>(null)
  const signup = mode === 'signup'

  const done = () => navigate(next.startsWith('/') ? next : '/', { replace: true })

  useEffect(() => {
    const el = googleEl.current
    if (!el || !options?.google_client_id) return
    renderGoogleButton(el, options.google_client_id, resolved === 'dark', async (credential) => {
      setError(null)
      setBusy(true)
      try { await signInWithGoogle(credential); done() } catch (err) { setError((err as Error).message) } finally { setBusy(false) }
    }).catch(() => el.replaceChildren())
  }, [options?.google_client_id, resolved]) // eslint-disable-line react-hooks/exhaustive-deps

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    if (signup && password.length < 8) return setError('Use at least 8 characters for your password.')
    setBusy(true)
    try {
      if (signup) await signUp(email, password, name || undefined)
      else await signIn(email, password)
      done()
    } catch (err) {
      setError(err instanceof TypeError ? `Can't reach the server at ${config.apiUrl}.` : (err as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    // Desktop is pinned to the viewport: the preview column scrolls inside its own panel.
    <div className="grid min-h-dvh lg:h-dvh lg:grid-cols-[minmax(0,1.1fr)_minmax(440px,0.9fr)] lg:overflow-hidden">
      {/* Product panel */}
      <aside className="relative hidden min-h-0 flex-col border-r bg-sidebar px-12 pt-10 pb-0 lg:flex">
        <Logo />
        <div className="mt-16 max-w-[34rem]">
          <h1 className="font-serif text-[46px] leading-[1.04] font-medium tracking-[-0.02em] text-balance">
            Every headline, read and checked against its source.
          </h1>
          <p className="mt-5 max-w-md text-[15px] leading-relaxed text-muted-foreground">
            US and Indian markets, summarised every hour. A daily brief cites each claim, and the stories that matter most are ranked for you.
          </p>
        </div>
        <div className="mt-10 min-h-0 flex-1"><WirePreview /></div>
      </aside>

      {/* Form */}
      <main className="flex min-h-0 flex-col overflow-y-auto px-5 py-8 sm:px-10">
        <div className="lg:hidden"><Logo /></div>
        <div className="m-auto w-full max-w-[380px] py-10">
          <h2 className="text-[27px] leading-tight font-semibold tracking-[-0.02em]">{signup ? 'Create your account' : 'Sign in'}</h2>
          <p className="mt-2 text-[14.5px] text-muted-foreground">
            {signup ? 'Free, and it takes ten seconds.' : 'Welcome back. The wire kept running while you were away.'}
          </p>

          {offline && (
            <div role="status" className="mt-6 rounded-lg border border-signal/40 bg-signal/10 px-3.5 py-3 text-[13px] leading-relaxed">
              Can't reach the server at <span className="num">{config.apiUrl}</span> right now. Retrying automatically; if the
              laptop is off or asleep, start it (<span className="num">make up</span>). Or{' '}
              <a href="?demo=1#/" className="font-medium underline underline-offset-4">explore the demo data</a>.
            </div>
          )}

          {options?.google_client_id && (
            <>
              <div ref={googleEl} className="mt-7 flex h-11 w-full justify-center" aria-label="Continue with Google" />
              <div className="my-6 flex items-center gap-3 text-xs text-muted-foreground"><span className="h-px flex-1 bg-border" />or<span className="h-px flex-1 bg-border" /></div>
            </>
          )}

          <form onSubmit={submit} className={cn('space-y-4', !options?.google_client_id && 'mt-8')} noValidate>
            {signup && (
              <Field label="Name" hint={<span className="text-xs font-normal text-muted-foreground">Optional</span>}>
                <input className={input} value={name} onChange={(e) => setName(e.target.value)} autoComplete="name" maxLength={80} placeholder="Rahul Sharma" />
              </Field>
            )}
            <Field label="Email">
              <input className={input} type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" required
                autoFocus placeholder="rahul.sharma@company.in" inputMode="email" />
            </Field>
            <Field label="Password" hint={signup ? <span className="text-xs font-normal text-muted-foreground">8+ characters</span> : undefined}>
              <span className="relative block">
                <input className={cn(input, 'pr-11')} type={show ? 'text' : 'password'} value={password} onChange={(e) => setPassword(e.target.value)}
                  autoComplete={signup ? 'new-password' : 'current-password'} required minLength={signup ? 8 : undefined} maxLength={128} />
                <button type="button" onClick={() => setShow((v) => !v)} aria-label={show ? 'Hide password' : 'Show password'}
                  className="absolute inset-y-0 right-0 grid w-11 place-items-center text-muted-foreground transition-colors hover:text-foreground">
                  {show ? <EyeOff className="size-4" strokeWidth={1.75} /> : <Eye className="size-4" strokeWidth={1.75} />}
                </button>
              </span>
            </Field>

            <p aria-live="polite" className={cn('min-h-5 text-[13px] text-down', !error && 'invisible')}>{error ?? '.'}</p>

            <button type="submit" disabled={busy || !email || !password}
              className="group flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-foreground text-[14.5px] font-medium text-background transition-opacity hover:opacity-90 disabled:opacity-50">
              {busy ? <LoaderCircle className="size-4 animate-spin" /> : <>{signup ? 'Create account' : 'Sign in'}<ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" /></>}
            </button>
          </form>

          <p className="mt-6 text-center text-[13.5px] text-muted-foreground">
            {signup ? 'Already have an account? ' : 'New here? '}
            <Link to={{ pathname: signup ? '/login' : '/signup', search: location.search }} className="font-medium text-foreground underline-offset-4 hover:underline">
              {signup ? 'Sign in' : 'Create an account'}
            </Link>
          </p>
          <p className="mt-2 text-center text-[13.5px] text-muted-foreground">
            Just looking? <a href="?demo=1#/" className="font-medium text-foreground underline-offset-4 hover:underline">Explore with sample data</a>
          </p>
        </div>
        <p className="text-center text-xs text-muted-foreground">Written by AI from public news. It can be wrong. Not investment advice.</p>
      </main>
    </div>
  )
}
