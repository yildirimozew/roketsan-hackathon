import type { Detection, TrackMatch, VehicleRisk } from '@/api/types'
import { t } from '@/i18n'
import { formatKm, formatMeters, formatPercent } from '@/lib/format'
import { useSelection } from '@/hooks/useSelection'
import { cn } from '@/lib/utils'
import { RiskBadge } from './RiskBadge'

interface VehicleTableProps {
  detections: Detection[]
  matches: TrackMatch[]
  risks: VehicleRisk[]
}

export function VehicleTable({ detections, matches, risks }: VehicleTableProps) {
  const { selectedEvidenceId, select } = useSelection()

  return (
    <table className="w-full text-sm">
      <thead className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
        <tr>
          <th className="py-1 font-medium">{t.vehicles.id}</th>
          <th className="py-1 font-medium">{t.vehicles.type}</th>
          <th className="py-1 font-medium">{t.vehicles.track}</th>
          <th className="py-1 font-medium">{t.vehicles.distance}</th>
          <th className="py-1 text-right font-medium">{t.vehicles.score}</th>
          <th className="py-1 text-right font-medium">{t.vehicles.level}</th>
        </tr>
      </thead>
      <tbody className="font-mono text-xs">
        {detections.map((det) => {
          const match = matches.find((m) => m.detection_id === det.id)
          const risk = risks.find((r) => r.detection_id === det.id)
          return (
            <tr
              key={det.id}
              onClick={() => select(det.id)}
              className={cn(
                'cursor-pointer border-t hover:bg-accent/50',
                selectedEvidenceId === det.id && 'bg-primary/10',
              )}
            >
              <td className="py-1.5">{det.id}</td>
              <td className="py-1.5 font-sans">
                {det.label} <span className="text-muted-foreground">{formatPercent(det.confidence)}</span>
              </td>
              <td className="py-1.5">
                {match?.track_id ?? '—'}{' '}
                <span className="text-muted-foreground">{formatMeters(match?.distance_m)}</span>
              </td>
              <td className="py-1.5">{formatKm(det.distance_to_base_m)}</td>
              <td className="py-1.5 text-right">{risk?.score ?? '—'}</td>
              <td className="py-1.5 text-right">{risk && <RiskBadge level={risk.level} />}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}
