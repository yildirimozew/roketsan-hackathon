import { useMemo } from 'react'
import type { ImageMeta, MapReport, MapTrack, Scene } from '@/api/types'
import type { FrameMark } from '@/components/map/FrameLayer'
import type { ReportMark } from '@/components/map/ReportLayer'
import type { ActivityBin, TimeTick } from '@/components/map/TimeScrubber'
import type { TrackMark } from '@/components/map/TrackLayer'
import type { ZoneMark } from '@/components/map/ZoneLayer'
import { project, toSamples } from '@/lib/fieldMap'
import { toLocalM } from '@/lib/geo'

const ACTIVITY_BIN_MIN = 5
/** Minutes the field map clock starts before the first track. */
const LEAD_IN_MIN = 5

export interface ZonedTrack extends TrackMark {
  zone: string | null
  startMin: number
  endMin: number
}

export interface ZonedFrame extends FrameMark {
  zone: string | null
}

export interface ZonedReport extends ReportMark {
  zone: string | null
  source: string
}

/** Projects the day's data into map space once; the per-tick work is only interpolation. */
export function useFieldMapModel(scene: Scene, images: ImageMeta[], tracks: MapTrack[], reports: MapReport[]) {
  return useMemo(() => {
    const origin = scene.base.position
    const imageById = new Map(images.map((m) => [m.image_id, m]))
    const zones: ZoneMark[] = scene.zones.map((z) => ({ name: z.name, p: project(origin, z.center), position: z.center }))

    const zonedTracks: ZonedTrack[] = tracks.map((tr) => {
      const samples = toSamples(origin, tr.points)
      return {
        id: tr.track_id,
        samples,
        zone: (tr.image_id && imageById.get(tr.image_id)?.zone) ?? null,
        startMin: samples[0]?.t ?? 0,
        endMin: samples[samples.length - 1]?.t ?? 0,
      }
    })

    const frames: ZonedFrame[] = images.map((m) => {
      const c = m.corners
      const corners = [c.tl, c.tr, c.br, c.bl].filter((p) => p !== undefined).map((p) => project(origin, p))
      const center = corners.reduce((a, p) => ({ x: a.x + p.x / corners.length, y: a.y + p.y / corners.length }), { x: 0, y: 0 })
      return { id: m.image_id, captureMin: m.capture_min, captureTime: m.capture_time, corners, center, zone: m.zone ?? null }
    })

    const located: ZonedReport[] = reports.flatMap((r) =>
      r.location
        ? [{ id: r.report_id, timeMin: r.time_min, time: r.time, official: r.source === 'official', p: project(origin, r.location), zone: r.zone ?? null, source: r.source }]
        : [],
    )

    const ticks: TimeTick[] = [
      ...images.map((m) => ({ minute: m.capture_min, kind: 'frame' as const })),
      ...reports.map((r) => ({ minute: r.time_min, kind: r.source === 'official' ? ('official' as const) : ('third_party' as const) })),
    ]

    const times = [...zonedTracks.flatMap((tr) => [tr.startMin, tr.endMin]), ...reports.map((r) => r.time_min)]
    // The clock opens a few minutes before the first track, so the map starts empty and fills up.
    const start = Math.min(Math.min(...zonedTracks.map((tr) => tr.startMin)) - LEAD_IN_MIN, ...reports.map((r) => r.time_min))
    const end = Math.ceil(Math.max(...times) / 10) * 10

    // Active-track count per bin, for the time bar's activity lane.
    const activity: ActivityBin[] = []
    for (let m = start; m <= end; m += ACTIVITY_BIN_MIN) {
      activity.push({ minute: m, count: zonedTracks.filter((tr) => tr.startMin <= m && m <= tr.endMin).length })
    }

    // Everything we draw should fit: zones plus a margin for the tracks around them.
    const zoneR = Math.max(1000, ...scene.zones.map((z) => Math.hypot(toLocalM(origin, z.center).x, toLocalM(origin, z.center).y)))

    return { origin, imageById, zones, tracks: zonedTracks, frames, reports: located, ticks, activity, start, end, fitRadiusM: zoneR + 1800 }
  }, [scene, images, tracks, reports])
}
