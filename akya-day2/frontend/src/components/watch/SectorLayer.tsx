import type { ZoneMark } from '@/components/map/ZoneLayer'

interface Props {
  zones: ZoneMark[]
  checks: Record<string, string> // watcher id -> sector checked this tick
}

const HALF_WEDGE = Math.PI / 8 // 8 sectors around the base: ±22.5°
const REACH_M = 8000

/** Shades the sectors checked this tick (nearest-zone wedges). */
export function SectorLayer({ zones, checks }: Props) {
  const byZone = new Map(Object.entries(checks).map(([w, z]) => [z, w]))
  return (
    <g className="pointer-events-none">
      {zones.map((z) => {
        if (!byZone.has(z.name)) return null
        const a = Math.atan2(z.p.x, -z.p.y) // bearing from north, clockwise
        const pt = (ang: number, r: number) => `${(Math.sin(ang) * r).toFixed(0)},${(-Math.cos(ang) * r).toFixed(0)}`
        const wedge = `0,0 ${pt(a - HALF_WEDGE, REACH_M)} ${pt(a, REACH_M * 1.08)} ${pt(a + HALF_WEDGE, REACH_M)}`
        return (
          <polygon key={z.name} points={wedge} className="fill-cyan-500/[0.05] stroke-cyan-600/25" strokeWidth={1} vectorEffect="non-scaling-stroke" />
        )
      })}
    </g>
  )
}
