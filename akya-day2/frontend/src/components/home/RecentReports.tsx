import { ArrowRight } from 'lucide-react'
import { Link } from 'react-router'
import type { MapReport } from '@/api/types'
import { SourceBadge } from '@/components/map/SourceBadge'
import { t } from '@/i18n'
import { placeName } from '@/lib/format'

interface Props {
  reports: MapReport[] // newest first, already limited
}

/** Latest field reports up to the dashboard time; the full feed lives on the field map. */
export function RecentReports({ reports }: Props) {
  const tr = t.home.reports
  return (
    <section className="flex flex-col rounded-lg border bg-card">
      <header className="flex items-center justify-between border-b px-4 py-2.5">
        <h2 className="text-xs font-semibold tracking-widest text-emerald-700">{tr.title.toLocaleUpperCase('tr-TR')}</h2>
        <Link to="/watch" className="flex items-center gap-1 text-[11px] text-muted-foreground transition-colors hover:text-foreground">
          {tr.all}
          <ArrowRight aria-hidden className="size-3" />
        </Link>
      </header>
      {reports.length === 0 ? (
        <p className="p-4 text-xs text-muted-foreground">{tr.empty}</p>
      ) : (
        <ol className="divide-y">
          {reports.map((r) => (
            <li key={r.report_id} className="flex flex-col gap-1 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-foreground">{r.time}</span>
                <SourceBadge source={r.source} />
                {r.zone && <span className="ml-auto truncate text-[10px] text-muted-foreground">{placeName(r.zone)}</span>}
              </div>
              <p className="line-clamp-2 font-mono text-[11px] leading-snug text-slate-700">{r.text}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  )
}
