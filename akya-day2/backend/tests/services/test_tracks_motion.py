import pytest

from app.core.timefmt import to_hhmm
from app.domain.detection import Detection
from app.domain.geo import LatLon
from app.domain.track import Track, TrackPoint
from app.services.geo import offset_m
from app.services.motion import find_stops, motion_profile
from app.services.tracks import match_detections, position_at

BASE = LatLon(lat=39.92184, lon=32.85306)


def track(tid: str, points: list[tuple[int, float, float]]) -> Track:
    """Track from (minute, east_m, north_m) offsets relative to BASE."""
    return Track(
        track_id=tid,
        points=[
            TrackPoint(time=to_hhmm(t), time_min=t, position=offset_m(BASE, e, n))
            for t, e, n in points
        ],
    )


def det(did: str, e: float, n: float) -> Detection:
    return Detection(
        id=did,
        label="car",
        confidence=0.9,
        bbox=(0, 0, 1, 1),
        center_px=(0, 0),
        position=offset_m(BASE, e, n),
    )


def test_position_interpolates_and_bounds() -> None:
    t = track("T1", [(600, 0, 0), (605, 100, 0)])
    mid = position_at(t, 602.5)
    assert mid is not None and mid.lon == pytest.approx(offset_m(BASE, 50, 0).lon)
    assert position_at(t, 599) is None and position_at(t, 606) is None


def test_hungarian_prefers_global_optimum_over_greedy() -> None:
    # Greedy would give DET-1 -> A (1 m) and leave DET-2 with B (19 m); optimum swaps them.
    positions = {"A": offset_m(BASE, 0, 0), "B": offset_m(BASE, 20, 0)}
    dets = [det("DET-1", 1, 0), det("DET-2", -9, 0)]
    matches = {m.detection_id: m for m in match_detections(dets, positions, max_m=25)}
    assert matches["DET-1"].track_id == "B"
    assert matches["DET-2"].track_id == "A"


def test_gate_rejects_far_tracks() -> None:
    (m,) = match_detections([det("DET-1", 0, 0)], {"A": offset_m(BASE, 100, 0)}, max_m=25)
    assert m.track_id is None and m.confidence == "none"
    assert m.distance_m == pytest.approx(100, abs=0.5)


def test_stop_duration_counts_sample_slots() -> None:
    t = track("T1", [(730 + 5 * i, 0, 0) for i in range(8)] + [(770, 1500, 0), (775, 3000, 0)])
    (stop,) = find_stops(t.points, 1.0, BASE, [], 2000)
    assert (stop.start, stop.duration_min) == ("12:10", 40)


def test_motion_profile_closing_vehicle() -> None:
    # Straight approach from 6 km east to 1 km east over 60 min, after 60 min parked.
    pts = [(600 + 5 * i, 6000, 0) for i in range(13)]
    pts += [(665 + 5 * i, 6000 - 5000 * (i + 1) / 12, 0) for i in range(12)]
    p = motion_profile(track("T1", pts), 720, BASE, [], 1.0, 2000)
    assert p.dist_now_m == pytest.approx(1000, abs=5)
    assert p.approach_rate_m_per_min == pytest.approx(5000 / 60, abs=1)
    assert p.heading_deg == pytest.approx(270, abs=1)
    assert p.bearing_to_base_deg == pytest.approx(270, abs=1)
    assert p.eta_to_base_min is not None
    assert [s.duration_min for s in p.stops] == [65]
