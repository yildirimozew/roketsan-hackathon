"""Deterministic brief and report reasons built only from code outputs (AGENT_DESIGN §8)."""

from app.agent.fallback_templates import VEHICLE, Lang, T, km
from app.domain.brief import Brief, RecommendedAction, VehicleBriefLine
from app.domain.detection import Detection, TrackMatch
from app.domain.image import ImageMeta
from app.domain.report import ReportAssessment, ReportClaim
from app.domain.risk import VehicleRisk
from app.domain.track import MotionProfile
from app.services.reports import VerificationResult
from app.services.risk import frame_level

ACTION: dict[str, RecommendedAction] = {
    "LOW": "MONITOR",
    "MEDIUM": "MONITOR",
    "HIGH": "VERIFY",
    "CRITICAL": "ESCALATE",
}


def report_reason(result: VerificationResult, lang: Lang) -> str:
    """One-sentence reason for a code-side verdict."""
    t = T[lang]
    if result.instructions:
        return t["r_instructions"]
    if result.verdict == "CONTRADICTED":
        what = ", ".join(t[f"c_{c.name}"] for c in result.checks if c.status == "mismatch")
        return t["r_contradicted"].format(what=what)
    if result.lowers_threat:
        return t["r_lowering"]
    if result.verdict == "CORROBORATED":
        return t["r_corroborated"]
    return t["r_unverified"]


def _vehicle_line(
    det: Detection, risk: VehicleRisk, motion: MotionProfile | None, lang: Lang
) -> VehicleBriefLine:
    t = T[lang]
    name = VEHICLE[lang].get(det.label, det.label).capitalize()
    evidence = [det.id] + ([f"TRK-{risk.track_id}"] if risk.track_id else [])
    if motion is None:
        text = t["vehicle_untracked"].format(vehicle=name)
    else:
        key = "vehicle_line_eta" if motion.eta_to_base_min is not None else "vehicle_line"
        text = t[key].format(
            vehicle=name,
            track=motion.track_id,
            km=km(motion.dist_now_m, lang),
            eta=f"{motion.eta_to_base_min or 0:.0f}",
            score=risk.score,
        )
    return VehicleBriefLine(
        detection_id=det.id,
        track_id=risk.track_id,
        level=risk.level,
        text=text,
        evidence_ids=evidence,
    )


def build_brief(
    meta: ImageMeta,
    detections: list[Detection],
    matches: list[TrackMatch],
    motions: list[MotionProfile],
    risks: list[VehicleRisk],
    claims: list[ReportClaim],
    assessments: list[ReportAssessment],
    lang: Lang,
) -> Brief:
    """Template brief from rubric outputs; `generated_by="fallback"`."""
    t = T[lang]
    by_det = {d.id: d for d in detections}
    motion_by_track = {m.track_id: m for m in motions}
    claim_by_id = {c.report_id: c for c in claims}
    level = frame_level(risks)
    ranked = sorted(risks, key=lambda r: r.score, reverse=True)

    lines = [
        _vehicle_line(by_det[r.detection_id], r, motion_by_track.get(r.track_id or ""), lang)
        for r in ranked
    ]
    summary: list[str] = []
    if not ranked:
        headline, summary = t["headline_none"], [t["summary_none"]]
    else:
        top = ranked[0]
        det = by_det[top.detection_id]
        motion = motion_by_track.get(top.track_id or "")
        rate = motion.approach_rate_m_per_min if motion else 0.0
        moving_now = motion is not None and motion.last10_speed_ms >= 1.0
        if not moving_now or abs(rate) <= 5:
            trend = t["trend_static"]
        else:
            trend = t["trend_closing"] if rate > 0 else t["trend_leaving"]
        dist = motion.dist_now_m if motion else (det.distance_to_base_m or 0)
        headline = t["headline"].format(
            n=len(detections),
            vehicle=VEHICLE[lang].get(det.label, det.label),
            km=km(dist, lang),
            trend=trend,
        )
        if motion and motion.dist_60m_ago_m is not None and abs(rate) > 5:
            summary.append(
                t["motion"].format(
                    track=motion.track_id,
                    d60=km(motion.dist_60m_ago_m, lang),
                    dnow=km(motion.dist_now_m, lang),
                    verb=t["motion_close"] if rate > 0 else t["motion_away"],
                )
            )
        long_stops = [s for s in (motion.stops if motion else []) if s.duration_min >= 20]
        if long_stops:
            detail = ", ".join(
                f"{s.start} · {s.duration_min} dk"
                if lang == "tr"
                else f"{s.start} · {s.duration_min} min"
                for s in long_stops
            )
            summary.append(t["stops"].format(n=len(long_stops), detail=detail))
        summary.append(lines[0].text)

    notes = [
        t["report_note"].format(
            rid=a.report_id,
            source=claim_by_id[a.report_id].source,
            time=claim_by_id[a.report_id].time,
            verdict=t[f"v_{a.verdict}"],
            reason=a.reason,
        )
        for a in assessments
    ]
    unmatched = [m.detection_id for m in matches if m.track_id is None]
    uncertainties = [t["u_oblique"], t["u_fallback"]]
    if unmatched:
        uncertainties.insert(1, t["u_unmatched"].format(ids=", ".join(unmatched)))

    evidence = [d.id for d in detections]
    evidence += [f"TRK-{m.track_id}" for m in matches if m.track_id]
    evidence += [a.report_id for a in assessments]
    if meta.zone:
        evidence.append(f"ZONE-{meta.zone}")

    return Brief(
        image_id=meta.image_id,
        level=level,
        headline=headline,
        summary=" ".join(summary),
        vehicles=lines,
        report_notes=notes,
        uncertainties=uncertainties,
        recommended_action=ACTION[level],
        evidence_ids=evidence,
        generated_by="fallback",
    )
