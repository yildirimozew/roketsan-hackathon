import type { Analysis } from '@/api/types'
import { imageUrl } from '@/api/endpoints'
import { t } from '@/i18n'
import { formatCoord, formatKm } from '@/lib/format'
import { fitToBox, toLocalM } from '@/lib/geo'
import { frameSizeM } from '@/lib/narrative'
import { OverlayLabel } from './OverlayLabel'

const W = 1000
const H = 562
const FRAME_W = 330
const FRAME_H = (FRAME_W * 9) / 16

/** Schematic (not to scale) frame-to-base placement plus a to-scale inset of the 8 zones. */
export function PlacementScene({ analysis }: { analysis: Analysis }) {
  const { image, scene } = analysis
  if (!image || !scene) return null
  const base = scene.base.position
  const center = { lat: (image.corners.tl!.lat + image.corners.br!.lat) / 2, lon: (image.corners.tl!.lon + image.corners.br!.lon) / 2 }
  const rel = toLocalM(base, center)
  const len = Math.hypot(rel.x, rel.y) || 1
  // Frame sits right of center; base is drawn in the true direction, at a fixed schematic distance.
  const fx = 600
  const fy = 250
  const bx = Math.max(60, Math.min(W - 60, fx - (rel.x / len) * 420))
  const by = Math.max(60, Math.min(H - 90, fy + (rel.y / len) * 420))
  const nearest = [...analysis.detections].sort((a, b) => (a.distance_to_base_m ?? 0) - (b.distance_to_base_m ?? 0))[0]
  const dist = nearest?.distance_to_base_m ?? len
  const { w, h } = frameSizeM(analysis)

  const zonePts = scene.zones.map((z) => ({ name: z.name, ...toLocalM(base, z.center) }))
  const fit = fitToBox([...zonePts, { x: 0, y: 0 }, rel], 170, 170, 18)
  const inset = (p: { x: number; y: number }) => fit.project(p)

  return (
    <div className="absolute inset-0">
      <svg viewBox={`0 0 ${W} ${H}`} className="absolute inset-0 size-full">
        <defs>
          <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
            <path d="M 100 0 L 0 0 0 100" fill="none" stroke="rgb(255 255 255 / 0.05)" />
          </pattern>
        </defs>
        <rect width={W} height={H} fill="url(#grid)" />
        <line x1={bx} y1={by} x2={fx} y2={fy} stroke="#dc2626" strokeWidth={2} strokeDasharray="8 6" />
        <rect x={bx - 11} y={by - 11} width={22} height={22} transform={`rotate(45 ${bx} ${by})`} fill="none" stroke="#dc2626" strokeWidth={3} />
        <text x={bx + 18} y={by + 6} fill="#dc2626" fontSize={18}>{t.scene.base}</text>
        <image href={imageUrl(image.image_id)} x={fx - FRAME_W / 2} y={fy - FRAME_H / 2} width={FRAME_W} height={FRAME_H} preserveAspectRatio="none" />
        <rect x={fx - FRAME_W / 2} y={fy - FRAME_H / 2} width={FRAME_W} height={FRAME_H} fill="none" stroke="#d97706" strokeWidth={3} />
        {analysis.detections.map((d) => (
          <circle key={d.id} cx={fx - FRAME_W / 2 + (d.center_px[0] / image.width_px) * FRAME_W} cy={fy - FRAME_H / 2 + (d.center_px[1] / image.height_px) * FRAME_H} r={5} fill="#d97706" stroke="#ffffff" strokeWidth={2} />
        ))}
        <g transform={`translate(${W - 50} 40)`}>
          <line x1={0} y1={50} x2={0} y2={0} stroke="#3f3f46" strokeWidth={3} />
          <path d="M -8 12 L 0 0 L 8 12" fill="none" stroke="#3f3f46" strokeWidth={3} />
          <text x={12} y={16} fill="#3f3f46" fontSize={16}>{t.scene.north}</text>
        </g>
        <g transform={`translate(18 ${H - 200})`}>
          <rect width={170} height={170} rx={6} fill="rgb(0 0 0 / 0.55)" stroke="rgb(255 255 255 / 0.1)" />
          {zonePts.map((z) => {
            const p = inset(z)
            return <circle key={z.name} cx={p.x} cy={p.y} r={4} fill="#71717a" />
          })}
          <circle cx={inset({ x: 0, y: 0 }).x} cy={inset({ x: 0, y: 0 }).y} r={5} fill="#dc2626" />
          <circle cx={inset(rel).x} cy={inset(rel).y} r={5} fill="#d97706" />
          <text x={8} y={162} fill="#71717a" fontSize={11}>{t.scene.zonesInset}</text>
        </g>
      </svg>
      <OverlayLabel x={((fx - FRAME_W / 2) / W) * 100} y={((fy - FRAME_H / 2) / H) * 100 - 1} anchor="bl">
        {`${formatCoord(image.corners.tl!.lat, 6)}, ${formatCoord(image.corners.tl!.lon, 6)}`}
      </OverlayLabel>
      <OverlayLabel x={((fx + FRAME_W / 2) / W) * 100} y={((fy + FRAME_H / 2) / H) * 100 + 1} anchor="tr">
        {`${formatCoord(image.corners.br!.lat, 6)}, ${formatCoord(image.corners.br!.lon, 6)}`}
      </OverlayLabel>
      <OverlayLabel x={(((bx + fx) / 2) / W) * 100} y={(((by + fy) / 2) / H) * 100 + 2}>{t.scene.toBase(formatKm(dist))}</OverlayLabel>
      <OverlayLabel x={50} y={97} anchor="bl" className="w-[92%] -translate-x-1/2 text-center whitespace-normal">
        {t.scene.placementNote(w.toFixed(0), h.toFixed(0)).map((line) => <div key={line}>{line}</div>)}
      </OverlayLabel>
    </div>
  )
}
