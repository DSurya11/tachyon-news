import { LogOut, Moon, Sun } from 'lucide-react'
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { useAuth } from '@/hooks/use-auth'
import { useTheme } from '@/hooks/use-theme'

function initials(name: string | null, email: string) {
  const src = (name || email.split('@')[0]).trim()
  const parts = src.split(/[\s._-]+/).filter(Boolean)
  return ((parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '')).toUpperCase() || '?'
}

export function UserMenu() {
  const { user, status, signOut } = useAuth()
  const { resolved, setTheme } = useTheme()
  if (status === 'demo' || !user) return null
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Account"
        className="grid size-9 shrink-0 place-items-center rounded-full border bg-surface text-[12px] font-semibold tracking-wide transition-[border-color] hover:border-foreground/40">
        {initials(user.name, user.email)}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="py-2">
          <div className="truncate text-[13.5px] font-medium">{user.name || user.email.split('@')[0]}</div>
          <div className="truncate text-xs font-normal text-muted-foreground">{user.email}</div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => setTheme(resolved === 'dark' ? 'light' : 'dark')}>
          {resolved === 'dark' ? <Sun /> : <Moon />} {resolved === 'dark' ? 'Light theme' : 'Dark theme'}
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => void signOut()}>
          <LogOut /> Sign out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
