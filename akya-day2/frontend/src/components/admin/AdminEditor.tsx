import type { UseMutationResult } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '@/api/client'
import type { AgentTuning, TuningView } from '@/api/types'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { t } from '@/i18n'
import { changedPaths, parseProblems, setAt } from '@/lib/tuningFields'
import { AdminToolbar } from './AdminToolbar'
import { PromptsTab } from './PromptsTab'
import { RiskRulesTab } from './RiskRulesTab'

export type FieldErrors = Record<string, { code: string; arg: string }>

const KNOWN_PATH = /^(behavior|groups|rubric|ceiling|judgment|agents|prompts)\./

interface Props {
  view: TuningView
  save: UseMutationResult<TuningView, Error, AgentTuning>
  reset: UseMutationResult<TuningView, Error, void>
}

/** Holds the unsaved draft; remounted (key = view.hash) after every save or reset. */
export function AdminEditor({ view, save, reset }: Props) {
  const [draft, setDraft] = useState<AgentTuning>(view.current)
  const [invalid, setInvalid] = useState<Set<string>>(new Set())
  // Bumped on revert so every field drops its locally typed (possibly invalid) text.
  const [revision, setRevision] = useState(0)
  const onChange = (path: string, value: unknown) => setDraft((d) => setAt(d, path, value))
  const onInvalid = (key: string, bad: boolean) =>
    setInvalid((s) => {
      if (s.has(key) === bad) return s
      const next = new Set(s)
      if (bad) next.add(key)
      else next.delete(key)
      return next
    })

  const err = save.error ?? reset.error
  const errors: FieldErrors =
    err instanceof ApiError && err.status === 422 ? parseProblems(err.detail) : {}
  // A 422 we cannot map to a field (e.g. FastAPI's own type errors) still needs a visible message.
  const mapped = Object.keys(errors).some((p) => KNOWN_PATH.test(p))
  const banner = err && !mapped ? t.admin.saveFailed : undefined
  const tabProps = { draft, view, errors, onChange, onInvalid }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <AdminToolbar
        unsaved={changedPaths(draft, view.current).length}
        overridden={view.overridden.length}
        invalid={invalid.size > 0}
        saving={save.isPending || reset.isPending}
        error={banner}
        onSave={() => save.mutate(draft)}
        onRevert={() => {
          setInvalid(new Set())
          setDraft(view.current)
          setRevision((r) => r + 1)
        }}
        onResetAll={() => reset.mutate()}
      />
      {view.load_warning && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t.admin.loadWarning(view.load_warning)}
        </p>
      )}
      <Tabs key={revision} defaultValue="rules">
        <TabsList>
          <TabsTrigger value="rules">{t.admin.tabs.rules}</TabsTrigger>
          <TabsTrigger value="prompts">{t.admin.tabs.prompts}</TabsTrigger>
        </TabsList>
        <TabsContent value="rules" forceMount className="data-[state=inactive]:hidden">
          <RiskRulesTab {...tabProps} />
        </TabsContent>
        <TabsContent value="prompts" forceMount className="data-[state=inactive]:hidden">
          <PromptsTab {...tabProps} />
        </TabsContent>
      </Tabs>
    </div>
  )
}
