// Current user and login/logout, provided by AuthProvider (lib/authContext.tsx).
import { createContext, useContext } from 'react'
import type { AuthUser } from '@/lib/auth'

export interface AuthState {
  user: AuthUser | null
  login: (username: string, password: string) => Promise<AuthUser>
  logout: () => void
}

export const AuthContext = createContext<AuthState | null>(null)

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
