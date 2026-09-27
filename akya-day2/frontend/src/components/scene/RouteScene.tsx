import type { Analysis } from '@/api/types'
import { t } from '@/i18n'
import { formatKm, formatSpeed } from '@/lib/format'
import { fitToBox, toLocalM } from '@/lib/geo'
import { primaryMotion, trendOf } from '@/lib/narrative'
import { OverlayLabel } from './OverlayLabel'

const W = 1000
const H = 562

/** To-scale bird's-eye plot of the followed track's last 2 hours with stops and the base. */
export function RouteScene({ analysis }: { analysis: Analysis }) {
  const motion = primaryMotion(analysis)
  const scene = analysis.scene
  if (!motion || !scene || motion.points.length === 0) {
    return <p className="absolute inset-0 grid place-items-center text-sm text-muted-foreground">{t.scene.noTrack}</p>
  }
  const base = scene.base.position
  const local = motion.points.map((p) => toLocalM(base, p.position))
  const others = analysis.motions.filter((m) => m.track_id !== motion.track_id)
  const fit = fitToBox([...local, { x: 0, y: 0 }], W, H - 60, 70)
  const pts = local.map(fit.project)
  const path = pts.map((p, i) => `${i ? 'L' : 'M'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ')
  const b = fit.project({ x: 0, y: 0 })
  const now = pts[pts.length - 1]!
  const pct = (p: { x: number; y: number }) => ({ x: (p.x / W) * 100, y: (p.y / H) * 100 })
  const trend = trendOf(motion)
  const trendText = trend === 'closing' ? t.scene.trendClosing : trend === 'leaving' ? t.scene.trendLeaving : t.scene.trendStatic
  const first = motion.points[0]!
  const last = motion.points[motion.points.length - 1]!

  return (
    <div className="absolute inset-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 size-full">
        {others.map((m) => {
          const d = m.points.map((p, i) => {
            const q = fit.project(toLocalM(base, p.position))
            return `${i ? 'L' : 'M'} ${q.x.toFixed(1)} ${q.y.toFixed(1)}`
          })
          return <path key={m.track_id} d={d.join(' ')} fill="none" stroke="rgb(161 161 170 / 0.4)" strokeWidth={2} />
        })}
        <path d={path} fill="none" stroke="#d97706" strokeWidth={3} strokeLinejoin="round" className="animate-in fade-in duration-500" />
        <line x1={b.x} y1={b.y} x2={now.x} y2={now.y} stroke="#dc2626" strokeWidth={2} strokeDasharray="7 6" />
        <rect x={b.x - 11} y={b.y - 11} width={22} height={22} transform={`rotate(45 ${b.x} ${b.y})`} fill="none" stroke="#dc2626" strokeWidth={3} />
        <text x={b.x + 18} y={b.y + 6} fill="#dc2626" fontSize={18}>{t.scene.base}</text>
        {motion.stops.map((s) => {
          const p = fit.project(toLocalM(base, s.position))
          return <circle key={s.start} cx={p.x} cy={p.y} r={9} fill="#ffffff" stroke="#71717a" strokeWidth={3} />
        })}
        <circle cx={now.x} cy={now.y} r={10} fill="#d97706" />
      </svg>
      <OverlayLabel x={2} y={3}>{t.scene.routeTitle(motion.track_id, first.time, last.time)}</OverlayLabel>
      {motion.stops.map((s) => {
        const p = pct(fit.project(toLocalM(base, s.position)))
        const right = p.x > 55 // keep labels inside the stage: right-half stops label to the left
        return (
          <OverlayLabel key={s.start} x={right ? p.x - 1.8 : p.x + 1.8} y={p.y} anchor={right ? 'tr' : 'left'} className={right ? '-translate-y-1/2' : ''}>
            {t.scene.waited(s.start, s.duration_min)}
            {s.duration_min >= 30 ? t.scene.stopToBase(formatKm(s.distance_to_base_m)) : ''}
          </OverlayLabel>
        )
      })}
      <OverlayLabel x={pct(now).x + 1.5} y={pct(now).y - 2} anchor="bl" className="text-amber-700">
        {t.scene.nowAt(last.time, formatKm(motion.dist_now_m))}
      </OverlayLabel>
      <OverlayLabel x={2} y={97} anchor="bl">
        {t.scene.routeFooter(formatSpeed(motion.last10_speed_ms), `${motion.path_km.toLocaleString('tr-TR')} km`, trendText)}
      </OverlayLabel>
    </div>
  )
}
