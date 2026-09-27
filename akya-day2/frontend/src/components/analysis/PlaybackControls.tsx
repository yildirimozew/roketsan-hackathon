import { ChevronLeft, ChevronRight, Pause, Play, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { t } from '@/i18n'

interface PlaybackControlsProps {
  step: number
  total: number
  playing: boolean
  onPrev: () => void
  onNext: () => void
  onToggle: () => void
  onRestart: () => void
}

export function PlaybackControls({ step, total, playing, onPrev, onNext, onToggle, onRestart }: PlaybackControlsProps) {
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="icon" onClick={onPrev} disabled={step === 0} aria-label={t.playback.prev}>
        <ChevronLeft />
      </Button>
      <Button onClick={onToggle} className="min-w-28">
        {playing ? <Pause aria-hidden /> : <Play aria-hidden />}
        {playing ? t.playback.pause : t.playback.play}
      </Button>
      <Button variant="outline" size="icon" onClick={onNext} disabled={step >= total} aria-label={t.playback.next}>
        <ChevronRight />
      </Button>
      <Button variant="ghost" onClick={onRestart}>
        <RotateCcw aria-hidden />
        {t.playback.restart}
      </Button>
    </div>
  )
}
