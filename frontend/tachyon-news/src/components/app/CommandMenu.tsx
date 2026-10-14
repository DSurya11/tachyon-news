import { Banknote, BookOpenText, Globe2, LayoutGrid, LogOut, Moon, Newspaper, Search, Star, Sun, Trophy } from 'lucide-react'
import { defaultFilter } from 'cmdk'
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { CommandDialog, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList, CommandShortcut } from '@/components/ui/command'
import { useNewsPages, useSummary } from '@/hooks/queries'
import { useAuth } from '@/hooks/use-auth'
import { useInspector } from '@/hooks/use-inspector'
import { CURRENCY_LABEL, useCurrency } from '@/hooks/use-currency'
import { MARKET_LABEL, useMarket } from '@/hooks/use-market'
import { useTheme } from '@/hooks/use-theme'
import { useWatchlist } from '@/hooks/use-watchlist'
import { ago } from '@/lib/format'

/*
  What counts as a match, and what Enter runs.

  Any short word could be a ticker, so it gets a "Look up X" row. That row used to sit first and
  win: Enter on "brief", "theme" or "energy" looked up a ticker by that name. Now, when the word
  names something (a page, a setting, a sector, a ticker in the news), that comes first and the
  lookup goes to the end; a symbol that names nothing else ("TSM") is still one Enter away.

  cmdk scores a word or its initials at about 0.8-0.9 and letters scattered through a phrase
  under 0.2. Pages, settings and sectors need the former: scattered letters made "india" offer
  Industrials and "tsm" Consumer Discretionary. (This cmdk version keeps groups in the order
  they are written, whatever they score, so the order below is the order on screen.)
*/
const NAMES = 0.5
const FIXED_ROWS = [
  'go overview', 'go wire feed', 'go brief', 'go watchlist', 'go top picks ai ranked important', 'toggle theme dark light',
  ...(['all', 'global', 'india'] as const).map((m) => `market ${MARKET_LABEL[m]}`),
  ...(['native', 'USD', 'INR'] as const).map((c) => `currency prices ${CURRENCY_LABEL[c]} ${c}`),
  'sign out log out',
]
const matches: typeof defaultFilter = (value, search, keywords) => {
  // Offered for this very text, or matched by the server (perhaps in the summary, not the headline).
  if (value.startsWith('lookup ') || value.startsWith('story ')) return 1
  const score = defaultFilter(value, search, keywords)
  if (value.startsWith('ticker ')) return score // already narrowed to symbols containing the text
  return score >= NAMES ? score : 0
}

