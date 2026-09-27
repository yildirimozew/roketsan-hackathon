import { Siren } from 'lucide-react'
import type { WatchEventOf } from '@/api/types'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import type { FieldReport } from '@/api/types'
import { type JudgedReport, judgeLabel } from '@/lib/watchDemo'
import { AgentText, LinkedIds } from './AgentText'
import { ReportRef } from './ReportRef'

type Alert = WatchEventOf<'operator_alert'>['alert']

/** The model often repeats the urgency at the start of the headline; the badge already shows it. */
const headline = (a: Alert) => a.headline.replace(/^\s*(ACİL|ACIL|DERHAL|URGENT|IMMEDIATE)\s*[:–—-]\s*/iu, '')

interface Props {
  tick: string
  decision: WatchEventOf<'supervisor_decision'> | undefined
  alerts: Alert[] // this tick's alerts
  history: Alert[] // earlier alerts, newest first
  contradicted: JudgedReport[] // this tick's contradicted reports (watchers and supervisor)
  texts: Map<string, FieldReport>
  progress: number // supervisor text, 0..1
  alertProgress: number // operator alert, 0..1
}

const URGENCY: Record<string, string> = {
  advisory: 'border-sky-500/40 bg-sky-50',
  urgent: 'border-orange-500/50 bg-orange-50',
  immediate: 'border-red-500/60 bg-red-50',
}
const URGENCY_TEXT: Record<string, string> = {
  advisory: 'text-sky-700',
  urgent: 'text-orange-700',
  immediate: 'text-red-700',
}

/** Operator view: current threat, one-line situation, the alert to act on, and the alert log.
 *  Internal detail (patterns, level changes, traces) is left out on purpose. */
export function SupervisorCard({ tick, decision, alerts, history, contradicted, texts, progress, alertProgress }: Props) {
  const w = t.watch
  const d = decision?.decision
  return (
    <div className="flex flex-col gap-3">
      <section className="flex flex-col gap-2 rounded-lg border bg-card p-4 shadow-xs">
        <header className="flex items-center justify-between">
          <span className="text-xs text-muted-foreground">{w.asOf(tick)}</span>
          {d && progress > 0 ? <RiskBadge level={d.threat_level} size="lg" /> : <span className="animate-pulse text-xs text-muted-foreground">{w.thinking}</span>}
        </header>
        {d && progress > 0 && <AgentText text={d.situation_summary} max={120} progress={progress} className="text-sm" />}
      </section>

      {alertProgress > 0 &&
        alerts.map((a) => (
          <AlertBox key={a.alert_id} alert={a} progress={alertProgress} />
        ))}
      {progress >= 1 && alertProgress >= 1 && alerts.length === 0 && (
        <p className="rounded-lg border border-dashed bg-card p-3 text-xs text-muted-foreground">{w.noAlerts}</p>
      )}

      {progress > 0 && contradicted.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="text-xs font-semibold tracking-widest text-red-700 uppercase">{w.contradicted}</h3>
          {contradicted.map((j) => (
            <ReportRef
              key={j.report.report_id}
              report={j.report}
              judgment={j.judgment}
              texts={texts}
              meta={`${judgeLabel(j.by, w.report.supervisor)} · ${j.tick}`}
            />
          ))}
        </section>
      )}

      {history.length > 0 && (
        <section className="flex flex-col gap-1.5">
          <h3 className="text-xs font-semibold tracking-widest text-muted-foreground uppercase">{w.alertLog}</h3>
          {history.map((a) => (
            <div key={a.alert_id} className="rounded-md border bg-card px-3 py-2 text-xs">
              <p className={cn('mb-0.5 font-mono', URGENCY_TEXT[a.urgency])}>
                {a.tick} · {w.urgency[a.urgency] ?? a.urgency}
              </p>
              <AgentText text={headline(a)} max={90} />
            </div>
          ))}
        </section>
      )}
    </div>
  )
}

function AlertBox({ alert: a, progress }: { alert: Alert; progress: number }) {
  const w = t.watch
  return (
    <section className={cn('flex flex-col gap-1.5 rounded-lg border p-4 shadow-xs animate-in fade-in zoom-in-95 duration-300', URGENCY[a.urgency])}>
      <p className={cn('flex items-center gap-2 text-xs font-semibold tracking-wider', URGENCY_TEXT[a.urgency])}>
        <Siren aria-hidden className="size-4" />
        {w.alerts} · {w.urgency[a.urgency] ?? a.urgency}
      </p>
      <AgentText text={headline(a)} max={120} progress={Math.min(1, progress * 2)} className="text-sm font-semibold" />
      {progress >= 0.5 && <AgentText text={a.description} max={140} progress={Math.min(1, (progress - 0.5) * 2)} className="text-sm text-muted-foreground" />}
      {progress >= 1 && (
        <p className="flex flex-wrap gap-1 text-xs">
          <LinkedIds text={a.track_ids.join(' ')} />
        </p>
      )}
    </section>
  )
}
