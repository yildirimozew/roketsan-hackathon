import { type Pt, type Sample, TRACK_LINGER_MIN, pathAt, toPoints, trailAt } from '@/lib/fieldMap'
import { cn } from '@/lib/utils'

export interface TrackMark {
  id: string
  samples: Sample[]
}

interface Props {
  tracks: TrackMark[]
  minute: number
  mpp: number
  showAll: boolean
  selectedId: string | null
  onSelect: (id: string) => void
}

const LIVE_TRAIL_MIN = 20

interface Drawn {
  id: string
  path: Pt[] // the part drawn in full colour
  route: Pt[] | null // an ended track's full route, drawn faint
  opacity: number
  head: 'live' | 'last' | null
}

/** How a track looks at `minute`: live while active, fading for TRACK_LINGER_MIN after its last
 *  sample, then only as a faint route when `showAll` is on (or it is selected). Never ahead of `minute`. */
function drawTrack(tr: TrackMark, minute: number, showAll: boolean, selected: boolean): Drawn | null {
  const first = tr.samples[0]
  const last = tr.samples[tr.samples.length - 1]
  if (!first || !last) return null
  if (minute < first.t) return null
  const live = pathAt(tr.samples, minute)
  // Live tracks show their last LIVE_TRAIL_MIN only (the selected one: its whole path) so the map
  // stays readable with ~100 vehicles on it.
  if (live.length > 0) {
    const path = selected ? live : trailAt(tr.samples, minute, LIVE_TRAIL_MIN)
    return { id: tr.id, path, route: null, opacity: 1, head: 'live' }
  }
  const since = minute - last.t
  if (since <= TRACK_LINGER_MIN) {
    return { id: tr.id, path: tr.samples, route: null, opacity: 1 - (since / TRACK_LINGER_MIN) * 0.85, head: 'last' }
  }
  return showAll || selected ? { id: tr.id, path: [], route: tr.samples, opacity: 1, head: null } : null
}

/** Vehicle tracks: live path + position, a fading "last seen" tail, and optionally every ended track so far. */
export function TrackLayer({ tracks, minute, mpp, showAll, selectedId, onSelect }: Props) {
  const drawn = tracks.flatMap((tr) => drawTrack(tr, minute, showAll, tr.id === selectedId) ?? [])
  // Faint routes first, live tracks above them, the selected track on top.
  const rank = (d: Drawn) => (d.id === selectedId ? 3 : d.head === 'live' ? 2 : d.head === 'last' ? 1 : 0)
  drawn.sort((a, b) => rank(a) - rank(b))

  return (
    <g>
      {drawn.map(({ id, path, route, opacity, head }) => {
        const selected = id === selectedId
        const end = path[path.length - 1]
        const hit = toPoints(route ?? path)
        return (
          <g key={id} className="group cursor-pointer" opacity={opacity} onClick={() => onSelect(id)}>
            <title>{id}</title>
            <polyline points={hit} fill="none" stroke="transparent" strokeWidth={10} vectorEffect="non-scaling-stroke" />
            {route && (
              <polyline
                points={toPoints(route)}
                fill="none"
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeWidth={selected ? 1.5 : 1}
                className={selected ? 'stroke-cyan-600/50' : 'stroke-emerald-600/20 group-hover:stroke-emerald-600/60'}
                vectorEffect="non-scaling-stroke"
              />
            )}
            {path.length > 0 && (
              <polyline
                points={toPoints(path)}
                fill="none"
                strokeLinejoin="round"
                strokeLinecap="round"
                strokeWidth={selected ? 2.5 : 1.25}
                className={cn(
                  'transition-colors',
                  selected ? 'stroke-cyan-600' : 'stroke-emerald-600/45 group-hover:stroke-emerald-600',
                )}
                vectorEffect="non-scaling-stroke"
              />
            )}
            {end && head === 'live' && (
              <circle cx={end.x} cy={end.y} r={(selected ? 5 : 3) * mpp} className={selected ? 'fill-cyan-700' : 'fill-emerald-700'} />
            )}
            {end && head === 'last' && (
              <circle
                cx={end.x}
                cy={end.y}
                r={(selected ? 5 : 3) * mpp}
                fill="none"
                strokeWidth={1.25}
                className={selected ? 'stroke-cyan-600' : 'stroke-emerald-600'}
                vectorEffect="non-scaling-stroke"
              />
            )}
            {end && selected && (
              <text x={end.x + 8 * mpp} y={end.y - 8 * mpp} fontSize={11 * mpp} className="pointer-events-none fill-cyan-700 font-mono">
                {id}
              </text>
            )}
          </g>
        )
      })}
    </g>
  )
}
