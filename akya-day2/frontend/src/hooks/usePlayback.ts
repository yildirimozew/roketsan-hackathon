import { useCallback, useEffect, useState } from 'react'

const STEP_MS = 1800

/** Step player: 0 = idle, 1..total = pipeline steps. Arrow keys and space control it. */
export function usePlayback(total: number, resetKey: string) {
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [lastKey, setLastKey] = useState(resetKey)

  if (lastKey !== resetKey) {
    setLastKey(resetKey)
    setStep(0)
    setPlaying(false)
  }

  const goTo = useCallback((n: number) => setStep(Math.max(0, Math.min(total, n))), [total])
  const next = useCallback(() => setStep((s) => Math.min(total, s + 1)), [total])
  const prev = useCallback(() => setStep((s) => Math.max(0, s - 1)), [])
  const reset = useCallback(() => {
    setPlaying(false)
    setStep(0)
  }, [])
  const toggle = useCallback(() => {
    if (playing) {
      setPlaying(false)
      return
    }
    // Starting from idle or the end restarts at step 1.
    if (step === 0 || step >= total) setStep(1)
    setPlaying(true)
  }, [playing, step, total])

  useEffect(() => {
    if (!playing || step >= total) return
    const id = window.setTimeout(() => {
      setStep(step + 1)
      if (step + 1 >= total) setPlaying(false)
    }, STEP_MS)
    return () => window.clearTimeout(id)
  }, [playing, step, total])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement) return
      if (e.key === 'ArrowRight') next()
      else if (e.key === 'ArrowLeft') prev()
      else if (e.key === ' ') {
        e.preventDefault()
        toggle()
      } else return
      if (e.key !== ' ') setPlaying(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [next, prev, toggle])

  return { step, playing, total, goTo, next, prev, reset, toggle, done: step >= total }
}
