import { createContext, useContext, useEffect, useLayoutEffect, useMemo, useRef, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

/*
  The inspector is a stack of panels kept in the URL (?p=a:1042,t:NVDA), so it is shareable,
  survives a reload, and Back closes the newest panel. Older links (?a=<id> / ?t=<sym>) still open.

  Opening from the page starts a new stack. Opening from inside a panel (a ticker in a story, a
  story in a ticker's news) puts the new panel right after that one, so they sit side by side.
  Each panel provides its index through PanelIndexContext; `useInspectorActions()` reads it.

  Reading the URL subscribes a component to every navigation. Rows and chips only need to
  *open* panels, so they use `useInspectorActions()` — stable callbacks that never re-render
  them. Only the workspace reads the stack with `useInspector()`.
*/
export type Panel = { kind: 'a'; id: number } | { kind: 't'; sym: string }

const MAX_PANELS = 8

// eslint-disable-next-line react-refresh/only-export-components
export const panelKey = (p: Panel) => (p.kind === 'a' ? `a:${p.id}` : `t:${p.sym}`)

function parseStack(params: URLSearchParams): Panel[] {
  const raw = params.get('p')
  if (raw) {
    return raw.split(',').flatMap((item): Panel[] => {
      const [kind, ...rest] = item.split(':')
      const value = rest.join(':')
      if (kind === 'a' && /^\d+$/.test(value)) return [{ kind: 'a', id: Number(value) }]
      if (kind === 't' && value) return [{ kind: 't', sym: value }]
      return []
    })
  }
  const a = params.get('a'), t = params.get('t')
  return a && /^\d+$/.test(a) ? [{ kind: 'a', id: Number(a) }] : t ? [{ kind: 't', sym: t }] : []
}

interface Core {
  setStack: (next: Panel[]) => void
  getStack: () => Panel[]
}

const CoreCtx = createContext<Core | null>(null)
/** Index of the panel a component is rendered in; null on the page itself. */
// eslint-disable-next-line react-refresh/only-export-components
export const PanelIndexContext = createContext<number | null>(null)

// The element the user last pressed, so a new panel can unfold out of it (and a ticker chip
// can fly into the new panel's title).
export interface Origin { rect: DOMRect; chip: boolean }
let lastOrigin: Origin | null = null
// eslint-disable-next-line react-refresh/only-export-components
export const takeOrigin = () => { const r = lastOrigin; lastOrigin = null; return r }

export function InspectorProvider({ children }: { children: ReactNode }) {
  const [params, setParams] = useSearchParams()
  const latest = useRef({ params, setParams })
  useLayoutEffect(() => { latest.current = { params, setParams } })

  useEffect(() => {
    const onDown = (e: PointerEvent) => {
      const el = (e.target as Element | null)?.closest?.('[data-row], button, a, [role="button"]')
      lastOrigin = el ? { rect: el.getBoundingClientRect(), chip: el.matches('button.num') } : null
    }
    document.addEventListener('pointerdown', onDown, true)
    return () => document.removeEventListener('pointerdown', onDown, true)
  }, [])

  const core = useMemo<Core>(() => ({
    getStack: () => parseStack(latest.current.params),
    setStack: (next) => {
      const p = new URLSearchParams(latest.current.params)
      p.delete('a'); p.delete('t')
      if (next.length) p.set('p', next.slice(-MAX_PANELS).map(panelKey).join(','))
      else p.delete('p')
      latest.current.setParams(p)
    },
  }), [])
  return <CoreCtx.Provider value={core}>{children}</CoreCtx.Provider>
}

function useCore(): Core {
  const ctx = useContext(CoreCtx)
  if (!ctx) throw new Error('inspector hooks used outside InspectorProvider')
  return ctx
}

export interface Actions {
  openArticle: (id: number) => void
  openTicker: (sym: string) => void
  /** Close everything. */
  close: () => void
}

function open(core: Core, from: number | null, panel: Panel) {
  const stack = core.getStack()
  if (from == null) {
    if (stack.length === 1 && panelKey(stack[0]) === panelKey(panel)) return
    core.setStack([panel])
    return
  }
  const kept = stack.slice(0, from + 1)
  if (stack[from + 1] && panelKey(stack[from + 1]) === panelKey(panel) && stack.length === from + 2) return
  if (kept.some((p) => panelKey(p) === panelKey(panel))) return // already open to the left
  core.setStack([...kept, panel])
}

/** Stable open/close callbacks, aware of which panel (if any) they are called from. */
// eslint-disable-next-line react-refresh/only-export-components
export function useInspectorActions(): Actions {
  const core = useCore()
  const from = useContext(PanelIndexContext)
  return useMemo(() => ({
    openArticle: (id) => open(core, from, { kind: 'a', id }),
    openTicker: (sym) => open(core, from, { kind: 't', sym }),
    close: () => core.setStack([]),
  }), [core, from])
}

/** The panel stack + actions. Subscribes to the URL — use only where the stack is shown. */
// eslint-disable-next-line react-refresh/only-export-components
export function useInspector() {
  const [params] = useSearchParams()
  const core = useCore()
  const actions = useInspectorActions()
  const stack = parseStack(params)
  return {
    stack,
    ...actions,
    /** Remove one panel. */
    closeAt: (i: number) => core.setStack(stack.filter((_, j) => j !== i)),
    /** Keep panels up to and including i (a collapsed tab was clicked). */
    keepThrough: (i: number) => core.setStack(stack.slice(0, i + 1)),
  }
}
