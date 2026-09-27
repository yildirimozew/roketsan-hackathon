import { useCallback, useMemo, useState, type ReactNode } from 'react'
import { AuthContext } from '@/hooks/useAuth'
import { clearSession, login as loginRequest, readSession, writeSession, type AuthUser } from '@/lib/auth'

export function AuthProvider({ children }: { children: ReactNode }) {
  // Read synchronously so a reload never flashes the login page.
  const [user, setUser] = useState<AuthUser | null>(readSession)

  const login = useCallback(async (username: string, password: string) => {
    const next = await loginRequest(username, password)
    writeSession(next)
    setUser(next)
    return next
  }, [])

  const logout = useCallback(() => {
    clearSession()
    setUser(null)
  }, [])

  const value = useMemo(() => ({ user, login, logout }), [user, login, logout])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
