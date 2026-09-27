import type { Analysis } from '@/api/types'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { t } from '@/i18n'
import { FACTOR_SCALE, RISK_STYLES } from '@/lib/risk'

/** Rubric breakdown per vehicle: one bar per factor, total score and level. */
export function RiskScene({ analysis }: { analysis: Analysis }) {
  const risks = [...analysis.risks].sort((a, b) => b.score - a.score).slice(0, 3)
  return (
    <div className="absolute inset-0 overflow-y-auto p-6">
      <div className="grid min-h-full auto-rows-min content-center gap-4">
      {risks.length === 0 && <p className="text-center text-sm text-muted-foreground">{t.scene.noDetections}</p>}
      {risks.map((r) => (
        <article key={r.detection_id} className="rounded-lg border bg-card/80 p-4 animate-in fade-in duration-300">
          <header className="mb-3 flex items-center gap-3">
            <span className="font-mono text-sm">{`${r.detection_id}${r.track_id ? ` · ${r.track_id}` : ''}`}</span>
            <span className="ml-auto font-mono text-2xl font-semibold">{t.scene.scoreOf(r.score)}</span>
            <RiskBadge level={r.level} size="lg" />
          </header>
          <div className="h-2 overflow-hidden rounded bg-muted">
            <div className="h-full transition-all duration-700" style={{ width: `${r.score}%`, background: RISK_STYLES[r.level].stroke }} />
          </div>
          <ul className="mt-3 grid gap-1.5 sm:grid-cols-2">
            {r.factors.map((f) => (
              <li key={f.name} title={f.detail} className="grid grid-cols-[1fr_auto] items-center gap-x-2 text-xs">
                <span className="text-muted-foreground">{t.factors[f.name] ?? f.name}</span>
                <span className="font-mono">{f.points > 0 ? `+${f.points}` : '0'}</span>
                <span className="col-span-2 h-1 overflow-hidden rounded bg-muted">
                  <span className="block h-full bg-primary" style={{ width: `${(f.points / FACTOR_SCALE) * 100}%` }} />
                </span>
              </li>
            ))}
          </ul>
        </article>
      ))}
      </div>
    </div>
  )
}
