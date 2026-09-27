"""Motion features of one track over the 2 h window before capture (AGENT_DESIGN §3 step 5)."""

from itertools import pairwise

from app.domain.geo import LatLon
from app.domain.scene import Zone
from app.domain.track import MotionProfile, Stop, Track, TrackPoint
from app.services.geo import bearing_deg, haversine_m
from app.services.tracks import position_at

WINDOW_MIN = 120
SAMPLE_MIN = 5
MIN_STOP_MIN = 10
MIN_MOVE_M = 5.0  # below this a segment is jitter, not a heading


def nearest_zone(p: LatLon, zones: list[Zone], radius_m: float) -> str | None:
    """Name of the closest zone center within `radius_m`, else None."""
    best = min(zones, key=lambda z: haversine_m(p, z.center), default=None)
    if best is None or haversine_m(p, best.center) > radius_m:
        return None
    return best.name


def _mean_position(points: list[TrackPoint]) -> LatLon:
    return LatLon(
        lat=sum(p.position.lat for p in points) / len(points),
        lon=sum(p.position.lon for p in points) / len(points),
    )


def find_stops(
    points: list[TrackPoint],
    stop_speed_ms: float,
    base: LatLon,
    zones: list[Zone],
    zone_radius_m: float,
) -> list[Stop]:
    """Runs of consecutive segments slower than `stop_speed_ms` lasting ≥ 10 min (sample slots)."""
    stops: list[Stop] = []
    run: list[TrackPoint] = []

    def close_run() -> None:
        if len(run) >= 2 and len(run) * SAMPLE_MIN >= MIN_STOP_MIN:
            pos = _mean_position(run)
            stops.append(
                Stop(
                    start=run[0].time,
                    duration_min=min(WINDOW_MIN, len(run) * SAMPLE_MIN),
                    position=pos,
                    zone=nearest_zone(pos, zones, zone_radius_m),
                    distance_to_base_m=round(haversine_m(pos, base)),
                )
            )

    for a, b in pairwise(points):
        dt_s = (b.time_min - a.time_min) * 60
        speed = haversine_m(a.position, b.position) / dt_s if dt_s > 0 else 0.0
        if speed < stop_speed_ms:
            if not run:
                run.append(a)
            run.append(b)
        else:
            close_run()
            run = []
    close_run()
    return stops


def _path_m(points: list[TrackPoint]) -> float:
    return sum(haversine_m(a.position, b.position) for a, b in pairwise(points))


def motion_profile(
    track: Track,
    capture_min: int,
    base: LatLon,
    zones: list[Zone],
    stop_speed_ms: float,
    zone_radius_m: float,
) -> MotionProfile:
    """Speeds (m/s), distances (m), approach rate (m/min, + = closing), stops and ETA (min)."""
    window = [p for p in track.points if capture_min - WINDOW_MIN <= p.time_min <= capture_min]
    now = position_at(track, capture_min) or window[-1].position

    path_m = _path_m(window)
    span_s = (window[-1].time_min - window[0].time_min) * 60
    recent = [p for p in window if p.time_min >= capture_min - 10]
    recent_span_s = (recent[-1].time_min - recent[0].time_min) * 60 if len(recent) > 1 else 0

    heading: float | None = None
    for a, b in reversed(list(pairwise(window))):
        if haversine_m(a.position, b.position) >= MIN_MOVE_M:
            heading = round(bearing_deg(a.position, b.position), 1)
            break

    def dist_ago(minutes: int) -> float | None:
        pos = position_at(track, capture_min - minutes)
        return None if pos is None else round(haversine_m(pos, base))

    dist_now = haversine_m(now, base)
    d60 = dist_ago(60)
    ref_dist, ref_span = (
        (d60, 60)
        if d60 is not None
        else (haversine_m(window[0].position, base), max(1, capture_min - window[0].time_min))
    )
    approach = (ref_dist - dist_now) / ref_span
    last10 = _path_m(recent) / recent_span_s if recent_span_s else 0.0

    visited: list[str] = []
    for p in window:
        name = nearest_zone(p.position, zones, zone_radius_m)
        if name and name not in visited:
            visited.append(name)

    return MotionProfile(
        track_id=track.track_id,
        points=window,
        path_km=round(path_m / 1000, 2),
        mean_speed_ms=round(path_m / span_s, 2) if span_s else 0.0,
        last10_speed_ms=round(last10, 2),
        heading_deg=heading,
        bearing_to_base_deg=round(bearing_deg(now, base), 1),
        dist_now_m=round(dist_now),
        dist_30m_ago_m=dist_ago(30),
        dist_60m_ago_m=d60,
        min_dist_m=round(min([dist_now, *(haversine_m(p.position, base) for p in window)])),
        approach_rate_m_per_min=round(approach, 1),
        stops=find_stops(window, stop_speed_ms, base, zones, zone_radius_m),
        zones_visited=visited,
        eta_to_base_min=(
            round(dist_now / last10 / 60, 1) if approach > 0 and last10 >= 0.5 else None
        ),
    )
