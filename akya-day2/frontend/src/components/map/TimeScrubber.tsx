import { useEffect, useRef, useState } from 'react'
import { t } from '@/i18n'
import { hhmm } from '@/lib/fieldMap'
import { cn } from '@/lib/utils'

export interface TimeTick {
  minute: number
  kind: 'frame' | 'official' | 'third_party'
}

export interface ActivityBin {
  minute: number
  count: number
}

interface Props {
  start: number
  end: number
  minute: number
  /** Live edge: the part after it is not broadcast yet (dimmed; seeking stops there). */
  live?: number
  ticks: TimeTick[]
  activity: ActivityBin[]
  onSeek: (minute: number) => void
}

/** Minimum pixels per hour label; narrower axes label every 2nd/3rd hour. */
const LABEL_PX = 36

const DOT: Record<Exclude<TimeTick['kind'], 'frame'>, string> = {
  official: 'bg-sky-400',
  third_party: 'bg-amber-400',
}

/** Scrubber with labelled lanes: active-track curve, frames, reports and an hour axis. */
export function TimeScrubber({ start, end, minute, live = end, ticks, activity, onSeek }: Props) {
  const lanes = t.fieldMap.lanes
  const ref = useRef<HTMLDivElement>(null)
  const [hover, setHover] = useState<number | null>(null)
  const [width, setWidth] = useState(0)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const ro = new ResizeObserver(([entry]) => setWidth(entry?.contentRect.width ?? 0))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])
  const span = end - start || 1
  const frac = (m: number) => (m - start) / span
  const pct = (m: number) => `${frac(m) * 100}%`
  const hours: number[] = []
  for (let h = Math.ceil(start / 60) * 60; h <= end; h += 60) hours.push(h)
  const labelEvery = width > 0 ? Math.max(1, Math.ceil(LABEL_PX / ((width * 60) / span))) : 1

  // Activity curve in a 1000×100 box, stretched to the lane.
  const peak = Math.max(1, ...activity.map((b) => b.count))
  const line = activity.map((b) => `${(frac(b.minute) * 1000).toFixed(1)},${(100 - (b.count / peak) * 92).toFixed(1)}`)
  const area = line.length ? `M0,100 L${line.join(' L')} L1000,100 Z` : ''

  const minuteAt = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect()
    if (!r) return start
    return start + Math.max(0, Math.min(1, (clientX - r.left) / r.width)) * span
  }

  return (
    <div className="flex min-w-0 flex-1 gap-2">
      <div aria-hidden className="flex shrink-0 flex-col justify-between py-px text-right font-mono text-[9px] leading-none text-muted-foreground/70">
        <span className="flex h-5 items-center justify-end">{lanes.tracks}</span>
        <span className="flex h-2.5 items-center justify-end">{lanes.frames}</span>
        <span className="flex h-2.5 items-center justify-end">{lanes.reports}</span>
        <span className="h-3" />
      </div>
      <div
        ref={ref}
        role="slider"
        tabIndex={0}
        aria-label={t.fieldMap.timeline}
        aria-valuemin={start}
        aria-valuemax={end}
        aria-valuenow={Math.floor(minute)}
        aria-valuetext={hhmm(minute)}
        className="relative min-w-0 flex-1 cursor-pointer touch-none select-none"
        onPointerDown={(e) => {
          e.currentTarget.setPointerCapture(e.pointerId)
          onSeek(minuteAt(e.clientX))
        }}
        onPointerMove={(e) => {
          setHover(minuteAt(e.clientX))
          if (e.currentTarget.hasPointerCapture(e.pointerId)) onSeek(minuteAt(e.clientX))
        }}
        onPointerLeave={() => setHover(null)}
      >
        <div className="flex flex-col gap-px">
          {/* Lane 1: active tracks over the day; the played part is brighter. */}
          <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="h-5 w-full">
            <defs>
              <clipPath id="timebar-played">
                <rect x={0} y={0} width={frac(minute) * 1000} height={100} />
              </clipPath>
            </defs>
            <path d={area} className="fill-emerald-400/15" />
            <path d={area} className="fill-emerald-400/45" clipPath="url(#timebar-played)" />
          </svg>
          {/* Lane 2: frames, same square as on the map. */}
          <div className="relative h-2.5">
            {ticks.map((tk, i) =>
              tk.kind === 'frame' ? (
                <span
                  key={i}
                  className={cn(
                    'absolute top-1/2 size-1.5 -translate-1/2 border border-sky-500 bg-sky-500/50',
                    tk.minute > minute && 'opacity-35',
                  )}
                  style={{ left: pct(tk.minute) }}
                />
              ) : null,
            )}
          </div>
          {/* Lane 3: reports by source. */}
          <div className="relative h-2.5">
            {ticks.map((tk, i) =>
              tk.kind === 'frame' ? null : (
                <span
                  key={i}
                  className={cn('absolute top-1/2 size-1.5 -translate-1/2 rounded-full', DOT[tk.kind], tk.minute > minute && 'opacity-35')}
                  style={{ left: pct(tk.minute) }}
                />
              ),
            )}
          </div>
          {/* Hour axis. */}
          <div className="relative h-3 border-t border-border/70">
            {hours.map((h, i) => (
              <span key={h} className="absolute top-0 flex -translate-x-1/2 flex-col items-center" style={{ left: pct(h) }}>
                <span className="h-1 w-px bg-border" />
                {i % labelEvery === 0 && <span className="font-mono text-[9px] leading-none text-muted-foreground">{hhmm(h)}</span>}
              </span>
            ))}
          </div>
        </div>
        {hover !== null && (
          <>
            <span className="pointer-events-none absolute top-0 bottom-3 w-px bg-foreground/25" style={{ left: pct(hover) }} />
            <span
              className="pointer-events-none absolute -top-5 -translate-x-1/2 rounded border bg-popover px-1 font-mono text-[10px] text-foreground"
              style={{ left: pct(hover) }}
            >
              {hhmm(hover)}
            </span>
          </>
        )}
        {/* Not broadcast yet: after the live edge. */}
        {live < end && (
          <span
            className="pointer-events-none absolute top-0 right-0 bottom-3 bg-[repeating-linear-gradient(135deg,transparent_0_4px,var(--color-border)_4px_5px)] opacity-80"
            style={{ left: pct(live) }}
            title={t.clock.notYet}
          />
        )}
        {/* Playhead through all lanes. */}
        <span className="pointer-events-none absolute top-0 bottom-3 w-0.5 -translate-x-1/2 rounded bg-emerald-300 shadow-[0_0_8px] shadow-emerald-400/60" style={{ left: pct(minute) }} />
        <span
          className="pointer-events-none absolute bottom-2 size-2.5 -translate-x-1/2 translate-y-1/2 rounded-full border-2 border-emerald-500 bg-emerald-400"
          style={{ left: pct(minute) }}
        />
      </div>
    </div>
  )
}
