import { useEffect, useRef } from 'react'
import type { Analysis } from '@/api/types'
import { t } from '@/i18n'
import { buildNarrative } from '@/lib/narrative'
import { StepCard } from './StepCard'

interface AgentTimelineProps {
  analysis: Analysis
  /** Number of revealed steps (0 = none yet). */
  revealed: number
  onSelect: (step: number) => void
}

/** Chat-like agent log: one message per revealed step. */
export function AgentTimeline({ analysis, revealed, onSelect }: AgentTimelineProps) {
  const activeRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    // Scroll only the timeline's own container, never the page (keeps the stage in view).
    const el = activeRef.current
    const box = el?.closest<HTMLElement>('[data-scroll-container]')
    if (!el || !box) return
    const top = el.offsetTop + el.offsetHeight - box.clientHeight + 16 // box is the offsetParent
    box.scrollTo({ top: Math.max(0, top), behavior: 'smooth' })
  }, [revealed])

  const steps = analysis.steps.slice(0, revealed)
  return (
    <section aria-label={t.analysis.timeline} className="flex flex-col gap-2.5">
      {steps.map((step) => (
        <div key={step.step} ref={step.index === revealed ? activeRef : undefined}>
          <StepCard
            step={step}
            total={analysis.steps.length}
            narrative={buildNarrative(analysis, step.step)}
            active={step.index === revealed}
            onSelect={() => onSelect(step.index)}
          />
        </div>
      ))}
    </section>
  )
}
