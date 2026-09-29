import { motion } from 'motion/react'
import { Fragment, type ElementType } from 'react'
import { cn } from '@/lib/utils'

/**
 * Headline reveal: words rise out of a soft blur, one after another.
 * Spaces stay real text between the word spans, so wrapped lines never start indented.
 */
export function WordsReveal({ text, as = 'h1', className, delay = 0 }: { text: string; as?: ElementType; className?: string; delay?: number }) {
  const Tag = as
  const words = text.split(/\s+/).filter(Boolean)
  return (
    <Tag className={cn(className)} aria-label={text}>
      {words.map((w, i) => (
        <Fragment key={`${w}-${i}`}>
          <motion.span aria-hidden className="inline-block will-change-transform"
            initial={{ opacity: 0, y: '0.35em', filter: 'blur(8px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            transition={{ duration: 0.55, delay: delay + i * 0.045, ease: [0.16, 1, 0.3, 1] }}>
            {w}
          </motion.span>
          {i < words.length - 1 && ' '}
        </Fragment>
      ))}
    </Tag>
  )
}
