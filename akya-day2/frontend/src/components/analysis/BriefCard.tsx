import { Bot, FileWarning } from 'lucide-react'
import type { Brief } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { t } from '@/i18n'
import { EvidenceChip } from './EvidenceChip'
import { RiskBadge } from './RiskBadge'

function Section({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null
  return (
    <div>
      <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
        {title}
      </h3>
      <ul className="list-disc space-y-0.5 pl-4 text-sm text-muted-foreground">
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  )
}

export function BriefCard({ brief }: { brief: Brief }) {
  const SourceIcon = brief.generated_by === 'llm' ? Bot : FileWarning
  return (
    <Card className="animate-in fade-in slide-in-from-bottom-2 duration-300">
      <CardHeader className="flex flex-row items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <RiskBadge level={brief.level} size="lg" />
          <CardTitle className="text-lg">{brief.headline}</CardTitle>
        </div>
        <span className="flex items-center gap-1 text-xs text-muted-foreground">
          <SourceIcon aria-hidden className="size-3.5" />
          {t.brief.generatedBy[brief.generated_by]}
        </span>
      </CardHeader>
      <CardContent className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <div className="space-y-3">
          <p className="text-sm leading-relaxed">{brief.summary}</p>
          {brief.vehicles.map((v) => (
            <div key={v.detection_id} className="flex flex-wrap items-center gap-2 text-sm">
              <RiskBadge level={v.level} />
              <span>{v.text}</span>
              {v.evidence_ids.map((id) => (
                <EvidenceChip key={id} id={id} />
              ))}
            </div>
          ))}
          <Section title={t.brief.reportNotes} items={brief.report_notes} />
        </div>
        <div className="space-y-3">
          <div>
            <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              {t.brief.action}
            </h3>
            <p className="text-base font-semibold text-primary">
              {t.action[brief.recommended_action]}
            </p>
          </div>
          <Section title={t.brief.uncertainties} items={brief.uncertainties} />
          <div>
            <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-widest text-muted-foreground">
              {t.brief.evidence}
            </h3>
            <div className="flex flex-wrap gap-1">
              {brief.evidence_ids.map((id) => (
                <EvidenceChip key={id} id={id} />
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
