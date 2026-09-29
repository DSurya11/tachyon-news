import { useEffect, useState, type RefObject } from 'react'

/*
  "Has this element come near the viewport yet?" — one shared IntersectionObserver for the
  whole app instead of one per element (a long wire has hundreds of ticker chips).
*/
const onSeen = new WeakMap<Element, () => void>()
let io: IntersectionObserver | null = null

function observer() {
  io ??= new IntersectionObserver((entries) => {
    for (const e of entries) {
      if (!e.isIntersecting) continue
      onSeen.get(e.target)?.()
      onSeen.delete(e.target)
      io?.unobserve(e.target)
    }
  }, { rootMargin: '240px 0px' })
  return io
}

export function useSeenOnce(ref: RefObject<Element | null>) {
  const [seen, setSeen] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el || seen) return
    onSeen.set(el, () => setSeen(true))
    observer().observe(el)
    return () => {
      onSeen.delete(el)
      io?.unobserve(el)
    }
  }, [ref, seen])
  return seen
}
