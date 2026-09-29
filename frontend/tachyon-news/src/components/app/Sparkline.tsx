import { motion } from 'motion/react'
import { useId } from 'react'

/** Trend line that draws itself in when first shown. */
export function Sparkline({ values, width = 96, height = 28, className }: { values: number[]; width?: number; height?: number; className?: string }) {
  const id = useId()
  const v = values.filter((x) => Number.isFinite(x))
  if (v.length < 2) return <svg width={width} height={height} className={className} aria-hidden />
  const min = Math.min(...v), max = Math.max(...v), rng = max - min || 1
  const pts = v.map((y, i) => [(i / (v.length - 1)) * width, height - 2 - ((y - min) / rng) * (height - 4)] as const)
  const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const up = v[v.length - 1] >= v[0]
  const color = up ? 'var(--up)' : 'var(--down)'
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden>
      <defs>
        <linearGradient id={id} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor={color} stopOpacity=".22" />
          <stop offset="1" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      <motion.path d={`${d} L${width},${height} L0,${height} Z`} fill={`url(#${id})`}
        initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.8, delay: 0.3 }} />
      <motion.path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round"
        initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1] }} />
    </svg>
  )
}
