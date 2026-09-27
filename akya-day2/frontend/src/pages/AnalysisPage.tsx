import { ArrowLeft } from 'lucide-react'
import { useLocation, useNavigate, useParams } from 'react-router'
import { AgentTimeline } from '@/components/analysis/AgentTimeline'
import { BriefCard } from '@/components/analysis/BriefCard'
import { PlaybackControls } from '@/components/analysis/PlaybackControls'
import { RiskBadge } from '@/components/analysis/RiskBadge'
import { VehicleTable } from '@/components/analysis/VehicleTable'
import { SceneStage } from '@/components/scene/SceneStage'
import { StepScene } from '@/components/scene/StepScene'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { useAnalysis } from '@/hooks/useAnalysis'
import { usePlayback } from '@/hooks/usePlayback'
import { t } from '@/i18n'
import { SelectionProvider } from '@/lib/selection'
import { placeName } from '@/lib/format'

export function AnalysisPage() {
  const { imageId = '' } = useParams()
  const navigate = useNavigate()
  // Opened only from an overview card or a map frame card; go back to whichever one it was.
  const from: 'overview' | 'watch' = (useLocation().state as { from?: string } | null)?.from === 'watch' ? 'watch' : 'overview'
  const goBack = () => {
    const idx = (window.history.state as { idx?: number } | null)?.idx ?? 0
    if (idx > 0) void navigate(-1)
    else void navigate(from === 'watch' ? '/watch' : '/overview')
  }
  const { data: analysis, isPending, isError } = useAnalysis(imageId)
  const pb = usePlayback(analysis?.steps.length ?? 8, imageId)

  if (isPending) {
    return (
      <div className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <Skeleton className="aspect-video" />
        <Skeleton className="h-96" />
      </div>
    )
  }
  if (isError || !analysis.image) {
    return <p className="grid h-60 place-items-center text-sm text-muted-foreground">{t.analysis.notFound}</p>
  }

  const { image, brief } = analysis
  const current = pb.step === 0 ? null : (analysis.steps[pb.step - 1]?.step ?? null)
  const status = pb.step === 0 ? t.playback.ready : pb.done ? t.playback.done : t.playback.step(pb.step, pb.total)

  return (
    <SelectionProvider>
      <div className="mx-auto flex max-w-[1800px] flex-col gap-5 p-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap items-center gap-4">
            <Button size="sm" variant="ghost" onClick={goBack} className="text-muted-foreground">
              <ArrowLeft />
              {t.analysis.back[from]}
            </Button>
            <h1 className="font-mono text-sm font-semibold">{image.image_id}</h1>
            <span className="text-sm text-muted-foreground">
              {t.analysis.zone}: <span className="text-foreground">{image.zone ? placeName(image.zone) : '—'}</span>
            </span>
            <span className="text-sm text-muted-foreground">
              {t.analysis.captured}: <span className="font-mono text-foreground">{image.capture_time}</span>
            </span>
            {pb.done && brief && <RiskBadge level={brief.level} size="lg" />}
          </div>
          <PlaybackControls step={pb.step} total={pb.total} playing={pb.playing} onPrev={pb.prev} onNext={pb.next} onToggle={pb.toggle} onRestart={pb.reset} />
        </header>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
          <div className="flex flex-col gap-2 lg:sticky lg:top-4">
            <SceneStage title={`${image.image_id} · ${image.zone ? placeName(image.zone) : ''}`} status={status}>
              <StepScene key={current ?? 'idle'} analysis={analysis} step={current} />
            </SceneStage>
            <p className="text-xs text-muted-foreground">{t.playback.hint}</p>
          </div>
          <div data-scroll-container className="relative max-h-[calc(100vh-11rem)] overflow-y-auto pr-1">
            <AgentTimeline analysis={analysis} revealed={pb.step} onSelect={pb.goTo} />
          </div>
        </div>

        {pb.done && brief && (
          <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
            <BriefCard brief={brief} />
            <Card>
              <CardContent>
                <VehicleTable detections={analysis.detections} matches={analysis.matches} risks={analysis.risks} />
              </CardContent>
            </Card>
          </div>
        )}
      </div>
    </SelectionProvider>
  )
}
