"""Default tuning, override diffs and validation (spec §3.1-3.2). Pure; no I/O."""

import hashlib
from itertools import pairwise
from typing import Any

from app.domain.tuning import (
    AgentKnobs,
    AgentTuning,
    JudgmentTuning,
    PromptOverrides,
)
from app.services.behavior import DEFAULT_BEHAVIOR, DEFAULT_GROUPS
from app.services.risk import DEFAULT_CEILING, DEFAULT_RUBRIC

# A vehicle closing faster than this in the last tick is sent to the LLM in full.
DETAIL_CLOSING_M_PER_MIN = 100.0
DEFAULT_JUDGMENT = JudgmentTuning(closing_min_m_per_min=DETAIL_CLOSING_M_PER_MIN)

DEFAULT_TUNING = AgentTuning(
    behavior=DEFAULT_BEHAVIOR,
    groups=DEFAULT_GROUPS,
    rubric=DEFAULT_RUBRIC,
    ceiling=DEFAULT_CEILING,
    judgment=DEFAULT_JUDGMENT,
    agents=AgentKnobs(
        watcher_max_tool_calls=None,
        supervisor_max_tool_calls=None,
        watcher_spot_checks=None,
        watcher_reasoning_effort=None,
        supervisor_reasoning_effort=None,
        brief_language=None,
    ),
    prompts=PromptOverrides(watcher=None, supervisor=None),
)


def flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Nested dict -> {"a.b": leaf}; lists (rubric tiers) are one leaf."""
    out: dict[str, Any] = {}
    for key, value in data.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out |= flatten(value, f"{path}.")
        else:
            out[path] = value
    return out


def _nest(flat: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for path, value in flat.items():
        *parents, leaf = path.split(".")
        node = out
        for p in parents:
            node = node.setdefault(p, {})
        node[leaf] = value
    return out


def _merge(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in extra.items():
        out[key] = (
            _merge(out[key], value)
            if isinstance(value, dict) and isinstance(out.get(key), dict)
            else value
        )
    return out


def overrides_of(t: AgentTuning) -> dict[str, Any]:
    """Only the leaves that differ from DEFAULT_TUNING, nested (what the override file stores)."""
    default = flatten(DEFAULT_TUNING.model_dump(mode="json"))
    current = flatten(t.model_dump(mode="json"))
    return _nest({p: v for p, v in current.items() if default.get(p) != v})


def apply_overrides(overrides: dict[str, Any]) -> AgentTuning:
    """DEFAULT_TUNING with `overrides` merged in; raises ValidationError on unknown keys/types."""
    return AgentTuning.model_validate(_merge(DEFAULT_TUNING.model_dump(mode="json"), overrides))


def overridden_paths(t: AgentTuning) -> list[str]:
    """Dotted paths of the leaves that differ from DEFAULT_TUNING, sorted."""
    return sorted(flatten(overrides_of(t)))


def tuning_hash(t: AgentTuning) -> str:
    """Short stable hash of the whole tuning (logged at run start, analysis cache key)."""
    return hashlib.sha256(t.model_dump_json().encode("utf-8")).hexdigest()[:8]


_POSITIVE = (
    "behavior.parked_max_path_m",
    "behavior.leaving_start_m",
    "behavior.leaving_gain_m",
    "behavior.orbit_min_path_m",
    "behavior.orbit_max_range_m",
    "behavior.approach_gain_m",
    "behavior.probe_in_m",
    "behavior.probe_out_m",
    "behavior.probe_back_m",
    "behavior.probe_range_m",
    "behavior.stakeout_near_m",
    "behavior.stakeout_arrival_m",
    "behavior.stakeout_min",
    "behavior.stop_step_m",
    "groups.group_radius_m",
    "groups.group_min_move_m",
    "rubric.long_stop_min",
    "rubric.stop_near_base_m",
    "ceiling.at_base_m",
    "ceiling.arrived_from_m",
    "ceiling.pattern_high_m",
    "ceiling.approach_high_m",
    "ceiling.approach_high_eta_min",
)
_RANGES: dict[str, tuple[float, float]] = {
    "behavior.loop_sweep_deg": (1, 1080),
    "groups.large_group": (2, 50),
    "rubric.heading_points": (0, 100),
    "rubric.heading_tolerance_deg": (0, 180),
    "rubric.stop_points_first": (0, 100),
    "rubric.stop_points_extra": (0, 100),
    "rubric.pattern_points.loops_around_base": (0, 100),
    "rubric.pattern_points.fixed_range_orbit": (0, 100),
    "rubric.pattern_points.probing_return": (0, 100),
    "rubric.pattern_points.perimeter_stakeout": (0, 100),
    "rubric.group_points": (0, 100),
    "rubric.type_points.truck": (0, 100),
    "rubric.type_points.bus": (0, 100),
    "rubric.type_points.van": (0, 100),
    "rubric.level_step": (1, 50),
    "ceiling.approach_heading_deg": (0, 180),
    "judgment.closing_min_m_per_min": (0, 10000),
    "agents.watcher_max_tool_calls": (0, 10),
    "agents.supervisor_max_tool_calls": (0, 10),
    "agents.watcher_spot_checks": (0, 10),
}
_NOT_ABOVE = (
    # a stakeout must be by the perimeter, not beyond where "near the base" ends
    ("behavior.stakeout_near_m", "ceiling.pattern_high_m"),
)


def _fmt(x: float) -> str:
    return f"{x:g}"


def _tier_problems(path: str, tiers: list[dict[str, Any]], count: int, rising: bool) -> list[str]:
    if len(tiers) != count:
        return [f"{path}: tier_count {count}"]
    problems = []
    limits = [t["limit"] for t in tiers]
    ordered = (
        all(a < b for a, b in pairwise(limits))
        if rising
        else all(a > b for a, b in pairwise(limits))
    )
    if not ordered:
        problems.append(f"{path}: {'increasing' if rising else 'decreasing'}")
    if any(lim <= 0 for lim in limits):
        problems.append(f"{path}: positive")
    if any(not 0 <= t["points"] <= 100 for t in tiers):
        problems.append(f"{path}: range 0-100")
    return problems


def tuning_problems(t: AgentTuning) -> list[str]:
    """Every rule the tuning breaks, as "<dotted.path>: <code> [arg]" (spec §3.1)."""
    flat = flatten(t.model_dump(mode="json"))
    problems = [f"{p}: positive" for p in _POSITIVE if flat[p] <= 0]
    for path, (lo, hi) in _RANGES.items():
        value = flat[path]
        if value is not None and not lo <= value <= hi:
            problems.append(f"{path}: range {_fmt(lo)}-{_fmt(hi)}")
    problems += _tier_problems("rubric.distance_tiers", flat["rubric.distance_tiers"], 3, True)
    problems += _tier_problems(
        "rubric.approach_rate_tiers", flat["rubric.approach_rate_tiers"], 2, False
    )
    for low, high in _NOT_ABOVE:
        if flat[low] > flat[high]:
            problems.append(f"{low}: not_above {high}")
    return problems
