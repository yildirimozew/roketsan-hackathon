// Display-only projection helpers (no domain math: distances and verdicts come from the API).
import type { LatLon } from '@/api/types'

const M_PER_DEG = (Math.PI / 180) * 6_371_000

/** Local east/north meters of `p` relative to `origin`, for drawing schematic maps. */
export function toLocalM(origin: LatLon, p: LatLon): { x: number; y: number } {
  return {
    x: (p.lon - origin.lon) * M_PER_DEG * Math.cos((origin.lat * Math.PI) / 180),
    y: (p.lat - origin.lat) * M_PER_DEG,
  }
}

/** Inverse of `toLocalM`: the lat/lon at local east/north meters from `origin`. */
export function fromLocalM(origin: LatLon, x: number, y: number): LatLon {
  return {
    lat: origin.lat + y / M_PER_DEG,
    lon: origin.lon + x / (M_PER_DEG * Math.cos((origin.lat * Math.PI) / 180)),
  }
}

export interface Fit {
  project: (p: { x: number; y: number }) => { x: number; y: number }
}

/** Uniform-scale fit of local-meter points into a width×height box (north up). */
export function fitToBox(points: { x: number; y: number }[], width: number, height: number, pad: number): Fit {
  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const scale = Math.min((width - 2 * pad) / (maxX - minX || 1), (height - 2 * pad) / (maxY - minY || 1))
  const offX = (width - (maxX - minX) * scale) / 2
  const offY = (height - (maxY - minY) * scale) / 2
  return {
    project: (p) => ({ x: offX + (p.x - minX) * scale, y: height - offY - (p.y - minY) * scale }),
  }
}
