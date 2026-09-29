import { BookOpenText, LayoutGrid, Newspaper, Star } from 'lucide-react'

export const NAV = [
  { to: '/', label: 'Overview', short: 'Overview', icon: LayoutGrid },
  { to: '/wire', label: 'The wire', short: 'Wire', icon: Newspaper },
  { to: '/brief', label: 'Daily brief', short: 'Brief', icon: BookOpenText },
  { to: '/watchlist', label: 'Watchlist', short: 'Watchlist', icon: Star },
] as const
