// Home dashboard: vehicles to watch, joined from the zones' latest analyses.
// Scores, levels, approach rates and ETAs are the API's; this only joins and sorts them.
import type { Analysis, RiskLevel } from '@/api/types'

/** Approach rate (m/min) from which a vehicle counts as closing in, as on the track card. */
export const CLOSING_M_PER_MIN = 0.5

export interface WatchedVehicle {
  key: string
  imageId: string
  zone: string | null
  capturedAt: string
  trackId: string | null
  level: RiskLevel
  score: number
  text: string // the brief's sentence for this vehicle
  distanceM: number | null
  etaMin: number | null
  closing: boolean
}

export function watchedVehicles(analyses: Analysis[]): WatchedVehicle[] {
  return analyses.flatMap((a) => {
    const motion = new Map(a.motions.map((m) => [m.track_id, m]))
    const line = new Map((a.brief?.vehicles ?? []).map((v) => [v.detection_id, v.text]))
    return a.risks.map((r) => {
      const m = r.track_id ? motion.get(r.track_id) : undefined
      return {
        key: `${a.image_id}:${r.detection_id}`,
        imageId: a.image_id,
        zone: a.image?.zone ?? null,
        capturedAt: a.image?.capture_time ?? '',
        trackId: r.track_id ?? null,
        level: r.level,
        score: r.score,
        text: line.get(r.detection_id) ?? r.track_id ?? r.detection_id,
        distanceM: m?.dist_now_m ?? null,
        etaMin: m?.eta_to_base_min ?? null,
        closing: (m?.approach_rate_m_per_min ?? 0) >= CLOSING_M_PER_MIN,
      }
    })
  })
}

const ORDER: RiskLevel[] = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']

/** Highest of the given levels, or null when none are known yet. */
export const maxLevel = (levels: RiskLevel[]): RiskLevel | null =>
  levels.length ? levels.reduce((a, b) => (ORDER.indexOf(b) > ORDER.indexOf(a) ? b : a)) : null
