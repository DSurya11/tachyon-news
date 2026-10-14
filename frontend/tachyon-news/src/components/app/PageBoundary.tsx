import { Component, type ReactNode } from 'react'
import { Empty } from './Empty'

/**
 * Catches an error thrown while its children render and shows `fallback` instead. Without one
 * React unmounts everything: a single bad value on one page left the whole dashboard blank,
 * with no way back but editing the address.
 */
export class ErrorBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    return this.state.failed ? this.props.fallback : this.props.children
  }
}

const reload = (
  <button type="button" onClick={() => window.location.reload()} className="text-sm font-medium underline">Reload</button>
)

/** In place of one page (keyed by the page in App, so opening another page clears it). */
export function PageFailed() {
  return (
    <div className="pt-10">
      <Empty title="This page couldn't be shown" action={reload}>Something on it failed to load. The other pages still work.</Empty>
    </div>
  )
}

/** The last resort, when the frame around the pages failed too. */
export function AppFailed() {
  return (
    <div className="grid min-h-dvh place-items-center p-6">
      <Empty title="Tachyon News couldn't be shown" action={reload}>Something failed while drawing the page. Reloading usually fixes it.</Empty>
    </div>
  )
}
