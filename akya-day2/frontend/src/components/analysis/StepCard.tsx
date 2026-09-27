import { ChevronRight } from 'lucide-react'
import { useState } from 'react'
import type { StepResult } from '@/api/types'
import { t } from '@/i18n'
import type { Narrative } from '@/lib/narrative'
import { formatMs } from '@/lib/format'
import { cn } from '@/lib/utils'

interface StepCardProps {
  step: StepResult
  total: number
  narrative: Narrative
  active: boolean
  onSelect: () => void
}

/** One agent message: "3/8 · ARACI TESPİT ET", a sentence, and mono facts; raw data on demand. */
export function StepCard({ step, total, narrative, active, onSelect }: StepCardProps) {
  const [raw, setRaw] = useState(false)
  return (
    <article
      className={cn(
        'rounded-lg border bg-card px-4 py-3 transition-colors animate-in fade-in slide-in-from-bottom-2 duration-300',
        active ? 'border-primary shadow-[0_0_16px] shadow-primary/15' : 'opacity-80 hover:opacity-100',
      )}
    >
      <button type="button" onClick={onSelect} className="w-full text-left">
        <div className="flex items-baseline justify-between gap-2">
          <h3 className="font-mono text-[11px] font-semibold tracking-widest">
            <span className="text-primary">{`${step.index}/${total}`}</span>
            <span className="text-muted-foreground">{` · ${t.steps[step.step].toLocaleUpperCase('tr-TR')}`}</span>
          </h3>
          <span className="font-mono text-[10px] text-muted-foreground">{formatMs(step.duration_ms)}</span>
        </div>
        <p className="mt-1.5 text-sm leading-relaxed">{narrative.headline}</p>
        {step.status === 'warning' && <p className="mt-1 text-xs text-amber-700">{t.narrative.warning}</p>}
        {narrative.facts.length > 0 && (
          <ul className="mt-1.5 space-y-0.5 font-mono text-xs text-muted-foreground">
            {narrative.facts.map((fact) => (
              <li key={fact}>{fact}</li>
            ))}
          </ul>
        )}
      </button>
      {active && (
        <button
          type="button"
          onClick={() => setRaw((r) => !r)}
          className="mt-2 flex items-center gap-1 font-mono text-[10px] text-muted-foreground hover:text-foreground"
        >
          <ChevronRight aria-hidden className={cn('size-3 transition-transform', raw && 'rotate-90')} />
          {t.common.raw}
        </button>
      )}
      {active && raw && (
        <pre className="mt-1 max-h-40 overflow-auto rounded bg-background p-2 font-mono text-[10px] text-muted-foreground">
          {step.summary}
          {step.warnings.map((w) => `
⚠ ${w}`).join('')}
          {Object.keys(step.data).length > 0 ? `\n${JSON.stringify(step.data, null, 2)}` : ''}
        </pre>
      )}
    </article>
  )
}
