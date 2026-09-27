import type { WatchLevel } from '@/api/types'
import type { TrackMark } from '@/components/map/TrackLayer'
import { pathAt, toPoints, trailAt } from '@/lib/fieldMap'
import { hasTypeIcon } from '@/lib/vehicleTypes'
import { VehicleTypeIcon } from './VehicleTypeIcon'
import { t } from '@/i18n'
import { RISK_STYLES } from '@/lib/risk'
import type { VehicleState } from '@/lib/watchDemo'

interface Props {
  tracks: TrackMark[]
  minute: number
  mpp: number
  levels: Map<string, VehicleState>
  /** Vehicles in the operator alert → simulated minute the alert was written (trail grows in). */
  focus: Map<string, number>
  /** Detected vehicle types (car, van, truck, bus) by track id; shown as icons. */
  types: Map<string, string>
  /** Vehicles the operator announced (kept LOW): sky blue, ringed, with their trail and a label. */
  expected: Set<string>
  selectedId: string | null
  onSelect: (id: string) => void
}

const ORDER: Record<WatchLevel, number> = { LOW: 0, MEDIUM: 1, HIGH: 2 }
const FOCUS_TRAIL_MIN = 45 // vehicles in the operator alert
const HIGH_TRAIL_MIN = 120 // HIGH vehicles: the whole route so far (tracks cover 2 h)
const REVEAL_MIN = 0.3 // simulated minutes for a new trail to draw itself in (~1 s at 1x)
const ANNOUNCED = '#0284c7' // sky-600: a vehicle the operator announced, not a risk color
const DOT: Record<WatchLevel, number> = { LOW: 2.5, MEDIUM: 4, HIGH: 5 }
// Identified vehicles (type from a drone-frame detection): icon in a level-colored disc, px.
const ICON_R = 8.5
const ICON_SIZE = 11

/** Every vehicle as a dot colored by its agent level. HIGH vehicles show their whole route so far,
 *  MEDIUM/HIGH vehicles in the operator alert their last 45 min; the selected one also shows its id. */
export function VehicleLayer({ tracks, minute, mpp, levels, focus, types, expected, selectedId, onSelect }: Props) {
  const drawn = tracks
    .map((tr) => {
      const full = pathAt(tr.samples, minute)
      const state = levels.get(tr.id)
      // LOW vehicles named in an alert stay dots: a green trail would read as "safe but highlighted".
      const since = state && state.level !== 'LOW' ? focus.get(tr.id) : undefined
      // A trail draws itself in from the moment the vehicle entered the alert or became HIGH.
      const grow = (from: number | undefined) =>
        from === undefined ? 0 : Math.max(0, Math.min(1, (minute - from) / REVEAL_MIN))
      const trailMin = expected.has(tr.id)
        ? FOCUS_TRAIL_MIN
        : Math.max(FOCUS_TRAIL_MIN * grow(since), HIGH_TRAIL_MIN * grow(state?.highSince))
      const path = tr.id === selectedId ? full : trailMin > 0 ? trailAt(tr.samples, minute, trailMin) : []
      return { id: tr.id, path, head: full[full.length - 1], state, focused: since !== undefined }
    })
    .filter((v) => v.head !== undefined)
    .sort(
      (a, b) =>
        ORDER[a.state?.level ?? 'LOW'] - ORDER[b.state?.level ?? 'LOW'] ||
        Number(a.focused) - Number(b.focused) ||
        Number(a.id === selectedId) - Number(b.id === selectedId),
    )

  return (
    <g>
      {drawn.map(({ id, path, head, state, focused }) => {
        if (!head) return null
        const level = state?.level ?? 'LOW'
        const selected = id === selectedId
        const announced = expected.has(id)
        const color = selected ? '#0891b2' : announced ? ANNOUNCED : RISK_STYLES[level].stroke
        const type = types.get(id)
        const Icon = hasTypeIcon(type)
        return (
          <g key={id} className="cursor-pointer" onClick={() => onSelect(id)}>
            <title>{`${id} · ${level}`}</title>
            {path.length > 1 && (
              <polyline
                points={toPoints(path)}
                fill="none"
                stroke={color}
                strokeOpacity={selected ? 0.9 : 0.7}
                strokeWidth={selected ? 2.5 : 2}
                strokeLinejoin="round"
                strokeLinecap="round"
                vectorEffect="non-scaling-stroke"
              />
            )}
            <circle cx={head.x} cy={head.y} r={14 * mpp} fill="transparent" />
            {Icon ? (
              <g>
                <circle
                  cx={head.x}
                  cy={head.y}
                  r={ICON_R * mpp}
                  fill={color}
                  stroke="white"
                  strokeWidth={1.5}
                  vectorEffect="non-scaling-stroke"
                />
                <VehicleTypeIcon
                  vehicleType={type}
                  x={head.x - ICON_SIZE * mpp * 0.5}
                  y={head.y - ICON_SIZE * mpp * 0.5}
                  size={ICON_SIZE * mpp}
                  color="white"
                  strokeWidth={2.25}
                  className="pointer-events-none"
                />
              </g>
            ) : (
              <circle
                cx={head.x}
                cy={head.y}
                r={(selected || focused || announced ? 6 : DOT[level]) * mpp}
                fill={color}
                fillOpacity={level === 'LOW' && !selected && !announced ? 0.35 : 1}
                stroke={focused || selected || announced ? 'white' : 'none'}
                strokeWidth={1.5}
                vectorEffect="non-scaling-stroke"
              />
            )}
            {state?.pending && !focused && (
              <circle cx={head.x} cy={head.y} r={(Icon ? ICON_R + 3 : 8) * mpp} fill="none" stroke={color} strokeOpacity={0.6} strokeDasharray="2 2" vectorEffect="non-scaling-stroke" />
            )}
            {announced && (
              <circle cx={head.x} cy={head.y} r={(Icon ? ICON_R + 3.5 : 9.5) * mpp} fill="none" stroke={ANNOUNCED} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
            )}
            {announced && !selected && (
              <text x={head.x + 11 * mpp} y={head.y - 9 * mpp} fontSize={11 * mpp} fill={ANNOUNCED} className="pointer-events-none font-mono font-semibold">
                {t.watch.vehicle.announcedLabel(id)}
              </text>
            )}
            {selected && (
              <text x={head.x + 9 * mpp} y={head.y - 8 * mpp} fontSize={11 * mpp} fill={color} className="pointer-events-none font-mono font-semibold">
                {id}
              </text>
            )}
          </g>
        )
      })}
    </g>
  )
}
