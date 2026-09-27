import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '@/hooks/useAuth'
import type { Role } from '@/lib/auth'
import { Forbidden } from './Forbidden'

/** Route guard: no session → /login (remembering where to return); wrong role → Forbidden. */
export function RequireAuth({ role }: { role?: Role }) {
  const { user } = useAuth()
  const location = useLocation()

  if (!user) {
    const next = location.pathname + location.search
    const to = next === '/' ? '/login' : `/login?next=${encodeURIComponent(next)}`
    return <Navigate to={to} replace />
  }
  if (role && user.role !== role) return <Forbidden />
  return <Outlet />
}
