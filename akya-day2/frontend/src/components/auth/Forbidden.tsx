import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router'
import { Button } from '@/components/ui/button'
import { t } from '@/i18n'

export function Forbidden() {
  const a = t.auth
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center">
      <ShieldAlert aria-hidden className="size-10 text-muted-foreground" />
      <h1 className="text-lg font-semibold">{a.forbiddenTitle}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{a.forbiddenBody}</p>
      <Button asChild variant="outline">
        <Link to="/">{a.backHome}</Link>
      </Button>
    </div>
  )
}
