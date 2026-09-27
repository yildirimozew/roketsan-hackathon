import { TrendingDown } from 'lucide-react'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { t } from '@/i18n'
import { formatKm, placeName } from '@/lib/format'
import type { WatchedVehicle } from '@/lib/watchlist'

interface Props {
  vehicles: WatchedVehicle[] // already sorted, highest risk first
  isPending: boolean
}

/** Highest-scoring vehicles across the zones' latest frames. */
export function VehicleWatchList({ vehicles, isPending }: Props) {
  const tw = t.home.watch
  return (
    <section className="flex flex-col rounded-lg border bg-card">
      <header className="border-b px-4 py-2.5">
        <h2 className="text-xs font-semibold tracking-widest text-emerald-700">{tw.title.toLocaleUpperCase('tr-TR')}</h2>
        <p className="text-[11px] text-muted-foreground">{tw.hint}</p>
      </header>
      {isPending && vehicles.length === 0 ? (
        <div className="flex flex-col gap-2 p-3">
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
          <Skeleton className="h-12" />
        </div>
      ) : vehicles.length === 0 ? (
        <p className="p-4 text-xs text-muted-foreground">{tw.empty}</p>
      ) : (
        <ol className="divide-y">
          {vehicles.map((v) => (
            <li key={v.key} className="flex flex-col gap-1 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <RiskBadge level={v.level} />
                <span className="font-mono text-xs text-foreground">{v.trackId ?? '—'}</span>
                <span className="font-mono text-[11px] text-muted-foreground">{tw.score(v.score)}</span>
                {v.closing && (
                  <span className="ml-auto flex items-center gap-1 text-[11px] text-orange-700">
                    <TrendingDown aria-hidden className="size-3.5" />
                    {tw.closing}
                  </span>
                )}
              </div>
              <p className="text-xs leading-snug text-foreground/85">{v.text}</p>
              <p className="font-mono text-[10px] text-muted-foreground">
                {[v.zone ? placeName(v.zone) : null, v.capturedAt, v.distanceM != null ? formatKm(v.distanceM) : null].filter(Boolean).join(' · ')}
              </p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
