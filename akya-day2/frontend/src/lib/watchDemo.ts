// Groups a recorded watch run's events by tick for the demo player. No domain logic: levels,
// reasons and alerts are exactly what the agents produced; this only indexes them.
import type { FieldReport, MapTrack, ReportJudgment, VehicleRow, WatchEvent, WatchEventOf, WatchLevel, WatchRecording } from '@/api/types'

export interface TickView {
  tick: string
  minute: number
  start: WatchEventOf<'tick_started'>
  frames: WatchEventOf<'frame_analyzed'>[]
  watchers: WatchEventOf<'watcher_report'>[]
  traces: Map<string, WatchEventOf<'agent_trace'>> // agent ("watcher:W1", "supervisor") -> trace
  supervisor: WatchEventOf<'supervisor_decision'> | undefined
  alerts: WatchEventOf<'operator_alert'>[]
  changes: WatchEventOf<'level_changed'>[]
  done: WatchEventOf<'tick_completed'> | undefined
}

export interface VehicleState {
  level: WatchLevel
  pending: boolean
  /** Simulated minute the vehicle became HIGH (its agent finished writing); set while HIGH. */
  highSince?: number
}

/** Simulated minute at which `by` ("watcher:W1" / "supervisor") finished writing in a tick. */
function finishMinute(tv: TickView, by: string): number {
  const i = tv.watchers.findIndex((w) => `watcher:${w.watcher}` === by)
  const span = i >= 0 ? SCHEDULE.watcher(i) : SCHEDULE.supervisor
  return tv.minute - TICK_MIN + span.start + span.dur
}

/** Applies one level change; keeps `highSince` while the vehicle stays HIGH. */
function applyChange(levels: Map<string, VehicleState>, tv: TickView, c: WatchEventOf<'level_changed'>) {
  const prev = levels.get(c.track_id)
  const highSince =
    c.to_level !== 'HIGH' ? undefined : prev?.level === 'HIGH' ? prev.highSince : finishMinute(tv, c.by)
  levels.set(c.track_id, { level: c.to_level, pending: c.pending, highSince })
}

/** One operator message to the supervisor and the supervisor's answer. */
export interface ChatEntry {
  time: string
  minute: number
  text: string
  reply: WatchEventOf<'operator_reply'> | undefined
}

export interface DemoModel {
  ticks: TickView[]
  /** The operator conversation (scenario runs only), in time order. */
  chat: ChatEntry[]
  /** Synthetic vehicles of a scenario run, drawn with the real tracks. */
  extraTracks: MapTrack[]
  /** Announced vehicles: registered, then matched to a track. */
  expected: WatchEventOf<'expected_vehicle'>[]
  /** Registry level of every vehicle after each tick (index = tick index). */
  levelsAfter: Map<string, VehicleState>[]
  /** Latest code-computed row per vehicle seen by a watcher up to each tick. */
  rowsUpTo: (index: number) => Map<string, VehicleRow>
}

export const toMinute = (hhmm: string): number => {
  const [h = 0, m = 0] = hhmm.split(':').map(Number)
  return h * 60 + m
}

