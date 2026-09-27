import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface Props {
  icon: LucideIcon
  label: string
  value: ReactNode
  unit?: string
  detail?: ReactNode
  note?: ReactNode
  accent?: string // text color class for the icon
}

/** Headline number tile: small-caps label, large mono value, one or two quiet detail lines. */
export function KpiTile({ icon: Icon, label, value, unit, detail, note, accent = 'text-muted-foreground' }: Props) {
  return (
    <section className="flex flex-col gap-2 rounded-lg border bg-card p-4">
      <header className="flex items-center justify-between gap-2">
        <h2 className="text-[11px] font-medium tracking-wider text-muted-foreground">{label.toLocaleUpperCase('tr-TR')}</h2>
        <Icon aria-hidden className={cn('size-4', accent)} />
      </header>
      <p className="flex items-baseline gap-1.5">
        <span className="font-mono text-4xl font-semibold tabular-nums text-foreground">{value}</span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </p>
      {detail && <p className="text-xs text-foreground/80">{detail}</p>}
      {note && <p className="text-[11px] text-muted-foreground">{note}</p>}
    </section>
  )
}
