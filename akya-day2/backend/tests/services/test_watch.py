"""Watch-mode facts: sectors, layout, behavior classes, rows and one-liners."""

import math

import pytest

from app.domain.geo import LatLon
from app.domain.scene import Zone
from app.domain.track import Track, TrackPoint
from app.domain.watch import VehicleRow
from app.services import watch as w

BASE = LatLon(lat=39.92184, lon=32.85306)
M_LAT = 1 / 111_320  # degrees per meter north
M_LON = 1 / (111_320 * 0.7669)  # degrees per meter east at this latitude


def at(east_m: float, north_m: float) -> LatLon:
    return LatLon(lat=BASE.lat + north_m * M_LAT, lon=BASE.lon + east_m * M_LON)


ZONES = [
    Zone(name=n, center=at(3200 * dx, 3200 * dy))
    for n, dx, dy in [
        ("N", 0, 1),
        ("NE", 0.707, 0.707),
        ("E", 1, 0),
        ("SE", 0.707, -0.707),
        ("S", 0, -1),
        ("SW", -0.707, -0.707),
        ("W", -1, 0),
        ("NW", -0.707, 0.707),
    ]
]


def track(points: list[tuple[float, float]], start: int = 12 * 60) -> Track:
    return Track(
        track_id="T1",
        points=[
            TrackPoint(
                time=f"{(start + 5 * i) // 60:02d}:{(start + 5 * i) % 60:02d}",
                time_min=start + 5 * i,
                position=at(e, n),
            )
            for i, (e, n) in enumerate(points)
        ],
    )


def test_sector_is_nearest_zone() -> None:
    assert w.sector_of(at(3000, 200), ZONES) == "E"
    assert w.sector_of(at(-100, 500), ZONES) == "N"


def test_watcher_groups_are_contiguous_clockwise_from_north() -> None:
    four = w.watcher_groups(ZONES, BASE, 4)
    assert four == {"W1": ["N", "NE"], "W2": ["E", "SE"], "W3": ["S", "SW"], "W4": ["W", "NW"]}
    three = w.watcher_groups(ZONES, BASE, 3)
    assert [len(g) for g in three.values()] == [3, 3, 2]
    assert w.watcher_groups(ZONES, BASE, 8)["W3"] == ["E"]
    assert w.watcher_groups(ZONES, BASE, 20) == w.watcher_groups(ZONES, BASE, 8)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ([(5000, 0)] * 10, "parked"),
        ([(7000 - 600 * i, 0) for i in range(10)], "steady_approach"),
        ([(500, 0)] * 4 + [(500 + 700 * i, 0) for i in range(1, 6)], "leaving_base"),
        (
            [(900 * math.cos(a / 3), 900 * math.sin(a / 3)) for a in range(20)],
            "loops_around_base",
        ),
        ([(3000, 0), (3000, 100)], "unknown"),
    ],
)
def test_behavior_class(path: list[tuple[float, float]], expected: str) -> None:
    assert w.behavior_class(track(path).points, BASE) == expected


def test_track_until_needs_a_sample_at_the_tick() -> None:
    t = track([(5000, 0), (4000, 0), (3000, 0)])  # 12:00, 12:05, 12:10
    assert w.track_until(t, 12 * 60 + 5) is not None
    assert w.track_until(t, 12 * 60 + 7) is None
    assert w.track_until(t, 12 * 60 + 15) is None


def test_vehicle_row_closing_vehicle() -> None:
    t = track([(6300, 0)] * 8 + [(5000, 0), (3800, 0)])  # parked 40 min, then drives at base
    row = w.vehicle_row(
        t,
        t.points[-1].time_min,
        BASE,
        ZONES,
        stop_speed_ms=1.0,
        zone_radius_m=2000,
        prev_sector="E",
        registry_level="LOW",
        pending_level=None,
        notes_count=0,
        lang="en",
    )
    assert row.sector == "E" and row.status == "staying" and row.moving
    assert row.closing_last5_m_per_min == 240
    assert row.heading_vs_base_deg == 0
    assert row.long_stops_within_6km == 0  # the stop was 6.3 km out, not within 6 km
    assert row.one_liner.startswith("T1 · 3.8 km E · closing 240 m/min · heading at base")


def test_parked_row_has_no_heading_and_counts_current_stop() -> None:
    t = track([(4000, 0), (2000, 0)] + [(1600, 0)] * 6)
    row = w.vehicle_row(
        t,
        t.points[-1].time_min,
        BASE,
        ZONES,
        stop_speed_ms=1.0,
        zone_radius_m=2000,
        prev_sector=None,
        registry_level="LOW",
        pending_level=None,
        notes_count=0,
        lang="tr",
    )
    assert not row.moving and row.heading_deg is None and row.eta_to_base_min is None
    assert row.current_stop_min == 30
    assert "30 dk duruyor" in row.one_liner and "1,6 km D" in row.one_liner


