import { FileText } from 'lucide-react'
import { useState } from 'react'
import type { FieldReport, ReportJudgment, ReportVerdict } from '@/api/types'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { LinkedIds } from './AgentText'

interface Props {
  report: FieldReport
  judgment: ReportJudgment
  /** Texts of other reports, to show the ones this report conflicts with. */
  texts?: Map<string, FieldReport>
  /** Who judged it and when, e.g. "W2 · 10:15". */
  meta?: string
  /** Show the report text without a click (the conflicting reports' texts still open on click). */
  showText?: boolean
  className?: string
}

const VERDICT: Record<ReportVerdict, { box: string; badge: string; bar: string }> = {
  CONSISTENT: { box: 'border-emerald-500/30', badge: 'bg-emerald-100 text-emerald-800', bar: 'bg-emerald-500' },
  CONTRADICTED: { box: 'border-red-500/40 bg-red-50/60', badge: 'bg-red-100 text-red-800', bar: 'bg-red-500' },
  UNVERIFIABLE: { box: 'border-slate-400/40', badge: 'bg-slate-100 text-slate-700', bar: 'bg-slate-400' },
  IRRELEVANT: { box: 'border-dashed', badge: 'bg-muted text-muted-foreground', bar: 'bg-slate-300' },
}

/** A field report as an agent judged it: verdict, the model's 0-100 credibility, reason, the
 *  reports it contradicts; a click on the id shows the untrusted texts. */
export function ReportRef({ report, judgment: j, texts, meta, showText = false, className }: Props) {
  const r = t.watch.report
  const [open, setOpen] = useState(false)
  const style = VERDICT[j.verdict]
  const conflicts = j.conflicts_with.map((id) => ({ id, text: texts?.get(id) }))
  const extraTracks = j.track_ids.filter((id) => !j.reason.includes(id)) // the reason often names them
  return (
    <div className={cn('flex flex-col gap-1 rounded-md border px-2 py-1.5 text-xs', style.box, className)}>
      <p className="flex flex-wrap items-center gap-x-1.5 gap-y-1">
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="inline-flex items-center gap-1 rounded border bg-card px-1 font-mono text-[11px] hover:bg-muted"
        >
          <FileText aria-hidden className="size-3" />
          {report.report_id} · {r.source[report.source] ?? report.source} · {report.time}
        </button>
        <span className={cn('rounded px-1.5 py-px text-[10px] font-semibold tracking-wide uppercase', style.badge)}>{r.verdict[j.verdict]}</span>
        <span className="inline-flex items-center gap-1 font-mono text-[11px] text-muted-foreground" title={r.credibilityHint}>
          <span className="h-1.5 w-10 overflow-hidden rounded-full bg-muted">
            <span className={cn('block h-full rounded-full', style.bar)} style={{ width: `${j.credibility}%` }} />
          </span>
          {j.credibility}
        </span>
        {j.deception && <span className="rounded bg-red-600 px-1.5 py-px text-[10px] font-semibold text-white">{r.deception}</span>}
        {meta && <span className="ml-auto font-mono text-[10px] text-muted-foreground">{meta}</span>}
      </p>
      {showText && <Quote label={r.untrusted} text={report.text} />}
      <p className="leading-relaxed">
        <LinkedIds text={j.reason} />
        {extraTracks.length > 0 && (
          <span className="text-muted-foreground">
            {' · '}
            <LinkedIds text={extraTracks.join(' ')} />
          </span>
        )}
      </p>
      {conflicts.length > 0 && (
        <p className="flex flex-wrap items-center gap-1 text-[11px] text-red-700">
          <span>{r.conflicts}</span>
          {conflicts.map((c) => (
            <button key={c.id} type="button" onClick={() => setOpen(true)} className="rounded border border-red-300 px-1 font-mono hover:bg-red-100">
              {c.id}
            </button>
          ))}
        </p>
      )}
      {open && (
        <div className="flex flex-col gap-1">
          {!showText && <Quote label={`${report.report_id} · ${r.untrusted}`} text={report.text} />}
          {conflicts.map((c) =>
            c.text ? <Quote key={c.id} label={`${c.id} · ${r.source[c.text.source] ?? c.text.source} · ${c.text.time}`} text={c.text.text} /> : null,
          )}
        </div>
      )}
    </div>
  )
}

function Quote({ label, text }: { label: string; text: string }) {
  return (
    <blockquote className="rounded border-l-2 border-muted-foreground/30 bg-muted/50 px-2 py-1 text-muted-foreground">
      <span className="mb-0.5 block font-mono text-[10px] tracking-wider uppercase">{label}</span>
      {text}
    </blockquote>
  )
}
