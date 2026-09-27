"""Watch-mode facts per tick (docs/AGENT_PROMPTS_AND_TOOLS.md §3). Pure and deterministic.

Sectors, per-vehicle rows, behavior class, the track-only rubric, one-line summaries and report
lookups. Distances in meters, speeds in m/s, rates in m/min, bearings in degrees from north.
"""

import math
from typing import Literal

from app.core.timefmt import to_minutes
from app.domain.detection import Detection
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.report import ReportClaim
from app.domain.risk import RiskFactor, RiskLevel
from app.domain.scene import Zone
from app.domain.track import MotionProfile, Track, TrackPoint
from app.domain.tuning import AgentTuning
from app.domain.watch import (
    WATCH_LEVELS,
    BehaviorClass,
    ExpectedVehicle,
    FrameDetection,
    ReportLookup,
    Rubric,
    VehicleRow,
    VehicleStatus,
    WatchLevel,
)
from app.services.behavior import behavior_class
from app.services.geo import angle_diff_deg, bearing_deg, haversine_m, pixel_to_latlon
from app.services.motion import motion_profile
from app.services.reports import normalize
from app.services.risk import (
    distance_factor,
    group_factor,
    level_ceiling,
    level_for,
    motion_factors,
    pattern_factor,
)
from app.services.tracks import match_detections, tracks_at
from app.services.tuning import DEFAULT_TUNING

WATCH_LEVEL_OF: dict[RiskLevel, WatchLevel] = {
    "LOW": "LOW",
    "MEDIUM": "MEDIUM",
    "HIGH": "HIGH",
    "CRITICAL": "HIGH",
}
TICK_MIN = 5
MOVING_STEP_M = 30.0  # moved more than this during the last tick => moving
LONG_STOP_MIN = 20
NEAR_BASE_M = 6000.0

Lang = Literal["tr", "en"]
_COMPASS = {
    "en": ("N", "NE", "E", "SE", "S", "SW", "W", "NW"),
    "tr": ("K", "KD", "D", "GD", "G", "GB", "B", "KB"),
}


def sector_of(p: LatLon, zones: list[Zone]) -> str:
    """Sector = name of the nearest zone center (no radius, so every point has one)."""
    return min(zones, key=lambda z: haversine_m(p, z.center)).name


def watcher_groups(zones: list[Zone], base: LatLon, count: int) -> dict[str, list[str]]:
    """Watcher id -> its sectors: zones ordered clockwise from north, split into `count`
    contiguous groups as evenly as possible (8 zones, 4 watchers -> 2 neighbours each)."""
    ordered = [z.name for z in sorted(zones, key=lambda z: bearing_deg(base, z.center))]
    count = max(1, min(count, len(ordered)))
    groups: dict[str, list[str]] = {}
    start = 0
    for i in range(count):
        size = len(ordered) // count + (1 if i < len(ordered) % count else 0)
        groups[f"W{i + 1}"] = ordered[start : start + size]
        start += size
    return groups


def track_until(track: Track, minute: int) -> Track | None:
    """The track up to `minute`, or None unless it has a sample exactly at `minute`."""
    points = [p for p in track.points if p.time_min <= minute]
    if not points or points[-1].time_min != minute:
        return None
    return Track(track_id=track.track_id, points=points)


def track_rubric(
    motion: MotionProfile,
    vehicle_type: str | None = None,
    behavior: BehaviorClass = "unknown",
    group_size: int = 1,
    tuning: AgentTuning = DEFAULT_TUNING,
) -> Rubric:
    """Rubric from the track (AGENT_DESIGN §3 step 7) plus vehicle-type points when a frame
    detection gave the type; report points are left to the agents."""
    rubric = tuning.rubric
    factors = [
        distance_factor(motion.dist_now_m, rubric),
        *motion_factors(motion, rubric),
        pattern_factor(behavior, rubric),
        group_factor(group_size, rubric, tuning.groups.large_group),
    ]
    if vehicle_type is not None:
        factors.append(
            RiskFactor(
                name="vehicle_type",
                points=rubric.type_points.model_dump().get(vehicle_type, 0),
                detail=vehicle_type,
            )
        )
    score = min(100, sum(f.points for f in factors))
    return Rubric(score=score, level=level_for(score, rubric), factors=factors)