export function CommandMenu({ open, setOpen }: { open: boolean; setOpen: (o: boolean) => void }) {
  const navigate = useNavigate()
  // Tickers and sectors of the chosen range (from the API's summary); stories are searched on the server.
  const { data: summary } = useSummary({ top: 200 })
  const { openArticle, openTicker } = useInspector()
  const { resolved, setTheme } = useTheme()
  const { list } = useWatchlist()
  const { market, setMarket } = useMarket()
  const { currency, setCurrency } = useCurrency()
  const { status, signOut } = useAuth()
  const [query, setQuery] = useState('')
  const run = (fn: () => void) => { setOpen(false); setQuery(''); fn() }

  const [needle, setNeedle] = useState('')
  useEffect(() => { const t = setTimeout(() => setNeedle(query.trim()), 250); return () => clearTimeout(t) }, [query])
  const { data: found, isFetching: searching } = useNewsPages({ q: needle }, 8, open && needle.length >= 2)
  const stories = needle.length >= 2 ? (found?.pages[0]?.articles ?? []) : []

  const tickers = summary?.tickers ?? []
  const upper = query.trim().toUpperCase()
  // Typing narrows to tickers that contain it (exact first); otherwise the most discussed. Every
  // match is listed, not just the top 40, so the fuzzy filter never has to guess a neighbour.
  const matching = upper
    ? tickers.filter((t) => t.symbol.includes(upper)).sort((a, b) => Number(b.symbol === upper) - Number(a.symbol === upper) || Number(b.symbol.startsWith(upper)) - Number(a.symbol.startsWith(upper)) || b.count - a.count)
    : tickers
  const shownTickers = [...new Set([...(upper ? [] : list), ...list.filter((s) => s.includes(upper)), ...matching.slice(0, 40).map((t) => t.symbol)])]
  const lookup = /^(?:[A-Z][A-Z0-9.-]{0,5}|[A-Z][A-Z0-9&-]{0,14}\.(?:NS|BO))$/.test(upper) && !shownTickers.includes(upper)
  const named = lookup && [...FIXED_ROWS, ...(summary?.sectors ?? []).map((x) => `sector ${x.name}`), ...shownTickers.map((x) => `ticker ${x}`)]
    .some((v) => defaultFilter(v, query.trim()) >= NAMES)
  const lookupRow = lookup && (
    <CommandItem value={`lookup ${upper}`} onSelect={() => run(() => openTicker(upper))}>
      <Search /> Look up <span className="num font-medium">{upper}</span>
    </CommandItem>
  )

  return (
    <CommandDialog open={open} onOpenChange={setOpen} filter={matches} title="Search" description="Search tickers, sectors and stories">
      <CommandInput placeholder="Search tickers, sectors, stories…" value={query} onValueChange={setQuery} />
      <CommandList>
        <CommandEmpty>No results.</CommandEmpty>
        <CommandGroup heading="Tickers">
          {shownTickers.map((s) => {
            const t = tickers.find((x) => x.symbol === s)
            return (
              <CommandItem key={s} value={`ticker ${s}`} onSelect={() => run(() => openTicker(s))}>
                {list.includes(s) ? <Star className="text-signal" /> : <span className="num w-4 text-center text-[10px] text-muted-foreground">$</span>}
                <span className="num font-medium">{s}</span>
                <span className="ml-auto text-xs text-muted-foreground">{t ? `${t.count} stories` : 'watchlist'}</span>
              </CommandItem>
            )
          })}
          {!named && lookupRow}
        </CommandGroup>
        <CommandGroup heading="Sectors">
          {(summary?.sectors ?? []).map((s) => (
            <CommandItem key={s.name} value={`sector ${s.name}`} onSelect={() => run(() => navigate(`/wire?sector=${encodeURIComponent(s.name)}`))}>
              <LayoutGrid /> {s.name}<span className="ml-auto text-xs text-muted-foreground">{s.count}</span>
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Go to">
          <CommandItem value="go overview" onSelect={() => run(() => navigate('/'))}><LayoutGrid /> Overview<CommandShortcut>1</CommandShortcut></CommandItem>
          <CommandItem value="go wire feed" onSelect={() => run(() => navigate('/wire'))}><Newspaper /> The wire<CommandShortcut>2</CommandShortcut></CommandItem>
          <CommandItem value="go brief" onSelect={() => run(() => navigate('/brief'))}><BookOpenText /> Daily brief<CommandShortcut>3</CommandShortcut></CommandItem>
          <CommandItem value="go watchlist" onSelect={() => run(() => navigate('/watchlist'))}><Star /> Watchlist<CommandShortcut>4</CommandShortcut></CommandItem>
          <CommandItem value="go top picks ai ranked important" onSelect={() => run(() => navigate('/wire?view=top'))}><Trophy /> Top picks</CommandItem>
          <CommandItem value="toggle theme dark light" onSelect={() => run(() => setTheme(resolved === 'dark' ? 'light' : 'dark'))}>
            {resolved === 'dark' ? <Sun /> : <Moon />} Switch to {resolved === 'dark' ? 'light' : 'dark'} theme
          </CommandItem>
        </CommandGroup>
        <CommandGroup heading="Market">
          {(['all', 'global', 'india'] as const).map((m) => (
            <CommandItem key={m} value={`market ${MARKET_LABEL[m]}`} onSelect={() => run(() => setMarket(m))}>
              <Globe2 /> {MARKET_LABEL[m]}{market === m && <span className="ml-auto text-xs text-muted-foreground">current</span>}
            </CommandItem>
          ))}
        </CommandGroup>
        <CommandGroup heading="Currency">
          {(['native', 'USD', 'INR'] as const).map((c) => (
            <CommandItem key={c} value={`currency prices ${CURRENCY_LABEL[c]} ${c}`} onSelect={() => run(() => setCurrency(c))}>
              <Banknote /> Prices in {CURRENCY_LABEL[c].toLowerCase()}{currency === c && <span className="ml-auto text-xs text-muted-foreground">current</span>}
            </CommandItem>
          ))}
        </CommandGroup>
        {status === 'signed-in' && (
          <CommandGroup heading="Account">
            <CommandItem value="sign out log out" onSelect={() => run(() => void signOut())}><LogOut /> Sign out</CommandItem>
          </CommandGroup>
        )}
        {query.trim().length >= 2 && (
          <CommandGroup heading={searching ? 'Stories · searching…' : 'Stories'}>
            {stories.map((a) => (
              // The query is part of the value: the server already matched it (maybe in the summary, not the headline).
              <CommandItem key={a.id} value={`story ${a.id} ${a.headline} ${query}`} onSelect={() => run(() => openArticle(a.id))}>
                <Newspaper /><span className="truncate">{a.headline}</span>
                <span className="ml-auto shrink-0 text-xs text-muted-foreground">{ago(a.published_at)}</span>
              </CommandItem>
            ))}
          </CommandGroup>
        )}
        {named && <CommandGroup heading="Ticker">{lookupRow}</CommandGroup>}
      </CommandList>
    </CommandDialog>
  )
}
