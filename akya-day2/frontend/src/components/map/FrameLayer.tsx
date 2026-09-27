import { t } from '@/i18n'
import { type Pt, toPoints } from '@/lib/fieldMap'
import { cn } from '@/lib/utils'

export interface FrameMark {
  id: string
  captureMin: number
  captureTime: string
  corners: Pt[]
  center: Pt
}

interface Props {
  frames: FrameMark[]
  minute: number
  mpp: number
  selectedId: string | null
  onSelect: (id: string) => void
}

/** Minutes after a capture time during which the frame is shown as just taken. */
const LIVE_MIN = 5
/** Simulated minutes the \"image taken\" popup stays up after the capture. */
const POPUP_MIN = 3

/** Drone frame footprints, shown from their capture time on: that is when the frame's tracks end
 *  inside it (tracks.csv stops at capture). A fresh frame glows, older ones stay dim, the selected
 *  one is cyan. Click = detail card. */
export function FrameLayer({ frames, minute, mpp, selectedId, onSelect }: Props) {
  return (
    <g>
      {frames.map((f) => {
        if (f.captureMin > minute) return null
        const live = minute - f.captureMin <= LIVE_MIN
        const selected = f.id === selectedId
        const s = (live || selected ? 6 : 4) * mpp
        return (
          <g key={f.id} className="group cursor-pointer" onClick={() => onSelect(f.id)}>
            <title>{f.captureTime}</title>
            <polygon
              points={toPoints(f.corners)}
              className={
                selected
                  ? 'fill-cyan-400/25 stroke-cyan-600'
                  : live
                    ? 'fill-sky-400/30 stroke-sky-600'
                    : 'fill-sky-400/10 stroke-sky-600/50'
              }
              vectorEffect="non-scaling-stroke"
            />
            {/* Footprints are 100-370 m wide: a constant-size marker keeps them visible and clickable. */}
            <rect
              x={f.center.x - s}
              y={f.center.y - s}
              width={2 * s}
              height={2 * s}
              className={cn(
                'stroke-sky-600 group-hover:fill-sky-700',
                selected ? 'fill-cyan-700 stroke-cyan-200' : live ? 'fill-sky-700' : 'fill-sky-500/40',
              )}
              vectorEffect="non-scaling-stroke"
            />
            {live && (
              <circle cx={f.center.x} cy={f.center.y} fill="none" className="stroke-sky-600" vectorEffect="non-scaling-stroke">
                <animate attributeName="r" from={10 * mpp} to={26 * mpp} dur="1.2s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="1" to="0" dur="1.2s" repeatCount="indefinite" />
              </circle>
            )}
            {minute < f.captureMin + POPUP_MIN && (
              <FramePopup x={f.center.x} y={f.center.y - 12 * mpp} mpp={mpp} text={t.fieldMap.frameTaken(f.captureTime)} />
            )}
          </g>
        )
      })}
    </g>
  )
}

/** A small callout above a frame, constant size on screen. */
function FramePopup({ x, y, mpp, text }: { x: number; y: number; mpp: number; text: string }) {
  const w = (text.length * 6.2 + 18) * mpp
  const h = 20 * mpp
  const tip = 5 * mpp
  return (
    <g className="pointer-events-none animate-in fade-in duration-300" transform={`translate(${x} ${y})`}>
      <path
        d={`M ${-w / 2} ${-h - tip} h ${w} v ${h} h ${-(w / 2 - tip)} l ${-tip} ${tip} l ${-tip} ${-tip} h ${-(w / 2 - tip)} Z`}
        className="fill-card stroke-sky-600"
        strokeWidth={1}
        vectorEffect="non-scaling-stroke"
      />
      <text y={-tip - h / 2 + 3.5 * mpp} textAnchor="middle" fontSize={10.5 * mpp} className="fill-sky-800 font-medium">
        {text}
      </text>
    </g>
  )
}
