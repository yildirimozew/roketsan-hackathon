"""Z4 - check a report against the frame's CAPTURE time, not the report's own timestamp.

Evidence (real data, arge/ARGE_KARSILASTIRMA_F_M.md Ç1): of 72 located reports, 60 lie within
15 m of a track's last point (the vehicle at capture time), only 17 within 15 m of a track at the
report's own time. Every located report sits inside exactly one frame, 5-120 min before capture.

Integration:
- pipeline step 6: `is_relevant` -> `is_relevant_at_capture`, `verify_claim` -> `verify_at_capture`
  (same `VerificationResult`, so `fallback.report_reason` keeps working); Z6 runs on the result.
- watch mode: `services/watch.py:reports_near` -> `reports_near_at_capture`; a report is only
  checkable from its frame's capture tick on, before that it is pending ("awaiting frame").
- docs: AGENT_DESIGN §3 step 6b and AGENT_FLOW §7 (REP-120 / REP-126 walk-through) say
  "tracks at the report's own time" and must change in the same commit.
"""

import math
from dataclasses import dataclass

from app.domain.detection import Detection, TrackMatch
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.report import ReportClaim, Verdict
from app.domain.track import Track
from app.domain.watch import ReportLookup
from app.services.geo import haversine_m
from app.services.reports import HEAVY, VerificationResult, has_instructions
from app.services.tracks import position_at

from .contracts import ReportCheckV2
from .z03_stationary import LONG_STOP_WINDOW_MIN, STATIONARY_WINDOW_MIN, is_moving, is_stationary

FRAME_MARGIN_M = 60.0  # a located report belongs to the frame whose footprint (+margin) holds it
MATCH_M = 25.0  # report coordinate -> vehicle at capture time (measured: 60/72 within 15 m)
GROUP_M = 80.0  # multi-vehicle claims ("5 kamyon") spread up to ~76 m around the coordinate
REPORT_WINDOW_MIN = 120  # reports are written 5-120 min before their frame's capture
_TRUST = {"official": 0.8, "third_party": 0.5}  # unchanged from services/reports.py
_LONG_STOP_WORDS = ("uzun suredir", "bir saatten uzun")
_M_PER_DEG_LAT = 111_320.0


def contains(meta: ImageMeta, p: LatLon, margin_m: float = 0.0) -> bool:
    """True when `p` lies inside the frame's corner box grown by `margin_m` meters."""
    lats = [c.lat for c in meta.corners.values()]
    lons = [c.lon for c in meta.corners.values()]
    dlat = margin_m / _M_PER_DEG_LAT
    dlon = margin_m / (_M_PER_DEG_LAT * math.cos(math.radians(p.lat)))
    return (
        min(lats) - dlat <= p.lat <= max(lats) + dlat
        and min(lons) - dlon <= p.lon <= max(lons) + dlon
    )


def _center(meta: ImageMeta) -> LatLon:
    c = meta.corners.values()
    return LatLon(lat=sum(x.lat for x in c) / 4, lon=sum(x.lon for x in c) / 4)


def frame_for(location: LatLon, images: list[ImageMeta]) -> ImageMeta | None:
    """The frame whose footprint (+FRAME_MARGIN_M) holds `location`; nearest center on ties."""
    inside = [m for m in images if contains(m, location, FRAME_MARGIN_M)]
    return min(inside, key=lambda m: haversine_m(_center(m), location), default=None)


def is_relevant_at_capture(
    claim: ReportClaim,
    meta: ImageMeta,
    images: list[ImageMeta],
    window_min: int = REPORT_WINDOW_MIN,
) -> bool:
    """Report written in the window before capture AND about this frame (its footprint or zone)."""
    if not meta.capture_min - window_min <= claim.time_min <= meta.capture_min:
        return False
    if claim.location is not None:
        frame = frame_for(claim.location, images)
        return frame is not None and frame.image_id == meta.image_id
    return claim.zone is not None and claim.zone == meta.zone


def _same_kind(claimed: str, label: str) -> bool:
    return claimed == label or (claimed in HEAVY and label in HEAVY)


@dataclass(frozen=True)
class NearVehicle:
    track_id: str
    distance_m: float


