// Home dashboard aggregation: counts and "latest" lookups at a chosen minute of the day.
// Display-only: risk levels, motion and verdicts come from the API's analyses, never from here.
import type { ImageMeta, MapReport, MapTrack } from '@/api/types'

/** Window for "recent" reports on the dashboard. */
export const RECENT_REPORT_MIN = 60
/** Bin size of the day-activity series. */
export const SERIES_BIN_MIN = 5

export interface ZoneState {
  zone: string
  frame: ImageMeta | null // latest frame captured in the zone up to `now`
  activeTracks: number
  recentReports: number
}

export interface SeriesPoint {
  minute: number
  tracks: number
  reports: number
}

export interface Situation {
  now: number
  start: number
  end: number
  activeTracks: number
  activeTracksBefore: number // 30 minutes earlier, for the trend
  tracksSoFar: number
  reportsRecent: MapReport[]
  reportsSoFar: number
  framesSoFar: number
  framesTotal: number
  lastFrame: ImageMeta | null
  zones: ZoneState[]
  latestReports: MapReport[] // newest first
  series: SeriesPoint[] // whole day; points after `now` are not drawn
  reportMarks: { minute: number; source: string }[]
}

const span = (tr: MapTrack) => ({ start: tr.points[0]?.time_min ?? 0, end: tr.points[tr.points.length - 1]?.time_min ?? 0 })

/** Day bounds of the data: first track to last track/report, on the 5-minute grid. */
export function dayBounds(tracks: MapTrack[], reports: MapReport[]) {
  const times = [...tracks.flatMap((tr) => Object.values(span(tr))), ...reports.map((r) => r.time_min)]
  if (times.length === 0) return { start: 0, end: 0 }
  return {
    start: Math.floor(Math.min(...times) / SERIES_BIN_MIN) * SERIES_BIN_MIN,
    end: Math.ceil(Math.max(...times) / SERIES_BIN_MIN) * SERIES_BIN_MIN,
  }
}

export function situationAt(
  now: number,
  zoneNames: string[],
  images: ImageMeta[],
  tracks: MapTrack[],
  reports: MapReport[],
): Situation {
  const { start, end } = dayBounds(tracks, reports)
  const imageZone = new Map(images.map((m) => [m.image_id, m.zone]))
  const spans = tracks.map((tr) => ({ ...span(tr), zone: (tr.image_id && imageZone.get(tr.image_id)) || null }))
  const activeAt = (m: number) => spans.filter((s) => s.start <= m && m <= s.end)
  const active = activeAt(now)
  const soFar = reports.filter((r) => r.time_min <= now)
  const recent = soFar.filter((r) => r.time_min > now - RECENT_REPORT_MIN)
  const captured = images.filter((m) => m.capture_min <= now).sort((a, b) => a.capture_min - b.capture_min)

  const zones = zoneNames.map((zone) => ({
    zone,
    frame: [...captured].reverse().find((m) => m.zone === zone) ?? null,
    activeTracks: active.filter((s) => s.zone === zone).length,
    recentReports: recent.filter((r) => r.zone === zone).length,
  }))

  const series: SeriesPoint[] = []
  for (let m = start; m <= end; m += SERIES_BIN_MIN) {
    series.push({
      minute: m,
      tracks: activeAt(m).length,
      reports: reports.filter((r) => r.time_min > m - SERIES_BIN_MIN && r.time_min <= m).length,
    })
  }

  return {
    now,
    start,
    end,
    activeTracks: active.length,
    activeTracksBefore: activeAt(now - 30).length,
    tracksSoFar: spans.filter((s) => s.start <= now).length,
    reportsRecent: recent,
    reportsSoFar: soFar.length,
    framesSoFar: captured.length,
    framesTotal: images.length,
    lastFrame: captured[captured.length - 1] ?? null,
    zones,
    latestReports: [...soFar].sort((a, b) => b.time_min - a.time_min),
    series,
    reportMarks: soFar.map((r) => ({ minute: r.time_min, source: r.source })),
  }
}