def row_ceiling(
    row: VehicleRow,
    tuning: AgentTuning = DEFAULT_TUNING,
    start_m: float | None = None,
    closest_m: float | None = None,
) -> WatchLevel:
    """Highest level this vehicle may get (`services.risk.level_ceiling` on the row's facts;
    `start_m` / `closest_m`: distance when first seen / closest approach so far, m)."""
    closing_now = row.moving and row.closing_last5_m_per_min > 0
    return level_ceiling(
        row.dist_to_base_m,
        closing_now,
        row.heading_vs_base_deg,
        row.eta_to_base_min,
        row.behavior_class,
        len(row.group_ids) + 1,
        start_m=start_m,
        closest_m=closest_m,
        cfg=tuning.ceiling,
        large_group=tuning.groups.large_group,
    )


def gated_level(level: WatchLevel, row: VehicleRow) -> WatchLevel:
    """`level` limited to the vehicle's ceiling (`row.max_level`)."""
    return min(level, row.max_level, key=WATCH_LEVELS.index)


def rubric_watch_level(row: VehicleRow) -> WatchLevel:
    """The rubric's level on the watch scale (CRITICAL -> HIGH), limited by the ceiling."""
    return gated_level(WATCH_LEVEL_OF[row.rubric.level], row)


def watch_level_of(level: RiskLevel) -> WatchLevel:
    """Map the four rubric levels onto the three watch levels (CRITICAL -> HIGH)."""
    return WATCH_LEVEL_OF[level]


def closing_last_tick_m_per_min(points: list[TrackPoint], base: LatLon) -> int:
    """Distance change toward the base over the last tick (m/min, + = closing)."""
    if len(points) < 2:
        return 0
    a, b = points[-2], points[-1]
    span = max(1, b.time_min - a.time_min)
    return round((haversine_m(a.position, base) - haversine_m(b.position, base)) / span)


def current_stop_min(motion: MotionProfile, tick_min: int) -> int:
    """Length (min) of a stop that is still going on at `tick_min`, else 0."""
    for stop in reversed(motion.stops):
        if to_minutes(stop.start) + stop.duration_min - TICK_MIN >= tick_min:
            return stop.duration_min
    return 0


def compass_point(bearing: float, lang: Lang) -> str:
    """8-point compass label for a bearing (degrees from north)."""
    return _COMPASS[lang][round(bearing / 45) % 8]


def one_liner(row: VehicleRow, lang: Lang) -> str:
    """Instant code-made summary of one vehicle (shown before any model answers)."""
    km = f"{row.dist_to_base_m / 1000:.1f}"
    where = f"{km} km {compass_point(row.bearing_from_base_deg, lang)}"
    if lang == "tr":
        where = where.replace(".", ",")
    parts = [f"{row.track_id} ({row.vehicle_type})" if row.vehicle_type else row.track_id, where]
    if not row.moving:
        stop = row.current_stop_min
        parts.append(
            (f"{stop} dk duruyor" if lang == "tr" else f"parked {stop} min")
            if stop
            else ("duruyor" if lang == "tr" else "stationary")
        )
    elif row.closing_last5_m_per_min > 0:
        rate = row.closing_last5_m_per_min
        parts.append(f"{rate} m/dk yaklaşıyor" if lang == "tr" else f"closing {rate} m/min")
    else:
        rate = -row.closing_last5_m_per_min
        parts.append(f"{rate} m/dk uzaklaşıyor" if lang == "tr" else f"moving away {rate} m/min")
    if row.heading_vs_base_deg is not None and row.heading_vs_base_deg < 30:
        parts.append("üsse yönelmiş" if lang == "tr" else "heading at base")
    if row.long_stops_within_6km:
        n = row.long_stops_within_6km
        parts.append(f"{n} uzun duruş" if lang == "tr" else f"{n} long stop{'s' * (n > 1)}")
    return " · ".join(parts)


