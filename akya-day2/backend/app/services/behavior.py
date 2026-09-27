"""Static behavior class of a route so far (classes from docs/figures/stage2_data_overview.png).

Pure; used by the watch rows and by the per-frame risk rubric. Distances in meters, bearings in
degrees from north.
"""

from itertools import combinations, pairwise

from app.domain.geo import LatLon
from app.domain.track import Track, TrackPoint
from app.domain.tuning import BehaviorTuning, GroupTuning
from app.domain.watch import BehaviorClass
from app.services.geo import bearing_deg, haversine_m

# The patterns that count as danger in themselves (looping around / orbiting the base).
DANGER_PATTERNS: tuple[BehaviorClass, ...] = ("loops_around_base", "fixed_range_orbit")
# Reconnaissance signs that are worth a closer look (MEDIUM; a probe that came within 1 km: HIGH).
RECON_SIGNS: tuple[BehaviorClass, ...] = ("probing_return", "perimeter_stakeout")

# Behavior classes (thresholds from docs/figures/stage2_data_overview.png)
PARKED_MAX_PATH_M = 300.0
LEAVING_START_M = 1300.0
LEAVING_GAIN_M = 1500.0
LOOP_SWEEP_DEG = 270.0
ORBIT_MIN_PATH_M = 12000.0
ORBIT_MAX_RANGE_M = 600.0
APPROACH_GAIN_M = 1500.0

# Reconnaissance signs besides circling (movement analysis, 27 Sep; see AGENT_DESIGN §3 step 7):
# approach, pull back, come back ("probing_return"): closer by PROBE_IN_M to within PROBE_RANGE_M,
# then away by PROBE_OUT_M, then closer again by PROBE_BACK_M.
# Wandering 3-5 km out is common in the data (about 1 in 8 vehicles goes back and forth there), so
# a probe must come within viewing range and pull back and return decisively: ~3% of vehicles.
PROBE_IN_M = 1500.0
PROBE_OUT_M = 3000.0
PROBE_BACK_M = 2000.0
PROBE_RANGE_M = 2500.0
# Drove in and parked by the perimeter ("perimeter_stakeout"): a stop of STAKEOUT_MIN+ within
# STAKEOUT_NEAR_M of the base, after coming in from STAKEOUT_ARRIVAL_M farther out (cars parked
# there all along are "parked" / "leaving_base": the base's own traffic).
STAKEOUT_NEAR_M = 1000.0
STAKEOUT_ARRIVAL_M = 1500.0
STAKEOUT_MIN = 15  # three stationary samples (5-minute steps)
STOP_STEP_M = 50.0  # moved less than this between samples: stopped
DEFAULT_BEHAVIOR = BehaviorTuning(
    parked_max_path_m=PARKED_MAX_PATH_M,
    leaving_start_m=LEAVING_START_M,
    leaving_gain_m=LEAVING_GAIN_M,
    loop_sweep_deg=LOOP_SWEEP_DEG,
    orbit_min_path_m=ORBIT_MIN_PATH_M,
    orbit_max_range_m=ORBIT_MAX_RANGE_M,
    approach_gain_m=APPROACH_GAIN_M,
    probe_in_m=PROBE_IN_M,
    probe_out_m=PROBE_OUT_M,
    probe_back_m=PROBE_BACK_M,
    probe_range_m=PROBE_RANGE_M,
    stakeout_near_m=STAKEOUT_NEAR_M,
    stakeout_arrival_m=STAKEOUT_ARRIVAL_M,
    stakeout_min=STAKEOUT_MIN,
    stop_step_m=STOP_STEP_M,
)


def probed(dists: list[float], cfg: BehaviorTuning = DEFAULT_BEHAVIOR) -> bool:
    """Approached, pulled back and came back (distances to the base in sample order, m)."""
    n = len(dists)
    for i in range(1, n):
        if dists[i] > cfg.probe_range_m or max(dists[:i]) - dists[i] < cfg.probe_in_m:
            continue
        for k in range(i + 1, n):
            if dists[k] - dists[i] >= cfg.probe_out_m and any(
                dists[k] - dists[j] >= cfg.probe_back_m for j in range(k + 1, n)
            ):
                return True
    return False


