import { Activity, Images, Navigation, RadioTower } from 'lucide-react'
import { Link } from 'react-router'
import { useMemo } from 'react'
import type { Analysis } from '@/api/types'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { ActivityChart } from '@/components/home/ActivityChart'
import { KpiTile } from '@/components/home/KpiTile'
import { RecentReports } from '@/components/home/RecentReports'
import { VehicleWatchList } from '@/components/home/VehicleWatchList'
import { ZoneStatusCard } from '@/components/home/ZoneStatusCard'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useAnalyses } from '@/hooks/useAnalysis'
import { useFieldMapData } from '@/hooks/useFieldMap'
import { useMasterClock } from '@/hooks/useMasterClock'
import { t } from '@/i18n'
import { hhmm } from '@/lib/fieldMap'
import { dayBounds, situationAt } from '@/lib/situation'
import { maxLevel, watchedVehicles } from '@/lib/watchlist'

const WATCH_LIMIT = 5
const REPORT_LIMIT = 6

/** Situation board for the security chief: where things stand at the master clock's minute. */
export function HomePage() {
  const th = t.home
  const { scene, images, tracks, reports, isPending, isError, refetch } = useFieldMapData()
  const clock = useMasterClock()
  const bounds = useMemo(() => dayBounds(tracks ?? [], reports ?? []), [tracks, reports])
  // Whole minutes, so the board is recomputed once per simulated minute, not every frame.
  const now = Math.min(bounds.end, Math.max(bounds.start, Math.floor(clock.minute)))

  const sit = useMemo(
    () => (scene && images && tracks && reports ? situationAt(now, scene.zones.map((z) => z.name), images, tracks, reports) : null),
    [now, scene, images, tracks, reports],
  )
  const frameIds = sit?.zones.flatMap((z) => (z.frame ? [z.frame.image_id] : [])) ?? []
  const queries = useAnalyses(frameIds)
  const analyses = new Map<string, Analysis>()
  queries.forEach((q, i) => q.data && analyses.set(frameIds[i]!, q.data))
  const analysesPending = queries.some((q) => q.isPending)

  if (isError) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-sm text-muted-foreground">
        <p>{th.loadError}</p>
        <Button size="sm" variant="outline" onClick={refetch}>
          {t.common.retry}
        </Button>
      </div>
    )
  }
  if (isPending || !sit) {
    return (
      <div className="flex flex-col gap-4 p-6">
        <Skeleton className="h-10 w-80" />
        <div className="grid grid-cols-3 gap-4">
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-32" />)}
        </div>
        <Skeleton className="h-96" />
      </div>
    )
  }

  const loaded = [...analyses.values()]
  const overall = maxLevel(loaded.flatMap((a) => (a.brief ? [a.brief.level] : [])))
  const watched = watchedVehicles(loaded)
  const top = [...watched].sort((a, b) => b.score - a.score).slice(0, WATCH_LIMIT)
  const closing = watched.filter((v) => v.closing)
  const etas = closing.flatMap((v) => (v.etaMin != null ? [v.etaMin] : []))
  const official = sit.reportsRecent.filter((r) => r.source === 'official').length
  const delta = sit.activeTracks - sit.activeTracksBefore

  return (
    <div className="mx-auto flex max-w-[1600px] flex-col gap-5 p-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">{th.title}</h1>
          <p className="text-sm text-muted-foreground">{th.subtitle(hhmm(now))}</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Button asChild size="sm" variant="outline">
            <Link to="/overview">
              <Images aria-hidden />
              {th.allFrames}
            </Link>
          </Button>
          <span className="flex items-center gap-2 text-xs text-muted-foreground">
            {th.overall}
            {overall ? <RiskBadge level={overall} size="lg" /> : <Skeleton className="h-7 w-16" />}
          </span>
        </div>
      </header>

      <div className="grid grid-cols-3 gap-4">
        <KpiTile icon={Activity} accent="text-emerald-700" label={th.kpi.tracks} value={sit.activeTracks} detail={th.kpi.tracksTrend(delta)} note={th.kpi.tracksTotal(sit.tracksSoFar)} />
        <KpiTile
          icon={Navigation}
          accent="text-orange-700"
          label={th.kpi.closing}
          value={analysesPending && loaded.length === 0 ? '…' : closing.length}
          detail={th.kpi.closingEta(etas.length ? Math.min(...etas) : null)}
          note={th.kpi.closingNote}
        />
        <KpiTile icon={RadioTower} accent="text-sky-700" label={th.kpi.reports} value={sit.reportsRecent.length} detail={th.kpi.reportsSplit(official, sit.reportsRecent.length - official)} note={th.kpi.reportsTotal(sit.reportsSoFar)} />
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
        <section className="flex flex-col gap-3">
          <div className="flex items-baseline justify-between gap-2">
            <h2 className="text-xs font-semibold tracking-widest text-emerald-700">{th.zones.title.toLocaleUpperCase('tr-TR')}</h2>
            <span className="text-[11px] text-muted-foreground">{th.zones.hint}</span>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            {sit.zones.map((z) => (
              <ZoneStatusCard
                key={z.zone}
                state={z}
                now={now}
                analysis={z.frame ? analyses.get(z.frame.image_id) : undefined}
                isPending={analysesPending}
              />
            ))}
          </div>
          <ActivityChart series={sit.series} reportMarks={sit.reportMarks} start={sit.start} end={sit.end} now={now} />
        </section>
        <div className="flex flex-col gap-5">
          <VehicleWatchList vehicles={top} isPending={analysesPending} />
          <RecentReports reports={sit.latestReports.slice(0, REPORT_LIMIT)} />
        </div>
      </div>
    </div>
  )
}
