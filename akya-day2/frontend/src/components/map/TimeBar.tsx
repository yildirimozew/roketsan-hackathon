import { useMasterClock } from '@/hooks/useMasterClock'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { type ActivityBin, type TimeTick, TimeScrubber } from './TimeScrubber'

interface Props {
  ticks: TimeTick[]
  activity: ActivityBin[]
}

/** A page's slider on the master clock, like a live stream's: drag back to rewatch, never past
 *  the live edge; the live button jumps back. Play and speed live in the sidebar. */
export function TimeBar({ ticks, activity }: Props) {
  const clock = useMasterClock()
  const c = t.clock
  const behind = Math.round(clock.behind)
  return (
    <div className="flex items-center gap-3 rounded-lg border bg-card/85 px-3 pt-2.5 pb-1.5 backdrop-blur">
      <button
        type="button"
        onClick={clock.goLive}
        disabled={behind === 0}
        title={behind > 0 ? c.behind(behind) : c.live}
        className={cn(
          'flex shrink-0 items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold tracking-widest uppercase',
          behind === 0 ? 'border-red-500/40 text-red-600' : 'text-muted-foreground hover:border-red-500/40 hover:text-red-600',
        )}
      >
        <span aria-hidden className={cn('size-2 rounded-full', behind === 0 ? 'bg-red-600' : 'bg-muted-foreground/50', behind === 0 && clock.playing && 'animate-pulse')} />
        {c.goLive}
        {behind > 0 && <span className="font-mono tracking-normal normal-case">{c.behindShort(behind)}</span>}
      </button>
      <TimeScrubber start={clock.start} end={clock.end} minute={clock.minute} live={clock.live} ticks={ticks} activity={activity} onSeek={clock.seek} />
    </div>
  )
}