def staked_out(
    points: list[TrackPoint], dists: list[float], cfg: BehaviorTuning = DEFAULT_BEHAVIOR
) -> bool:
    """Drove in and then stopped STAKEOUT_MIN+ minutes within STAKEOUT_NEAR_M of the base."""
    i = 0
    while i < len(points) - 1:
        if haversine_m(points[i].position, points[i + 1].position) >= cfg.stop_step_m:
            i += 1
            continue
        j = i
        while (
            j < len(points) - 1
            and haversine_m(points[j].position, points[j + 1].position) < cfg.stop_step_m
        ):
            j += 1
        minutes = points[j].time_min - points[i].time_min
        arrived = i > 0 and max(dists[:i]) - dists[i] >= cfg.stakeout_arrival_m
        if minutes >= cfg.stakeout_min and dists[i] <= cfg.stakeout_near_m and arrived:
            return True
        i = j
    return False


def behavior_class(
    points: list[TrackPoint], base: LatLon, cfg: BehaviorTuning = DEFAULT_BEHAVIOR
) -> BehaviorClass:
    """Static classification of a route so far (see the overview figure for the classes)."""
    if len(points) < 3:
        return "unknown"
    dists = [haversine_m(p.position, base) for p in points]
    path = sum(haversine_m(a.position, b.position) for a, b in pairwise(points))
    bearings = [bearing_deg(base, p.position) for p in points]
    sweep, unwrapped = 0.0, 0.0
    for a, b in pairwise(bearings):
        unwrapped += (b - a + 180) % 360 - 180
        sweep = max(sweep, abs(unwrapped))
    if path < cfg.parked_max_path_m:
        return "parked"
    if dists[0] < cfg.leaving_start_m and dists[-1] - dists[0] > cfg.leaving_gain_m:
        return "leaving_base"
    if sweep > cfg.loop_sweep_deg:
        return "loops_around_base"
    if path > cfg.orbit_min_path_m and max(dists) - min(dists) < cfg.orbit_max_range_m:
        return "fixed_range_orbit"
    if probed(dists, cfg):
        return "probing_return"
    if staked_out(points, dists, cfg):
        return "perimeter_stakeout"
    if dists[0] - dists[-1] > cfg.approach_gain_m:
        return "steady_approach"
    return "mixed_transit"


# Moving together: at least LARGE_GROUP vehicles, each moving, pairwise linked when within
# GROUP_RADIUS_M at each of their last GROUP_SAMPLES positions. Vehicles that only meet at the end
# (every track ends inside its drone frame at capture time) do not count.
LARGE_GROUP = 4
GROUP_RADIUS_M = 500.0
GROUP_SAMPLES = 3  # 15 minutes at 5-minute steps
GROUP_MIN_MOVE_M = 150.0  # over those samples; parked cars are not a group
DEFAULT_GROUPS = GroupTuning(
    large_group=LARGE_GROUP, group_radius_m=GROUP_RADIUS_M, group_min_move_m=GROUP_MIN_MOVE_M
)


def moving_groups(
    tracks: list[Track], minute: int, cfg: GroupTuning = DEFAULT_GROUPS
) -> dict[str, list[str]]:
    """Track id -> ids of the vehicles moving with it (itself included), for groups of 2+.
    Only tracks with a sample exactly at `minute` take part."""
    recent: dict[str, list[TrackPoint]] = {}
    for tr in tracks:
        pts = [p for p in tr.points if p.time_min <= minute][-GROUP_SAMPLES:]
        if len(pts) < GROUP_SAMPLES or pts[-1].time_min != minute:
            continue
        if (
            sum(haversine_m(a.position, b.position) for a, b in pairwise(pts))
            < cfg.group_min_move_m
        ):
            continue
        recent[tr.track_id] = pts
    parent = {t: t for t in recent}

    def find(t: str) -> str:
        while parent[t] != t:
            parent[t] = parent[parent[t]]
            t = parent[t]
        return t

    for a, b in combinations(recent, 2):
        together = all(
            haversine_m(pa.position, pb.position) <= cfg.group_radius_m
            for pa, pb in zip(recent[a], recent[b], strict=True)
        )
        if together:
            parent[find(a)] = find(b)
    members: dict[str, list[str]] = {}
    for t in recent:
        members.setdefault(find(t), []).append(t)
    return {t: sorted(g) for g in members.values() if len(g) > 1 for t in g}
