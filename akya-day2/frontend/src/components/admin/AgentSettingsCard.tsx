import type { AgentTuning, PromptName, TuningView } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { t } from '@/i18n'
import { AGENT_FIELDS, getAt } from '@/lib/tuningFields'
import type { FieldErrors } from './AdminEditor'
import { NumberField } from './NumberField'

interface Props {
  agent: PromptName
  draft: AgentTuning
  view: TuningView
  errors: FieldErrors
  onChange: (path: string, value: unknown) => void
  onInvalid: (key: string, invalid: boolean) => void
}

const EFFORTS = ['low', 'high', 'max'] as const

function Select({ label, value, env, options, onChange }: {
  label: string
  value: string | null
  env: string
  options: { value: string; label: string }[]
  onChange: (v: string | null) => void
}) {
  return (
    <label className="flex items-center justify-between gap-3 py-1.5 text-sm">
      {label}
      <select
        aria-label={label}
        className="h-8 rounded-md border bg-background px-2 text-sm"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      >
        <option value="">{t.admin.envOption(env)}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  )
}

/** Lookup limit and reasoning effort; empty = env. */
export function AgentSettingsCard({ agent, draft, view, errors, onChange, onInvalid }: Props) {
  const effortPath = `agents.${agent}_reasoning_effort`
  const envEffort = String(getAt(view.env_knobs, `${agent}_reasoning_effort`))
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{t.admin.agentSettings}</CardTitle></CardHeader>
      <CardContent className="divide-y">
        {AGENT_FIELDS[agent].map((field) => (
          <NumberField
            key={field.path}
            label={t.admin.fields[field.path] ?? field.path}
            unit={field.unit}
            nullable
            integer
            value={getAt(draft, field.path) as number | null}
            defaultValue={null}
            envValue={getAt(view.env_knobs, field.path.slice('agents.'.length)) as number}
            error={errors[field.path]}
            onChange={(v) => onChange(field.path, v === null ? null : Math.round(v))}
            onInvalid={(bad) => onInvalid(field.path, bad)}
          />
        ))}
        <Select
          label={t.admin.reasoningEffort}
          value={getAt(draft, effortPath) as string | null}
          env={envEffort}
          options={EFFORTS.map((e) => ({ value: e, label: e }))}
          onChange={(v) => onChange(effortPath, v)}
        />
      </CardContent>
    </Card>
  )
}
