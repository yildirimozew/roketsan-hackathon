import { useState } from 'react'
import { useNavigate } from 'react-router'
import type { ImageMeta, MapReport, MapTrack, Scene } from '@/api/types'
import { TimeBar } from '@/components/map/TimeBar'
import { useMasterClock } from '@/hooks/useMasterClock'
import { t } from '@/i18n'
import { WatchMap } from './WatchMap'

interface Props {
  field: { scene: Scene; images: ImageMeta[]; tracks: MapTrack[]; reports: MapReport[] }
  windows: string[] // clock spans the recordings cover, e.g. "10:05-11:10"
}

const EMPTY = new Map()
const NONE = new Set<string>()

/** The watch page when no recorded agent run covers the master clock: the live map without agent
 *  levels, and where recordings exist. */
export function NoRecording({ field, windows }: Props) {
  const clock = useMasterClock()
  const [selected, setSelected] = useState<string | null>(null)
  const navigate = useNavigate()
  const w = t.watch
  return (
    <div className="flex h-full flex-col gap-3 p-3">
      <div className="flex min-h-0 flex-1 gap-3">
        <div className="relative min-w-0 flex-1">
          <WatchMap
            {...field}
            minute={clock.minute}
            checks={{}}
            levels={EMPTY}
            focus={EMPTY}
            types={EMPTY}
            expected={NONE}
            selectedId={selected}
            onSelect={setSelected}
            onOpenFrame={(id) => void navigate(`/analysis/${id}`, { state: { from: 'watch' } })}
          />
        </div>
        <aside className="flex w-[27rem] shrink-0 flex-col gap-2 rounded-lg border border-dashed bg-card p-4 text-sm text-muted-foreground">
          <p>{w.noRecording}</p>
          {windows.length > 0 && <p className="font-mono text-xs">{w.recordedWindows(windows.join(', '))}</p>}
        </aside>
      </div>
      <TimeBar ticks={[]} activity={[]} />
    </div>
  )
}
