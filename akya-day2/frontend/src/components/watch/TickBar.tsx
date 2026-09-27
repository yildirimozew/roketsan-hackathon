import type { WatchLevel } from '@/api/types'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'

interface Props {
  ticks: { tick: string; minute: number }[]
  current: number // index of the tick being evaluated
  complete: boolean // its outputs are fully written
  threat: WatchLevel | undefined
  onSeek: (minute: number) => void
}

/** Jump chips per tick (a jump shows that tick fully evaluated) and the latest threat level. */
export function TickBar({ ticks, current, complete, threat, onSeek }: Props) {
  const w = t.watch
  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-1">
        {ticks.map((tk, i) => (
          <button
            key={tk.tick}
            type="button"
            onClick={() => onSeek(tk.minute)}
            className={cn(
              'rounded-md px-2 py-1 font-mono text-sm transition-colors',
              i === current
                ? complete
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-primary/15 text-primary ring-1 ring-primary/40 ring-inset'
                : i < current
                  ? 'text-foreground hover:bg-accent'
                  : 'text-muted-foreground hover:bg-accent',
            )}
          >
            {tk.tick}
          </button>
        ))}
      </div>
      {threat && (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {w.threat}
          <RiskBadge level={threat} size="lg" />
        </div>
      )}
    </div>
  )
}
