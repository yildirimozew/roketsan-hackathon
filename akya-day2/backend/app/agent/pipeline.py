"""Fixed 8-step analysis state machine (AGENT_DESIGN §3).

Runs synchronously and reports each finished step through `on_step`, so the same code serves
batch precompute, the request/response API and (P2) SSE streaming.
TODO(P2): LLM refinement in steps 6 and 8 (currently the deterministic fallback path).
"""

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.agent import fallback
from app.core.config import Settings
from app.core.errors import DetectorError, NotFoundError
from app.data.repository import Repository
from app.domain.analysis import Analysis
from app.domain.detection import Detection, TrackMatch
from app.domain.events import STEP_NAMES, StepName, StepResult
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.report import ReportAssessment
from app.domain.track import TrackSnapshot
from app.domain.tuning import AgentTuning
from app.domain.watch import BehaviorClass
from app.services import motion as motion_svc
from app.services import reports as report_svc
from app.services import risk as risk_svc
from app.services.behavior import behavior_class, moving_groups
from app.services.detection import Detector
from app.services.geo import (
    bearing_deg,
    frame_size_m,
    haversine_m,
    in_frame,
    latlon_to_pixel,
    pixel_to_latlon,
)
from app.services.tracks import match_detections, tracks_at
from app.services.tuning import DEFAULT_TUNING

logger = logging.getLogger(__name__)
StepCallback = Callable[[StepResult], None]


def _round6(p: LatLon) -> LatLon:
    """6 decimals ≈ 0.1 m: enough for display and matching."""
    return LatLon(lat=round(p.lat, 6), lon=round(p.lon, 6))


def _georeference(dets: list[Detection], meta: ImageMeta, base: LatLon) -> list[Detection]:
    out: list[Detection] = []
    for d in dets:
        pos = pixel_to_latlon(d.center_px[0], d.center_px[1], meta)
        out.append(
            d.model_copy(
                update={
                    "position": _round6(pos),
                    "distance_to_base_m": round(haversine_m(base, pos)),
                    "bearing_from_base_deg": round(bearing_deg(base, pos), 1),
                }
            )
        )
    return out


