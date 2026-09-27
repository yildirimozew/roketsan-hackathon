import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import { imageUrl } from '@/api/endpoints'
import type { Analysis } from '@/api/types'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { Skeleton } from '@/components/ui/skeleton'
import { t } from '@/i18n'
import { placeName } from '@/lib/format'
import type { ZoneState } from '@/lib/situation'
import { cn } from '@/lib/utils'

interface Props {
  state: ZoneState
  now: number
  analysis: Analysis | undefined
  isPending: boolean
}

const EDGE: Record<string, string> = {
  LOW: 'border-l-emerald-500/70',
  MEDIUM: 'border-l-amber-400/80',
  HIGH: 'border-l-orange-400/90',
  CRITICAL: 'border-l-red-500',
}

/** One zone at a glance: its latest frame's risk, headline and action, plus live counts. */
export function ZoneStatusCard({ state, now, analysis, isPending }: Props) {
  const tz = t.home.zones
  const { frame } = state
  const brief = analysis?.brief
  const level = brief?.level

  return (
    <article className={cn('flex flex-col overflow-hidden rounded-lg border border-l-4 bg-card', level ? EDGE[level] : 'border-l-border')}>
      <div className="flex gap-3 p-3">
        {frame ? (
          <img src={imageUrl(frame.image_id)} alt={frame.image_id} loading="lazy" className="aspect-video w-24 shrink-0 rounded object-cover" />
        ) : (
          <div className="aspect-video w-24 shrink-0 rounded border border-dashed" />
        )}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-sm leading-tight font-semibold">{placeName(state.zone)}</h3>
            {level ? <RiskBadge level={level} className="shrink-0" /> : frame && isPending ? <Skeleton className="h-5 w-12" /> : null}
          </div>
          {!frame ? (
            <p className="text-xs text-muted-foreground">{tz.noFrame}</p>
          ) : brief ? (
            <p className="line-clamp-2 text-xs text-foreground/85">{brief.headline}</p>
          ) : isPending ? (
            <p className="text-xs text-muted-foreground">{t.home.pending}</p>
          ) : null}
          {frame && <p className="font-mono text-[10px] text-muted-foreground">{tz.frameAt(frame.capture_time, Math.round(now - frame.capture_min))}</p>}
        </div>
      </div>
      <footer className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 border-t px-3 py-1.5 text-[11px] whitespace-nowrap text-muted-foreground">
        <span>
          <span className="font-mono text-emerald-700">{state.activeTracks}</span> {tz.active}
        </span>
        <span>
          <span className="font-mono text-sky-700">{state.recentReports}</span> {tz.reports}
        </span>
        {brief && <span className="rounded bg-accent px-1.5 py-0.5 text-foreground">{t.action[brief.recommended_action]}</span>}
        <Link
          to={`/overview?zone=${encodeURIComponent(state.zone)}`}
          className="ml-auto flex items-center gap-1 transition-colors hover:text-foreground"
        >
          {tz.frames}
          <ArrowRight aria-hidden className="size-3" />
        </Link>
      </footer>
    </article>
  )
}
