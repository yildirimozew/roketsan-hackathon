import type { FieldReport, ReportVerdict } from '@/api/types'
import { t } from '@/i18n'
import { type JudgedReport, judgeLabel } from '@/lib/watchDemo'
import { ReportRef } from './ReportRef'

const SECTIONS: ReportVerdict[] = ['CONTRADICTED', 'UNVERIFIABLE', 'CONSISTENT', 'IRRELEVANT']

interface Props {
  judged: JudgedReport[] // latest judgment per report up to the playhead, newest first
  texts: Map<string, FieldReport>
}

/** Every field report the agents have judged so far: verdict, the model's credibility score and
 *  the reports it contradicts; on top, counts and the average score per source. */
export function ReportsTab({ judged, texts }: Props) {
  const w = t.watch
  if (judged.length === 0) return <p className="rounded-lg border border-dashed bg-card p-4 text-sm text-muted-foreground">{w.reportsEmpty}</p>
  const bad = judged.filter((j) => j.judgment.verdict === 'CONTRADICTED').length
  const deception = judged.filter((j) => j.judgment.deception).length
  const scored = judged.filter((j) => j.judgment.verdict !== 'IRRELEVANT')
  const sources = [...new Set(scored.map((j) => j.report.source))].sort()
  return (
    <div className="flex flex-col gap-2">
      <section className="flex flex-col gap-1 rounded-lg border bg-card px-3 py-2 text-xs">
        <p className="font-medium">{w.reportsSummary(judged.length, bad, deception)}</p>
        {sources.map((source) => {
          const mine = scored.filter((j) => j.report.source === source)
          const avg = Math.round(mine.reduce((sum, j) => sum + j.judgment.credibility, 0) / mine.length)
          return (
            <p key={source} className="font-mono text-muted-foreground">
              {w.sourceScore(w.report.source[source] ?? source, avg, mine.length)}
            </p>
          )
        })}
        <p className="text-[11px] text-muted-foreground">{w.reportsHint}</p>
      </section>
      {SECTIONS.map((verdict) => {
        const items = judged.filter((j) => j.judgment.verdict === verdict)
        if (items.length === 0) return null
        return (
          <section key={verdict} className="flex flex-col gap-1.5">
            <h3 className="mt-1 text-xs font-semibold tracking-widest text-muted-foreground uppercase">
              {w.report.verdict[verdict]} · {items.length}
            </h3>
            {items.map((j) => (
              <ReportRef
                key={j.report.report_id}
                report={j.report}
                judgment={j.judgment}
                texts={texts}
                meta={`${judgeLabel(j.by, w.report.supervisor)} · ${j.tick}`}
                showText
              />
            ))}
          </section>
        )
      })}
    </div>
  )
}