export function buildDemoModel(events: WatchEvent[]): DemoModel {
  const ticks: TickView[] = []
  const chat: ChatEntry[] = []
  const expected: WatchEventOf<'expected_vehicle'>[] = []
  let extraTracks: MapTrack[] = []
  let cur: TickView | undefined
  for (const e of events) {
    if (e.type === 'scenario_loaded') extraTracks = e.extra_tracks
    else if (e.type === 'operator_message') chat.push({ time: e.time, minute: toMinute(e.time), text: e.text, reply: undefined })
    else if (e.type === 'operator_reply') {
      const entry = chat.find((c) => c.time === e.time && !c.reply)
      if (entry) entry.reply = e
    } else if (e.type === 'expected_vehicle') expected.push(e)
    if (e.type === 'tick_started') {
      cur = {
        tick: e.tick,
        minute: toMinute(e.tick),
        start: e,
        frames: [],
        watchers: [],
        traces: new Map(),
        supervisor: undefined,
        alerts: [],
        changes: [],
        done: undefined,
      }
      ticks.push(cur)
      continue
    }
    if (!cur) continue
    if (e.type === 'frame_analyzed') cur.frames.push(e)
    else if (e.type === 'watcher_report') cur.watchers.push(e)
    else if (e.type === 'agent_trace') cur.traces.set(e.agent, e)
    else if (e.type === 'supervisor_decision') cur.supervisor = e
    else if (e.type === 'operator_alert') cur.alerts.push(e)
    else if (e.type === 'level_changed') cur.changes.push(e)
    else if (e.type === 'tick_completed') cur.done = e
  }

  const levelsAfter: Map<string, VehicleState>[] = []
  let levels = new Map<string, VehicleState>()
  for (const tv of ticks) {
    levels = new Map(levels)
    for (const c of tv.changes) applyChange(levels, tv, c)
    levelsAfter.push(levels)
  }

  const rowsUpTo = (index: number) => {
    const rows = new Map<string, VehicleRow>()
    for (const tv of ticks.slice(0, index + 1)) {
      for (const w of tv.watchers) for (const r of w.rows) rows.set(r.track_id, r)
    }
    return rows
  }

  return { ticks, chat, extraTracks, expected, levelsAfter, rowsUpTo }
}

/** One agent's judgment of a field report, with the report and who judged it when. */
export interface JudgedReport {
  report: FieldReport
  judgment: ReportJudgment
  by: string // "W1" or "supervisor"
  tick: string
}

/** Report judgments of one tick: watchers (those in `done` on a live tick), then the supervisor
 *  once `supervisorDone`. Older recordings have none. */
export function tickJudgments(tv: TickView, done?: Set<string>, supervisorDone = true): JudgedReport[] {
  const out: JudgedReport[] = []
  for (const w of tv.watchers) {
    if (done && !done.has(`watcher:${w.watcher}`)) continue
    const texts = new Map((w.reports ?? []).map((r) => [r.report_id, r]))
    for (const j of w.report.report_checks ?? []) {
      const report = texts.get(j.report_id)
      if (report) out.push({ report, judgment: j, by: w.watcher, tick: tv.tick })
    }
  }
  const sup = tv.supervisor
  if (sup && supervisorDone) {
    const texts = new Map((sup.reports ?? []).map((r) => [r.report_id, r]))
    for (const j of sup.decision.report_checks ?? []) {
      const report = texts.get(j.report_id)
      if (report) out.push({ report, judgment: j, by: 'supervisor', tick: tv.tick })
    }
  }
  return out
}

/** One entry per report: the last judgment wins (the supervisor comes after the watchers) and
 *  `by` names every agent that judged it, e.g. "W1 → supervisor". */
export function latestPerReport(items: JudgedReport[]): JudgedReport[] {
  const out = new Map<string, JudgedReport>()
  for (const j of items) {
    const prev = out.get(j.report.report_id)
    out.set(j.report.report_id, prev && prev.by !== j.by ? { ...j, by: `${prev.by} → ${j.by}` } : j)
  }
  return [...out.values()]
}

/** The latest judgment of every report up to the playhead, newest report first. */
export function reportJudgments(model: DemoModel, head: Playhead, done: Set<string>, supervisorDone: boolean): JudgedReport[] {
  const latest = new Map<string, JudgedReport>()
  model.ticks.slice(0, head.index + 1).forEach((tv, i) => {
    const live = i === head.index
    for (const j of latestPerReport(tickJudgments(tv, live ? done : undefined, !live || supervisorDone))) latest.set(j.report.report_id, j)
  })
  return [...latest.values()].sort((a, b) => b.report.time_min - a.report.time_min || b.report.report_id.localeCompare(a.report.report_id))
}

/** Display name of the agents in `JudgedReport.by`. */
export const judgeLabel = (by: string, supervisor: string): string =>
  by
    .split(' → ')
    .map((name) => (name === 'supervisor' ? supervisor : name))
    .join(' → ')

