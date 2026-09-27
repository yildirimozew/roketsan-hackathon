// Presentation metadata for the admin tuning form: which fields, in which order, with which unit.
// Values, defaults and validation come from the API; nothing here decides a risk level.
import type { AgentTuning, PromptName } from '@/api/types'

export type Unit = 'm' | 'ms' | 'deg' | 'min' | 'pts' | 'count' | 'mpm'
export type SectionId = 'behavior' | 'groups' | 'ceiling'
export interface FieldDef {
  path: string
  unit: Unit
  nullable?: boolean
  integer?: boolean
}
export interface SectionDef {
  id: SectionId
  fields: FieldDef[]
}

// Points and counts are integers in the backend model; everything else is a float.
const f = (path: string, unit: Unit, nullable = false): FieldDef => ({
  path,
  unit,
  nullable,
  integer: unit === 'pts' || unit === 'count',
})

// Only the thresholds that decide whether a vehicle is marked risky; every other tuning field
// keeps its backend default (see services/tuning.DEFAULT_TUNING).
export const SECTIONS: SectionDef[] = [
  {
    id: 'behavior',
    fields: [
      f('behavior.loop_sweep_deg', 'deg'),
      f('behavior.orbit_max_range_m', 'm'),
      f('behavior.probe_range_m', 'm'),
      f('behavior.probe_out_m', 'm'),
      f('behavior.stakeout_near_m', 'm'),
      f('behavior.stakeout_min', 'min'),
    ],
  },
  {
    id: 'groups',
    fields: [f('groups.large_group', 'count'), f('groups.group_radius_m', 'm')],
  },
  {
    id: 'ceiling',
    fields: [
      f('ceiling.at_base_m', 'm'),
      f('ceiling.arrived_from_m', 'm'),
      f('ceiling.pattern_high_m', 'm'),
      f('ceiling.approach_high_m', 'm'),
    ],
  },
]

export const AGENT_FIELDS: Record<PromptName, FieldDef[]> = {
  watcher: [f('agents.watcher_max_tool_calls', 'count', true)],
  supervisor: [f('agents.supervisor_max_tool_calls', 'count', true)],
}

export function getAt(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>(
    (node, key) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[key] : undefined),
    obj,
  )
}

export function setAt<T>(obj: T, path: string, value: unknown): T {
  const [head, ...rest] = path.split('.')
  const node = (obj ?? {}) as Record<string, unknown>
  if (head === undefined) return obj
  return { ...node, [head]: rest.length ? setAt(node[head], rest.join('.'), value) : value } as T
}

const LEAF_PATHS: string[] = [
  ...SECTIONS.flatMap((s) => s.fields.map((x) => x.path)),
  ...Object.values(AGENT_FIELDS).flatMap((fs) => fs.map((x) => x.path)),
  'agents.watcher_reasoning_effort',
  'agents.supervisor_reasoning_effort',
  'prompts.watcher',
  'prompts.supervisor',
]

/** Leaf paths whose values differ between two tunings. */
export function changedPaths(a: AgentTuning, b: AgentTuning): string[] {
  return LEAF_PATHS.filter((p) => JSON.stringify(getAt(a, p)) !== JSON.stringify(getAt(b, p)))
}

/** "path: code arg; path: code" (backend tuning_problems) -> { path: { code, arg } }. */
export function parseProblems(detail: string): Record<string, { code: string; arg: string }> {
  const out: Record<string, { code: string; arg: string }> = {}
  for (const part of detail.split('; ')) {
    const [path, rest = ''] = part.split(': ')
    if (!path) continue
    const [code = '', ...args] = rest.split(' ')
    out[path] = { code, arg: args.join(' ') }
  }
  return out
}
