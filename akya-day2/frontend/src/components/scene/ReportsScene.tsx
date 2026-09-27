import { Check, CircleHelp, X } from 'lucide-react'
import type { Analysis, ReportCheck } from '@/api/types'
import { ReportVerdictChip } from '@/components/reports/ReportVerdictChip'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'

function CheckItem({ check }: { check: ReportCheck }) {
  const Icon = check.status === 'match' ? Check : check.status === 'mismatch' ? X : CircleHelp
  const tone = check.status === 'match' ? 'text-emerald-700' : check.status === 'mismatch' ? 'text-red-700' : 'text-zinc-700'
  return (
    <span className={cn('inline-flex items-center gap-1', tone)} title={check.detail}>
      {t.checks[check.name]}
      <Icon aria-label={check.status} className="size-3.5" />
    </span>
  )
}

/** Relevant reports as quoted, untrusted text next to our own checks and verdict. */
export function ReportsScene({ analysis }: { analysis: Analysis }) {
  const items = analysis.report_assessments
  return (
    // Outer box scrolls; inner min-h-full centers when short and grows (no clipping) when long.
    <div className="absolute inset-0 overflow-y-auto p-6">
      <div className="flex min-h-full flex-col items-center justify-center gap-3">
      {items.length === 0 && <p className="text-sm text-muted-foreground">{t.scene.noReports}</p>}
      {items.map((a) => {
        const claim = analysis.reports.find((c) => c.report_id === a.report_id)
        return (
          <article key={a.report_id} className="w-full max-w-2xl rounded-lg border bg-card/80 p-4 animate-in fade-in slide-in-from-bottom-1 duration-300">
            <div className="mb-2 flex items-center gap-2 font-mono text-xs text-muted-foreground">
              <span>{`${claim?.time ?? ''} · ${claim?.source ?? ''} · field_reports.json · ${a.report_id}`}</span>
              <span className="ml-auto">
                <ReportVerdictChip verdict={a.verdict} />
              </span>
            </div>
            {/* Untrusted text: rendered as plain text only, never interpreted. */}
            <p className="font-mono text-sm text-zinc-700">“{claim?.text}”</p>
            <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 border-t pt-2 font-mono text-xs">
              {a.checks.map((c) => (
                <CheckItem key={c.name} check={c} />
              ))}
            </div>
            <p className="mt-1.5 text-xs text-muted-foreground">{a.reason}</p>
          </article>
        )
      })}
      <p className="mt-2 text-center font-mono text-xs text-muted-foreground">
        {t.scene.reportsFooter.map((line) => (
          <span key={line} className="block">{line}</span>
        ))}
      </p>
      </div>
    </div>
  )
}