def vehicle_row(
    track: Track,
    tick_min: int,
    base: LatLon,
    zones: list[Zone],
    *,
    stop_speed_ms: float,
    zone_radius_m: float,
    prev_sector: str | None,
    registry_level: WatchLevel,
    pending_level: WatchLevel | None,
    notes_count: int,
    lang: Lang,
    vehicle_type: str | None = None,
    group: list[str] | None = None,
    tuning: AgentTuning = DEFAULT_TUNING,
) -> VehicleRow:
    """All facts about one vehicle at a tick. `track` must end exactly at `tick_min`."""
    motion = motion_profile(track, tick_min, base, zones, stop_speed_ms, zone_radius_m)
    behavior = behavior_class(track.points, base, tuning.behavior)
    others = [t for t in group or [] if t != track.track_id]
    here = track.points[-1].position
    sector = sector_of(here, zones)
    last_step_m = haversine_m(track.points[-2].position, here) if len(track.points) > 1 else 0.0
    moving = last_step_m > MOVING_STEP_M
    heading = motion.heading_deg if moving else None
    status: VehicleStatus = (
        "new_track"
        if len(track.points) == 1
        else "new_in_sector"
        if prev_sector is not None and prev_sector != sector
        else "staying"
    )
    long_stops = [
        s
        for s in motion.stops
        if s.duration_min >= tuning.rubric.long_stop_min
        and s.distance_to_base_m <= tuning.rubric.stop_near_base_m
    ]
    row = VehicleRow(
        track_id=track.track_id,
        vehicle_type=vehicle_type,
        status=status,
        position=LatLon(lat=round(here.lat, 6), lon=round(here.lon, 6)),
        sector=sector,
        dist_to_base_m=round(motion.dist_now_m),
        bearing_from_base_deg=round(bearing_deg(base, here)) % 360,
        moving=moving,
        speed_last10_ms=motion.last10_speed_ms,
        heading_deg=heading,
        heading_vs_base_deg=(
            None if heading is None else round(angle_diff_deg(heading, motion.bearing_to_base_deg))
        ),
        approach_rate_60m_m_per_min=motion.approach_rate_m_per_min,
        closing_last5_m_per_min=closing_last_tick_m_per_min(track.points, base),
        eta_to_base_min=motion.eta_to_base_min if moving else None,
        current_stop_min=0 if moving else current_stop_min(motion, tick_min),
        long_stops_within_6km=len(long_stops),
        behavior_class=behavior,
        rubric=track_rubric(motion, vehicle_type, behavior, len(others) + 1, tuning),
        group_ids=others,
        registry_level=registry_level,
        pending_level=pending_level,
        notes_count=notes_count,
        one_liner="",
    )
    dists = [haversine_m(p.position, base) for p in track.points]
    ceiling = row_ceiling(row, tuning, start_m=dists[0], closest_m=min(dists))
    row = row.model_copy(update={"max_level": ceiling})
    return row.model_copy(update={"one_liner": one_liner(row, lang)})


def claim_sector(claim: ReportClaim, zones: list[Zone]) -> str | None:
    """Sector a report is about: its coordinates, else a zone it names, else None."""
    if claim.location is not None:
        return sector_of(claim.location, zones)
    return claim.zone


def claims_between(claims: list[ReportClaim], start_min: int, end_min: int) -> list[ReportClaim]:
    """Claims with report time in (start_min, end_min]."""
    return [c for c in claims if start_min < c.time_min <= end_min]


def claims_for_sectors(
    claims: list[ReportClaim], sectors: list[str], zones: list[Zone]
) -> list[ReportClaim]:
    """Cheap prefilter: claims whose location or named zone falls in one of `sectors`."""
    return [c for c in claims if claim_sector(c, zones) in sectors]


def area_claims(claims: list[ReportClaim]) -> list[ReportClaim]:
    """Claims without a location or zone: area-wide, judged by the supervisor."""
    return [c for c in claims if c.location is None and c.zone is None]


