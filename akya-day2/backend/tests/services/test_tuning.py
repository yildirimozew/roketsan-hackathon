"""AgentTuning defaults, override diffs and validation (spec §3.1)."""

import pytest
from pydantic import ValidationError

from app.domain.tuning import Tier
from app.services import behavior, risk
from app.services.tuning import (
    DEFAULT_TUNING,
    apply_overrides,
    overridden_paths,
    overrides_of,
    tuning_hash,
    tuning_problems,
)


def test_defaults_equal_todays_constants() -> None:
    t = DEFAULT_TUNING
    assert t.behavior.loop_sweep_deg == behavior.LOOP_SWEEP_DEG
    assert t.behavior.orbit_max_range_m == behavior.ORBIT_MAX_RANGE_M
    assert t.groups.large_group == behavior.LARGE_GROUP
    assert t.groups.group_radius_m == behavior.GROUP_RADIUS_M
    assert [(x.limit, x.points) for x in t.rubric.distance_tiers] == [
        (1000, 30),
        (2000, 20),
        (4000, 10),
    ]
    assert [(x.limit, x.points) for x in t.rubric.approach_rate_tiers] == [(80, 15), (50, 8)]
    assert t.rubric.pattern_points.loops_around_base == risk.PATTERN_POINTS["loops_around_base"]
    assert t.rubric.type_points.truck == risk.TYPE_POINTS["truck"]
    assert t.rubric.group_points == risk.GROUP_POINTS
    assert t.rubric.level_step == 25
    assert t.ceiling.at_base_m == risk.AT_BASE_M
    assert t.ceiling.arrived_from_m == risk.ARRIVED_FROM_M
    assert t.behavior.probe_range_m == behavior.PROBE_RANGE_M
    assert t.behavior.stakeout_min == behavior.STAKEOUT_MIN
    assert t.rubric.pattern_points.probing_return == risk.PATTERN_POINTS["probing_return"]
    assert t.judgment.closing_min_m_per_min == 100
    assert t.agents.watcher_max_tool_calls is None
    assert t.prompts.watcher is None and t.prompts.supervisor is None


def test_default_has_no_overrides() -> None:
    assert overrides_of(DEFAULT_TUNING) == {}
    assert overridden_paths(DEFAULT_TUNING) == []
    assert apply_overrides({}) == DEFAULT_TUNING


def test_overrides_store_only_changed_leaves() -> None:
    t = DEFAULT_TUNING.model_copy(
        update={"ceiling": DEFAULT_TUNING.ceiling.model_copy(update={"at_base_m": 1500.0})}
    )
    assert overrides_of(t) == {"ceiling": {"at_base_m": 1500.0}}
    assert overridden_paths(t) == ["ceiling.at_base_m"]
    assert apply_overrides(overrides_of(t)) == t


def test_tier_lists_are_one_leaf() -> None:
    tiers = [Tier(limit=900, points=30), Tier(limit=2000, points=20), Tier(limit=4000, points=10)]
    t = DEFAULT_TUNING.model_copy(
        update={"rubric": DEFAULT_TUNING.rubric.model_copy(update={"distance_tiers": tiers})}
    )
    assert overridden_paths(t) == ["rubric.distance_tiers"]
    assert apply_overrides(overrides_of(t)) == t


def test_unknown_key_is_rejected() -> None:
    with pytest.raises(ValidationError):
        apply_overrides({"ceiling": {"no_such_field": 1}})


def test_hash_changes_with_values() -> None:
    changed = DEFAULT_TUNING.model_copy(
        update={"groups": DEFAULT_TUNING.groups.model_copy(update={"large_group": 3})}
    )
    assert tuning_hash(DEFAULT_TUNING) == tuning_hash(DEFAULT_TUNING.model_copy())
    assert tuning_hash(changed) != tuning_hash(DEFAULT_TUNING)
    assert len(tuning_hash(DEFAULT_TUNING)) == 8


def test_defaults_are_valid() -> None:
    assert tuning_problems(DEFAULT_TUNING) == []


def _with(section: str, **values: object):  # type: ignore[no-untyped-def]
    sub = getattr(DEFAULT_TUNING, section).model_copy(update=values)
    return DEFAULT_TUNING.model_copy(update={section: sub})


@pytest.mark.parametrize(
    ("tuning", "problem"),
    [
        (_with("behavior", parked_max_path_m=0.0), "behavior.parked_max_path_m: positive"),
        (_with("groups", large_group=1), "groups.large_group: range 2-50"),
        (_with("rubric", group_points=120), "rubric.group_points: range 0-100"),
        (_with("rubric", level_step=0), "rubric.level_step: range 1-50"),
        (
            _with(
                "rubric",
                distance_tiers=[
                    Tier(limit=2000, points=30),
                    Tier(limit=1000, points=20),
                    Tier(limit=4000, points=10),
                ],
            ),
            "rubric.distance_tiers: increasing",
        ),
        (
            _with("rubric", distance_tiers=[Tier(limit=1000, points=30)]),
            "rubric.distance_tiers: tier_count 3",
        ),
        (
            _with(
                "rubric",
                approach_rate_tiers=[Tier(limit=50, points=15), Tier(limit=80, points=8)],
            ),
            "rubric.approach_rate_tiers: decreasing",
        ),
        (
            _with("behavior", stakeout_near_m=6000.0),
            "behavior.stakeout_near_m: not_above ceiling.pattern_high_m",
        ),
        (_with("ceiling", arrived_from_m=0.0), "ceiling.arrived_from_m: positive"),
        (_with("ceiling", approach_heading_deg=200.0), "ceiling.approach_heading_deg: range 0-180"),
        (_with("agents", watcher_max_tool_calls=11), "agents.watcher_max_tool_calls: range 0-10"),
    ],
)
def test_problems(tuning, problem: str) -> None:  # type: ignore[no-untyped-def]
    assert problem in tuning_problems(tuning)