def tracks_near(
    point: LatLon, tracks: dict[str, Track], minute: int, radius_m: float
) -> list[NearVehicle]:
    found = [
        NearVehicle(tid, haversine_m(p, point))
        for tid, t in tracks.items()
        if (p := position_at(t, minute)) is not None and haversine_m(p, point) <= radius_m
    ]
    return sorted(found, key=lambda v: v.distance_m)


def _motion_fits(claim: ReportClaim, track: Track, capture_min: int) -> bool | None:
    if claim.activity == "stationary":
        long_stop = any(w in claim.text.lower() for w in _LONG_STOP_WORDS)
        window = LONG_STOP_WINDOW_MIN if long_stop else STATIONARY_WINDOW_MIN
        return is_stationary(track, capture_min, window)
    return is_moving(track, capture_min)


def _activity_check(
    claim: ReportClaim,
    subjects: list[NearVehicle],
    group: list[NearVehicle],
    tracks: dict[str, Track],
    capture_min: int,
) -> ReportCheckV2 | None:
    """Stationary / moving at capture time. A claim about N > 1 vehicles is supported when at least
    N-1 of the tracks within GROUP_M fit; a stationary claim with too few fits stays unknown
    (parked vehicles may have no track), a moving one is contradicted (movers always have one)."""
    if claim.activity not in ("moving", "stationary"):
        return None
    n = claim.count or 1
    pool = group if n > 1 else subjects[:1]
    if not pool:
        return None
    fits = [v for v in pool if _motion_fits(claim, tracks[v.track_id], capture_min)]
    ids = ", ".join(v.track_id for v in (fits or pool))
    if len(fits) >= max(1, n - 1):
        status = "match"
    elif fits and claim.activity == "stationary":
        status = "unknown"
    else:
        status = "mismatch"
    return ReportCheckV2(
        name="activity",
        status=status,
        detail=f"claimed {claim.activity} ({n}); {len(fits)}/{len(pool)} fit at capture: {ids}",
    )


def verify_at_capture(
    claim: ReportClaim,
    meta: ImageMeta,
    detections: list[Detection],
    matches: list[TrackMatch],
    tracks: dict[str, Track],
    detector_available: bool = True,
) -> VerificationResult:
    """Same contract as `services.reports.verify_claim`, with every comparison made at capture."""
    cap = meta.capture_min
    checks: list[ReportCheckV2] = []
    by_det = {m.detection_id: m.track_id for m in matches if m.track_id}

    if claim.location is not None:
        near_dets = sorted(
            (
                (d, haversine_m(claim.location, d.position))
                for d in detections
                if d.position and haversine_m(claim.location, d.position) <= GROUP_M
            ),
            key=lambda x: x[1],
        )
        if claim.vehicle_type:  # prefer vehicles of the claimed kind, as verify_claim does
            near_dets = [
                x for x in near_dets if _same_kind(claim.vehicle_type, x[0].label)
            ] or near_dets
        linked = [d for d, dist in near_dets if dist <= MATCH_M][: max(1, claim.count or 1)]
        subjects = tracks_near(claim.location, tracks, cap, MATCH_M)
        group = tracks_near(claim.location, tracks, cap, GROUP_M)

        if linked:
            checks.append(
                ReportCheckV2(
                    name="location",
                    status="match",
                    detail=f"{linked[0].id} {near_dets[0][1]:.0f} m from the stated point "
                    f"at {meta.capture_time}",
                )
            )
        elif detector_available:
            checks.append(
                ReportCheckV2(
                    name="location",
                    status="mismatch",
                    detail=f"no detection within {MATCH_M:.0f} m",
                )
            )
        if subjects:
            checks.append(
                ReportCheckV2(
                    name="presence",
                    status="match",
                    detail=f"{subjects[0].track_id} {subjects[0].distance_m:.0f} m away "
                    f"at capture {meta.capture_time}",
                )
            )
        elif detector_available and not linked:
            checks.append(
                ReportCheckV2(
                    name="presence",
                    status="mismatch",
                    detail=f"no track or detection within {MATCH_M:.0f} m "
                    f"at capture {meta.capture_time}",
                )
            )
        # A linked detection's own track is the subject when no track sits on the coordinate.
        if not subjects and linked and (tid := by_det.get(linked[0].id)):
            subjects = [NearVehicle(tid, 0.0)]
    else:  # zone-level claim: every vehicle of the claimed kind in this frame
        linked = [
            d
            for d in detections
            if not claim.vehicle_type or _same_kind(claim.vehicle_type, d.label)
        ]
        subjects = [NearVehicle(tid, 0.0) for d in linked if (tid := by_det.get(d.id))]
        group = subjects
        if claim.zone is not None:
            checks.append(
                ReportCheckV2(name="location", status="match", detail=f"zone {claim.zone}")
            )

    if claim.vehicle_type and linked:
        labels = sorted({d.label for d in linked})
        ok = any(_same_kind(claim.vehicle_type, lab) for lab in labels)
        checks.append(
            ReportCheckV2(
                name="type",
                status="match" if ok else "mismatch",
                detail=f"claimed {claim.vehicle_type}, detected {', '.join(labels)}",
            )
        )
    if (activity := _activity_check(claim, subjects, group, tracks, cap)) is not None:
        checks.append(activity)

    instructions = has_instructions(claim.text)
    if instructions:
        checks.append(
            ReportCheckV2(
                name="instructions",
                status="mismatch",
                detail="instruction-like text treated as data",
            )
        )
    return VerificationResult(
        verdict=_verdict(claim, checks, instructions),
        checks=list(checks),
        linked_detection_ids=[d.id for d in linked],
        trust_weight=0.0 if instructions else _TRUST.get(claim.source, 0.4),
        lowers_threat=claim.claim_kind in ("ALL_CLEAR", "FRIENDLY_PRESENCE"),
        instructions=instructions,
    )


