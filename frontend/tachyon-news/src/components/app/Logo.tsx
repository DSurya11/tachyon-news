/* Wordmark: a bespoke "tick" glyph — the shape of a price print — next to the name. */
export function Logo({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <span className="grid size-7 place-items-center rounded-lg bg-foreground text-background">
        <svg viewBox="0 0 20 20" className="size-4" aria-hidden>
          <path d="M3 13.5 7.5 9l3 3L17 5.5" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
          <circle cx="17" cy="5.5" r="1.6" fill="currentColor" />
        </svg>
      </span>
      {!compact && (
        <span className="leading-none">
          <span className="block text-[15px] font-semibold tracking-tight">Tachyon News</span>
          <span className="block pt-0.5 text-[11px] text-muted-foreground">Market news, verified</span>
        </span>
      )}
    </span>
  )
}
