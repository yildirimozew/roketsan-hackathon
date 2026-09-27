import type { Analysis } from '@/api/types'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { t } from '@/i18n'

/** Final evaluation card shown on the stage at the last step. */
export function BriefScene({ analysis }: { analysis: Analysis }) {
  const brief = analysis.brief
  if (!brief) return null
  return (
    <div className="absolute inset-0 flex flex-col items-center justify-center gap-6 p-6">
      <article className="w-full max-w-2xl rounded-lg border border-primary/60 bg-card/80 p-6 animate-in fade-in zoom-in-95 duration-300">
        <header className="mb-3 flex items-center justify-between gap-3">
          <h3 className="font-mono text-sm font-semibold tracking-widest text-primary">{t.scene.briefTitle(analysis.image_id)}</h3>
          <RiskBadge level={brief.level} size="lg" />
        </header>
        <p className="font-mono text-base leading-relaxed">{brief.summary}</p>
        <p className="mt-4 font-mono text-xs text-muted-foreground">{t.scene.sources}</p>
      </article>
      <p className="text-center font-mono text-xs text-muted-foreground">
        {t.scene.briefFooter.map((line) => (
          <span key={line} className="block">{line}</span>
        ))}
      </p>
    </div>
  )
}
