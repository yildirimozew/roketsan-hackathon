import type { Analysis, StepName } from '@/api/types'
import { BriefScene } from './BriefScene'
import { FrameScene } from './FrameScene'
import { PlacementScene } from './PlacementScene'
import { ReportsScene } from './ReportsScene'
import { RiskScene } from './RiskScene'
import { RouteScene } from './RouteScene'

/** Picks the stage visual for the current step (null = idle, before playback). */
export function StepScene({ analysis, step }: { analysis: Analysis; step: StepName | null }) {
  switch (step) {
    case null:
      return <FrameScene analysis={analysis} mode="idle" />
    case 'load_frame':
      return <FrameScene analysis={analysis} mode="corners" />
    case 'detect':
      return <FrameScene analysis={analysis} mode="boxes" />
    case 'georeference':
      return <PlacementScene analysis={analysis} />
    case 'match_tracks':
      return <FrameScene analysis={analysis} mode="tracks" />
    case 'analyze_motion':
      return <RouteScene analysis={analysis} />
    case 'assess_reports':
      return <ReportsScene analysis={analysis} />
    case 'score_risk':
      return <RiskScene analysis={analysis} />
    case 'write_brief':
      return <BriefScene analysis={analysis} />
  }
}
