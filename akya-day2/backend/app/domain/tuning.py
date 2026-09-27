"""Admin-editable agent tuning: risk thresholds, agent knobs and prompt overrides (spec §3.1).

Models only; defaults live in services (`services/tuning.DEFAULT_TUNING`).
"""

from typing import Literal

from pydantic import ConfigDict

from app.domain.base import DomainModel

ReasoningEffort = Literal["low", "high", "max"]
PromptName = Literal["watcher", "supervisor"]


class TuningModel(DomainModel):
    """Base for tuning models: unknown keys are errors (a stale override file must not pass)."""

    model_config = ConfigDict(extra="forbid", json_schema_serialization_defaults_required=True)


class BehaviorTuning(TuningModel):
    """Route classification thresholds (services/behavior.behavior_class). Meters, degrees."""

    parked_max_path_m: float
    leaving_start_m: float
    leaving_gain_m: float
    loop_sweep_deg: float
    orbit_min_path_m: float
    orbit_max_range_m: float
    approach_gain_m: float
    # Reconnaissance signs (movement analysis, 27 Sep): approach, pull back, come back ...
    probe_in_m: float
    probe_out_m: float
    probe_back_m: float
    probe_range_m: float
    # ... and a stakeout: drove in, stopped stakeout_min+ minutes within stakeout_near_m.
    stakeout_near_m: float
    stakeout_arrival_m: float
    stakeout_min: float
    stop_step_m: float  # moved less than this between samples: stopped


class GroupTuning(TuningModel):
    """Moving-together thresholds (services/behavior.moving_groups). Meters."""

    large_group: int
    group_radius_m: float
    group_min_move_m: float


class Tier(TuningModel):
    """One rubric tier: `points` when the value passes `limit`."""

    limit: float
    points: int


class PatternPoints(TuningModel):
    """Rubric points for the danger patterns."""

    loops_around_base: int
    fixed_range_orbit: int
    probing_return: int
    perimeter_stakeout: int


class TypePoints(TuningModel):
    """Rubric points by detected vehicle type (other types score 0)."""

    truck: int
    bus: int
    van: int


class RubricTuning(TuningModel):
    """Baseline risk rubric (services/risk). Meters, m/min, degrees, minutes, points."""

    distance_tiers: list[Tier]  # 3 tiers, limit increasing: dist < limit -> points
    approach_rate_tiers: list[Tier]  # 2 tiers, limit decreasing: rate > limit -> points
    heading_points: int
    heading_tolerance_deg: float
    long_stop_min: float
    stop_near_base_m: float
    stop_points_first: int
    stop_points_extra: int
    pattern_points: PatternPoints
    group_points: int
    type_points: TypePoints
    level_step: int  # score // level_step -> LOW, MEDIUM, HIGH, CRITICAL


class CeilingTuning(TuningModel):
    """Level ceiling rules (services/risk.level_ceiling). Meters, degrees, m/s, minutes."""

    at_base_m: float
    arrived_from_m: float  # within at_base_m may be HIGH only if first seen this far out
    pattern_high_m: float
    approach_heading_deg: float
    approach_high_m: float
    approach_high_eta_min: float


class JudgmentTuning(TuningModel):
    """Which watch rows go to the LLM in full (agent/watch/watcher.needs_judgment)."""

    closing_min_m_per_min: float


class AgentKnobs(TuningModel):
    """Agent settings; names match `Settings`, None = use the Settings value."""

    watcher_max_tool_calls: int | None
    supervisor_max_tool_calls: int | None
    watcher_spot_checks: int | None
    watcher_reasoning_effort: ReasoningEffort | None
    supervisor_reasoning_effort: ReasoningEffort | None
    brief_language: Literal["tr", "en"] | None


class PromptOverrides(TuningModel):
    """Admin prompt texts; None = the versioned .md file."""

    watcher: str | None
    supervisor: str | None


class AgentTuning(TuningModel):
    """Everything the admin can tune."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, json_schema_serialization_defaults_required=True
    )

    behavior: BehaviorTuning
    groups: GroupTuning
    rubric: RubricTuning
    ceiling: CeilingTuning
    judgment: JudgmentTuning
    agents: AgentKnobs
    prompts: PromptOverrides


class PromptTexts(DomainModel):
    """One text per prompt."""

    watcher: str
    supervisor: str


class PromptVariables(DomainModel):
    """Required `{{variables}}` per prompt."""

    watcher: list[str]
    supervisor: list[str]


class EnvKnobs(DomainModel):
    """Settings values used when an `AgentKnobs` field is None."""

    watcher_max_tool_calls: int
    supervisor_max_tool_calls: int
    watcher_spot_checks: int
    watcher_reasoning_effort: ReasoningEffort
    supervisor_reasoning_effort: ReasoningEffort
    brief_language: Literal["tr", "en"]


class TuningView(DomainModel):
    """GET/PUT/DELETE /api/admin/tuning response."""

    defaults: AgentTuning
    current: AgentTuning
    overridden: list[str]
    env_knobs: EnvKnobs
    prompt_defaults: PromptTexts
    prompt_variables: PromptVariables
    hash: str
    load_warning: str | None


class PromptPreviewRequest(DomainModel):
    """POST /api/admin/prompts/preview body."""

    name: PromptName
    text: str
    tuning: AgentTuning


class PromptPreview(DomainModel):
    """Rendered prompt with sample scene values, or the variable problems."""

    rendered: str | None
    missing: list[str]
    unknown: list[str]
