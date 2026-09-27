import type { LatLon } from '@/api/types'
import { formatCoord } from '@/lib/format'

interface Props {
  position: LatLon
  mpp: number
}

/** The protected base at the SVG origin: diamond + coordinates, no title (keeps the center clear). */
export function BaseMarker({ position, mpp }: Props) {
  const s = 7 * mpp
  return (
    <g className="pointer-events-none">
      <rect
        x={-s}
        y={-s}
        width={2 * s}
        height={2 * s}
        transform="rotate(45)"
        className="fill-emerald-400 stroke-white"
        vectorEffect="non-scaling-stroke"
      />
      <text y={30 * mpp} textAnchor="middle" fontSize={9 * mpp} className="fill-emerald-600/80 font-mono">
        {`${formatCoord(position.lat)}, ${formatCoord(position.lon)}`}
      </text>
    </g>
  )
}
