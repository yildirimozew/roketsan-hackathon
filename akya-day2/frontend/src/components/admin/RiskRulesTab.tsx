import type { AgentTuning, TuningView } from '@/api/types'
import { SECTIONS } from '@/lib/tuningFields'
import type { FieldErrors } from './AdminEditor'
import { RuleSection } from './RuleSection'

interface Props {
  draft: AgentTuning
  view: TuningView
  errors: FieldErrors
  onChange: (path: string, value: unknown) => void
  onInvalid: (key: string, invalid: boolean) => void
}

/** The five threshold cards in pipeline order. */
export function RiskRulesTab(props: Props) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {SECTIONS.map((section) => (
        <RuleSection key={section.id} section={section} {...props} />
      ))}
    </div>
  )
}
