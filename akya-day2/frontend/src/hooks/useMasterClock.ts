import { createContext, useContext } from 'react'

/** Playback multipliers, cycled by the speed button. */
export const CLOCK_SPEEDS = [1, 2, 4, 8, 16] as const
export type ClockSpeed = (typeof CLOCK_SPEEDS)[number]

/** The app's one simulated clock, played like a live stream: the live edge moves forward while
 *  playing; the viewer can go back (behind live) but never past the live edge. Minutes of day. */
export interface MasterClock {
  minute: number // what every page shows
  live: number // live edge: the latest minute "broadcast" so far
  start: number // first minute of the data day
  end: number // last minute of the data day
  playing: boolean
  speed: ClockSpeed
  behind: number // minutes behind live (0 = live)
  toggle: () => void
  seek: (minute: number) => void // clamped to [start, live]
  goLive: () => void
  cycleSpeed: () => void
}

export const MasterClockContext = createContext<MasterClock | null>(null)

/** The master clock (from `MasterClockProvider` in the app shell). */
export function useMasterClock(): MasterClock {
  const clock = useContext(MasterClockContext)
  if (!clock) throw new Error('useMasterClock needs MasterClockProvider')
  return clock
}
