import type { CSSProperties } from "react"

import { cn } from "@/lib/utils"

/**
 * A single light that travels around the parent's border (parent needs `relative` and a radius).
 * Pure CSS (see `.edge-light` in index.css): a transform-only animation on the compositor,
 * coloured by the theme's neutral `--beam` token.
 */
export function BorderBeam({ duration = 9, className }: { duration?: number; className?: string }) {
  return (
    <div aria-hidden className={cn("edge-light", className)} style={{ "--edge-duration": `${duration}s` } as CSSProperties}>
      <i />
    </div>
  )
}
