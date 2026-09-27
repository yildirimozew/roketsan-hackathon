import { Pause, Play } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useMasterClock } from '@/hooks/useMasterClock'
import { t } from '@/i18n'
import { hhmm } from '@/lib/fieldMap'
import { cn } from '@/lib/utils'

/** The master clock's controls in the sidebar: time, live state, play/pause, speed, back to live. */
export function SidebarClock({ open }: { open: boolean }) {
  const clock = useMasterClock()
  const c = t.clock
  const behind = Math.round(clock.behind)
  const playButton = (
    <Button
      size={open ? 'icon' : 'icon-sm'}
      variant="outline"
      onClick={clock.toggle}
      aria-label={clock.playing ? c.pause : c.play}
      title={clock.playing ? c.pause : c.play}
      className="shrink-0 border-emerald-500/50 text-emerald-700"
    >
      {clock.playing ? <Pause aria-hidden /> : <Play aria-hidden />}
    </Button>
  )
  if (!open) {
    return (
      <div className="flex flex-col items-center gap-1.5" title={c.title}>
        <LiveDot live={behind === 0} playing={clock.playing} />
        <span className="font-mono text-[11px] font-semibold">{hhmm(clock.minute)}</span>
        {playButton}
      </div>
    )
  }
  return (
    <section aria-label={c.title} className="flex flex-col gap-2 rounded-lg border bg-card px-3 py-2.5">
      <p className="flex items-center gap-1.5 text-[10px] font-semibold tracking-widest uppercase">
        <LiveDot live={behind === 0} playing={clock.playing} />
        <span className={behind === 0 ? 'text-red-600' : 'text-muted-foreground'}>
          {behind > 0 ? c.behind(behind) : clock.playing ? c.live : c.paused}
        </span>
      </p>
      <p className="font-mono text-3xl leading-none font-semibold tracking-wider" aria-live="off">
        {hhmm(clock.minute)}
      </p>
      <div className="flex items-center gap-2">
        {playButton}
        <Button
          size="sm"
          variant="secondary"
          onClick={clock.cycleSpeed}
          aria-label={`${c.speedLabel}: ${c.speed(clock.speed)}`}
          title={c.speedLabel}
          className={cn('w-12 font-mono', clock.speed > 1 && 'text-emerald-700')}
        >
          {c.speed(clock.speed)}
        </Button>
        {behind > 0 && (
          <Button size="sm" variant="outline" onClick={clock.goLive} className="ml-auto border-red-500/40 text-red-700">
            {c.goLive}
          </Button>
        )}
      </div>
    </section>
  )
}

function LiveDot({ live, playing }: { live: boolean; playing: boolean }) {
  return <span aria-hidden className={cn('size-2 rounded-full', live ? 'bg-red-600' : 'bg-muted-foreground/50', live && playing && 'animate-pulse')} />
}
