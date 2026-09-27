export interface Bounds {
  x0: number
  y0: number
  x1: number
  y1: number
}

const STEP_M = 1000
const MAX_LINES = 60 // per axis; the step doubles when zoomed far out so the grid stays cheap

/** Background: a 1 km grid over the whole visible area plus the 8 bearing spokes from the base. */
export function MapGrid({ bounds }: { bounds: Bounds }) {
  const { x0, y0, x1, y1 } = bounds
  let step = STEP_M
  while (Math.max(x1 - x0, y1 - y0) / step > MAX_LINES) step *= 2
  const range = (a: number, b: number) => {
    const out: number[] = []
    for (let v = Math.floor(a / step) * step; v <= b; v += step) out.push(v)
    return out
  }
  const reach = 1.5 * Math.max(Math.abs(x0), Math.abs(x1), Math.abs(y0), Math.abs(y1))
  return (
    <g className="pointer-events-none">
      {range(x0, x1).map((v) => (
        <line key={`x${v}`} x1={v} y1={y0} x2={v} y2={y1} className="stroke-slate-200" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      ))}
      {range(y0, y1).map((v) => (
        <line key={`y${v}`} x1={x0} y1={v} x2={x1} y2={v} className="stroke-slate-200" strokeWidth={1} vectorEffect="non-scaling-stroke" />
      ))}
      {[0, 45, 90, 135].map((deg) => {
        const r = (deg * Math.PI) / 180
        const dx = Math.sin(r) * reach
        const dy = Math.cos(r) * reach
        return (
          <line
            key={deg}
            x1={-dx}
            y1={dy}
            x2={dx}
            y2={-dy}
            className="stroke-slate-600"
            strokeDasharray="2 6"
            vectorEffect="non-scaling-stroke"
          />
        )
      })}
    </g>
  )
}