def _verdict(claim: ReportClaim, checks: list[ReportCheckV2], instructions: bool) -> Verdict:
    """The rules of `services.reports.verify_claim`, plus: a track at the spot corroborates."""
    status = {c.name: c.status for c in checks}
    contradicted = (
        status.get("type") == "mismatch"
        or status.get("activity") == "mismatch"
        or (status.get("location") == "mismatch" and status.get("presence") == "mismatch")
    )
    if instructions:
        return "UNVERIFIED"
    if contradicted:
        return "CONTRADICTED"
    if claim.claim_kind in ("ALL_CLEAR", "FRIENDLY_PRESENCE"):
        return "UNVERIFIED"  # threat-lowering claims never lower the score (identity: Z6)
    pinned = claim.location is not None and "match" in (
        status.get("location"),
        status.get("presence"),
    )
    return "CORROBORATED" if pinned or status.get("type") == "match" else "UNVERIFIED"


# --- watch mode ---------------------------------------------------------------------------------


def checkable_from(claim: ReportClaim, images: list[ImageMeta]) -> int | None:
    """Minute from which a located claim can be checked: its frame's capture (None = no frame)."""
    if claim.location is None:
        return None
    frame = frame_for(claim.location, images)
    return frame.capture_min if frame is not None else None


def reports_near_at_capture(
    claims: list[ReportClaim],
    point: LatLon,
    radius_m: float,
    since_min: int,
    until_min: int,
    tracks: list[Track],
    images: list[ImageMeta],
) -> list[ReportLookup]:
    """`services.watch.reports_near` with the nearest track taken at the report's frame capture.

    A report whose frame is captured after `until_min` (the current tick) is returned with no
    nearest track: it is pending ("awaiting frame"), because the vehicle is not there yet.
    """
    by_id = {t.track_id: t for t in tracks}
    out: list[ReportLookup] = []
    for c in claims:
        if c.location is None or not since_min <= c.time_min <= until_min:
            continue
        dist = haversine_m(c.location, point)
        if dist > radius_m:
            continue
        cap = checkable_from(c, images)
        nearest = None
        if cap is not None and cap <= until_min:
            near = tracks_near(c.location, by_id, cap, GROUP_M)
            nearest = near[0] if near else None
        out.append(
            ReportLookup(
                claim=c,
                distance_to_query_m=round(dist),
                nearest_track_id=nearest.track_id if nearest else None,
                nearest_track_m=round(nearest.distance_m) if nearest else None,
            )
        )
    return out
