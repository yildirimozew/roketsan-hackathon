import { Eye, EyeOff, LoaderCircle, LogIn } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { t } from '@/i18n'
import type { MockAccount } from '@/lib/auth'
import { DemoAccounts } from './DemoAccounts'

interface LoginFormProps {
  /** Resolves true on success; on false the password field is cleared. */
  onSubmit: (username: string, password: string) => Promise<boolean>
  error: string | null
  pending: boolean
  demoAccounts: readonly MockAccount[]
}

export function LoginForm({ onSubmit, error, pending, demoAccounts }: LoginFormProps) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const a = t.auth
  const canSubmit = username.trim() !== '' && password !== '' && !pending

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!canSubmit) return
    const ok = await onSubmit(username, password)
    if (!ok) setPassword('')
  }

  const invalid = error ? true : undefined

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <Label htmlFor="login-username">{a.username}</Label>
        <Input
          id="login-username"
          name="username"
          autoComplete="username"
          autoFocus
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          aria-invalid={invalid}
        />
      </div>
      <div className="flex flex-col gap-2">
        <Label htmlFor="login-password">{a.password}</Label>
        <div className="relative">
          <Input
            id="login-password"
            name="password"
            type={showPassword ? 'text' : 'password'}
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={invalid}
            aria-describedby={error ? 'login-error' : undefined}
            className="pr-10"
          />
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            onClick={() => setShowPassword((s) => !s)}
            aria-label={showPassword ? a.hidePassword : a.showPassword}
            aria-pressed={showPassword}
            className="absolute top-1/2 right-1 -translate-y-1/2 text-muted-foreground"
          >
            {showPassword ? <EyeOff /> : <Eye />}
          </Button>
        </div>
      </div>
      {error && (
        <p id="login-error" role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      <Button type="submit" disabled={!canSubmit} className="w-full">
        {pending ? <LoaderCircle aria-hidden className="animate-spin" /> : <LogIn aria-hidden />}
        {pending ? a.submitting : a.submit}
      </Button>
      <DemoAccounts
        accounts={demoAccounts}
        onPick={(acc) => {
          setUsername(acc.username)
          setPassword(acc.password)
        }}
      />
    </form>
  )
}
