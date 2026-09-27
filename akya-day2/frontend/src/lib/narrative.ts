// Turkish step narration built from API data (formatting only; all numbers come from the API).
import type { Analysis, MotionProfile, StepName, VehicleRisk } from '@/api/types'
import { t } from '@/i18n'
import { formatCoord, formatKm, formatMeters, formatPercent, formatSpeed, placeName } from './format'

export interface Narrative {
  headline: string
  facts: string[]
}

const n = t.narrative

/** The vehicle the story follows: highest risk score, else first detection. */
export function primaryRisk(a: Analysis): VehicleRisk | undefined {
  return [...a.risks].sort((x, y) => y.score - x.score)[0]
}

export function primaryMotion(a: Analysis): MotionProfile | undefined {
  const risk = primaryRisk(a)
  return a.motions.find((m) => m.track_id === risk?.track_id) ?? a.motions[0]
}

export function trendOf(m: MotionProfile): 'closing' | 'leaving' | 'static' {
  if (m.last10_speed_ms < 1 || Math.abs(m.approach_rate_m_per_min) <= 5) return 'static'
  return m.approach_rate_m_per_min > 0 ? 'closing' : 'leaving'
}

export function frameSizeM(a: Analysis): { w: number; h: number } {
  const size = a.steps.find((s) => s.step === 'georeference')?.data as { frame_w_m?: number; frame_h_m?: number } | undefined
  return { w: size?.frame_w_m ?? 0, h: size?.frame_h_m ?? 0 }
}

export function buildNarrative(a: Analysis, step: StepName): Narrative {
  const image = a.image
  switch (step) {
    case 'load_frame': {
      const tl = image?.corners.tl
      return {
        headline: n.load,
        facts: image
          ? [`${image.width_px}×${image.height_px} px · ${image.capture_time}`, tl ? `sol üst ${formatCoord(tl.lat)}, ${formatCoord(tl.lon)}` : '']
          : [],
      }
    }
    case 'detect':
      return {
        headline: n.detect(a.detections.length),
        facts: a.detections.flatMap((d) => [
          `${d.id} · ${d.label} ${formatPercent(d.confidence)} · kutu (${d.bbox.join(', ')})`,
          `merkez piksel (${d.center_px.map(Math.round).join(', ')})`,
        ]),
      }
    case 'georeference': {
      const { w, h } = frameSizeM(a)
      return {
        headline: n.georef,
        facts: [
          ...a.detections.map((d) =>
            d.position
              ? `${d.id} → ${formatCoord(d.position.lat)}, ${formatCoord(d.position.lon)} · üsse ${formatKm(d.distance_to_base_m)}`
              : d.id,
          ),
          n.frameSize(w.toFixed(0), h.toFixed(0), image?.zone ? placeName(image.zone) : '—'),
        ],
      }
    }
    case 'match_tracks': {
      const matched = a.matches.filter((m) => m.track_id)
      return {
        headline: n.match(matched.length, a.detections.length),
        facts: a.matches.map((m) =>
          m.track_id
            ? `${m.detection_id} → ${m.track_id} · ${formatMeters(m.distance_m)} · ${n.confidence[m.confidence]}` +
              (m.second_best_track_id ? ` (${n.second(m.second_best_track_id, formatMeters(m.second_best_m))})` : '')
            : n.unmatched(m.detection_id, formatMeters(m.distance_m)),
        ),
      }
    }
    case 'analyze_motion': {
      const m = primaryMotion(a)
      if (!m) return { headline: n.motionNone, facts: [] }
      const trend = trendOf(m)
      const trendText = trend === 'closing' ? n.trendClosing : trend === 'leaving' ? n.trendLeaving : n.trendStatic
      const rate = m.approach_rate_m_per_min
      return {
        headline: n.motion(m.track_id, trendText),
        facts: [
          n.distanceTrend(formatKm(m.dist_60m_ago_m), formatKm(m.dist_now_m), `${rate > 0 ? '+' : ''}${rate.toFixed(0)}`),
          n.speedHeading(formatSpeed(m.last10_speed_ms), m.heading_deg?.toFixed(0) ?? '—', m.bearing_to_base_deg.toFixed(0)),
          n.pathStops(`${m.path_km.toLocaleString('tr-TR')} km`, m.stops.length),
          ...(m.eta_to_base_min != null ? [n.eta(m.eta_to_base_min.toFixed(0))] : []),
        ],
      }
    }
    case 'assess_reports':
      return {
        headline: n.reports(a.report_assessments.length),
        facts: a.report_assessments.map((ra) => {
          const claim = a.reports.find((c) => c.report_id === ra.report_id)
          return `${ra.report_id} · ${claim?.time ?? ''} · ${claim?.source ?? ''} → ${t.verdict[ra.verdict]}`
        }),
      }
    case 'score_risk':
      return {
        headline: n.risk(a.brief ? t.risk[a.brief.level] : '—'),
        facts: a.risks.map((r) => `${r.detection_id}${r.track_id ? ` · ${r.track_id}` : ''} → ${r.score}/100 ${t.risk[r.level]}`),
      }
    case 'write_brief':
      return {
        headline: a.brief?.summary ?? '',
        facts: a.brief
          ? [n.action(t.action[a.brief.recommended_action]), ...(a.brief.generated_by === 'fallback' ? [n.fallback] : [])]
          : [],
      }
  }
}
