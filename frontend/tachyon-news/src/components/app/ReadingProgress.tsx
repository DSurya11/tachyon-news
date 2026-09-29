import { useEffect, useRef } from 'react'

/*
  Reading progress: a 2px rule along the top edge of the window. It fills exactly as far as
  the page is scrolled, with no easing lag.

  Where the browser has native scroll timelines, CSS drives it (index.css: .reading-progress):
  exact, off the main thread, and it follows the page as it grows or shrinks. Elsewhere this
  hook does the same arithmetic on scroll, and again whenever the page changes size, because
  content loading or rows rendering in changes the length without any scroll event.
*/
const nativeTimeline = typeof CSS !== 'undefined' && CSS.supports?.('animation-timeline: scroll()')

export function ReadingProgress() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (nativeTimeline || !el) return
    let frame = 0
    const update = () => {
      frame = 0
      const max = document.documentElement.scrollHeight - window.innerHeight
      const p = max > 0 ? Math.min(1, Math.max(0, window.scrollY / max)) : 0
      el.style.transform = `scaleX(${p})`
    }
    const schedule = () => { if (!frame) frame = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    const ro = new ResizeObserver(schedule)
    ro.observe(document.body)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      ro.disconnect()
    }
  }, [])

  return (
    <div ref={ref} aria-hidden style={{ transform: 'scaleX(0)' }}
      className="reading-progress pointer-events-none fixed inset-x-0 top-0 z-50 h-[2px] origin-left bg-foreground" />
  )
}
