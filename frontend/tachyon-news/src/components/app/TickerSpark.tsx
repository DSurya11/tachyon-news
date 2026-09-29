import { useInView } from 'motion/react'
import { useRef } from 'react'
import { useCandles } from '@/hooks/queries'
import { Sparkline } from './Sparkline'

export function TickerSpark({ symbol, width = 88, height = 26 }: { symbol: string; width?: number; height?: number }) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '100px' })
  const { data } = useCandles(inView ? symbol : null)
  return <span ref={ref} className="inline-block" style={{ width, height }}>{data && <Sparkline values={data.candles} width={width} height={height} />}</span>
}
