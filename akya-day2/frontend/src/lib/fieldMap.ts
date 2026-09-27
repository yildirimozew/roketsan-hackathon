// Display helpers for the field map: projection to local meters and time interpolation for drawing.
// No domain math here: motion figures (speed, approach, stops) come from the API.
import type { LatLon, TrackPoint } from '@/api/types'
import { fromLocalM, toLocalM } from './geo'

export interface Pt {
  x: number
  y: number
}

/** A projected track sample: minute of day and SVG position in meters. */
export interface Sample extends Pt {
  t: number
}

/** Minutes of the agent's look-back window; report pins fade out over it. */
export const REPORT_WINDOW_MIN = 120

/** Minutes a track stays on the map after its last sample, fading out. */
export const TRACK_LINGER_MIN = 20

/** SVG coordinates in meters around the base: x east, y south (SVG y grows downward). */
export function project(origin: LatLon, p: LatLon): Pt {
  const { x, y } = toLocalM(origin, p)
  return { x, y: -y }
}

/** Inverse of `project`: SVG meters back to lat/lon. */
export const unproject = (origin: LatLon, p: Pt): LatLon => fromLocalM(origin, p.x, -p.y)

export const toSamples = (origin: LatLon, points: TrackPoint[]): Sample[] =>
  points.map((p) => ({ t: p.time_min, ...project(origin, p.position) }))

export const hhmm = (minute: number): string => {
  const m = Math.floor(minute)
  return `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`
}

/** Samples up to `minute` plus the interpolated current position; empty when not active. */
export function pathAt(samples: Sample[], minute: number): Pt[] {
  const first = samples[0]
  const last = samples[samples.length - 1]
  if (!first || !last || minute < first.t || minute > last.t) return []
  const out: Pt[] = []
  for (let i = 0; i < samples.length; i++) {
    const b = samples[i]
    if (!b) break
    if (b.t <= minute) {
      out.push(b)
      continue
    }
    const a = samples[i - 1]
    if (a) {
      const k = (minute - a.t) / (b.t - a.t || 1)
      out.push({ x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k })
    }
    break
  }
  return out
}

export const toPoints = (pts: Pt[]): string =>
  pts.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' ')

/** The last `windowMin` minutes of a track up to `minute` (interpolated at both ends). */
export function trailAt(samples: Sample[], minute: number, windowMin: number): Pt[] {
  const since = minute - windowMin
  const firstIn = samples.findIndex((p) => p.t >= since)
  const from = firstIn > 0 ? samples.slice(firstIn - 1) : samples
  const path = pathAt(from, minute)
  const [a, b] = from
  if (!a || !b || path.length < 2 || a.t >= since) return path
  const k = (since - a.t) / (b.t - a.t || 1)
  return [{ x: a.x + (b.x - a.x) * k, y: a.y + (b.y - a.y) * k }, ...path.slice(1)]
}