def run_analysis(
    analysis_id: str,
    image_id: str,
    repo: Repository,
    detector: Detector,
    settings: Settings,
    on_step: StepCallback | None = None,
    fallback_detector: Detector | None = None,
    tuning: AgentTuning = DEFAULT_TUNING,
) -> Analysis:
    """Analyze one frame end to end.

    Detector, LLM and report problems never raise: they fall back and become step warnings.
    """
    steps: list[StepResult] = []

    def record(
        name: StepName,
        started: float,
        summary: str,
        data: dict[str, Any],
        warnings: list[str] | None = None,
    ) -> None:
        result = StepResult(
            step=name,
            index=STEP_NAMES.index(name) + 1,
            status="warning" if warnings else "done",
            summary=summary,
            data=data,
            warnings=warnings or [],
            duration_ms=round((time.perf_counter() - started) * 1000),
        )
        steps.append(result)
        logger.info(
            "step done",
            extra={"analysis_id": analysis_id, "step": name, "duration_ms": result.duration_ms},
        )
        if on_step:
            on_step(result)

    # 1 load_frame
    t0 = time.perf_counter()
    meta = repo.get_image_meta(image_id)
    record(
        "load_frame",
        t0,
        f"{meta.width_px}x{meta.height_px} frame at {meta.capture_time}, zone {meta.zone}",
        {"capture_time": meta.capture_time, "zone": meta.zone},
    )

    # 2 detect
    t0 = time.perf_counter()
    try:
        image_path: Path | None = repo.image_path(image_id)
    except NotFoundError:
        image_path = None
    used, detect_warnings = detector, []
    try:
        detections = detector.detect(image_id, image_path)
    except DetectorError as exc:
        if fallback_detector is None:
            raise
        logger.warning("detector failed, using fallback", extra={"why": exc.detail})
        used = fallback_detector
        detect_warnings.append(f"{detector.name} failed ({exc.detail}); used {used.name}")
        detections = used.detect(image_id, image_path)
    labels = ", ".join(f"{d.label} {d.confidence:.2f}" for d in detections) or "none"
    record(
        "detect",
        t0,
        f"{len(detections)} vehicle(s): {labels}",
        {"detector": used.name, "count": len(detections)},
        detect_warnings,
    )

    # 3 georeference
    t0 = time.perf_counter()
    detections = _georeference(detections, meta, repo.scene.base.position)
    frame_w_m, frame_h_m = frame_size_m(meta)
    nearest = min((d.distance_to_base_m or 0 for d in detections), default=None)
    record(
        "georeference",
        t0,
        f"{len(detections)} position(s); nearest "
        f"{'-' if nearest is None else f'{nearest / 1000:.2f} km'} from base",
        {"frame_w_m": round(frame_w_m, 1), "frame_h_m": round(frame_h_m, 1)},
    )

    # 4 match_tracks
    t0 = time.perf_counter()
    positions = tracks_at(list(repo.tracks.values()), meta.capture_min)
    matches = match_detections(detections, positions, settings.match_max_m)
    matched_by_track = {m.track_id: m.detection_id for m in matches if m.track_id}
    snapshots = []
    for tid, pos in positions.items():
        x, y = latlon_to_pixel(pos, meta)
        if in_frame(x, y, meta):
            snapshots.append(
                TrackSnapshot(
                    track_id=tid,
                    position=_round6(pos),
                    center_px=(round(x, 1), round(y, 1)),
                    matched_detection_id=matched_by_track.get(tid),
                )
            )
    n_matched = sum(1 for m in matches if m.track_id)
    record(
        "match_tracks",
        t0,
        f"{n_matched}/{len(detections)} matched; {len(snapshots)} track(s) inside frame",
        {"candidates": len(positions)},
    )

    # 5 analyze_motion
    t0 = time.perf_counter()
    motions = [
        motion_svc.motion_profile(
            repo.tracks[m.track_id],
            meta.capture_min,
            repo.scene.base.position,
            repo.scene.zones,
            settings.stop_speed_ms,
            settings.zone_radius_m,
        )
        for m in matches
        if m.track_id
    ]
    record(
        "analyze_motion",
        t0,
        "; ".join(
            f"{p.track_id} {p.approach_rate_m_per_min:+.0f} m/min, {len(p.stops)} stop(s)"
            for p in motions
        )
        or "no matched tracks",
        {},
    )

    # 6 assess_reports (rules; TODO(P2): LLM extraction + verdict with this as fallback)
    t0 = time.perf_counter()
    lang = settings.brief_language
    window = repo.reports_between(meta.capture_min - motion_svc.WINDOW_MIN, meta.capture_min)
    claims = [report_svc.extract_claim(r, repo.scene.zones) for r in window]
    relevant = [
        c for c in claims if report_svc.is_relevant(c, meta, detections, settings.report_radius_m)
    ]
    assessments: list[ReportAssessment] = []
    for claim in relevant:
        result = report_svc.verify_claim(
            claim,
            meta,
            detections,
            matches,
            repo.tracks,
            settings.report_radius_m,
            settings.stop_speed_ms,
        )
        assessments.append(
            ReportAssessment(
                report_id=claim.report_id,
                verdict=result.verdict,
                reason=fallback.report_reason(result, lang),
                checks=result.checks,
                linked_detection_ids=result.linked_detection_ids,
                trust_weight=result.trust_weight,
            )
        )
    record(
        "assess_reports",
        t0,
        f"{len(relevant)} relevant of {len(window)} in window: "
        + (", ".join(f"{a.report_id} {a.verdict}" for a in assessments) or "none"),
        {},
    )

    # 7 score_risk
    t0 = time.perf_counter()
    match_by_det = {m.detection_id: m for m in matches}
    motion_by_track = {p.track_id: p for p in motions}
    claim_by_id = {c.report_id: c for c in relevant}

    def behavior_of(match: TrackMatch | None) -> BehaviorClass:
        motion = motion_by_track.get(match.track_id or "") if match else None
        return (
            behavior_class(motion.points, repo.scene.base.position, tuning.behavior)
            if motion
            else "unknown"
        )

    groups = moving_groups(list(repo.tracks.values()), meta.capture_min, tuning.groups)

    def group_size_of(match: TrackMatch | None) -> int:
        return max(1, len(groups.get(match.track_id or "", []))) if match else 1

    risks = [
        risk_svc.score_vehicle(
            d,
            match_by_det.get(d.id),
            motion_by_track.get(match_by_det[d.id].track_id or "")
            if d.id in match_by_det
            else None,
            assessments,
            claim_by_id,
            behavior_of(match_by_det.get(d.id)),
            group_size_of(match_by_det.get(d.id)),
            rubric=tuning.rubric,
            ceiling=tuning.ceiling,
            large_group=tuning.groups.large_group,
        )
        for d in detections
    ]
    level = risk_svc.frame_level(risks)
    record(
        "score_risk",
        t0,
        f"frame level {level}; " + ", ".join(f"{r.detection_id}={r.score}" for r in risks),
        {"level": level},
    )

    # 8 write_brief (fallback template; TODO(P2): LLM brief + validator)
    t0 = time.perf_counter()
    brief = fallback.build_brief(
        meta, detections, matches, motions, risks, relevant, assessments, lang
    )
    record(
        "write_brief",
        t0,
        f"{brief.level} brief ({brief.generated_by}), action {brief.recommended_action}",
        {"generated_by": brief.generated_by},
    )

    return Analysis(
        id=analysis_id,
        image_id=image_id,
        status="done",
        image=meta,
        scene=repo.scene,
        steps=steps,
        detections=detections,
        track_snapshots=snapshots,
        matches=matches,
        motions=motions,
        reports=relevant,
        report_assessments=assessments,
        risks=risks,
        brief=brief,
        timings_ms={s.step: s.duration_ms or 0 for s in steps},
    )
