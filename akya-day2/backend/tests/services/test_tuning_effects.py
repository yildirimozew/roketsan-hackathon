"""Changing one threshold changes the outcome; defaults keep today's outcome (spec §6)."""

import math

from app.data.repository import Repository
from app.domain.geo import LatLon
from app.domain.track import TrackPoint
from app.domain.tuning import Tier
from app.services import risk
from app.services.behavior import DEFAULT_BEHAVIOR, behavior_class
from app.services.geo import offset_m
from app.services.motion import motion_profile
from app.services.risk import DEFAULT_CEILING, DEFAULT_RUBRIC, level_ceiling, level_for
from app.services.tuning import DEFAULT_TUNING
from app.services.watch import track_rubric

BASE = LatLon(lat=39.93, lon=32.85)


def _arc(sweep_deg: float, radius_m: float = 2000, steps: int = 12) -> list[TrackPoint]:
    """Points on a circle around BASE covering `sweep_deg`, 5 minutes apart."""
    points = []
    for i in range(steps + 1):
        bearing = math.radians(sweep_deg * i / steps)
        minute = 600 + i * 5
        points.append(
            TrackPoint(
                time=f"{minute // 60:02d}:{minute % 60:02d}",
                time_min=minute,
                position=offset_m(BASE, radius_m * math.sin(bearing), radius_m * math.cos(bearing)),
            )
        )
    return points


def test_half_loop_is_a_loop_only_with_a_lower_sweep_threshold() -> None:
    half = _arc(200)
    assert behavior_class(half, BASE) != "loops_around_base"
    lower = DEFAULT_BEHAVIOR.model_copy(update={"loop_sweep_deg": 180.0})
    assert behavior_class(half, BASE, lower) == "loops_around_base"


def test_car_stopped_at_1500_m_may_be_high_only_with_a_wider_at_base_radius() -> None:
    wider = DEFAULT_CEILING.model_copy(update={"at_base_m": 2000.0})

    def ceiling(behavior: str, start_m: float, **kw: object) -> str:
        return level_ceiling(1500, False, None, None, behavior, start_m=start_m, **kw)  # type: ignore[arg-type]

    # drove in from 5 km and stopped 1.5 km out
    assert ceiling("steady_approach", 5000) == "LOW"
    assert ceiling("steady_approach", 5000, cfg=wider) == "HIGH"
    # parked there from the start: the base's own traffic, whatever the radius
    assert ceiling("parked", 1500, cfg=wider) == "LOW"


def test_three_vehicle_group_is_medium_only_with_large_group_three() -> None:
    def ceiling(**kw: object) -> str:
        return level_ceiling(8000, False, None, None, "mixed_transit", 3, **kw)  # type: ignore[arg-type]

    assert ceiling() == "LOW"
    assert ceiling(large_group=3) == "MEDIUM"
    assert risk.group_factor(3).points == 0
    assert risk.group_factor(3, large_group=3).points == risk.GROUP_POINTS


def test_level_step_moves_the_level_bands() -> None:
    assert level_for(30) == "MEDIUM"
    assert level_for(30, DEFAULT_RUBRIC.model_copy(update={"level_step": 40})) == "LOW"


def test_distance_tiers_are_read_from_the_rubric() -> None:
    assert risk.distance_factor(900).points == 30
    tiers = [Tier(limit=500, points=30), Tier(limit=2000, points=20), Tier(limit=4000, points=10)]
    custom = DEFAULT_RUBRIC.model_copy(update={"distance_tiers": tiers})
    assert risk.distance_factor(900, custom).points == 20


def test_track_rubric_uses_the_tuning(golden_repo: Repository) -> None:
    track = next(iter(golden_repo.tracks.values()))
    last = track.points[-1].time_min
    base, zones = golden_repo.scene.base.position, golden_repo.scene.zones
    motion = motion_profile(track, last, base, zones, 1.0, 2000)
    before = track_rubric(motion)
    rubric = DEFAULT_TUNING.rubric.model_copy(update={"level_step": 50, "heading_points": 0})
    tuned = DEFAULT_TUNING.model_copy(update={"rubric": rubric})
    after = track_rubric(motion, tuning=tuned)
    assert after.level == level_for(after.score, rubric)
    heading = next(f for f in after.factors if f.name == "heading_to_base")
    assert heading.points == 0
    assert before.score - after.score == next(
        f.points for f in before.factors if f.name == "heading_to_base"
    )


def _stop_track(stop_min: int) -> list[TrackPoint]:
    """Drives 2 km east of BASE, stops `stop_min` minutes, drives on; 5-minute samples."""
    east = [0, 1500, 3000] + [3000] * (stop_min // 5) + [4500, 6000]
    return [
        TrackPoint(
            time=f"{(600 + i * 5) // 60:02d}:{(600 + i * 5) % 60:02d}",
            time_min=600 + i * 5,
            position=offset_m(BASE, e, 0),
        )
        for i, e in enumerate(east)
    ]


def test_row_long_stop_count_follows_the_tuned_stop_length(golden_repo: Repository) -> None:
    from app.domain.track import Track
    from app.services.watch import vehicle_row

    points = _stop_track(15)
    track = Track(track_id="T9999", points=points)

    def row(tuning: object) -> object:
        return vehicle_row(
            track,
            points[-1].time_min,
            BASE,
            golden_repo.scene.zones,
            stop_speed_ms=1.0,
            zone_radius_m=2000,
            prev_sector=None,
            registry_level="LOW",
            pending_level=None,
            notes_count=0,
            lang="en",
            tuning=tuning,  # type: ignore[arg-type]
        )

    assert row(DEFAULT_TUNING).long_stops_within_6km == 1  # type: ignore[attr-defined]
    longer = DEFAULT_TUNING.model_copy(
        update={"rubric": DEFAULT_TUNING.rubric.model_copy(update={"long_stop_min": 30})}
    )
    assert row(longer).long_stops_within_6km == 0  # type: ignore[attr-defined]
