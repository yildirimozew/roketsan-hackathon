import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useFieldMapData } from '@/hooks/useFieldMap'
import { CLOCK_SPEEDS, type ClockSpeed, type MasterClock, MasterClockContext } from '@/hooks/useMasterClock'
import { dayBounds } from '@/lib/situation'

/** The stream opens just before the first recorded agent tick (10:10), so the watch demo and the
 *  map show activity at once; earlier data is reachable by going back. */
const LIVE_START_MIN = 10 * 60 + 5
/** Simulated minutes per real second at 1x: one 5-minute tick per 20 s keeps agent text readable. */
const BASE_MIN_PER_SEC = 0.25
const FALLBACK_BOUNDS = { start: 8 * 60, end: 16 * 60 } // until the data has loaded

/** Minute from a `?at=HH:MM` deep link, read once when the app opens. */
function linkedMinute(): number | null {
  const m = new URLSearchParams(window.location.search).get('at')?.match(/^(\d{1,2}):(\d{2})$/)
  return m ? Number(m[1]) * 60 + Number(m[2]) : null
}

/** Owns the master clock for every page. Space plays/pauses, arrow keys step 5 minutes. */
export function MasterClockProvider({ children }: { children: ReactNode }) {
  const { tracks, reports } = useFieldMapData()
  const bounds = useMemo(() => {
    const b = tracks && reports ? dayBounds(tracks, reports) : null
    return b && b.end > b.start ? b : FALLBACK_BOUNDS
  }, [tracks, reports])
  const [initial] = useState(() => linkedMinute() ?? LIVE_START_MIN)
  const [minute, setMinute] = useState(initial)
  const [live, setLive] = useState(initial)
  const [playing, setPlaying] = useState(true)
  const [speed, setSpeed] = useState<ClockSpeed>(1)
  const ref = useRef({ minute: initial, live: initial })

  const set = useCallback((next: { minute: number; live: number }) => {
    ref.current = next
    setMinute(next.minute)
    setLive(next.live)
  }, [])

  const seek = useCallback(
    (m: number) => set({ minute: Math.max(bounds.start, Math.min(ref.current.live, m)), live: ref.current.live }),
    [bounds.start, set],
  )
  const goLive = useCallback(() => seek(ref.current.live), [seek])
  const toggle = useCallback(() => setPlaying((p) => !p), [])
  const cycleSpeed = useCallback(() => setSpeed((s) => CLOCK_SPEEDS[(CLOCK_SPEEDS.indexOf(s) + 1) % CLOCK_SPEEDS.length] ?? 1), [])

  useEffect(() => {
    if (!playing) return
    let last = performance.now()
    let id = requestAnimationFrame(function tick(now) {
      const step = ((now - last) / 1000) * BASE_MIN_PER_SEC * speed
      last = now
      const nextLive = Math.min(bounds.end, ref.current.live + step)
      set({ minute: Math.min(nextLive, ref.current.minute + step), live: nextLive })
      if (ref.current.minute >= bounds.end) setPlaying(false)
      else id = requestAnimationFrame(tick)
    })
    return () => cancelAnimationFrame(id)
  }, [playing, speed, bounds.end, set])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target
      if (el instanceof HTMLInputElement || el instanceof HTMLSelectElement || el instanceof HTMLTextAreaElement) return
      if (e.key === ' ') {
        e.preventDefault()
        toggle()
      } else if (e.key === 'ArrowRight') seek(Math.floor(ref.current.minute / 5) * 5 + 5)
      else if (e.key === 'ArrowLeft') seek(Math.ceil(ref.current.minute / 5) * 5 - 5)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [toggle, seek])

  const value: MasterClock = {
    minute,
    live,
    start: bounds.start,
    end: bounds.end,
    playing,
    speed,
    behind: Math.max(0, live - minute),
    toggle,
    seek,
    goLive,
    cycleSpeed,
  }
  return <MasterClockContext value={value}>{children}</MasterClockContext>
}
