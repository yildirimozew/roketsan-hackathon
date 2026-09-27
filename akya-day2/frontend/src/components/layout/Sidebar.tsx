import {
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  ShieldHalf,
  UserCog,
  type LucideIcon,
} from 'lucide-react'
import { useState } from 'react'
import { Link, NavLink } from 'react-router'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useAuth } from '@/hooks/useAuth'
import { t } from '@/i18n'
import type { Role } from '@/lib/auth'
import { cn } from '@/lib/utils'
import { SidebarClock } from './SidebarClock'
import { SidebarUser } from './SidebarUser'

// The overview is reached from the home page (logo), not the menu.
const NAV: readonly { to: string; label: string; icon: LucideIcon; role?: Role }[] = [
  { to: '/watch', label: t.nav.watch, icon: Radar },
  { to: '/admin', label: t.nav.admin, icon: UserCog, role: 'admin' },
]

const STORAGE_KEY = 'akya.sidebar.open'

// Per-viewer convenience only: storage can be unavailable (private mode, blocked site data).
function readOpen(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEY) !== 'false'
  } catch {
    return true
  }
}

function writeOpen(open: boolean) {
  try {
    localStorage.setItem(STORAGE_KEY, String(open))
  } catch {
    // ignore
  }
}

/** Left navigation: logo (→ home), page links and service status; collapses to an icon rail. */
export function Sidebar() {
  const [open, setOpen] = useState(readOpen)
  const toggle = () =>
    setOpen((o) => {
      writeOpen(!o)
      return !o
    })
  const sb = t.sidebar
  const { user } = useAuth()
  const items = NAV.filter((item) => !item.role || item.role === user?.role)

  return (
    <aside className={cn('flex shrink-0 flex-col border-r bg-sidebar transition-[width] duration-200', open ? 'w-56' : 'w-14')}>
      <Link
        to="/"
        aria-label={sb.home}
        title={sb.home}
        className="flex h-14 items-center gap-2 overflow-hidden border-b px-4 transition-colors hover:bg-accent/40"
      >
        <ShieldHalf aria-hidden className="size-6 shrink-0 text-primary" />
        {open && (
          <span className="flex min-w-0 flex-col leading-tight">
            <span className="text-base font-semibold tracking-[0.3em]">{t.app.name}</span>
            <span className="truncate text-[10px] text-muted-foreground">{t.app.tagline}</span>
          </span>
        )}
      </Link>

      <nav className="flex flex-col gap-1 p-2" aria-label={sb.menu}>
        {items.map(({ to, label, icon: Icon }) => {
          const link = (
            <NavLink
              to={to}
              className={({ isActive }) =>
                cn(
                  'flex h-9 items-center gap-3 rounded-md px-2.5 text-sm text-muted-foreground transition-colors hover:bg-accent/50 hover:text-foreground',
                  isActive && 'bg-accent text-foreground',
                )
              }
            >
              <Icon aria-hidden className="size-4 shrink-0" />
              {open ? <span className="truncate">{label}</span> : <span className="sr-only">{label}</span>}
            </NavLink>
          )
          return open ? (
            <div key={to}>{link}</div>
          ) : (
            <Tooltip key={to}>
              <TooltipTrigger asChild>{link}</TooltipTrigger>
              <TooltipContent side="right">{label}</TooltipContent>
            </Tooltip>
          )
        })}
      </nav>

      <div className="mt-auto flex flex-col gap-3 border-t p-3">
        <SidebarClock open={open} />
        <SidebarUser open={open} />
        <Button
          size="icon-sm"
          variant="ghost"
          onClick={toggle}
          aria-expanded={open}
          aria-label={open ? sb.collapse : sb.expand}
          title={open ? sb.collapse : sb.expand}
          className={cn('text-muted-foreground', open ? 'self-end' : 'self-center')}
        >
          {open ? <PanelLeftClose /> : <PanelLeftOpen />}
        </Button>
      </div>
    </aside>
  )
}