def test_ticks_are_five_minutes_inclusive() -> None:
    assert w.ticks(13 * 60 + 52, 14 * 60 + 5) == [835, 840, 845]


def _row(points: list[tuple[float, float]]) -> "VehicleRow":
    t = track(points)
    return w.vehicle_row(
        t,
        t.points[-1].time_min,
        BASE,
        ZONES,
        stop_speed_ms=1.0,
        zone_radius_m=2000,
        prev_sector="E",
        registry_level="LOW",
        pending_level=None,
        notes_count=0,
        lang="en",
    )


def test_ceiling_favours_recon_signs_over_normal_driving() -> None:
    fast_close = _row([(1400 + 1800 * (9 - i), 0) for i in range(10)])  # 6 m/s, 1.4 km out
    assert fast_close.max_level == "HIGH"  # a final approach right at the base
    normal = _row([(2800 + 1500 * (9 - i), 0) for i in range(10)])  # 5 m/s, 2.8 km out
    assert normal.max_level == "LOW"  # normal driving speed toward the base is traffic
    slow = _row([(6000 - 60 * i, 0) for i in range(10)])  # slow approach, 5.5 km out
    assert slow.max_level == "LOW" and w.gated_level("HIGH", slow) == "LOW"
    loop = _row([(900 * math.cos(a / 3), 900 * math.sin(a / 3)) for a in range(20)])
    assert loop.behavior_class == "loops_around_base" and loop.max_level == "HIGH"
    assert any(f.name == "pattern" and f.points > 0 for f in loop.rubric.factors)


def test_probing_and_stakeout_are_reconnaissance_signs() -> None:
    def east(*km: float) -> list[tuple[float, float]]:
        return [(1000 * k, 0) for k in km]

    # in to 2 km, out to 6 km, back to 3.5 km: probing, MEDIUM
    probe = _row(east(7, 5, 3, 2, 2, 4, 6, 6, 4.5, 3.5))
    assert probe.behavior_class == "probing_return" and probe.max_level == "MEDIUM"
    # the same after coming within 1 km: HIGH
    near_probe = _row(east(6, 3, 0.9, 0.9, 3, 5, 5, 4, 2.8))
    assert near_probe.behavior_class == "probing_return" and near_probe.max_level == "HIGH"
    # wandering back and forth 3-5 km out is common and not probing
    wander = _row(east(5, 4, 3.2, 4.5, 5.5, 4.2, 3.4))
    assert wander.behavior_class != "probing_return"
    # drove in from 5 km, parked 800 m out for 20 minutes, now 2.5 km out: stakeout, MEDIUM
    stake = _row(east(5, 3, 0.8, 0.8, 0.8, 0.8, 0.8, 1.5, 2.5))
    assert stake.behavior_class == "perimeter_stakeout" and stake.max_level == "MEDIUM"


def test_the_bases_own_traffic_is_low() -> None:
    parked = _row([(600, 0)] * 8)  # parked 600 m out from the start
    assert parked.behavior_class == "parked" and parked.max_level == "LOW"
    leaving = _row([(600, 0)] * 6 + [(1200, 0), (2000, 0), (3000, 0)])
    assert leaving.behavior_class == "leaving_base" and leaving.max_level == "LOW"


def test_moving_groups_need_to_travel_together_not_just_meet() -> None:
    from app.services.behavior import moving_groups

    def tr(tid: str, pts: list[tuple[float, float]]) -> Track:
        t = track(pts)
        return t.model_copy(update={"track_id": tid})

    # four vehicles driving side by side for 15 minutes: one group of 4
    convoy = [tr(f"C{i}", [(3000 + 100 * i, 4000 - 800 * k) for k in range(4)]) for i in range(4)]
    # four vehicles from four directions that only meet at the last sample (a frame's footprint)
    meet = [
        tr(f"M{i}", [(-3000 + 1000 * k * dx, 3000 + 1000 * k * dy) for k in range(4)])
        for i, (dx, dy) in enumerate([(1, 0), (0, -1), (1, -1), (0.5, -1)])
    ]
    groups = moving_groups([*convoy, *meet], convoy[0].points[-1].time_min)
    assert groups["C0"] == ["C0", "C1", "C2", "C3"]
    assert not any(t.startswith("M") for t in groups)


def test_other_vehicles_are_medium_only_in_a_large_group() -> None:
    from app.services.risk import level_ceiling

    args = (2700.0, False, None, None, "mixed_transit")
    assert level_ceiling(*args) == "LOW"
    assert level_ceiling(*args, group_size=3) == "LOW"
    assert level_ceiling(*args, group_size=4) == "MEDIUM"
