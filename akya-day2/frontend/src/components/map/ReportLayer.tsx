import { type Pt, REPORT_WINDOW_MIN } from '@/lib/fieldMap'

export interface ReportMark {
  id: string
  timeMin: number
  time: string
  official: boolean
  p: Pt
}

interface Props {
  reports: ReportMark[]
  minute: number
  mpp: number
  selectedId: string | null
  onSelect: (id: string) => void
}

const NEW_MIN = 10

/** Located reports from the last two hours; they fade with age and fresh ones ripple. */
export function ReportLayer({ reports, minute, mpp, selectedId, onSelect }: Props) {
  return (
    <g>
      {reports.map((r) => {
        const age = minute - r.timeMin
        const selected = r.id === selectedId
        if (age < 0 || (age > REPORT_WINDOW_MIN && !selected)) return null
        const fill = r.official ? 'fill-sky-400 stroke-white' : 'fill-amber-400 stroke-white'
        const ripple = r.official ? 'stroke-sky-600' : 'stroke-amber-600'
        const opacity = selected ? 1 : 1 - (Math.min(age, REPORT_WINDOW_MIN) / REPORT_WINDOW_MIN) * 0.75
        return (
          <g key={r.id} className="cursor-pointer" opacity={opacity} onClick={() => onSelect(r.id)}>
            <title>{`${r.id} · ${r.time}`}</title>
            <circle cx={r.p.x} cy={r.p.y} r={10 * mpp} fill="transparent" />
            <circle cx={r.p.x} cy={r.p.y} r={4 * mpp} className={fill} vectorEffect="non-scaling-stroke" />
            {age <= NEW_MIN && (
              <circle cx={r.p.x} cy={r.p.y} fill="none" className={ripple} vectorEffect="non-scaling-stroke">
                <animate attributeName="r" from={4 * mpp} to={18 * mpp} dur="1.6s" repeatCount="indefinite" />
                <animate attributeName="opacity" from="1" to="0" dur="1.6s" repeatCount="indefinite" />
              </circle>
            )}
            {selected && (
              <circle
                cx={r.p.x}
                cy={r.p.y}
                r={11 * mpp}
                fill="none"
                strokeWidth={2}
                className="stroke-cyan-600"
                vectorEffect="non-scaling-stroke"
              />
            )}
            {selected && (
              <text
                x={r.p.x + 14 * mpp}
                y={r.p.y + 4 * mpp}
                fontSize={11 * mpp}
                className="pointer-events-none fill-cyan-700 font-mono"
              >
                {`${r.time} · ${r.id}`}
              </text>
            )}
          </g>
        )
      })}
    </g>
  )
}