/** Every report text the recording carries up to a tick (judged reports and their conflicts). */
export function reportTexts(model: DemoModel, index: number): Map<string, FieldReport> {
  const out = new Map<string, FieldReport>()
  for (const tv of model.ticks.slice(0, index + 1)) {
    for (const w of tv.watchers) for (const r of w.reports ?? []) out.set(r.report_id, r)
    for (const r of tv.supervisor?.reports ?? []) out.set(r.report_id, r)
  }
  return out
}

/** Every watcher verdict about one vehicle up to a tick, oldest first; on the last tick only
 *  verdicts of agents in `done` (those that finished writing). */
export function verdictHistory(model: DemoModel, trackId: string, index: number, done?: Set<string>) {
  return model.ticks.slice(0, index + 1).flatMap((tv, i) =>
    tv.watchers
      .filter((w) => i < index || !done || done.has(`watcher:${w.watcher}`))
      .flatMap((w) =>
        w.report.vehicles
          .filter((v) => v.track_id === trackId)
          .map((v) => ({
            tick: tv.tick,
            watcher: w.watcher,
            sector: w.sectors[0] ?? '',
            verdict: v,
            reports: tickJudgments(tv).filter((j) => j.by === w.watcher && j.judgment.track_ids.includes(trackId)),
          })),
      ),
  )
}

// ---- playback: each tick's outputs stream in during the 5 simulated minutes before the tick ----

export const TICK_MIN = 5

/** When each agent "types" inside a tick window, in simulated minutes from the window start.
 *  Watchers overlap (they run in parallel), then the supervisor, then its alert. */
export const SCHEDULE = {
  frame: 0.1,
  watcher: (i: number) => ({ start: 0.3 + i * 0.5, dur: 2.2 }),
  supervisor: { start: 3.0, dur: 1.6 },
  alert: { start: 3.6, dur: 1.3 },
} as const

export const progress = (elapsed: number, span: { start: number; dur: number }): number =>
  Math.max(0, Math.min(1, (elapsed - span.start) / span.dur))

export interface Playhead {
  index: number // tick being worked on (its outputs stream until the clock reaches it)
  elapsed: number // simulated minutes into its window, 0..5
}

/** The tick whose window (tick − 5, tick] contains `minute`. */
export function playheadAt(model: DemoModel, minute: number): Playhead {
  const i = model.ticks.findIndex((tv) => minute <= tv.minute)
  const index = i === -1 ? model.ticks.length - 1 : i
  const tick = model.ticks[index]
  const elapsed = tick ? Math.max(0, Math.min(TICK_MIN, minute - (tick.minute - TICK_MIN))) : TICK_MIN
  return { index, elapsed }
}

/** Agents of the current tick that have finished writing ("watcher:W1", "supervisor"). */
export function finishedAgents(model: DemoModel, head: Playhead): Set<string> {
  const tick = model.ticks[head.index]
  const done = new Set<string>()
  if (!tick) return done
  tick.watchers.forEach((w, i) => {
    if (progress(head.elapsed, SCHEDULE.watcher(i)) >= 1) done.add(`watcher:${w.watcher}`)
  })
  if (progress(head.elapsed, SCHEDULE.supervisor) >= 1) done.add('supervisor')
  return done
}

/** Vehicle levels at the playhead: previous tick's registry plus changes by finished agents. */
export function levelsAt(model: DemoModel, head: Playhead): Map<string, VehicleState> {
  const levels = new Map(head.index > 0 ? model.levelsAfter[head.index - 1] : undefined)
  const done = finishedAgents(model, head)
  const tick = model.ticks[head.index]
  for (const c of tick?.changes ?? []) {
    if (tick && done.has(c.by)) applyChange(levels, tick, c)
  }
  return levels
}

// ---- text helpers ----

