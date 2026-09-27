import { ShieldHalf } from 'lucide-react'
import { useState } from 'react'
import { Navigate, useSearchParams } from 'react-router'
import { LoginBrandPanel } from '@/components/auth/LoginBrandPanel'
import { LoginForm } from '@/components/auth/LoginForm'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useAuth } from '@/hooks/useAuth'
import { t } from '@/i18n'
import { InvalidCredentialsError, MOCK_ACCOUNTS, safeNextPath } from '@/lib/auth'

export function LoginPage() {
  const { user, login } = useAuth()
  const [params] = useSearchParams()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)
  const a = t.auth

  // Covers both "already logged in" and "just logged in": the provider's state change re-renders here.
  if (user) return <Navigate to={safeNextPath(params.get('next'))} replace />

  async function handleSubmit(username: string, password: string): Promise<boolean> {
    if (pending) return false
    setPending(true)
    setError(null)
    try {
      await login(username, password)
      return true
    } catch (e) {
      setError(e instanceof InvalidCredentialsError ? a.invalid : a.failed)
      return false
    } finally {
      setPending(false)
    }
  }

  return (
    <div className="grid min-h-screen bg-background lg:grid-cols-[1.1fr_1fr]">
      <LoginBrandPanel />
      <main className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-sm">
          <div className="mb-6 flex items-center gap-2 lg:hidden">
            <ShieldHalf aria-hidden className="size-6 text-primary" />
            <span className="text-base font-semibold tracking-[0.3em]">{t.app.name}</span>
          </div>
          <Card>
            <CardHeader>
              <CardTitle className="text-xl">{a.title}</CardTitle>
              <CardDescription>{a.subtitle}</CardDescription>
            </CardHeader>
            <CardContent>
              <LoginForm onSubmit={handleSubmit} error={error} pending={pending} demoAccounts={MOCK_ACCOUNTS} />
            </CardContent>
          </Card>
        </div>
      </main>
    </div>
  )
}
