import { useMemo, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router'
import type { ImageMeta, MapReport, MapTrack, Scene } from '@/api/types'
import { TimeBar } from '@/components/map/TimeBar'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ReportsTab } from '@/components/watch/ReportsTab'
import { SupervisorCard } from '@/components/watch/SupervisorCard'
import { TickBar } from '@/components/watch/TickBar'
import { VehiclePanel } from '@/components/watch/VehiclePanel'
import { WatcherCard } from '@/components/watch/WatcherCard'
import { NoRecording } from '@/components/watch/NoRecording'
import { OperatorChat } from '@/components/watch/OperatorChat'
import { WatchMap } from '@/components/watch/WatchMap'
import { useFieldMapData } from '@/hooks/useFieldMap'
import { useMasterClock } from '@/hooks/useMasterClock'
import { VehicleLinkContext } from '@/hooks/useVehicleLink'
import { useWatchDemo } from '@/hooks/useWatchDemo'
import { t } from '@/i18n'
import {
  type DemoModel,
  alertFocus,
  chatAt,
  expectedAt,
  SCHEDULE,
  finishedAgents,
  latestPerReport,
  levelsAt,
  reportJudgments,
  reportTexts,
  tickJudgments,
  playheadAt,
  progress,
  vehicleTypes,
  verdictHistory,
} from '@/lib/watchDemo'

/** Demo mode: replays recorded multi-agent watch runs on the master clock (no LLM calls); the
 *  recording that covers the clock's minute is shown (the longest if several do).
 *  Deep links: /watch?at=<HH:MM>&vehicle=<track_id>&tab=watchers|reports|chat. */
export function WatchPage() {
  const [params] = useSearchParams()
  const clock = useMasterClock()
  const demo = useWatchDemo(clock.minute)
  const field = useFieldMapData()
  const w = t.watch

  if (demo.isError || field.isError) return <Centered>{w.loadError}</Centered>
  if (demo.isEmpty) return <Centered>{w.empty}</Centered>
  if (demo.isPending || field.isPending || !field.scene || !field.images || !field.tracks || !field.reports) {
    return <Skeleton className="m-3 h-[calc(100%-1.5rem)]" />
  }
  const fieldData = { scene: field.scene, images: field.images, tracks: field.tracks, reports: field.reports }
  if (!demo.model?.ticks.length) return <NoRecording field={fieldData} windows={demo.windows} />
  return (
    <WatchPlayer
      key={demo.recordingId}
      model={demo.model}
      field={fieldData}
      initialVehicle={params.get('vehicle')}
      initialTab={(['watchers', 'reports', 'chat'] as const).find((tab) => tab === params.get('tab')) ?? 'supervisor'}
    />
  )
}

type FieldData = { scene: Scene; images: ImageMeta[]; tracks: MapTrack[]; reports: MapReport[] }

interface PlayerProps {
  model: DemoModel
  field: FieldData
  initialVehicle: string | null
  initialTab: 'supervisor' | 'watchers' | 'reports' | 'chat'
}

