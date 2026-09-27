"""Z3 - "stationary" from the data: drift over a window, not one 5-minute step.

Integration: add these to `backend/app/services/motion.py`; `services/reports.py:_moving_at`
(one step at 1 m/s) is replaced by `is_stationary` / `is_moving` through Z4. `MotionProfile.stops`
stays as is (the golden test's ~40 / ~45 min stops are calibrated on it).

Evidence (real data): over 60 min parked tracks drift at most 39 m, every other track moves at
least 1087 m, so 100 m sits in the gap (`drift_gap`).
"""

from itertools import pairwise

from app.domain.geo import LatLon
from app.domain.track import Track
from app.services.geo import haversine_m
from app.services.tracks import position_at

STATIONARY_MAX_M = 100.0  # max drift from the final position that still counts as "not moving"
MOVING_MIN_M = 100.0  # min path over the window to count as "moving"
STATIONARY_WINDOW_MIN = 30
LONG_STOP_WINDOW_MIN = 60  # "uzun suredir bekliyor"
MOVING_WINDOW_MIN = 30


def _window(track: Track, end_min: int, window_min: int) -> list[LatLon]:
    """Samples in [end - window, end], plus the interpolated position at `end_min`."""
    pts = [p.position for p in track.points if end_min - window_min <= p.time_min <= end_min]
    end = position_at(track, end_min)
    if end is not None and (not pts or pts[-1] != end):
        pts.append(end)
    return pts


def drift_m(track: Track, end_min: int, window_min: int) -> float | None:
    """Largest distance (m) from the position at `end_min` in the window; None if not covered."""
    end = position_at(track, end_min)
    if end is None:
        return None
    return max(haversine_m(p, end) for p in _window(track, end_min, window_min))


def path_m(track: Track, end_min: int, window_min: int) -> float | None:
    """Distance travelled (m) during the window; None if the track does not cover `end_min`."""
    if position_at(track, end_min) is None:
        return None
    return sum(haversine_m(a, b) for a, b in pairwise(_window(track, end_min, window_min)))


def is_stationary(
    track: Track, end_min: int, window_min: int = STATIONARY_WINDOW_MIN
) -> bool | None:
    """True when the vehicle stayed within STATIONARY_MAX_M of its final spot (None = no data)."""
    drift = drift_m(track, end_min, window_min)
    return None if drift is None else drift <= STATIONARY_MAX_M


def is_moving(track: Track, end_min: int, window_min: int = MOVING_WINDOW_MIN) -> bool | None:
    """True when the vehicle travelled at least MOVING_MIN_M in the window (None = no data)."""
    path = path_m(track, end_min, window_min)
    return None if path is None else path >= MOVING_MIN_M


def closing_m(track: Track, end_min: int, base: LatLon, window_min: int = 30) -> float | None:
    """Drop in distance to the base (m) over the window; + = closing. None if not covered."""
    end = position_at(track, end_min)
    if end is None:
        return None
    before = position_at(track, end_min - window_min) or track.points[0].position
    return haversine_m(before, base) - haversine_m(end, base)


def drift_gap(tracks: list[Track], window_min: int = 60) -> tuple[float, float]:
    """(largest drift below the threshold, smallest drift above it) at each track's last sample."""
    drifts = [
        d
        for t in tracks
        if t.points and (d := drift_m(t, t.points[-1].time_min, window_min)) is not None
    ]
    below = max((d for d in drifts if d <= STATIONARY_MAX_M), default=0.0)
    above = min((d for d in drifts if d > STATIONARY_MAX_M), default=float("inf"))
    return below, above
