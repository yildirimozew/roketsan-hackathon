import { ScanSearch } from 'lucide-react'
import { useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import { imageUrl } from '@/api/endpoints'
import type { ImageMeta } from '@/api/types'
import { type ImageFilter, ImageFilters } from '@/components/overview/ImageFilters'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useImages } from '@/hooks/useImages'
import { useMasterClock } from '@/hooks/useMasterClock'
import { t } from '@/i18n'
import { hhmm } from '@/lib/fieldMap'
import { placeName } from '@/lib/format'

const NO_ZONE = '—'

const parseTime = (value: string | null): number | null => {
  const m = value?.match(/^(\d{1,2}):(\d{2})$/)
  return m ? Number(m[1]) * 60 + Number(m[2]) : null
}

/** Filter state lives in the URL (?from=09:00&to=12:30&zone=A&zone=B) so it survives a trip to an analysis. */
function useImageFilter(images: ImageMeta[]) {
  const [params, setParams] = useSearchParams()
  const bounds = useMemo(() => {
    const mins = images.map((m) => m.capture_min)
    return mins.length ? { from: Math.min(...mins), to: Math.max(...mins) } : { from: 0, to: 24 * 60 - 1 }
  }, [images])
  const filter: ImageFilter = {
    from: parseTime(params.get('from')) ?? bounds.from,
    to: parseTime(params.get('to')) ?? bounds.to,
    zones: params.getAll('zone'),
  }
  const setFilter = (f: ImageFilter) => {
    const next = new URLSearchParams()
    if (f.from !== bounds.from) next.set('from', hhmm(f.from))
    if (f.to !== bounds.to) next.set('to', hhmm(f.to))
    for (const z of f.zones) next.append('zone', z)
    setParams(next, { replace: true })
  }
  return { filter, bounds, setFilter, reset: () => setParams({}, { replace: true }) }
}

// TODO(P4): KPI strip, scene map with frame footprints, risk badges from batch precompute.
export function OverviewPage() {
  const { data, isPending, isError } = useImages()
  const all = useMemo(() => [...(data ?? [])].sort((a, b) => a.capture_min - b.capture_min), [data])
  const { filter, bounds, setFilter, reset } = useImageFilter(all)
  // Only frames captured by the master clock's minute exist yet.
  const now = Math.floor(useMasterClock().minute)
  const images = useMemo(() => all.filter((m) => m.capture_min <= now), [all, now])
  const navigate = useNavigate()

  const zoneCounts = useMemo(() => {
    const counts = new Map<string, number>()
    for (const m of images) counts.set(m.zone ?? NO_ZONE, (counts.get(m.zone ?? NO_ZONE) ?? 0) + 1)
    return [...counts].map(([zone, count]) => ({ zone, count })).sort((a, b) => placeName(a.zone).localeCompare(placeName(b.zone), 'tr'))
  }, [images])

  const shown = images.filter(
    (m) =>
      m.capture_min >= filter.from &&
      m.capture_min <= filter.to &&
      (filter.zones.length === 0 || filter.zones.includes(m.zone ?? NO_ZONE)),
  )

  return (
    <div className="flex flex-col gap-4 p-6">
      <div>
        <h1 className="text-lg font-semibold">{t.overview.title}</h1>
        {data && (
          <p className="text-sm text-muted-foreground">
            {t.overview.subtitle(images.length)} · {t.overview.asOf(hhmm(now), all.length)}
          </p>
        )}
      </div>
      {images.length > 0 && (
        <ImageFilters
          filter={filter}
          bounds={bounds}
          zoneCounts={zoneCounts}
          shown={shown.length}
          total={images.length}
          onChange={setFilter}
          onReset={reset}
        />
      )}
      {isPending && <Skeleton className="h-48" />}
      {all.length > 0 && images.length === 0 && (
        <p className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">{t.overview.noneYet(hhmm(now))}</p>
      )}
      {(isError || data?.length === 0) && <p className="text-sm text-muted-foreground">{t.overview.empty}</p>}
      {images.length > 0 && shown.length === 0 && (
        <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-sm text-muted-foreground">
          {t.overview.filters.noMatch}
          <Button size="sm" variant="outline" onClick={reset}>
            {t.overview.filters.clear}
          </Button>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
        {shown.map((m) => (
          <article key={m.image_id} className="overflow-hidden rounded-lg border bg-card">
            <div className="relative">
              <img src={imageUrl(m.image_id)} alt={m.image_id} loading="lazy" className="aspect-video w-full object-cover" />
              <Button
                size="xs"
                onClick={() => void navigate(`/analysis/${m.image_id}`, { state: { from: 'overview' } })}
                className="absolute right-2 bottom-2 shadow-md"
              >
                <ScanSearch />
                {t.analysis.analyze}
              </Button>
            </div>
            <div className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
              <span className="shrink-0 font-mono">{m.image_id}</span>
              <span className="flex min-w-0 gap-1 text-muted-foreground">
                <span className="truncate">{m.zone ? placeName(m.zone) : NO_ZONE}</span>
                <span className="shrink-0 font-mono">· {m.capture_time}</span>
              </span>
            </div>
          </article>
        ))}
      </div>
    </div>
  )
}
