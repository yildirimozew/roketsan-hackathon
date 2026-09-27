import type { Analysis } from '@/api/types'
import { imageUrl } from '@/api/endpoints'
import { useSelection } from '@/hooks/useSelection'
import { t } from '@/i18n'
import { formatCoord, formatMeters } from '@/lib/format'
import { RISK_STYLES } from '@/lib/risk'
import { OverlayLabel } from './OverlayLabel'

export type FrameMode = 'idle' | 'corners' | 'boxes' | 'tracks'

const MATCH = '#34d399'
const SELECTED = '#22d3ee'

/** The frame image with step-specific overlays in native pixel coordinates. */
export function FrameScene({ analysis, mode }: { analysis: Analysis; mode: FrameMode }) {
  const { selectedEvidenceId, select } = useSelection()
  const image = analysis.image
  if (!image) return null
  const { width_px: w, height_px: h, corners } = image
  const pct = (x: number, y: number) => ({ x: (x / w) * 100, y: (y / h) * 100 })
  const levelOf = (id: string) => analysis.risks.find((r) => r.detection_id === id)?.level ?? 'LOW'
  const first = analysis.detections[0]

  return (
    <div className="absolute inset-0">
      <img src={imageUrl(image.image_id)} alt={image.image_id} className="absolute inset-0 size-full object-cover" />
      <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className="absolute inset-0 size-full">
        {mode === 'corners' && <rect x={1} y={1} width={w - 2} height={h - 2} fill="none" stroke="#fbbf24" strokeWidth={3} />}
        {(mode === 'boxes' || mode === 'tracks') &&
          analysis.detections.map((d) => {
            const [x, y, bw, bh] = d.bbox
            const color = selectedEvidenceId === d.id ? SELECTED : RISK_STYLES[levelOf(d.id)].stroke
            return (
              <g key={d.id} className="cursor-pointer" onClick={() => select(d.id)}>
                <rect x={x} y={y} width={bw} height={bh} fill="none" stroke={color} strokeWidth={mode === 'tracks' ? 1.5 : 3} rx={2} />
                {mode === 'boxes' && <circle cx={d.center_px[0]} cy={d.center_px[1]} r={3} fill={color} />}
              </g>
            )
          })}
        {mode === 'tracks' &&
          analysis.track_snapshots.map((s) => (
            <circle
              key={s.track_id}
              cx={s.center_px[0]}
              cy={s.center_px[1]}
              r={s.matched_detection_id ? 9 : 6}
              fill={s.matched_detection_id ? `${MATCH}99` : '#0b1220aa'}
              stroke={s.matched_detection_id ? MATCH : '#e4e4e7'}
              strokeWidth={2}
            />
          ))}
      </svg>

      {mode === 'idle' && (
        <div className="absolute inset-x-0 bottom-0 bg-black/70 py-3 text-center">
          <p className="text-sm font-semibold text-zinc-100">{t.scene.waiting(image.image_id)}</p>
          <p className="font-mono text-xs text-zinc-400">{t.scene.pressPlay}</p>
        </div>
      )}

      {mode === 'corners' && (
        <>
          <OverlayLabel x={1} y={2}>{`${formatCoord(corners.tl!.lat, 6)}, ${formatCoord(corners.tl!.lon, 6)}`}</OverlayLabel>
          <OverlayLabel x={99} y={2} anchor="tr">{`${formatCoord(corners.tr!.lat, 6)}, ${formatCoord(corners.tr!.lon, 6)}`}</OverlayLabel>
          <OverlayLabel x={1} y={98} anchor="bl">{`${formatCoord(corners.bl!.lat, 6)}, ${formatCoord(corners.bl!.lon, 6)}`}</OverlayLabel>
          <OverlayLabel x={99} y={98} anchor="br">{t.scene.orientation}</OverlayLabel>
          <OverlayLabel x={50} y={50} anchor="center" className="text-center text-sm">
            {t.scene.sizeTime(w, h, image.capture_time).map((line) => <div key={line}>{line}</div>)}
          </OverlayLabel>
        </>
      )}

      {mode === 'boxes' &&
        (first ? (
          analysis.detections.map((d, i) => {
            const p = pct(d.bbox[0], d.bbox[1] + d.bbox[3])
            return (
              <OverlayLabel key={d.id} x={p.x} y={p.y + 1} anchor={p.x > 60 ? 'tr' : 'tl'} className={i > 2 ? 'hidden' : ''}>
                <div className="text-amber-300">{`${d.id} · ${d.label}`}</div>
                <div>{`${t.scene.box} (${d.bbox.join(', ')})`}</div>
                <div>{`${t.scene.centerPx} (${d.center_px.map(Math.round).join(', ')})`}</div>
              </OverlayLabel>
            )
          })
        ) : (
          <OverlayLabel x={50} y={50} anchor="center">{t.scene.noDetections}</OverlayLabel>
        ))}

      {mode === 'tracks' && (
        <>
          <OverlayLabel x={1} y={2}>{t.scene.tracksAt(image.capture_time)}</OverlayLabel>
          {analysis.matches.map((m) => {
            const snap = analysis.track_snapshots.find((s) => s.track_id === m.track_id)
            // Second-best labels only when one vehicle is in frame; with several they overlap.
            const second =
              analysis.matches.length === 1
                ? analysis.track_snapshots.find((s) => s.track_id === m.second_best_track_id)
                : undefined
            return [
              snap && (
                <OverlayLabel key={`${m.detection_id}-m`} {...pct(snap.center_px[0], snap.center_px[1] + 18)} anchor={snap.center_px[0] > w * 0.6 ? 'tr' : 'tl'} className="text-emerald-300">
                  {t.scene.matched(`${m.track_id} · ${formatMeters(m.distance_m)}`)}
                </OverlayLabel>
              ),
              second && (
                <OverlayLabel key={`${m.detection_id}-s`} {...pct(second.center_px[0] + 14, second.center_px[1])} anchor="left">
                  {`${second.track_id} · ${formatMeters(m.second_best_m)}`}
                </OverlayLabel>
              ),
            ]
          })}
          <OverlayLabel x={99} y={98} anchor="br">{t.scene.nearestNote}</OverlayLabel>
        </>
      )}
    </div>
  )
}