function WatchPlayer({ model, field, initialVehicle, initialTab }: PlayerProps) {
  const w = t.watch
  const clock = useMasterClock()
  const [selected, setSelected] = useState<string | null>(initialVehicle)
  // A scenario run's synthetic vehicles are drawn with the real tracks.
  const map = useMemo(() => ({ ...field, tracks: [...field.tracks, ...model.extraTracks] }), [field, model.extraTracks])
  const navigate = useNavigate()

  const head = playheadAt(model, clock.minute)
  const tick = model.ticks[head.index]
  if (!tick) return null
  const done = finishedAgents(model, head)
  const levels = levelsAt(model, head)
  const supProgress = progress(head.elapsed, SCHEDULE.supervisor)
  const complete = supProgress >= 1
  const threat = complete ? tick.supervisor?.decision.threat_level : model.ticks[head.index - 1]?.supervisor?.decision.threat_level
  const rows = model.rowsUpTo(head.index)
  const previous = model.ticks[head.index - 1]
  // Alerts already delivered: earlier ticks, plus this tick's once fully written; newest first.
  const alertDone = progress(head.elapsed, SCHEDULE.alert) >= 1
  // The previous tick's result (summary, alert, contradicted reports) stays up until this tick's
  // supervisor starts writing, so the operator has time to read an alert that just finished.
  const holding = head.elapsed < SCHEDULE.supervisor.start
  const shown = holding ? previous : tick
  const history = model.ticks
    .slice(0, holding ? Math.max(0, head.index - 1) : head.index)
    .flatMap((tv) => tv.alerts.map((e) => e.alert))
    .reverse()
  const alertLive = tick.alerts.length > 0 && head.elapsed >= SCHEDULE.alert.start && !alertDone
  const announced = expectedAt(model, clock.minute)
  const chat = chatAt(model, clock.minute)
  const chatLive = chat.some((c) => c.reply < 1)
  const judged = reportJudgments(model, head, done, complete)
  const texts = reportTexts(model, head.index)
  const contradicted = latestPerReport(shown ? tickJudgments(shown) : []).filter((j) => j.judgment.verdict === 'CONTRADICTED' || j.judgment.deception)
  const watchersLive = head.elapsed > 0 && !done.has(`watcher:${tick.watchers[tick.watchers.length - 1]?.watcher ?? ''}`)

  return (
    <VehicleLinkContext.Provider value={setSelected}>
      <div className="flex h-full flex-col gap-3 p-3">
        <div className="flex flex-wrap items-center justify-end gap-3">
          <TickBar ticks={model.ticks} current={head.index} complete={complete} threat={threat} onSeek={clock.seek} />
        </div>

        <div className="flex min-h-0 flex-1 gap-3">
          <div className="relative min-w-0 flex-1">
            <WatchMap
              {...map}
              minute={clock.minute}
              checks={tick.start.checks}
              levels={levels}
              focus={alertFocus(model, head)}
              types={vehicleTypes(model, head)}
              expected={new Set(announced.keys())}
              selectedId={selected}
              onSelect={setSelected}
              onOpenFrame={(id) => void navigate(`/analysis/${id}`, { state: { from: 'watch' } })}
            />
            <div className="pointer-events-none absolute top-3 left-3 rounded-md border bg-card/90 px-3 py-1.5 shadow-sm backdrop-blur">
              <p className="text-[11px] text-muted-foreground">{complete ? w.evaluated(tick.tick) : w.evaluating(tick.tick)}</p>
            </div>
            {selected && (
              <VehiclePanel
                trackId={selected}
                state={levels.get(selected)}
                row={rows.get(selected)}
                history={verdictHistory(model, selected, head.index, done)}
                announced={announced.get(selected)}
                onClose={() => setSelected(null)}
              />
            )}
          </div>

          <aside className="flex w-[27rem] shrink-0 flex-col rounded-lg border bg-sidebar p-2">
            <Tabs defaultValue={initialTab} className="flex min-h-0 flex-1 flex-col">
              <TabsList className="w-full">
                <TabsTrigger value="supervisor" className="gap-2">
                  {w.tabSupervisor}
                  {alertLive && <span className="size-2 animate-pulse rounded-full bg-red-600" aria-hidden />}
                </TabsTrigger>
                <TabsTrigger value="watchers" className="gap-2">
                  {w.tabWatchers(tick.watchers.length)}
                  {watchersLive && <span className="size-2 animate-pulse rounded-full bg-primary" aria-hidden />}
                </TabsTrigger>
                <TabsTrigger value="reports">{w.tabReports(judged.length)}</TabsTrigger>
                {model.chat.length > 0 && (
                  <TabsTrigger value="chat" className="gap-2">
                    {w.chat.tab}
                    {chatLive && <span className="size-2 animate-pulse rounded-full bg-sky-600" aria-hidden />}
                  </TabsTrigger>
                )}
              </TabsList>
              <TabsContent value="supervisor" className="min-h-0 overflow-y-auto pr-1">
                {head.elapsed === 0 && head.index === 0 ? (
                  <p className="rounded-lg border border-dashed bg-card p-4 text-sm text-muted-foreground">{w.start}</p>
                ) : (
                  <SupervisorCard
                    key={`sup-${tick.tick}`}
                    tick={head.elapsed >= SCHEDULE.supervisor.start ? tick.tick : (previous?.tick ?? tick.tick)}
                    decision={head.elapsed >= SCHEDULE.supervisor.start ? tick.supervisor : previous?.supervisor}
                    alerts={(shown?.alerts ?? []).map((e) => e.alert)}
                    history={history}
                    contradicted={contradicted}
                    texts={texts}
                    progress={head.elapsed >= SCHEDULE.supervisor.start ? supProgress : previous ? 1 : 0}
                    alertProgress={holding ? (previous ? 1 : 0) : progress(head.elapsed, SCHEDULE.alert)}
                  />
                )}
              </TabsContent>
              <TabsContent value="watchers" className="flex min-h-0 flex-col gap-3 overflow-y-auto pr-1">
                {head.elapsed === 0 && head.index === 0 && (
                  <p className="rounded-lg border border-dashed bg-card p-4 text-sm text-muted-foreground">{w.start}</p>
                )}
                {tick.watchers.map((report, i) =>
                  head.elapsed > 0 ? (
                    <WatcherCard
                      key={`${tick.tick}-${report.watcher}`}
                      report={report}
                      frames={head.elapsed >= SCHEDULE.frame ? tick.frames : []}
                      trace={tick.traces.get(`watcher:${report.watcher}`)}
                      progress={progress(head.elapsed, SCHEDULE.watcher(i))}
                    />
                  ) : null,
                )}
                <p className="text-[11px] text-muted-foreground">{w.hint}</p>
              </TabsContent>
              <TabsContent value="chat" className="min-h-0 overflow-y-auto pr-1">
                <OperatorChat items={chat} />
              </TabsContent>
              <TabsContent value="reports" className="min-h-0 overflow-y-auto pr-1">
                <ReportsTab judged={judged} texts={texts} />
              </TabsContent>
            </Tabs>
          </aside>
        </div>

        <TimeBar ticks={model.ticks.map((tv) => ({ minute: tv.minute, kind: 'frame' as const }))} activity={[]} />
      </div>
    </VehicleLinkContext.Provider>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return <div className="flex h-full items-center justify-center p-6 text-sm text-muted-foreground">{children}</div>
}
