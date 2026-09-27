import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { deleteTuning, getTuning, previewPrompt, putTuning } from '@/api/endpoints'
import type { AgentTuning, PromptName, TuningView } from '@/api/types'

const KEY = ['admin', 'tuning'] as const

/** Admin tuning: the saved view plus save and reset mutations (both refresh the view). */
export function useTuning() {
  const qc = useQueryClient()
  const query = useQuery({ queryKey: KEY, queryFn: getTuning, retry: false })
  const onSuccess = (view: TuningView) => {
    qc.setQueryData(KEY, view)
    // Analyses are cached forever client-side; a new tuning must re-run them.
    void qc.invalidateQueries({ queryKey: ['analysis'] })
  }
  const save = useMutation({ mutationFn: putTuning, onSuccess })
  const reset = useMutation({ mutationFn: deleteTuning, onSuccess })
  return { query, save, reset }
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

/** Rendered prompt for the editor text, 400 ms after the last change. */
export function usePromptPreview(name: PromptName, text: string, tuning: AgentTuning) {
  const input = useDebounced({ name, text, tuning }, 400)
  return useQuery({
    queryKey: ['admin', 'preview', input],
    queryFn: () => previewPrompt(input.name, input.text, input.tuning),
    placeholderData: (prev) => prev,
    retry: false,
  })
}