def reports_near(
    claims: list[ReportClaim],
    point: LatLon,
    radius_m: float,
    since_min: int,
    until_min: int,
    tracks: list[Track],
) -> list[ReportLookup]:
    """Located claims within `radius_m` of `point` and in [since, until], each checked against
    the tracks at the report's own time (nearest tracked vehicle to the claimed spot)."""
    out: list[ReportLookup] = []
    for c in claims:
        if c.location is None or not since_min <= c.time_min <= until_min:
            continue
        dist = haversine_m(c.location, point)
        if dist > radius_m:
            continue
        positions = tracks_at(tracks, c.time_min)
        nearest = min(
            ((tid, haversine_m(p, c.location)) for tid, p in positions.items()),
            key=lambda x: x[1],
            default=None,
        )
        out.append(
            ReportLookup(
                claim=c,
                distance_to_query_m=round(dist),
                nearest_track_id=nearest[0] if nearest else None,
                nearest_track_m=round(nearest[1]) if nearest else None,
            )
        )
    return out


def in_frame(meta: ImageMeta, p: LatLon) -> bool:
    """True when `p` lies inside the frame's corner box."""
    lats = [c.lat for c in meta.corners.values()]
    lons = [c.lon for c in meta.corners.values()]
    return min(lats) <= p.lat <= max(lats) and min(lons) <= p.lon <= max(lons)


def frame_detections(
    detections: list[Detection],
    meta: ImageMeta,
    positions: dict[str, LatLon],
    max_match_m: float,
) -> list[FrameDetection]:
    """Georeference detector boxes and match them one-to-one to track positions at capture."""
    located = [
        d.model_copy(update={"position": pixel_to_latlon(d.center_px[0], d.center_px[1], meta)})
        for d in detections
    ]
    matches = {m.detection_id: m for m in match_detections(located, positions, max_match_m)}
    out: list[FrameDetection] = []
    for d in located:
        m = matches.get(d.id)
        out.append(
            FrameDetection(
                detection_id=d.id,
                label=d.label,
                confidence=round(d.confidence, 2),
                position=(
                    LatLon(lat=round(d.position.lat, 6), lon=round(d.position.lon, 6))
                    if d.position
                    else None
                ),
                track_id=m.track_id if m else None,
                match_m=round(m.distance_m, 1) if m and m.distance_m is not None else None,
            )
        )
    return out


def ticks(start_min: int, end_min: int) -> list[int]:
    """Tick minutes from start to end inclusive, every 5 minutes."""
    first = math.ceil(start_min / TICK_MIN) * TICK_MIN
    return list(range(first, end_min + 1, TICK_MIN))


# ---- operator-announced vehicles ----

EXPECTED_EARLY_MIN = 10  # an announced vehicle may show up this long before its window


def resolve_sector(name: str, zones: list[Zone]) -> str | None:
    """Zone name for what the operator or the model wrote ("Doğu Yolu" -> "Dogu Yolu")."""
    want = normalize(name).strip()
    return next((z.name for z in zones if normalize(z.name) == want), None)


def match_expected(
    expected: ExpectedVehicle,
    rows: list[VehicleRow],
    tracks: dict[str, Track],
    zones: list[Zone],
    taken: set[str],
) -> str | None:
    """The track an announced vehicle is: first seen in the announced sector within the window
    (from EXPECTED_EARLY_MIN before it), moving and closing on the base now; the earliest such
    track, never one already matched to another announcement."""
    lo = to_minutes(expected.arrive_from) - EXPECTED_EARLY_MIN
    hi = to_minutes(expected.arrive_to)
    best: tuple[int, str] | None = None
    for row in rows:
        if row.track_id in taken or not (row.moving and row.closing_last5_m_per_min > 0):
            continue
        first = tracks[row.track_id].points[0]
        if not lo <= first.time_min <= hi or sector_of(first.position, zones) != expected.sector:
            continue
        if best is None or first.time_min < best[0]:
            best = (first.time_min, row.track_id)
    return best[1] if best else None


def mark_expected(row: VehicleRow, expected: ExpectedVehicle) -> VehicleRow:
    """An announced vehicle's row: capped at LOW, with who announced it and when."""
    note = f"{expected.expected_id}: announced by the operator at {expected.announced_at}"
    return row.model_copy(
        update={"max_level": "LOW", "expected": f"{note}: {expected.description}"}
    )
