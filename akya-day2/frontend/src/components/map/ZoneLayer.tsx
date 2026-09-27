import type { LatLon } from '@/api/types'
import type { Pt } from '@/lib/fieldMap'
import { placeName } from '@/lib/format'
import { cn } from '@/lib/utils'

export interface ZoneMark {
  name: string
  p: Pt
  position: LatLon
}

interface Props {
  zones: ZoneMark[]
  mpp: number
  activeZone: string | null
  flashZone: string | null
  onSelect: (name: string) => void
}

/** Zone centers as violet dots (name on hover, no map labels); sizes stay constant on zoom.
 *  The filtered zone turns cyan; a selected zone-only report makes its zone ripple. */
export function ZoneLayer({ zones, mpp, activeZone, flashZone, onSelect }: Props) {
  return (
    <g>
      {zones.map((z) => {
        const active = z.name === activeZone
        const flash = z.name === flashZone
        return (
          <g key={z.name} transform={`translate(${z.p.x} ${z.p.y})`} className="group cursor-pointer" onClick={() => onSelect(z.name)}>
            <title>{placeName(z.name)}</title>
            {/* Larger transparent hit area than the dot itself. */}
            <circle r={14 * mpp} fill="transparent" />
            {flash && (
              <circle fill="none" className="stroke-sky-600" vectorEffect="non-scaling-stroke">
                <animate attributeName="r" from={6 * mpp} to={28 * mpp} dur="1.4s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="1" to="0" dur="1.4s" repeatCount="indefinite" />
              </circle>
            )}
            <circle
              r={(active ? 7 : 5.5) * mpp}
              className={cn(
                'transition-colors',
                active ? 'fill-cyan-700 stroke-white' : 'fill-violet-400 stroke-white group-hover:fill-violet-700',
              )}
              strokeWidth={1.5}
              vectorEffect="non-scaling-stroke"
            />
            {active && <circle r={12 * mpp} fill="none" className="stroke-cyan-600/70" vectorEffect="non-scaling-stroke" />}
          </g>
        )
      })}
    </g>
  )
}
