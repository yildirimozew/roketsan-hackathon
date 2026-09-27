import { useQuery } from '@tanstack/react-query'
import { useMemo } from 'react'
import { getRecording, getRecordings } from '@/api/endpoints'
import { buildDemoModel, recordingAt, recordingWindow } from '@/lib/watchDemo'

const STATIC = { retry: false, staleTime: Infinity } as const

/** The recorded watch run that covers `minute` (master clock), indexed by tick; no model when
 *  no recording covers it. `windows` lists what the recordings cover, as HH:MM spans. */
export function useWatchDemo(minute: number) {
  const list = useQuery({ queryKey: ['watch-recordings'], queryFn: getRecordings, ...STATIC })
  const id = list.data ? recordingAt(list.data, minute) : null
  const events = useQuery({
    queryKey: ['watch-recording', id],
    queryFn: () => getRecording(id ?? ''),
    enabled: id !== null,
    ...STATIC,
  })
  const model = useMemo(() => (events.data ? buildDemoModel(events.data) : undefined), [events.data])
  const windows = useMemo(() => [...new Set((list.data ?? []).map(recordingWindow))], [list.data])
  return {
    recordingId: id,
    model: id === null ? undefined : model,
    windows,
    isPending: list.isPending || (id !== null && events.isPending),
    isError: list.isError || events.isError,
    isEmpty: list.data?.length === 0,
  }
}
