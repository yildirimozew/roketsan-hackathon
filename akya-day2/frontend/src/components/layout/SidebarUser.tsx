import { LogOut } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/hooks/useAuth'
import { t } from '@/i18n'

/** Sidebar footer: who is logged in (name + role) and a logout button; icon-only when collapsed. */
export function SidebarUser({ open }: { open: boolean }) {
  const { user, logout } = useAuth()
  if (!user) return null
  const a = t.auth

  const handleLogout = () => {
    logout()
    // Full load of plain /login (no next): the next person may have another role. A router navigate
    // here loses to RequireAuth's own redirect (which adds ?next=), and the reload also drops the
    // previous user's query cache.
    window.location.replace('/login')
  }

  const logoutButton = (
    <Button
      size="icon-sm"
      variant="ghost"
      onClick={handleLogout}
      aria-label={a.logout}
      title={a.logout}
      className="shrink-0 text-muted-foreground"
    >
      <LogOut />
    </Button>
  )

  if (!open) return <div className="flex justify-center">{logoutButton}</div>

  return (
    <div className="flex items-center gap-2">
      <div
        aria-hidden
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent text-xs font-semibold uppercase"
      >
        {user.username.slice(0, 1)}
      </div>
      <div className="flex min-w-0 flex-1 flex-col items-start leading-tight">
        <span className="max-w-full truncate font-mono text-sm">{user.username}</span>
        <Badge variant={user.role === 'admin' ? 'default' : 'secondary'} className="mt-0.5">
          {a.roles[user.role]}
        </Badge>
      </div>
      {logoutButton}
    </div>
  )
}
