import { Button } from '@/components/ui/button'
import { t } from '@/i18n'
import type { MockAccount } from '@/lib/auth'

interface DemoAccountsProps {
  accounts: readonly MockAccount[]
  onPick: (account: MockAccount) => void
}

/** Demo helper under the login form: clicking an account fills the form (no typing on stage). */
export function DemoAccounts({ accounts, onPick }: DemoAccountsProps) {
  const a = t.auth
  return (
    <div className="rounded-lg border border-dashed bg-muted/40 p-3">
      <p className="text-[11px] font-medium tracking-wider text-muted-foreground uppercase">{a.demoAccounts}</p>
      <p className="mt-0.5 text-xs text-muted-foreground">{a.demoHint}</p>
      <div className="mt-2 grid grid-cols-2 gap-2">
        {accounts.map((acc) => (
          <Button
            key={acc.username}
            type="button"
            variant="outline"
            onClick={() => onPick(acc)}
            className="h-auto flex-col items-start gap-0.5 px-3 py-2 text-left"
          >
            <span className="font-mono text-sm">{acc.username}</span>
            <span className="text-xs font-normal text-muted-foreground">{a.roles[acc.role]}</span>
            <span className="font-mono text-xs font-normal text-muted-foreground">{acc.password}</span>
          </Button>
        ))}
      </div>
    </div>
  )
}
