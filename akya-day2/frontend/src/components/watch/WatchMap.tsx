import { Maximize } from 'lucide-react'
import type { ImageMeta, MapReport, MapTrack, Scene } from '@/api/types'
import { BaseMarker } from '@/components/map/BaseMarker'
import { FrameLayer } from '@/components/map/FrameLayer'
import { MapGrid } from '@/components/map/MapGrid'
import { Button } from '@/components/ui/button'
import { useFieldMapModel } from '@/hooks/useFieldMapModel'
import { useMapViewport } from '@/hooks/useMapViewport'
import { t } from '@/i18n'
import type { VehicleState } from '@/lib/watchDemo'
import { SectorLayer } from './SectorLayer'
import { VehicleLayer } from './VehicleLayer'

interface Props {
  scene: Scene
  images: ImageMeta[]
  tracks: MapTrack[]
  reports: MapReport[]
  minute: number
  checks: Record<string, string>
  levels: Map<string, VehicleState>
  focus: Map<string, number>
  types: Map<string, string>
  expected: Set<string>
  selectedId: string | null
  onSelect: (id: string | null) => void
  onOpenFrame: (imageId: string) => void
}

/** The field at one tick: checked sectors, this tick's frame, and every vehicle by agent level. */
export function WatchMap(props: Props) {
  const { scene, images, tracks, reports, minute, checks, levels, focus, types, expected, selectedId, onSelect, onOpenFrame } = props
  const model = useFieldMapModel(scene, images, tracks, reports)
  const { ref, viewBox, bounds, mpp, fit, handlers } = useMapViewport(model.fitRadiusM)
  const frames = model.frames.filter((f) => Math.abs(f.captureMin - minute) <= 5)

  return (
    <div className="relative h-full overflow-hidden rounded-lg border bg-map">
      <svg ref={ref} viewBox={viewBox} className="absolute inset-0 size-full cursor-grab touch-none select-none active:cursor-grabbing" {...handlers}>
        <rect x={-1e5} y={-1e5} width={2e5} height={2e5} fill="transparent" onClick={() => onSelect(null)} />
        <MapGrid bounds={bounds} />
        <SectorLayer zones={model.zones} checks={checks} />
        <FrameLayer frames={frames} minute={minute} mpp={mpp} selectedId={null} onSelect={onOpenFrame} />
        <VehicleLayer tracks={model.tracks} minute={minute} mpp={mpp} levels={levels} focus={focus} types={types} expected={expected} selectedId={selectedId} onSelect={onSelect} />
        <BaseMarker position={scene.base.position} mpp={mpp} />
      </svg>
      <Button size="icon-sm" variant="outline" className="absolute right-3 bottom-3 bg-card/85" onClick={fit} aria-label={t.fieldMap.fit} title={t.fieldMap.fit}>
        <Maximize aria-hidden />
      </Button>
    </div>
  )
}
