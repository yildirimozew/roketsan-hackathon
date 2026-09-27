"""Z2 - vehicles we know from tracks but did not detect still get motion, risk and a brief line.

Today only detection-matched tracks reach steps 5-8; in-frame tracks without a box are listed as
`TrackSnapshot`s and ignored. With no detector (Z1) every vehicle in the frame is ignored.
Measured: 206 of 226 tracks end inside their frame, 20 end 7-26 m outside an edge.

Integration (pipeline step 4, then 5-8):
- `find_track_only` after `match_detections`; motion via `motion_svc.motion_profile`; risk via
  `score_track_only`. The risk row uses the id `TRK-<track_id>` in `detection_id`, so
  `VehicleRisk` and the brief need no schema change; the cleaner option (contract change, plan
  first) is `VehicleRisk.detection_id: str | None` plus a `source: "detection" | "track"` field.
- `explain_unmatched_detections` gives the existing "no_track" factor a reason sentence.
"""

import math
from typing import Literal

from app.domain.base import DomainModel
from app.domain.detection import Detection, TrackMatch
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.risk import RiskFactor, VehicleRisk
from app.domain.track import MotionProfile
from app.domain.watch import BehaviorClass
from app.services import risk as risk_svc
from app.services.geo import bearing_deg, frame_size_m, haversine_m, latlon_to_pixel

EDGE_MARGIN_M = 30.0  # measured: tracks ending outside their frame are 7-26 m from the edge
LOW_CONFIDENCE = 0.5  # an untracked box below this is more likely a false positive than parked
TRACK_ONLY_LABEL = "unknown"  # no image evidence of the type: no type points

Hypothesis = Literal["missed", "outside_near_edge"]


class TrackOnlyVehicle(DomainModel):
    """A tracked vehicle at capture time with no matching detection."""

    track_id: str
    position: LatLon
    center_px: tuple[float, float]
    hypothesis: Hypothesis  # missed: inside the frame, no box; outside_near_edge: just out of view
    edge_distance_m: float  # 0 inside the frame


class UnmatchedDetectionNote(DomainModel):
    """Why a detection has no track."""

    detection_id: str
    hypothesis: Literal["parked_likely", "false_positive_likely"]
    reason: str


def _edge_distance_m(x: float, y: float, meta: ImageMeta) -> float:
    w_m, h_m = frame_size_m(meta)
    dx = max(0.0, -x, x - meta.width_px) * w_m / meta.width_px
    dy = max(0.0, -y, y - meta.height_px) * h_m / meta.height_px
    return math.hypot(dx, dy)


def find_track_only(
    meta: ImageMeta,
    positions: dict[str, LatLon],
    matches: list[TrackMatch],
    edge_margin_m: float = EDGE_MARGIN_M,
) -> list[TrackOnlyVehicle]:
    """Tracks at capture time inside the frame (or within `edge_margin_m` of it) with no match."""
    matched = {m.track_id for m in matches if m.track_id}
    out: list[TrackOnlyVehicle] = []
    for tid, pos in sorted(positions.items()):
        if tid in matched:
            continue
        x, y = latlon_to_pixel(pos, meta)
        edge = _edge_distance_m(x, y, meta)
        if edge > edge_margin_m:
            continue
        out.append(
            TrackOnlyVehicle(
                track_id=tid,
                position=pos,
                center_px=(round(x, 1), round(y, 1)),
                hypothesis="missed" if edge == 0 else "outside_near_edge",
                edge_distance_m=round(edge, 1),
            )
        )
    return out


def score_track_only(
    vehicle: TrackOnlyVehicle,
    motion: MotionProfile,
    base: LatLon,
    behavior: BehaviorClass = "unknown",
    group_size: int = 1,
) -> VehicleRisk:
    """The normal rubric (`risk_svc.score_vehicle`) on a stand-in detection `TRK-<id>`."""
    stand_in = Detection(
        id=f"TRK-{vehicle.track_id}",
        label=TRACK_ONLY_LABEL,
        confidence=0.0,
        bbox=(round(vehicle.center_px[0]), round(vehicle.center_px[1]), 0, 0),
        center_px=vehicle.center_px,
        position=vehicle.position,
        distance_to_base_m=round(haversine_m(base, vehicle.position)),
        bearing_from_base_deg=round(bearing_deg(base, vehicle.position), 1),
    )
    match = TrackMatch(
        detection_id=stand_in.id,
        track_id=vehicle.track_id,
        distance_m=0.0,
        second_best_m=None,
        confidence="none",
    )
    risk = risk_svc.score_vehicle(stand_in, match, motion, [], {}, behavior, group_size)
    note = (
        "inside the frame but not detected"
        if vehicle.hypothesis == "missed"
        else f"{vehicle.edge_distance_m:.0f} m outside the frame edge"
    )
    return risk.model_copy(
        update={
            "factors": [*risk.factors, RiskFactor(name="not_seen_in_image", points=0, detail=note)]
        }
    )


def explain_unmatched_detections(
    detections: list[Detection], matches: list[TrackMatch], low_confidence: float = LOW_CONFIDENCE
) -> list[UnmatchedDetectionNote]:
    """Detections without a track: parked vehicles have no track; weak boxes may be false."""
    unmatched = {m.detection_id for m in matches if m.track_id is None}
    notes: list[UnmatchedDetectionNote] = []
    for d in detections:
        if d.id not in unmatched:
            continue
        if d.confidence < low_confidence:
            notes.append(
                UnmatchedDetectionNote(
                    detection_id=d.id,
                    hypothesis="false_positive_likely",
                    reason=f"no track and low confidence {d.confidence:.2f}",
                )
            )
        else:
            notes.append(
                UnmatchedDetectionNote(
                    detection_id=d.id,
                    hypothesis="parked_likely",
                    reason="no track: parked vehicles may have no recorded route",
                )
            )
    return notes
