import type { AgentTuning, PromptName, TuningView } from '@/api/types'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { t } from '@/i18n'
import type { FieldErrors } from './AdminEditor'
import { AgentSettingsCard } from './AgentSettingsCard'
import { PromptEditor } from './PromptEditor'
import { PromptPreview } from './PromptPreview'

interface Props {
  draft: AgentTuning
  view: TuningView
  errors: FieldErrors
  onChange: (path: string, value: unknown) => void
  onInvalid: (key: string, invalid: boolean) => void
}

const AGENTS: PromptName[] = ['watcher', 'supervisor']

/** Per agent: settings card, prompt editor and live preview. */
export function PromptsTab(props: Props) {
  const { draft, view, errors, onChange } = props
  return (
    <Tabs defaultValue="watcher">
      <TabsList>
        {AGENTS.map((a) => <TabsTrigger key={a} value={a}>{t.admin.agents[a]}</TabsTrigger>)}
      </TabsList>
      {AGENTS.map((agent) => {
        const text = draft.prompts[agent]
        return (
          <TabsContent key={agent} value={agent}
            forceMount
            className="grid gap-4 data-[state=inactive]:hidden xl:grid-cols-[20rem_1fr_1fr]"
          >
            <AgentSettingsCard agent={agent} {...props} />
            <PromptEditor
              text={text}
              fileText={view.prompt_defaults[agent]}
              variables={view.prompt_variables[agent]}
              error={errors[`prompts.${agent}`]}
              onChange={(v) => onChange(`prompts.${agent}`, v)}
            />
            <PromptPreview agent={agent} text={text ?? view.prompt_defaults[agent]} tuning={draft} />
          </TabsContent>
        )
      })}
    </Tabs>
  )
}
