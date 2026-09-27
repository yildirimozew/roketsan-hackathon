import { X } from 'lucide-react'
import type { ExpectedVehicle, VehicleRow } from '@/api/types'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { Button } from '@/components/ui/button'
import { t } from '@/i18n'
import type { VehicleState, verdictHistory } from '@/lib/watchDemo'
import { AgentText } from './AgentText'
import { ReportRef } from './ReportRef'
import { VehicleTypeIcon } from './VehicleTypeIcon'

interface Props {
  trackId: string
  state: VehicleState | undefined
  row: VehicleRow | undefined
  history: ReturnType<typeof verdictHistory>
  /** Set when the operator announced this vehicle (kept LOW). */
  announced: ExpectedVehicle | undefined
  onClose: () => void
}

/** Why the agents rate one vehicle the way they do: code facts plus every watcher's verdict. */
export function VehiclePanel({ trackId, state, row, history, announced, onClose }: Props) {
  const v = t.watch.vehicle
  return (
    <aside className="absolute top-[5.25rem] left-3 flex max-h-[calc(100%-6.5rem)] w-96 flex-col gap-3 overflow-auto rounded-lg border bg-card/95 p-4 shadow-xl backdrop-blur animate-in fade-in slide-in-from-left-2 duration-200">
      <header className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 font-mono text-sm font-semibold">
          <VehicleTypeIcon vehicleType={row?.vehicle_type} className="size-4 text-muted-foreground" />
          {v.title(trackId)}
        </h2>
        <div className="flex items-center gap-2">
          {state && <RiskBadge level={state.level} />}
          {state?.pending && <span className="text-[11px] text-amber-700">{t.watch.pending}</span>}
          <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label={v.close}>
            <X aria-hidden />
          </Button>
        </div>
      </header>
      {announced && (
        <p className="rounded-md border border-sky-500/40 bg-sky-50 px-2 py-1.5 text-xs text-sky-800">
          <span className="font-semibold">
            {v.announced} · {announced.announced_at} · {announced.expected_id}
          </span>
          <br />
          {announced.description}
        </p>
      )}
      {row ? (
        <div className="flex flex-col gap-1 text-xs">
          <p className="text-muted-foreground">{v.facts}</p>
          <p className="font-mono">{row.one_liner}</p>
          <p className="font-mono text-muted-foreground">
            rubric {row.rubric.score} · {row.behavior_class}
            {row.vehicle_type ? ` · ${v.type}: ${row.vehicle_type}` : ''}
          </p>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">{v.notSeen}</p>
      )}
      {history.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-xs text-muted-foreground">{v.history}</p>
          {history.map((h, i) => (
            <div key={i} className="flex flex-col gap-1 rounded-md border p-2 text-xs">
              <span className="flex items-center gap-2">
                <span className="font-mono text-muted-foreground">{`${h.tick} · ${h.watcher} · ${h.sector}`}</span>
                <RiskBadge level={h.verdict.level} />
              </span>
              <AgentText text={h.verdict.reason} max={110} />
              {h.verdict.note && <AgentText text={`${v.note}: ${h.verdict.note}`} max={110} className="text-muted-foreground italic" />}
              {h.reports.map((j) => (
                <ReportRef key={j.report.report_id} report={j.report} judgment={j.judgment} />
              ))}
            </div>
          ))}
        </div>
      )}
    </aside>
  )
}