/** First sentence of `text`, cut at a word boundary to at most `max` characters. */
export function concise(text: string, max: number): string {
  const first = text.split(/(?<=[.!?;])\s+/)[0] ?? text
  if (first.length <= max) return first
  const cut = first.slice(0, max)
  return `${cut.slice(0, Math.max(cut.lastIndexOf(' '), max * 0.6)).replace(/[\s,;:(–-]+$/, '')}…`
}

/** Splits text into plain parts and vehicle ids (T0xxx) so ids can be rendered as links. */
export function splitVehicleIds(text: string): { text: string; id?: string }[] {
  return text.split(/(\bT\d{4}\b)/).filter(Boolean).map((part) => (/^T\d{4}$/.test(part) ? { text: part, id: part } : { text: part }))
}

/** Vehicles in the latest operator alert at the playhead → simulated minute it was written. */
export function alertFocus(model: DemoModel, head: Playhead): Map<string, number> {
  for (let i = head.index; i >= 0; i--) {
    const tv = model.ticks[i]
    if (!tv || tv.alerts.length === 0) continue
    if (i === head.index && head.elapsed < SCHEDULE.alert.start) continue
    const at = tv.minute - TICK_MIN + SCHEDULE.alert.start
    return new Map(tv.alerts.flatMap((e) => e.alert.track_ids.map((id) => [id, at] as const)))
  }
  return new Map()
}

/** Vehicle types known at the playhead: from drone-frame detections matched to a track, once
 *  the frame has been analysed (a type stays known afterwards). */
export function vehicleTypes(model: DemoModel, head: Playhead): Map<string, string> {
  const types = new Map<string, string>()
  model.ticks.slice(0, head.index + 1).forEach((tv, i) => {
    if (i === head.index && head.elapsed < SCHEDULE.frame) return
    for (const f of tv.frames) for (const d of f.detections) if (d.track_id) types.set(d.track_id, d.label)
  })
  return types
}

// ---- which recording plays at a master-clock minute ----

/** The recording whose ticks cover `minute` (its first window starts 5 minutes before its first
 *  tick); the longest if several do, null if none. */
export function recordingAt(list: WatchRecording[], minute: number): string | null {
  let best: WatchRecording | null = null
  for (const r of list) {
    const first = r.ticks[0]
    const last = r.ticks[r.ticks.length - 1]
    if (!first || !last || minute < toMinute(first) - TICK_MIN || minute > toMinute(last)) continue
    if (!best || r.ticks.length > best.ticks.length) best = r
  }
  return best?.recording_id ?? null
}

/** "10:05-11:10": the clock span a recording covers. */
export function recordingWindow(r: WatchRecording): string {
  const first = r.ticks[0] ?? '00:00'
  const start = toMinute(first) - TICK_MIN
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(Math.floor(start / 60))}:${pad(start % 60)}-${r.ticks[r.ticks.length - 1] ?? first}`
}

// ---- the operator conversation (scenario runs) ----

/** The supervisor's reply types out over this many simulated minutes, starting this long after
 *  the operator's message. */
export const CHAT_REPLY = { delay: 0.25, dur: 1.2 } as const

/** Messages the operator has written by `minute`, each with how much of the reply is shown. */
export function chatAt(model: DemoModel, minute: number): { entry: ChatEntry; reply: number }[] {
  return model.chat
    .filter((c) => c.minute <= minute)
    .map((entry) => ({ entry, reply: progress(minute - entry.minute, { start: CHAT_REPLY.delay, dur: CHAT_REPLY.dur }) }))
}

/** Announced vehicles already matched to a track by `minute` (from their tick's window start). */
export function expectedAt(model: DemoModel, minute: number): Map<string, WatchEventOf<'expected_vehicle'>['vehicle']> {
  const out = new Map<string, WatchEventOf<'expected_vehicle'>['vehicle']>()
  for (const e of model.expected) {
    const id = e.vehicle.track_id
    if (id && toMinute(e.tick) - TICK_MIN <= minute) out.set(id, e.vehicle)
  }
  return out
}
