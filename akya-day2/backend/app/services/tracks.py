"""Track interpolation and globally optimal detection-to-track matching (Hungarian)."""

from itertools import pairwise

import numpy as np
from scipy.optimize import linear_sum_assignment

from app.domain.detection import Detection, MatchConfidence, TrackMatch
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.track import MapTrack, Track
from app.services.geo import haversine_m


def position_at(track: Track, minute: float) -> LatLon | None:
    """Linearly interpolated position at `minute`; None outside the track's time span."""
    pts = track.points
    if not pts or minute < pts[0].time_min or minute > pts[-1].time_min:
        return None
    for a, b in pairwise(pts):
        if a.time_min <= minute <= b.time_min:
            span = b.time_min - a.time_min
            t = 0.0 if span == 0 else (minute - a.time_min) / span
            return LatLon(
                lat=a.position.lat + (b.position.lat - a.position.lat) * t,
                lon=a.position.lon + (b.position.lon - a.position.lon) * t,
            )
    return pts[-1].position


def tracks_at(tracks: list[Track], minute: float) -> dict[str, LatLon]:
    """Positions of all tracks that cover `minute`, keyed by track id."""
    out: dict[str, LatLon] = {}
    for track in tracks:
        pos = position_at(track, minute)
        if pos is not None:
            out[track.track_id] = pos
    return out


def _confidence(distance_m: float, second_best_m: float | None) -> MatchConfidence:
    margin = None if second_best_m is None else second_best_m - distance_m
    if distance_m <= 5 and (margin is None or margin >= 10):
        return "high"
    if distance_m <= 12:
        return "medium"
    return "low"


def match_detections(
    detections: list[Detection], positions: dict[str, LatLon], max_m: float
) -> list[TrackMatch]:
    """One-to-one assignment minimizing total distance (m); pairs farther than `max_m` are dropped.

    Detections must already have `position`. `second_best_m` is the next-closest track to the
    detection, used as a match-ambiguity signal.
    """
    located = [d for d in detections if d.position is not None]
    track_ids = list(positions)
    unmatched = [
        TrackMatch(
            detection_id=d.id, track_id=None, distance_m=None, second_best_m=None, confidence="none"
        )
        for d in detections
    ]
    if not located or not track_ids:
        return unmatched

    cost = np.array(
        [[haversine_m(d.position, positions[t]) for t in track_ids] for d in located]  # type: ignore[arg-type]
    )
    rows, cols = linear_sum_assignment(cost)
    assigned = dict(zip(rows.tolist(), cols.tolist(), strict=True))

    by_id: dict[str, TrackMatch] = {}
    for i, det in enumerate(located):
        row = sorted(cost[i].tolist())
        j = assigned.get(i)
        if j is None or cost[i, j] > max_m:
            by_id[det.id] = TrackMatch(
                detection_id=det.id,
                track_id=None,
                distance_m=round(row[0], 1),
                second_best_m=None,
                confidence="none",
            )
            continue
        dist = float(cost[i, j])
        others = sorted((float(c), k) for k, c in enumerate(cost[i].tolist()) if k != j)
        second = others[0][0] if others else None
        by_id[det.id] = TrackMatch(
            detection_id=det.id,
            track_id=track_ids[j],
            distance_m=round(dist, 1),
            second_best_m=None if second is None else round(second, 1),
            second_best_track_id=track_ids[others[0][1]] if others else None,
            confidence=_confidence(dist, second),
        )
    return [by_id.get(m.detection_id, m) for m in unmatched]


def map_tracks(tracks: list[Track], images: list[ImageMeta]) -> list[MapTrack]:
    """Tracks with the frame whose capture time equals their last sample (organizer's join)."""
    by_capture = {m.capture_min: m.image_id for m in images}
    return [
        MapTrack(
            track_id=t.track_id,
            points=t.points,
            image_id=by_capture.get(t.points[-1].time_min) if t.points else None,
        )
        for t in tracks
    ]
