# Admin Agent Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an admin edit the watcher/supervisor prompts, agent knobs and every risk-marking threshold from `/admin`; the next frame analysis and the next live watch run use the saved values.

**Architecture:** A typed `AgentTuning` Pydantic model (domain) with defaults built from today's module constants (services). Pure service functions take the sub-model they need as a keyword argument that defaults to today's values, so every existing call and test is unchanged. A small file-backed `TuningStore` (agent layer) holds only the admin's differences from the defaults in `backend/.cache/admin_overrides.json`; runs take a snapshot at start. Thin `/api/admin/*` routes expose it; the React admin page edits a draft and saves it.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, pytest, ruff, mypy · React 19, TypeScript strict, TanStack Query, shadcn/ui, Tailwind, openapi-typescript.

**Spec:** `docs/superpowers/specs/2026-09-26-admin-agent-tuning-design.md`

## Global Constraints

- All code, identifiers, comments, commits, docs and prompts in English; user-facing UI text only in `frontend/src/i18n/tr.ts` (mirrored in `en.ts`).
- Layering stays one-way: `api/routes → agent → services → domain`. `domain/` is Pydantic models only, no imports from other app layers. `services/` stays pure (no I/O, no global state, no FastAPI).
- With every value at its default, behavior is byte-identical to today: all existing tests, `tests/test_golden_img_000860.py` and the adversarial tests pass unchanged.
- Config only via `core/config.py`; no `os.getenv` elsewhere.
- Errors are typed `SentinelError` subclasses mapped to `{error, detail}` JSON.
- Every route declares `response_model=`; API types reach the frontend only through `make gen-types` → `frontend/src/api/schema.d.ts`; aliases in `src/api/types.ts`.
- Frontend components ≤ ~150 lines, one per file, named export; presentational components never fetch; every async view has loading, empty and error states.
- The override file lives at `settings.cache_dir / "admin_overrides.json"` (gitignored `backend/.cache/`). Never commit it.
- No new dependency except the shadcn `textarea` component (added with the shadcn CLI).
- Commits: Conventional Commits, one logical change each, ending with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Backend commands run from `backend/`: `uv run pytest -q`, `uv run ruff check . && uv run ruff format --check . && uv run mypy app`. Frontend from `frontend/`: `pnpm typecheck && pnpm lint`.

## Review Focus

1. A developer's own `backend/.cache/admin_overrides.json` must never change test results (golden settings point at the real cache dir) → Task 6 overrides the tuning store in `tests/conftest.py` for every client and adds `test_golden_client_uses_an_isolated_tuning_store`.
2. An override file written by an older code version (unknown or renamed key, wrong type) must not crash the API or a run: defaults + `load_warning` → Task 5 test `test_stale_key_falls_back_with_warning`.
3. After changing a threshold, re-opening `/analysis` for a frame must not return the old cached analysis → Task 6 test `test_analysis_cache_respects_tuning`.
4. An empty or non-numeric number input must not be sent (FastAPI would answer with a list-shaped 422 the UI cannot map) → Task 8 blocks Save while any field is invalid; checked in the Task 8 browser run.
5. Turkish characters in a prompt override (ş, ğ, İ) must round-trip through the file unchanged → Task 5 test `test_prompt_override_round_trips_unicode`.

---

## File Structure

Backend (create):
- `backend/app/domain/tuning.py` — `AgentTuning` and its sub-models, `TuningView`, `PromptPreviewRequest`, `PromptPreview`.
- `backend/app/services/tuning.py` — `DEFAULT_TUNING`, `flatten`, `overrides_of`, `apply_overrides`, `overridden_paths`, `tuning_hash`, `tuning_problems`.
- `backend/app/agent/tuning_store.py` — `TuningStore` (file I/O), `with_agent_knobs`, `tuning_view`.
- `backend/app/agent/prompts/watcher_v8.md`, `supervisor_v8.md` — v7 with threshold variables.
- `backend/app/api/routes/admin.py` — thin admin routes.
- Tests: `backend/tests/services/test_tuning.py`, `backend/tests/services/test_tuning_effects.py`, `backend/tests/agent/test_prompts_v8.py`, `backend/tests/agent/test_tuning_store.py`, `backend/tests/test_admin_api.py`.

Backend (modify): `services/behavior.py`, `services/risk.py`, `services/watch.py`, `agent/pipeline.py`, `agent/store.py`, `agent/watch/prompts.py`, `agent/watch/watcher.py`, `agent/watch/supervisor.py`, `agent/watch/tools.py`, `agent/watch/runner.py`, `agent/watch/store.py`, `api/deps.py`, `api/routes/analyses.py`, `api/routes/watch.py`, `core/errors.py`, `main.py`, `scripts/watch_demo.py`, `tests/conftest.py`, `tests/agent/test_watch_agents.py` (only the tuple return of `system_prompt` if a test calls it).

Frontend (create): `src/hooks/useTuning.ts`, `src/lib/tuningFields.ts`, `src/components/admin/{AdminEditor,AdminToolbar,RiskRulesTab,RuleSection,NumberField,TierTable,PromptsTab,AgentSettingsCard,PromptEditor,PromptPreview}.tsx`, `src/components/ui/textarea.tsx` (shadcn CLI).

Frontend (modify): `src/api/client.ts`, `src/api/endpoints.ts`, `src/api/types.ts`, `src/api/schema.d.ts` (generated), `src/pages/AdminPage.tsx`, `src/i18n/tr.ts`, `src/i18n/en.ts`.

Docs (modify): `docs/AGENT_DESIGN.md`, `backend/CLAUDE.md`, `frontend/CLAUDE.md`.

---

### Task 1: Tuning model, defaults and pure helpers

**Files:**
- Create: `backend/app/domain/tuning.py`
- Create: `backend/app/services/tuning.py`
- Modify: `backend/app/services/behavior.py` (add `DEFAULT_BEHAVIOR`, `DEFAULT_GROUPS` after the constants)
- Modify: `backend/app/services/risk.py` (add `DEFAULT_RUBRIC`, `DEFAULT_CEILING` after the constants)
- Test: `backend/tests/services/test_tuning.py`

**Interfaces:**
- Produces (domain): `BehaviorTuning`, `GroupTuning`, `Tier`, `PatternPoints`, `TypePoints`, `RubricTuning`, `CeilingTuning`, `JudgmentTuning`, `AgentKnobs`, `PromptOverrides`, `AgentTuning`, `ReasoningEffort`, `PromptName = Literal["watcher", "supervisor"]`.
- Produces (services): `DEFAULT_BEHAVIOR: BehaviorTuning`, `DEFAULT_GROUPS: GroupTuning` (behavior.py); `DEFAULT_RUBRIC: RubricTuning`, `DEFAULT_CEILING: CeilingTuning` (risk.py); in `services/tuning.py`: `DEFAULT_JUDGMENT`, `DEFAULT_TUNING: AgentTuning`, `flatten(data: dict[str, Any], prefix: str = "") -> dict[str, Any]`, `overrides_of(t: AgentTuning) -> dict[str, Any]`, `apply_overrides(overrides: dict[str, Any]) -> AgentTuning` (raises `pydantic.ValidationError`), `overridden_paths(t: AgentTuning) -> list[str]`, `tuning_hash(t: AgentTuning) -> str`, `tuning_problems(t: AgentTuning) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

`backend/tests/services/test_tuning.py`:

```python
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
        (1000, 30), (2000, 20), (4000, 10)
    ]
    assert [(x.limit, x.points) for x in t.rubric.approach_rate_tiers] == [(80, 15), (50, 8)]
    assert t.rubric.pattern_points.loops_around_base == risk.PATTERN_POINTS["loops_around_base"]
    assert t.rubric.type_points.truck == risk.TYPE_POINTS["truck"]
    assert t.rubric.group_points == risk.GROUP_POINTS
    assert t.rubric.level_step == 25
    assert t.ceiling.at_base_m == risk.AT_BASE_M
    assert t.ceiling.approach_medium_ms == risk.APPROACH_MEDIUM_MS
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
            _with("ceiling", approach_high_m=3500.0),
            "ceiling.approach_high_m: not_above ceiling.approach_medium_m",
        ),
        (_with("ceiling", approach_heading_deg=200.0), "ceiling.approach_heading_deg: range 0-180"),
        (_with("agents", watcher_max_tool_calls=11), "agents.watcher_max_tool_calls: range 0-10"),
    ],
)
def test_problems(tuning, problem: str) -> None:  # type: ignore[no-untyped-def]
    assert problem in tuning_problems(tuning)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv --directory backend run pytest tests/services/test_tuning.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain.tuning'`

- [ ] **Step 3: Write the domain model**

`backend/app/domain/tuning.py`:

```python
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
    pattern_high_m: float
    approach_heading_deg: float
    approach_high_m: float
    approach_high_eta_min: float
    approach_medium_ms: float
    approach_medium_m: float
    approach_medium_eta_min: float


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
```

- [ ] **Step 4: Add the per-module defaults**

In `backend/app/services/behavior.py`, add the import `from app.domain.tuning import BehaviorTuning, GroupTuning` and, directly after `APPROACH_GAIN_M = 1500.0`:

```python
DEFAULT_BEHAVIOR = BehaviorTuning(
    parked_max_path_m=PARKED_MAX_PATH_M,
    leaving_start_m=LEAVING_START_M,
    leaving_gain_m=LEAVING_GAIN_M,
    loop_sweep_deg=LOOP_SWEEP_DEG,
    orbit_min_path_m=ORBIT_MIN_PATH_M,
    orbit_max_range_m=ORBIT_MAX_RANGE_M,
    approach_gain_m=APPROACH_GAIN_M,
)
```

and directly after `GROUP_MIN_MOVE_M = 150.0  # ...`:

```python
DEFAULT_GROUPS = GroupTuning(
    large_group=LARGE_GROUP, group_radius_m=GROUP_RADIUS_M, group_min_move_m=GROUP_MIN_MOVE_M
)
```

In `backend/app/services/risk.py`, add the import `from app.domain.tuning import CeilingTuning, PatternPoints, RubricTuning, Tier, TypePoints`, add the named constants that are literals today (keep values), and build the defaults after `GROUP_POINTS = 15`:

```python
DISTANCE_TIERS = ((1000, 30), (2000, 20), (4000, 10))  # dist < m -> points
APPROACH_RATE_TIERS = ((80, 15), (50, 8))  # rate > m/min -> points
HEADING_POINTS = 5
STOP_POINTS_FIRST, STOP_POINTS_EXTRA = 5, 5
LEVEL_STEP = 25

DEFAULT_RUBRIC = RubricTuning(
    distance_tiers=[Tier(limit=m, points=p) for m, p in DISTANCE_TIERS],
    approach_rate_tiers=[Tier(limit=r, points=p) for r, p in APPROACH_RATE_TIERS],
    heading_points=HEADING_POINTS,
    heading_tolerance_deg=HEADING_TOLERANCE_DEG,
    long_stop_min=LONG_STOP_MIN,
    stop_near_base_m=STOP_NEAR_BASE_M,
    stop_points_first=STOP_POINTS_FIRST,
    stop_points_extra=STOP_POINTS_EXTRA,
    pattern_points=PatternPoints(
        loops_around_base=PATTERN_POINTS["loops_around_base"],
        fixed_range_orbit=PATTERN_POINTS["fixed_range_orbit"],
    ),
    group_points=GROUP_POINTS,
    type_points=TypePoints(truck=TYPE_POINTS["truck"], bus=TYPE_POINTS["bus"], van=TYPE_POINTS["van"]),
    level_step=LEVEL_STEP,
)
DEFAULT_CEILING = CeilingTuning(
    at_base_m=AT_BASE_M,
    pattern_high_m=PATTERN_HIGH_M,
    approach_heading_deg=APPROACH_HEADING_DEG,
    approach_high_m=APPROACH_HIGH_M,
    approach_high_eta_min=APPROACH_HIGH_ETA_MIN,
    approach_medium_ms=APPROACH_MEDIUM_MS,
    approach_medium_m=APPROACH_MEDIUM_M,
    approach_medium_eta_min=APPROACH_MEDIUM_ETA_MIN,
)
```

(`GROUP_POINTS = 15` currently sits below `cap_level`; move it up next to `PATTERN_POINTS` so the defaults can be built in one place. Do not change any function body in this task.)

- [ ] **Step 5: Write the pure helpers**

`backend/app/services/tuning.py`:

```python
"""Default tuning, override diffs and validation (spec §3.1-3.2). Pure; no I/O."""

import hashlib
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
        out[key] = _merge(out[key], value) if isinstance(value, dict) and isinstance(
            out.get(key), dict
        ) else value
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
    "groups.group_radius_m",
    "groups.group_min_move_m",
    "rubric.long_stop_min",
    "rubric.stop_near_base_m",
    "ceiling.at_base_m",
    "ceiling.pattern_high_m",
    "ceiling.approach_high_m",
    "ceiling.approach_high_eta_min",
    "ceiling.approach_medium_ms",
    "ceiling.approach_medium_m",
    "ceiling.approach_medium_eta_min",
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
    ("ceiling.approach_high_m", "ceiling.approach_medium_m"),
    ("ceiling.approach_high_eta_min", "ceiling.approach_medium_eta_min"),
)


def _fmt(x: float) -> str:
    return f"{x:g}"


def _tier_problems(path: str, tiers: list[dict[str, Any]], count: int, rising: bool) -> list[str]:
    if len(tiers) != count:
        return [f"{path}: tier_count {count}"]
    problems = []
    limits = [t["limit"] for t in tiers]
    ordered = all(a < b for a, b in zip(limits, limits[1:], strict=False)) if rising else all(
        a > b for a, b in zip(limits, limits[1:], strict=False)
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
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `uv --directory backend run pytest tests/services/test_tuning.py -q`
Expected: PASS (all tests)

- [ ] **Step 7: Run the full backend suite, lint and types**

Run: `uv --directory backend run pytest -q` then `uv --directory backend run ruff check . && uv --directory backend run ruff format . && uv --directory backend run mypy app`
Expected: all pass, no mypy errors.

- [ ] **Step 8: Commit**

```bash
git add backend/app/domain/tuning.py backend/app/services/tuning.py backend/app/services/behavior.py backend/app/services/risk.py backend/tests/services/test_tuning.py
git commit -m "feat(agent): add AgentTuning model with defaults from current thresholds

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Thread tuning through behavior and risk services

**Files:**
- Modify: `backend/app/services/behavior.py` (`behavior_class`, `moving_groups`)
- Modify: `backend/app/services/risk.py` (`level_ceiling`, `motion_ceiling`, `group_factor`, `pattern_factor`, `level_for`, `distance_factor`, `motion_factors`, `score_vehicle`)
- Test: `backend/tests/services/test_tuning_effects.py`

**Interfaces:**
- Consumes: `DEFAULT_BEHAVIOR`, `DEFAULT_GROUPS`, `DEFAULT_RUBRIC`, `DEFAULT_CEILING` (Task 1).
- Produces (new keyword parameters, all defaulted, so existing calls are unchanged):
  - `behavior_class(points, base, cfg: BehaviorTuning = DEFAULT_BEHAVIOR) -> BehaviorClass`
  - `moving_groups(tracks, minute, cfg: GroupTuning = DEFAULT_GROUPS) -> dict[str, list[str]]`
  - `level_ceiling(dist_m, speed_ms, closing_now, heading_vs_base_deg, eta_min, behavior, group_size=1, cfg: CeilingTuning = DEFAULT_CEILING, large_group: int = LARGE_GROUP) -> WatchLevel`
  - `motion_ceiling(motion, dist_m, behavior, group_size=1, cfg: CeilingTuning = DEFAULT_CEILING, large_group: int = LARGE_GROUP) -> WatchLevel`
  - `group_factor(group_size, rubric: RubricTuning = DEFAULT_RUBRIC, large_group: int = LARGE_GROUP)`
  - `pattern_factor(behavior, rubric: RubricTuning = DEFAULT_RUBRIC)`
  - `level_for(score, rubric: RubricTuning = DEFAULT_RUBRIC)`
  - `distance_factor(dist_m, rubric: RubricTuning = DEFAULT_RUBRIC)`
  - `motion_factors(motion, rubric: RubricTuning = DEFAULT_RUBRIC)`
  - `score_vehicle(detection, match, motion, assessments, claims, behavior="unknown", group_size=1, rubric: RubricTuning = DEFAULT_RUBRIC, ceiling: CeilingTuning = DEFAULT_CEILING, large_group: int = LARGE_GROUP) -> VehicleRisk`

- [ ] **Step 1: Write the failing tests**

`backend/tests/services/test_tuning_effects.py`:

```python
"""Changing one threshold changes the outcome; defaults keep today's outcome (spec §6)."""

from app.domain.geo import LatLon
from app.domain.track import TrackPoint
from app.services import risk
from app.services.behavior import DEFAULT_BEHAVIOR, behavior_class
from app.services.geo import destination
from app.services.risk import DEFAULT_CEILING, DEFAULT_RUBRIC, level_ceiling, level_for

BASE = LatLon(lat=39.93, lon=32.85)


def _arc(sweep_deg: float, radius_m: float = 2000, steps: int = 12) -> list[TrackPoint]:
    """Points on a circle around BASE covering `sweep_deg`, 5 minutes apart."""
    return [
        TrackPoint(
            time=f"{10 + (i * 5) // 60:02d}:{(i * 5) % 60:02d}",
            time_min=600 + i * 5,
            position=destination(BASE, sweep_deg * i / steps, radius_m),
        )
        for i in range(steps + 1)
    ]


def test_half_loop_is_a_loop_only_with_a_lower_sweep_threshold() -> None:
    half = _arc(200)
    assert behavior_class(half, BASE) != "loops_around_base"
    lower = DEFAULT_BEHAVIOR.model_copy(update={"loop_sweep_deg": 180.0})
    assert behavior_class(half, BASE, lower) == "loops_around_base"


def test_parked_car_at_1500_m_may_be_high_only_with_a_wider_at_base_radius() -> None:
    args = dict(
        dist_m=1500, speed_ms=0.0, closing_now=False, heading_vs_base_deg=None, eta_min=None,
        behavior="parked",
    )
    assert level_ceiling(**args) == "LOW"  # type: ignore[arg-type]
    wider = DEFAULT_CEILING.model_copy(update={"at_base_m": 2000.0})
    assert level_ceiling(**args, cfg=wider) == "HIGH"  # type: ignore[arg-type]


def test_three_vehicle_group_is_medium_only_with_large_group_three() -> None:
    args = dict(
        dist_m=8000, speed_ms=10.0, closing_now=False, heading_vs_base_deg=None, eta_min=None,
        behavior="mixed_transit", group_size=3,
    )
    assert level_ceiling(**args) == "LOW"  # type: ignore[arg-type]
    assert level_ceiling(**args, large_group=3) == "MEDIUM"  # type: ignore[arg-type]
    assert risk.group_factor(3).points == 0
    assert risk.group_factor(3, large_group=3).points == risk.GROUP_POINTS


def test_level_step_moves_the_level_bands() -> None:
    assert level_for(30) == "MEDIUM"
    assert level_for(30, DEFAULT_RUBRIC.model_copy(update={"level_step": 40})) == "LOW"


def test_distance_tiers_are_read_from_the_rubric() -> None:
    assert risk.distance_factor(900).points == 30
    from app.domain.tuning import Tier

    tiers = [Tier(limit=500, points=30), Tier(limit=2000, points=20), Tier(limit=4000, points=10)]
    custom = DEFAULT_RUBRIC.model_copy(update={"distance_tiers": tiers})
    assert risk.distance_factor(900, custom).points == 20
```

Before writing the test, confirm the `TrackPoint` fields (`grep -n "class TrackPoint" -A8 backend/app/domain/track.py`) and adjust `_arc` to them; the test assumes `time`, `time_min`, `position`. Check that `app.services.geo` has a point-at-bearing helper: `grep -n "^def " backend/app/services/geo.py`. If there is no `destination(origin, bearing_deg, distance_m) -> LatLon`, add this pure helper to `geo.py` in this task with a one-line docstring and a round-trip test in `tests/services/test_geo.py` (`haversine_m(BASE, destination(BASE, 90, 1000)) ≈ 1000 ± 1` and `bearing_deg(BASE, destination(BASE, 90, 1000)) ≈ 90 ± 0.5`):

```python
def destination(origin: LatLon, bearing: float, distance_m: float) -> LatLon:
    """Point `distance_m` meters from `origin` along `bearing` degrees (spherical earth)."""
    r = 6_371_000.0
    lat1, lon1, brg = map(math.radians, (origin.lat, origin.lon, bearing))
    d = distance_m / r
    lat2 = math.asin(math.sin(lat1) * math.cos(d) + math.cos(lat1) * math.sin(d) * math.cos(brg))
    lon2 = lon1 + math.atan2(
        math.sin(brg) * math.sin(d) * math.cos(lat1), math.cos(d) - math.sin(lat1) * math.sin(lat2)
    )
    return LatLon(lat=math.degrees(lat2), lon=math.degrees(lon2))
```

(Use the earth radius constant `geo.py` already uses for `haversine_m` if it defines one.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv --directory backend run pytest tests/services/test_tuning_effects.py -q`
Expected: FAIL with `TypeError: behavior_class() takes 2 positional arguments but 3 were given` (and similar for the others).

- [ ] **Step 3: Implement the parameters in `behavior.py`**

Replace the constant reads in the two function bodies with the config fields:

```python
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
    if dists[0] - dists[-1] > cfg.approach_gain_m:
        return "steady_approach"
    return "mixed_transit"
```

In `moving_groups`, add `cfg: GroupTuning = DEFAULT_GROUPS` as the third parameter and replace `GROUP_MIN_MOVE_M` with `cfg.group_min_move_m` and `GROUP_RADIUS_M` with `cfg.group_radius_m`. `GROUP_SAMPLES` stays a constant. (The group size threshold is applied by callers via `large_group`.)

`DEFAULT_BEHAVIOR` must be defined above `behavior_class` (it already is, from Task 1) and `DEFAULT_GROUPS` above `moving_groups`.

- [ ] **Step 4: Implement the parameters in `risk.py`**

```python
def level_ceiling(
    dist_m: float,
    speed_ms: float,
    closing_now: bool,
    heading_vs_base_deg: float | None,
    eta_min: float | None,
    behavior: BehaviorClass,
    group_size: int = 1,
    cfg: CeilingTuning = DEFAULT_CEILING,
    large_group: int = LARGE_GROUP,
) -> WatchLevel:
    """(docstring unchanged; replace constant names with "cfg." fields)"""
    if dist_m <= cfg.at_base_m:
        return "HIGH"
    if behavior in DANGER_PATTERNS:
        return "HIGH" if dist_m <= cfg.pattern_high_m else "MEDIUM"
    pointed = heading_vs_base_deg is not None and heading_vs_base_deg <= cfg.approach_heading_deg
    if closing_now and pointed:
        if dist_m <= cfg.approach_high_m or (
            eta_min is not None and eta_min <= cfg.approach_high_eta_min
        ):
            return "HIGH"
        near = dist_m <= cfg.approach_medium_m or (
            eta_min is not None and eta_min <= cfg.approach_medium_eta_min
        )
        if speed_ms >= cfg.approach_medium_ms and near:
            return "MEDIUM"
    return "MEDIUM" if group_size >= large_group else "LOW"


def motion_ceiling(
    motion: MotionProfile | None,
    dist_m: float | None,
    behavior: BehaviorClass,
    group_size: int = 1,
    cfg: CeilingTuning = DEFAULT_CEILING,
    large_group: int = LARGE_GROUP,
) -> WatchLevel:
    """`level_ceiling` for a frame vehicle: closing now = moving at the base in the last 10 min."""
    if motion is None:
        return "HIGH" if dist_m is not None and dist_m <= cfg.at_base_m else "MEDIUM"
    heading_diff = (
        None
        if motion.heading_deg is None
        else angle_diff_deg(motion.heading_deg, motion.bearing_to_base_deg)
    )
    moving = motion.last10_speed_ms >= MOVING_MS
    return level_ceiling(
        motion.dist_now_m,
        motion.last10_speed_ms,
        moving,
        heading_diff,
        motion.eta_to_base_min,
        behavior,
        group_size,
        cfg,
        large_group,
    )


def group_factor(
    group_size: int, rubric: RubricTuning = DEFAULT_RUBRIC, large_group: int = LARGE_GROUP
) -> RiskFactor:
    """Points for moving in a large group (`large_group`+ vehicles together)."""
    points = rubric.group_points if group_size >= large_group else 0
    return RiskFactor(name="group", points=points, detail=f"{group_size} moving together")


def pattern_factor(behavior: BehaviorClass, rubric: RubricTuning = DEFAULT_RUBRIC) -> RiskFactor:
    """Points for the danger patterns (looping around / orbiting the base)."""
    points = rubric.pattern_points.model_dump().get(behavior, 0)
    return RiskFactor(name="pattern", points=points, detail=behavior)


def level_for(score: int, rubric: RubricTuning = DEFAULT_RUBRIC) -> RiskLevel:
    """score // level_step -> LOW, MEDIUM, HIGH, CRITICAL (default step 25)."""
    return RISK_LEVELS[min(3, score // rubric.level_step)]


def distance_factor(dist_m: float, rubric: RubricTuning = DEFAULT_RUBRIC) -> RiskFactor:
    """Points for the current distance to the base (m)."""
    tiers = tuple((t.limit, t.points) for t in rubric.distance_tiers)
    pts = _tier(dist_m, tiers, below=True)
    return RiskFactor(name="distance_to_base", points=pts, detail=f"{dist_m:.0f} m")
```

`_tier`'s signature changes to `tiers: tuple[tuple[float, int], ...]` (already the case). In `motion_factors(motion, rubric: RubricTuning = DEFAULT_RUBRIC)` replace:
- `((80, 15), (50, 8))` → `tuple((t.limit, t.points) for t in rubric.approach_rate_tiers)`
- `HEADING_TOLERANCE_DEG` → `rubric.heading_tolerance_deg`; `5 if pointing` → `rubric.heading_points if pointing`
- `LONG_STOP_MIN` → `rubric.long_stop_min`; `STOP_NEAR_BASE_M` → `rubric.stop_near_base_m`
- `stop_pts = 0 if not long_stops else 5 + (5 if len(long_stops) > 1 else 0)` →
  `stop_pts = 0 if not long_stops else rubric.stop_points_first + (rubric.stop_points_extra if len(long_stops) > 1 else 0)`
- the detail string: `f"{len(long_stops)} stop(s) ≥ {rubric.long_stop_min:g} min within {rubric.stop_near_base_m / 1000:g} km"` (with defaults this is `≥ 20 min within 6 km`, identical to today).

In `score_vehicle`, add the three keyword parameters after `group_size` and pass them on:
- `factors.append(distance_factor(dist, rubric))`
- `factors.extend(motion_factors(motion, rubric))`, `pattern_factor(behavior, rubric)`, `group_factor(group_size, rubric, large_group)`
- `TYPE_POINTS.get(detection.label, 0)` → `rubric.type_points.model_dump().get(detection.label, 0)`
- `ceiling = motion_ceiling(motion, dist, behavior, group_size, ceiling_cfg, large_group)` — name the parameter `ceiling: CeilingTuning` in the signature and rename the local variable to `cap` to avoid shadowing:

```python
    score = min(100, sum(f.points for f in factors))
    cap = motion_ceiling(motion, dist, behavior, group_size, ceiling, large_group)
    level = cap_level(level_for(score, rubric), cap)
    if level != level_for(score, rubric):
        factors.append(
            RiskFactor(name="ceiling", points=0, detail=f"score {score}: capped at {cap}")
        )
```

- [ ] **Step 5: Run the new tests and the full suite**

Run: `uv --directory backend run pytest -q`
Expected: PASS, including `test_golden_img_000860.py` and the existing `tests/services/test_reports_risk.py` unchanged.

- [ ] **Step 6: Lint and types**

Run: `uv --directory backend run ruff check . && uv --directory backend run ruff format . && uv --directory backend run mypy app`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/behavior.py backend/app/services/risk.py backend/app/services/geo.py backend/tests/services/test_tuning_effects.py backend/tests/services/test_geo.py
git commit -m "feat(agent): read behavior and risk thresholds from tuning parameters

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Tuning in watch rows, watch agents and the frame pipeline

**Files:**
- Modify: `backend/app/services/watch.py` (`track_rubric`, `row_ceiling`, `vehicle_row`)
- Modify: `backend/app/agent/pipeline.py` (`run_analysis`)
- Modify: `backend/app/agent/watch/watcher.py` (`needs_judgment`, `judged_rows`, `WatcherInput`)
- Modify: `backend/app/agent/watch/tools.py` (`WatchContext`, `_route`)
- Modify: `backend/app/agent/watch/runner.py` (`WatchRunner`)
- Create: `backend/app/agent/tuning_store.py` (only `with_agent_knobs` in this task)
- Test: append to `backend/tests/services/test_tuning_effects.py`; append to `backend/tests/agent/test_watch_agents.py`

**Interfaces:**
- Consumes: `DEFAULT_TUNING`, `tuning_hash` (Task 1); service parameters (Task 2).
- Produces:
  - `track_rubric(motion, vehicle_type=None, behavior="unknown", group_size=1, tuning: AgentTuning = DEFAULT_TUNING) -> Rubric`
  - `row_ceiling(row, tuning: AgentTuning = DEFAULT_TUNING) -> WatchLevel`
  - `vehicle_row(..., group=None, tuning: AgentTuning = DEFAULT_TUNING) -> VehicleRow`
  - `run_analysis(..., on_step=None, fallback_detector=None, tuning: AgentTuning = DEFAULT_TUNING) -> Analysis`
  - `needs_judgment(row, tuning: AgentTuning = DEFAULT_TUNING) -> bool`
  - `WatcherInput.tuning: AgentTuning = DEFAULT_TUNING` (last field)
  - `WatchContext.tuning: AgentTuning = DEFAULT_TUNING` (last field)
  - `WatchRunner(repo, settings, llm, on_event, detector=None, tuning: AgentTuning = DEFAULT_TUNING)`; `runner.tuning`; `runner.settings` has the agent knobs applied.
  - `with_agent_knobs(settings: Settings, tuning: AgentTuning) -> Settings` in `app/agent/tuning_store.py`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/services/test_tuning_effects.py` (move the imports to the top of the file):

```python
from app.services.tuning import DEFAULT_TUNING
from app.services.watch import track_rubric


def test_track_rubric_uses_the_tuning(golden_repo) -> None:  # type: ignore[no-untyped-def]
    from app.services.motion import motion_profile

    track = next(iter(golden_repo.tracks.values()))
    last = track.points[-1].time_min
    motion = motion_profile(
        track, last, golden_repo.scene.base.position, golden_repo.scene.zones, 1.0, 2000
    )
    before = track_rubric(motion)
    zero = DEFAULT_TUNING.model_copy(
        update={"rubric": DEFAULT_TUNING.rubric.model_copy(update={"level_step": 50})}
    )
    after = track_rubric(motion, tuning=zero)
    assert after.score == before.score
    assert after.level == level_for(before.score, zero.rubric)
```

Append to `backend/tests/agent/test_watch_agents.py` (move the three imports into the file's existing import block so ruff's import rules pass):

```python
from app.agent.tuning_store import with_agent_knobs
from app.agent.watch.watcher import needs_judgment
from app.services.tuning import DEFAULT_TUNING


def test_with_agent_knobs_only_overrides_set_values(golden_settings: Settings) -> None:
    knobs = DEFAULT_TUNING.agents.model_copy(update={"watcher_max_tool_calls": 1})
    s = with_agent_knobs(golden_settings, DEFAULT_TUNING.model_copy(update={"agents": knobs}))
    assert s.watcher_max_tool_calls == 1
    assert s.supervisor_max_tool_calls == golden_settings.supervisor_max_tool_calls
    assert with_agent_knobs(golden_settings, DEFAULT_TUNING) == golden_settings


def test_closing_threshold_decides_full_rows(golden_repo: Repository, golden_settings: Settings) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    row = next(iter(ctx.rows.values())).model_copy(
        update={
            "closing_last5_m_per_min": 60,
            "registry_level": "LOW",
            "pending_level": None,
            "notes_count": 0,
            "status": "staying",
            "max_level": "LOW",
        }
    )
    assert not needs_judgment(row)
    low = DEFAULT_TUNING.model_copy(
        update={"judgment": DEFAULT_TUNING.judgment.model_copy(update={"closing_min_m_per_min": 50})}
    )
    assert needs_judgment(row, low)


def test_runner_keeps_its_start_snapshot(golden_repo: Repository, golden_settings: Settings) -> None:
    tuned = DEFAULT_TUNING.model_copy(
        update={"groups": DEFAULT_TUNING.groups.model_copy(update={"large_group": 3})}
    )
    runner = WatchRunner(golden_repo, golden_settings, None, lambda e: None, None, tuned)
    assert runner.tuning is tuned
    assert runner.tuning.groups.large_group == 3
```

(`golden_repo` and `golden_settings` are fixtures from `tests/conftest.py`. If the row in `test_closing_threshold_decides_full_rows` has a rubric level above LOW, `needs_judgment` is True regardless; in that case pick a row with `rubric.level == "LOW"`: `row = next(r for r in ctx.rows.values() if r.rubric.level == "LOW")` before the `model_copy`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv --directory backend run pytest tests/services/test_tuning_effects.py tests/agent/test_watch_agents.py -q`
Expected: FAIL (`ModuleNotFoundError: app.agent.tuning_store`, unexpected keyword `tuning`).

- [ ] **Step 3: `services/watch.py`**

Add `from app.domain.tuning import AgentTuning` and `from app.services.tuning import DEFAULT_TUNING`. Then:

```python
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


def row_ceiling(row: VehicleRow, tuning: AgentTuning = DEFAULT_TUNING) -> WatchLevel:
    """Highest level this vehicle may get (`services.risk.level_ceiling` on the row's facts)."""
    closing_now = row.moving and row.closing_last5_m_per_min > 0
    return level_ceiling(
        row.dist_to_base_m,
        row.speed_last10_ms,
        closing_now,
        row.heading_vs_base_deg,
        row.eta_to_base_min,
        row.behavior_class,
        len(row.group_ids) + 1,
        tuning.ceiling,
        tuning.groups.large_group,
    )
```

Remove `TYPE_POINTS` from the `from app.services.risk import (...)` list if it becomes unused. In `vehicle_row`, add the keyword parameter `tuning: AgentTuning = DEFAULT_TUNING` after `group`, and change three lines:

```python
    behavior = behavior_class(track.points, base, tuning.behavior)
    ...
        rubric=track_rubric(motion, vehicle_type, behavior, len(others) + 1, tuning),
    ...
    row = row.model_copy(update={"max_level": row_ceiling(row, tuning)})
```

- [ ] **Step 4: `agent/pipeline.py`**

Add the import `from app.domain.tuning import AgentTuning` and `from app.services.tuning import DEFAULT_TUNING`; add `tuning: AgentTuning = DEFAULT_TUNING,` as the last parameter of `run_analysis`; in step 7:

```python
    def behavior_of(match: TrackMatch | None) -> BehaviorClass:
        motion = motion_by_track.get(match.track_id or "") if match else None
        return (
            behavior_class(motion.points, repo.scene.base.position, tuning.behavior)
            if motion
            else "unknown"
        )

    groups = moving_groups(list(repo.tracks.values()), meta.capture_min, tuning.groups)
```

and add to the `risk_svc.score_vehicle(...)` call, after `group_size_of(...)`:

```python
            rubric=tuning.rubric,
            ceiling=tuning.ceiling,
            large_group=tuning.groups.large_group,
```

- [ ] **Step 5: `agent/tuning_store.py` (knobs only for now)**

```python
"""Admin tuning: override file I/O and how a snapshot is applied to a run (spec §3.2)."""

from app.core.config import Settings
from app.domain.tuning import AgentTuning


def with_agent_knobs(settings: Settings, tuning: AgentTuning) -> Settings:
    """`settings` with every non-None agent knob of `tuning` applied (names match Settings)."""
    update = {k: v for k, v in tuning.agents.model_dump().items() if v is not None}
    return settings.model_copy(update=update) if update else settings
```

- [ ] **Step 6: Watch agent layer**

`agent/watch/watcher.py`: import `AgentTuning` and `DEFAULT_TUNING`; add `tuning: AgentTuning = field(default=DEFAULT_TUNING)` as the last field of `WatcherInput`; then

```python
def needs_judgment(row: VehicleRow, tuning: AgentTuning = DEFAULT_TUNING) -> bool:
    """Rows sent in full and required in the answer; the rest are one-liners treated as LOW."""
    return (
        rubric_watch_level(row) != "LOW"
        or row.registry_level != "LOW"
        or row.pending_level is not None
        or row.notes_count > 0
        or (row.status == "new_in_sector" and row.moving)
        or row.closing_last5_m_per_min > tuning.judgment.closing_min_m_per_min
    )


def judged_rows(inp: WatcherInput) -> list[VehicleRow]:
    """Rows sent in full and required in the answer: by condition, plus the random spot checks."""
    return [
        r for r in inp.rows if needs_judgment(r, inp.tuning) or r.track_id in inp.spot_checks
    ]
```

`agent/watch/tools.py`: import `AgentTuning`, `DEFAULT_TUNING` and `field` from dataclasses; add `tuning: AgentTuning = field(default=DEFAULT_TUNING)` as the last field of `WatchContext`; in `_route`:

```python
    behavior = behavior_class(points, ctx.base, ctx.tuning.behavior)
    rubric = watch_svc.track_rubric(motion, vehicle_type, behavior, tuning=ctx.tuning)
```

`agent/watch/runner.py`:
- imports: `from app.agent.tuning_store import with_agent_knobs`, `from app.domain.tuning import AgentTuning`, `from app.services.tuning import DEFAULT_TUNING, tuning_hash`.
- `__init__` gets `tuning: AgentTuning = DEFAULT_TUNING` as the last parameter; first lines become:

```python
        settings = with_agent_knobs(settings, tuning)
        self.repo, self.settings, self.llm, self.emit = repo, settings, llm, on_event
        self.tuning = tuning
        logger.info(
            "watch run tuning",
            extra={
                "tuning_hash": tuning_hash(tuning),
                "watcher_prompt": "admin" if tuning.prompts.watcher else "file",
                "supervisor_prompt": "admin" if tuning.prompts.supervisor else "file",
            },
        )
```

- `WatchContext(...)` in `tick` gets `tuning=self.tuning`.
- `_rows`: `groups = moving_groups(list(self.repo.tracks.values()), minute, self.tuning.groups)` and `watch_svc.vehicle_row(..., group=groups.get(tid), tuning=self.tuning)`.
- `_watcher_input`: `quiet = [r.track_id for r in mine if not needs_judgment(r, self.tuning)]` and pass `tuning=self.tuning` to `WatcherInput(...)`.

- [ ] **Step 7: Run all tests**

Run: `uv --directory backend run pytest -q`
Expected: PASS (all, including golden).

- [ ] **Step 8: Lint and types**

Run: `uv --directory backend run ruff check . && uv --directory backend run ruff format . && uv --directory backend run mypy app`
Expected: clean.

- [ ] **Step 9: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(agent): pass a tuning snapshot through watch runs and frame analysis

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Prompts v8 with threshold variables and admin overrides

**Files:**
- Create: `backend/app/agent/prompts/watcher_v8.md`, `backend/app/agent/prompts/supervisor_v8.md`
- Modify: `backend/app/agent/watch/prompts.py`
- Modify: `backend/app/agent/watch/watcher.py` (`PROMPT`, `LANGUAGE_NAMES` import, `system_prompt`, `run_watcher`)
- Modify: `backend/app/agent/watch/supervisor.py` (`PROMPT`, `LANGUAGE_NAMES` import, `system_prompt`, `run_supervisor`)
- Test: `backend/tests/agent/test_prompts_v8.py`

**Interfaces:**
- Consumes: `WatchContext.tuning` (Task 3), `DEFAULT_TUNING` (Task 1).
- Produces in `app/agent/watch/prompts.py`:
  - `PROMPT_FILES: dict[PromptName, str] = {"watcher": "watcher_v8", "supervisor": "supervisor_v8"}`
  - `LANGUAGE_NAMES = {"tr": "Turkish", "en": "English"}` (moved here; `watcher.LANGUAGE_NAMES` keeps working via import)
  - `file_text(name: str) -> str`
  - `required_vars(name: str) -> list[str]` (sorted vars in the file)
  - `render(name: str, override: str | None = None, **values: object) -> str`
  - `render_with_fallback(name: str, override: str | None, values: dict[str, object]) -> tuple[str, list[str]]`
  - `threshold_vars(tuning: AgentTuning) -> dict[str, str]`
  - `prompt_problems(prompt: PromptName, text: str) -> list[str]` — `"prompts.<prompt>: missing_vars a,b"` / `"prompts.<prompt>: unknown_vars a,b"`
  - `var_diff(prompt: PromptName, text: str) -> tuple[list[str], list[str]]` — (missing, unknown)
- Changes: `watcher.system_prompt(ctx, watcher_id, area) -> tuple[str, list[str]]`; `supervisor.system_prompt(ctx, layout) -> tuple[str, list[str]]` (text, warnings).

- [ ] **Step 1: Write the failing tests**

`backend/tests/agent/test_prompts_v8.py`:

```python
"""v8 prompts: same text as v7 with default thresholds; variables follow the tuning."""

from app.agent.watch.prompts import (
    PROMPT_FILES,
    prompt_problems,
    render,
    render_with_fallback,
    required_vars,
    threshold_vars,
)
from app.services.tuning import DEFAULT_TUNING

WATCHER_BASE = dict(
    watcher_id="W1", sector_names="A, B", base_name="Base", base_lat=39.9, base_lon=32.8,
    max_tool_calls=3, output_language="Turkish",
)
SUPERVISOR_BASE = dict(
    base_name="Base", base_lat=39.9, base_lon=32.8, n_watchers=4, watcher_layout="W1: A",
    tracker_rules="3. none", max_tool_calls=6, output_language="Turkish",
)


def test_v8_with_defaults_equals_v7() -> None:
    tv = threshold_vars(DEFAULT_TUNING)
    assert render("watcher_v8", **WATCHER_BASE, **tv) == render("watcher_v7", **WATCHER_BASE)
    assert render("supervisor_v8", **SUPERVISOR_BASE, **tv) == render(
        "supervisor_v7", **SUPERVISOR_BASE
    )


def test_thresholds_show_up_in_the_prompt() -> None:
    ceiling = DEFAULT_TUNING.ceiling.model_copy(update={"approach_medium_m": 2500.0})
    groups = DEFAULT_TUNING.groups.model_copy(update={"large_group": 3})
    tuned = DEFAULT_TUNING.model_copy(update={"ceiling": ceiling, "groups": groups})
    text = render("watcher_v8", **WATCHER_BASE, **threshold_vars(tuned))
    assert "within 2.5 km or 12 minutes may be MEDIUM" in text
    assert "three or more together may be MEDIUM" in text


def test_required_vars_come_from_the_file() -> None:
    assert "approach_high_km" in required_vars(PROMPT_FILES["watcher"])
    assert "watcher_id" in required_vars(PROMPT_FILES["watcher"])
    assert "tracker_rules" in required_vars(PROMPT_FILES["supervisor"])


def test_prompt_problems_names_missing_and_unknown_vars() -> None:
    from app.agent.watch.prompts import file_text

    text = file_text(PROMPT_FILES["watcher"]).replace("{{at_base_km}}", "{{at_base_miles}}")
    assert prompt_problems("watcher", text) == [
        "prompts.watcher: missing_vars at_base_km",
        "prompts.watcher: unknown_vars at_base_miles",
    ]
    assert prompt_problems("watcher", file_text(PROMPT_FILES["watcher"])) == []


def test_broken_override_falls_back_to_the_file() -> None:
    values = {**WATCHER_BASE, **threshold_vars(DEFAULT_TUNING)}
    text, warnings = render_with_fallback("watcher_v8", "Hello {{nope}}", values)
    assert text == render("watcher_v8", **values)
    assert warnings and "file prompt used" in warnings[0]
    text, warnings = render_with_fallback("watcher_v8", "Hi {{watcher_id}}", values)
    assert (text, warnings) == ("Hi W1", [])
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv --directory backend run pytest tests/agent/test_prompts_v8.py -q`
Expected: FAIL with `ImportError: cannot import name 'PROMPT_FILES'`.

- [ ] **Step 3: Create the v8 prompt files**

```bash
cp backend/app/agent/prompts/watcher_v7.md backend/app/agent/prompts/watcher_v8.md
cp backend/app/agent/prompts/supervisor_v7.md backend/app/agent/prompts/supervisor_v8.md
```

Edit `watcher_v8.md` — exactly three replacements:

1. `Only a very high approach counts: fast (4 m/s or more) and within 3 km or 12 minutes may be MEDIUM; within 1.5 km or 5 minutes may be HIGH.`
   → `Only a very high approach counts: fast ({{approach_medium_ms}} m/s or more) and within {{approach_medium_km}} km or {{approach_medium_eta_min}} minutes may be MEDIUM; within {{approach_high_km}} km or {{approach_high_eta_min}} minutes may be HIGH.`
2. `(within 500 m for the last 15 minutes); four or more together may be MEDIUM.`
   → `(within {{group_radius_m}} m for the last 15 minutes); {{large_group_word}} or more together may be MEDIUM.`
3. `within 1 km of the base anything may be HIGH`
   → `within {{at_base_km}} km of the base anything may be HIGH`

Edit `supervisor_v8.md` — exactly two replacements:

1. `only a very high approach (fast and within 1.5 km or 5 minutes) may be HIGH`
   → `only a very high approach (fast and within {{approach_high_km}} km or {{approach_high_eta_min}} minutes) may be HIGH`
2. `on large groups actually moving together (four or more)`
   → `on large groups actually moving together ({{large_group_word}} or more)`

Leave the Example sections unchanged (their numbers describe one example vehicle, not rules).

- [ ] **Step 4: Rewrite `agent/watch/prompts.py`**

```python
"""Load versioned prompt files from app/agent/prompts/, fill {{variables}}, and check admin
overrides (spec §3.4)."""

import logging
import re
from functools import cache
from pathlib import Path

from app.domain.tuning import AgentTuning, PromptName

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
PROMPT_FILES: dict[PromptName, str] = {"watcher": "watcher_v8", "supervisor": "supervisor_v8"}
LANGUAGE_NAMES = {"tr": "Turkish", "en": "English"}
_VAR = re.compile(r"\{\{(\w+)\}\}")
_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


@cache
def file_text(name: str) -> str:
    """Raw text of prompt file `name` (e.g. "watcher_v8")."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _vars(text: str) -> set[str]:
    return set(_VAR.findall(text))


def required_vars(name: str) -> list[str]:
    """The {{variables}} used in prompt file `name`, sorted."""
    return sorted(_vars(file_text(name)))


def render(name: str, override: str | None = None, **values: object) -> str:
    """Prompt `name` (or the `override` text) with {{vars}} filled; a missing var raises KeyError."""
    text = file_text(name) if override is None else override
    missing = sorted(_vars(text) - values.keys())
    if missing:
        raise KeyError(f"prompt {name} needs {missing}")
    return _VAR.sub(lambda m: str(values[m.group(1)]), text)


def render_with_fallback(
    name: str, override: str | None, values: dict[str, object]
) -> tuple[str, list[str]]:
    """Render the admin override if usable, else the file; returns (text, warnings)."""
    if override is not None:
        try:
            return render(name, override, **values), []
        except KeyError as exc:
            logger.warning("admin prompt unusable", extra={"prompt": name, "error": str(exc)})
            return render(name, **values), [f"admin prompt for {name} unusable ({exc}); file prompt used"]
    return render(name, **values), []


def _num(x: float) -> str:
    return f"{x:g}"


def threshold_vars(tuning: AgentTuning) -> dict[str, str]:
    """Threshold numbers written into the prompts, formatted like the v7 text (3 km, 4 m/s)."""
    c, g = tuning.ceiling, tuning.groups
    return {
        "approach_medium_ms": _num(c.approach_medium_ms),
        "approach_medium_km": _num(c.approach_medium_m / 1000),
        "approach_medium_eta_min": _num(c.approach_medium_eta_min),
        "approach_high_km": _num(c.approach_high_m / 1000),
        "approach_high_eta_min": _num(c.approach_high_eta_min),
        "at_base_km": _num(c.at_base_m / 1000),
        "group_radius_m": _num(g.group_radius_m),
        "large_group_word": _WORDS.get(g.large_group, str(g.large_group)),
    }


def var_diff(prompt: PromptName, text: str) -> tuple[list[str], list[str]]:
    """(missing, unknown) variables of `text` against the prompt's file."""
    need, have = set(required_vars(PROMPT_FILES[prompt])), _vars(text)
    return sorted(need - have), sorted(have - need)


def prompt_problems(prompt: PromptName, text: str) -> list[str]:
    """Validation problems of an admin override, in the tuning_problems format."""
    missing, unknown = var_diff(prompt, text)
    problems = []
    if missing:
        problems.append(f"prompts.{prompt}: missing_vars {','.join(missing)}")
    if unknown:
        problems.append(f"prompts.{prompt}: unknown_vars {','.join(unknown)}")
    return problems
```

(`render(name, **values)` keeps working for existing callers because `override` defaults to None. Wrap the long `return` line to satisfy ruff's line length.)

- [ ] **Step 5: Use it in the agents**

`agent/watch/watcher.py`:
- replace `PROMPT = "watcher_v7"` with `PROMPT = PROMPT_FILES["watcher"]`; delete the local `LANGUAGE_NAMES = {...}` line; import `PROMPT_FILES, LANGUAGE_NAMES, render_with_fallback, threshold_vars` from `app.agent.watch.prompts` (drop the `render` import if unused).
- `system_prompt`:

```python
def system_prompt(ctx: t.WatchContext, watcher_id: str, area: list[str]) -> tuple[str, list[str]]:
    """The watcher's fixed system prompt for its area (stable across ticks) and any warnings."""
    base = ctx.repo.scene.base
    values: dict[str, object] = {
        "watcher_id": watcher_id,
        "sector_names": ", ".join(area),
        "base_name": base.name,
        "base_lat": base.position.lat,
        "base_lon": base.position.lon,
        "max_tool_calls": ctx.settings.watcher_max_tool_calls,
        "output_language": LANGUAGE_NAMES[ctx.settings.brief_language],
        **threshold_vars(ctx.tuning),
    }
    return render_with_fallback(PROMPT, ctx.tuning.prompts.watcher, values)
```

- in `run_watcher`, replace `system, user = system_prompt(ctx, inp.watcher_id, inp.area), build_user_message(inp)` with

```python
    system, prompt_warnings = system_prompt(ctx, inp.watcher_id, inp.area)
    user = build_user_message(inp)
```

and prefix both warning lists: `warnings = [*prompt_warnings, *loop.warnings, "rubric fallback used"]` and `generated_by, warnings = "llm", prompt_warnings + loop.warnings + clamps`.

`agent/watch/supervisor.py`:
- `PROMPT = PROMPT_FILES["supervisor"]`; import `LANGUAGE_NAMES` from `app.agent.watch.prompts` instead of `app.agent.watch.watcher`; import `PROMPT_FILES, render_with_fallback, threshold_vars`.
- `system_prompt(ctx, layout) -> tuple[str, list[str]]`: build the same `values` dict it passes today plus `**threshold_vars(ctx.tuning)` and `return render_with_fallback(PROMPT, ctx.tuning.prompts.supervisor, values)`.
- in `run_supervisor`, replace `out.system, out.user = system_prompt(ctx, inp.layout), build_user_message(ctx, inp)` with

```python
    out.system, prompt_warnings = system_prompt(ctx, inp.layout)
    out.user = build_user_message(ctx, inp)
    out.warnings.extend(prompt_warnings)
```

- [ ] **Step 6: Run the tests**

Run: `uv --directory backend run pytest -q`
Expected: PASS. If `tests/agent/test_watch_agents.py` asserts a prompt name `"watcher_v7"` anywhere (`grep -n "_v7" backend/tests`), update it to `_v8`.

- [ ] **Step 7: Lint and types**

Run: `uv --directory backend run ruff check . && uv --directory backend run ruff format . && uv --directory backend run mypy app`
Expected: clean.

- [ ] **Step 8: Commit**

```bash
git add backend/app/agent backend/tests/agent
git commit -m "feat(agent): watcher and supervisor prompts v8 with threshold variables and admin overrides

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Tuning store (override file)

**Files:**
- Modify: `backend/app/agent/tuning_store.py`
- Modify: `backend/app/core/errors.py`
- Test: `backend/tests/agent/test_tuning_store.py`

**Interfaces:**
- Consumes: `apply_overrides`, `overrides_of`, `overridden_paths`, `tuning_hash`, `tuning_problems`, `DEFAULT_TUNING` (Task 1); `prompt_problems`, `PROMPT_FILES`, `file_text`, `required_vars`, `var_diff`, `render`, `threshold_vars`, `LANGUAGE_NAMES` (Task 4); `with_agent_knobs` (Task 3).
- Produces:
  - `core/errors.py`: `TuningValidationError` (422, `"invalid_tuning"`), `TuningStoreError` (503, `"tuning_store_error"`).
  - `class TuningStore(path: Path)`: `load() -> tuple[AgentTuning, str | None]`, `save(t: AgentTuning) -> None`, `reset() -> None`, attribute `path`.
  - `tuning_view(store: TuningStore, settings: Settings) -> TuningView`
  - `preview_prompt(req: PromptPreviewRequest, settings: Settings) -> PromptPreview`

- [ ] **Step 1: Write the failing tests**

`backend/tests/agent/test_tuning_store.py`:

```python
"""TuningStore: diff-only persistence, reset, safe loading, validation (spec §3.2, §5)."""

import json
from pathlib import Path

import pytest

from app.agent.tuning_store import TuningStore, preview_prompt, tuning_view
from app.agent.watch.prompts import PROMPT_FILES, file_text
from app.core.config import Settings
from app.core.errors import TuningValidationError
from app.domain.tuning import PromptPreviewRequest
from app.services.tuning import DEFAULT_TUNING


@pytest.fixture
def store(tmp_path: Path) -> TuningStore:
    return TuningStore(tmp_path / "admin_overrides.json")


def _at_base(m: float):  # type: ignore[no-untyped-def]
    return DEFAULT_TUNING.model_copy(
        update={"ceiling": DEFAULT_TUNING.ceiling.model_copy(update={"at_base_m": m})}
    )


def test_missing_file_gives_defaults(store: TuningStore) -> None:
    assert store.load() == (DEFAULT_TUNING, None)


def test_save_writes_only_the_diff(store: TuningStore) -> None:
    store.save(_at_base(1500.0))
    assert json.loads(store.path.read_text(encoding="utf-8")) == {"ceiling": {"at_base_m": 1500.0}}
    assert store.load() == (_at_base(1500.0), None)


def test_saving_defaults_removes_the_file(store: TuningStore) -> None:
    store.save(_at_base(1500.0))
    store.save(DEFAULT_TUNING)
    assert not store.path.exists()


def test_reset(store: TuningStore) -> None:
    store.save(_at_base(1500.0))
    store.reset()
    assert store.load() == (DEFAULT_TUNING, None)
    store.reset()  # idempotent


def test_corrupt_file_falls_back_with_warning(store: TuningStore) -> None:
    store.path.write_text("{not json", encoding="utf-8")
    tuning, warning = store.load()
    assert tuning == DEFAULT_TUNING and warning is not None


def test_stale_key_falls_back_with_warning(store: TuningStore) -> None:
    store.path.write_text(json.dumps({"ceiling": {"renamed_field": 1}}), encoding="utf-8")
    tuning, warning = store.load()
    assert tuning == DEFAULT_TUNING and warning is not None


def test_invalid_values_are_rejected_and_not_written(store: TuningStore) -> None:
    with pytest.raises(TuningValidationError) as err:
        store.save(_at_base(-5.0))
    assert "ceiling.at_base_m: positive" in err.value.detail
    assert not store.path.exists()


def test_prompt_override_needs_every_variable(store: TuningStore) -> None:
    text = file_text(PROMPT_FILES["watcher"]).replace("{{at_base_km}}", "1")
    bad = DEFAULT_TUNING.model_copy(
        update={"prompts": DEFAULT_TUNING.prompts.model_copy(update={"watcher": text})}
    )
    with pytest.raises(TuningValidationError) as err:
        store.save(bad)
    assert err.value.detail == "prompts.watcher: missing_vars at_base_km"


def test_prompt_override_round_trips_unicode(store: TuningStore) -> None:
    text = file_text(PROMPT_FILES["watcher"]) + "\nNot: şüpheli İzmir ğ"
    t = DEFAULT_TUNING.model_copy(
        update={"prompts": DEFAULT_TUNING.prompts.model_copy(update={"watcher": text})}
    )
    store.save(t)
    assert store.load()[0].prompts.watcher == text


def test_view_reports_overrides_and_env_knobs(store: TuningStore, settings: Settings) -> None:
    store.save(_at_base(1500.0))
    view = tuning_view(store, settings)
    assert view.overridden == ["ceiling.at_base_m"]
    assert view.defaults == DEFAULT_TUNING
    assert view.env_knobs.watcher_max_tool_calls == settings.watcher_max_tool_calls
    assert "at_base_km" in view.prompt_variables.watcher
    assert view.prompt_defaults.watcher == file_text(PROMPT_FILES["watcher"])
    assert view.load_warning is None and len(view.hash) == 8


def test_preview_renders_or_lists_problems(settings: Settings) -> None:
    ok = preview_prompt(
        PromptPreviewRequest(
            name="watcher", text=file_text(PROMPT_FILES["watcher"]), tuning=_at_base(2000.0)
        ),
        settings,
    )
    assert ok.rendered is not None and "within 2 km of the base" in ok.rendered
    bad = preview_prompt(
        PromptPreviewRequest(name="watcher", text="Hi {{nope}}", tuning=DEFAULT_TUNING), settings
    )
    assert bad.rendered is None and "nope" in bad.unknown and "watcher_id" in bad.missing
```

(`settings` is the existing isolated fixture from `tests/conftest.py`.)

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv --directory backend run pytest tests/agent/test_tuning_store.py -q`
Expected: FAIL with `ImportError: cannot import name 'TuningStore'`.

- [ ] **Step 3: Add the error types**

Append to `backend/app/core/errors.py` (before `register_exception_handlers`):

```python
class TuningValidationError(SentinelError):
    """Admin tuning breaks a rule; detail is "<path>: <code> [arg]" joined with "; "."""

    status_code = 422
    error = "invalid_tuning"


class TuningStoreError(SentinelError):
    """The admin override file could not be written."""

    status_code = 503
    error = "tuning_store_error"
```

- [ ] **Step 4: Implement the store, view and preview**

Replace `backend/app/agent/tuning_store.py` with:

```python
"""Admin tuning: override file I/O and how a snapshot is applied to a run (spec §3.2).

The file holds only the admin's differences from DEFAULT_TUNING. Loading never raises: a missing
file means defaults; an unreadable or stale one means defaults plus a warning for the UI.
"""

import json
import logging
import os
from pathlib import Path

from pydantic import ValidationError

from app.agent.watch.prompts import (
    LANGUAGE_NAMES,
    PROMPT_FILES,
    file_text,
    prompt_problems,
    render,
    required_vars,
    threshold_vars,
    var_diff,
)
from app.core.config import Settings
from app.core.errors import TuningStoreError, TuningValidationError
from app.domain.tuning import (
    AgentTuning,
    EnvKnobs,
    PromptPreview,
    PromptPreviewRequest,
    PromptTexts,
    PromptVariables,
    TuningView,
)
from app.services.tuning import (
    DEFAULT_TUNING,
    apply_overrides,
    overridden_paths,
    overrides_of,
    tuning_hash,
    tuning_problems,
)

logger = logging.getLogger(__name__)


def with_agent_knobs(settings: Settings, tuning: AgentTuning) -> Settings:
    """`settings` with every non-None agent knob of `tuning` applied (names match Settings)."""
    update = {k: v for k, v in tuning.agents.model_dump().items() if v is not None}
    return settings.model_copy(update=update) if update else settings


class TuningStore:
    """The admin override file (JSON, UTF-8)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> tuple[AgentTuning, str | None]:
        """Current tuning and a warning when the file could not be used."""
        if not self.path.exists():
            return DEFAULT_TUNING, None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("override file is not a JSON object")
            return apply_overrides(raw), None
        except (OSError, ValueError, ValidationError) as exc:
            logger.warning("admin overrides ignored", extra={"path": str(self.path), "error": str(exc)})
            return DEFAULT_TUNING, f"{self.path.name} ignored: {type(exc).__name__}"

    def save(self, tuning: AgentTuning) -> None:
        """Validate and persist the diff from the defaults; the defaults remove the file."""
        problems = tuning_problems(tuning)
        for name in PROMPT_FILES:
            text = getattr(tuning.prompts, name)
            if text is not None:
                problems += prompt_problems(name, text)
        if problems:
            raise TuningValidationError("; ".join(problems))
        diff = overrides_of(tuning)
        if not diff:
            self.reset()
            return
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            raise TuningStoreError(f"could not write {self.path.name}: {exc}") from exc

    def reset(self) -> None:
        """Back to the defaults (delete the file if present)."""
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise TuningStoreError(f"could not delete {self.path.name}: {exc}") from exc


def tuning_view(store: TuningStore, settings: Settings) -> TuningView:
    """Everything the admin page needs in one response."""
    current, warning = store.load()
    return TuningView(
        defaults=DEFAULT_TUNING,
        current=current,
        overridden=overridden_paths(current),
        env_knobs=EnvKnobs.model_validate(settings.model_dump(include=set(EnvKnobs.model_fields))),
        prompt_defaults=PromptTexts(
            watcher=file_text(PROMPT_FILES["watcher"]),
            supervisor=file_text(PROMPT_FILES["supervisor"]),
        ),
        prompt_variables=PromptVariables(
            watcher=required_vars(PROMPT_FILES["watcher"]),
            supervisor=required_vars(PROMPT_FILES["supervisor"]),
        ),
        hash=tuning_hash(current),
        load_warning=warning,
    )


# Scene values in previews are placeholders: the preview is about wording and thresholds.
_SAMPLE_SCENE: dict[str, object] = {
    "base_name": "<base>",
    "base_lat": "<lat>",
    "base_lon": "<lon>",
    "watcher_id": "W1",
    "sector_names": "<sector A>, <sector B>",
    "n_watchers": 4,
    "watcher_layout": "watcher W1: <sector A>, <sector B>; ...",
    "tracker_rules": "3. <tracker rules>",
}


def preview_prompt(req: PromptPreviewRequest, settings: Settings) -> PromptPreview:
    """`req.text` rendered with sample scene values and `req.tuning`, or its variable problems."""
    missing, unknown = var_diff(req.name, req.text)
    if missing or unknown:
        return PromptPreview(rendered=None, missing=missing, unknown=unknown)
    s = with_agent_knobs(settings, req.tuning)
    max_calls = s.watcher_max_tool_calls if req.name == "watcher" else s.supervisor_max_tool_calls
    values = {
        **_SAMPLE_SCENE,
        "max_tool_calls": max_calls,
        "output_language": LANGUAGE_NAMES[s.brief_language],
        **threshold_vars(req.tuning),
    }
    rendered = render(PROMPT_FILES[req.name], req.text, **values)
    return PromptPreview(rendered=rendered, missing=[], unknown=[])
```

Note on the import direction: `agent/tuning_store.py` → `agent/watch/prompts.py` → `domain`. `agent/watch/runner.py` imports `with_agent_knobs` from `agent/tuning_store.py`; `tuning_store` must not import `runner`, `watcher` or `supervisor` (it does not).

- [ ] **Step 5: Run the tests**

Run: `uv --directory backend run pytest -q`
Expected: PASS.

- [ ] **Step 6: Lint and types**

Run: `uv --directory backend run ruff check . && uv --directory backend run ruff format . && uv --directory backend run mypy app`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add backend/app/agent/tuning_store.py backend/app/core/errors.py backend/tests/agent/test_tuning_store.py
git commit -m "feat(agent): add file-backed admin tuning store with validation and preview

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Admin API, run snapshots and test isolation

**Files:**
- Create: `backend/app/api/routes/admin.py`
- Modify: `backend/app/api/deps.py`, `backend/app/main.py`, `backend/app/api/routes/analyses.py`, `backend/app/api/routes/watch.py`, `backend/app/agent/store.py`, `backend/app/agent/watch/store.py`, `backend/scripts/watch_demo.py`, `backend/tests/conftest.py`
- Test: `backend/tests/test_admin_api.py`

**Interfaces:**
- Consumes: `TuningStore`, `tuning_view`, `preview_prompt` (Task 5); `run_analysis(..., tuning=)`, `WatchRunner(..., tuning)` (Task 3); `tuning_hash` (Task 1).
- Produces:
  - `deps.get_tuning_store() -> TuningStore` (lru_cached, `get_settings().cache_dir / "admin_overrides.json"`), `deps.get_tuning(store) -> AgentTuning`.
  - Routes: `GET/PUT/DELETE /api/admin/tuning -> TuningView`, `POST /api/admin/prompts/preview -> PromptPreview`.
  - `AnalysisStore.put(analysis, config_key: str = "")`, `AnalysisStore.latest_for(image_id, config_key: str = "")`.
  - `WatchRunStore.start(repo, settings, llm, detector, start_min, end_min, tuning: AgentTuning = DEFAULT_TUNING)`; `WatchRun(..., tuning)` passes it to `WatchRunner`.

- [ ] **Step 1: Isolate the tuning store in tests**

In `backend/tests/conftest.py`: import `TuningStore` from `app.agent.tuning_store` and `get_tuning_store` from `app.api.deps`; change `_client` to take the store path and override the dependency; pass `tmp_path` from both fixtures:

```python
def _client(settings: Settings, repo: Repository | None, tuning_path: Path) -> Iterator[TestClient]:
    app = create_app()
    ...  # existing overrides unchanged
    tuning_store = TuningStore(tuning_path)
    app.dependency_overrides[get_tuning_store] = lambda: tuning_store
    ...


@pytest.fixture
def client(settings: Settings, tmp_path: Path) -> Iterator[TestClient]:
    """App with no data on disk."""
    yield from _client(settings, None, tmp_path / "admin_overrides.json")


@pytest.fixture
def golden_client(
    golden_settings: Settings, golden_repo: Repository, tmp_path: Path
) -> Iterator[TestClient]:
    """App serving the golden fixture."""
    yield from _client(golden_settings, golden_repo, tmp_path / "admin_overrides.json")
```

`tests/test_api.py` imports `_client` directly: `grep -n "_client(" backend/tests/*.py` and add a third argument `tmp_path / "admin_overrides.json"` at each call (add `tmp_path: Path` to that test's parameters).

- [ ] **Step 2: Write the failing API tests**

`backend/tests/test_admin_api.py`:

```python
"""Admin tuning API (spec §3.5)."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.agent.watch.prompts import PROMPT_FILES, file_text
from app.services.tuning import DEFAULT_TUNING


def _body(**ceiling: float) -> dict:  # type: ignore[type-arg]
    t = DEFAULT_TUNING.model_copy(
        update={"ceiling": DEFAULT_TUNING.ceiling.model_copy(update=ceiling)}
    )
    return t.model_dump(mode="json")


def test_get_returns_defaults(client: TestClient) -> None:
    view = client.get("/api/admin/tuning").json()
    assert view["overridden"] == [] and view["load_warning"] is None
    assert view["current"] == view["defaults"]
    assert "approach_high_km" in view["prompt_variables"]["watcher"]


def test_put_then_get_then_delete(client: TestClient) -> None:
    res = client.put("/api/admin/tuning", json=_body(at_base_m=1500.0))
    assert res.status_code == 200 and res.json()["overridden"] == ["ceiling.at_base_m"]
    assert client.get("/api/admin/tuning").json()["current"]["ceiling"]["at_base_m"] == 1500.0
    reset = client.delete("/api/admin/tuning").json()
    assert reset["overridden"] == []


def test_put_rejects_rule_breaks_with_paths(client: TestClient) -> None:
    res = client.put("/api/admin/tuning", json=_body(approach_high_m=4000.0))
    assert res.status_code == 422
    assert res.json() == {
        "error": "invalid_tuning",
        "detail": "ceiling.approach_high_m: not_above ceiling.approach_medium_m",
    }


def test_preview(client: TestClient) -> None:
    body = {
        "name": "supervisor",
        "text": file_text(PROMPT_FILES["supervisor"]),
        "tuning": DEFAULT_TUNING.model_dump(mode="json"),
    }
    res = client.post("/api/admin/prompts/preview", json=body).json()
    assert res["rendered"].startswith("# Role") and res["missing"] == []


def test_analysis_cache_respects_tuning(golden_client: TestClient) -> None:
    first = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    again = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    assert again["analysis_id"] == first["analysis_id"]
    golden_client.put("/api/admin/tuning", json=_body(at_base_m=1500.0))
    tuned = golden_client.post("/api/analyses", json={"image_id": "img_000860"}).json()
    assert tuned["analysis_id"] != first["analysis_id"]


def test_golden_client_uses_an_isolated_tuning_store(
    golden_client: TestClient, tmp_path: Path
) -> None:
    from app.api.deps import get_tuning_store

    store = golden_client.app.dependency_overrides[get_tuning_store]()  # type: ignore[attr-defined]
    assert store.path.is_relative_to(tmp_path)
    view = golden_client.get("/api/admin/tuning").json()
    assert view["overridden"] == [] and view["load_warning"] is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `uv --directory backend run pytest tests/test_admin_api.py -q`
Expected: FAIL (404 on `/api/admin/tuning`, ImportError for `get_tuning_store`).

- [ ] **Step 4: Dependencies and routes**

Append to `backend/app/api/deps.py` (imports: `from typing import Annotated`, `from fastapi import Depends`, `from app.agent.tuning_store import TuningStore`, `from app.domain.tuning import AgentTuning`):

```python
@lru_cache
def get_tuning_store() -> TuningStore:
    """Admin override file under the cache dir."""
    return TuningStore(get_settings().cache_dir / "admin_overrides.json")


def get_tuning(store: Annotated[TuningStore, Depends(get_tuning_store)]) -> AgentTuning:
    """Tuning snapshot for one request (defaults if the file is unusable)."""
    return store.load()[0]
```

`backend/app/api/routes/admin.py`:

```python
"""Admin endpoints: agent tuning and prompt preview (spec §3.5).

Unprotected by design for the local demo: auth is a frontend-only mock (frontend/CLAUDE.md).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.agent.tuning_store import TuningStore, preview_prompt, tuning_view
from app.api.deps import get_tuning_store
from app.core.config import Settings, get_settings
from app.domain.tuning import AgentTuning, PromptPreview, PromptPreviewRequest, TuningView

router = APIRouter(tags=["admin"])
Store = Annotated[TuningStore, Depends(get_tuning_store)]
Config = Annotated[Settings, Depends(get_settings)]


@router.get("/admin/tuning", response_model=TuningView)
def get_tuning_view(store: Store, settings: Config) -> TuningView:
    """Defaults, current values, overridden paths and prompt texts."""
    return tuning_view(store, settings)


@router.put("/admin/tuning", response_model=TuningView)
def put_tuning(body: AgentTuning, store: Store, settings: Config) -> TuningView:
    """Validate and save; applies to the next analysis and the next watch run."""
    store.save(body)
    return tuning_view(store, settings)


@router.delete("/admin/tuning", response_model=TuningView)
def reset_tuning(store: Store, settings: Config) -> TuningView:
    """Back to the defaults."""
    store.reset()
    return tuning_view(store, settings)


@router.post("/admin/prompts/preview", response_model=PromptPreview)
def post_prompt_preview(body: PromptPreviewRequest, settings: Config) -> PromptPreview:
    """Render a prompt text with sample scene values and the given tuning."""
    return preview_prompt(body, settings)
```

In `backend/app/main.py`: import `admin` in the routes import and add `app.include_router(admin.router, prefix="/api")`.

- [ ] **Step 5: Analysis cache keyed by tuning**

`backend/app/agent/store.py`:

```python
class AnalysisStore:
    """Holds analyses for the process lifetime; latest per (image, config) for quick reuse."""

    def __init__(self) -> None:
        self._by_id: dict[str, Analysis] = {}
        self._latest: dict[tuple[str, str], str] = {}

    ...

    def put(self, analysis: Analysis, config_key: str = "") -> None:
        """Store an analysis and mark it as the latest for its image under `config_key`."""
        self._by_id[analysis.id] = analysis
        self._latest[(analysis.image_id, config_key)] = analysis.id

    def latest_for(self, image_id: str, config_key: str = "") -> Analysis | None:
        """Most recent analysis of `image_id` made with `config_key`, if any."""
        aid = self._latest.get((image_id, config_key))
        return self._by_id.get(aid) if aid else None
```

Update the module docstring's TODO to: `TODO(P2): back with the disk cache keyed by (image_id, config_key) and per-analysis event buffers.`

`backend/app/api/routes/analyses.py` — add `tuning: Annotated[AgentTuning, Depends(get_tuning)]` and:

```python
    key = tuning_hash(tuning)
    cached = None if body.force_refresh else store.latest_for(body.image_id, key)
    if cached is not None:
        return AnalysisCreated(analysis_id=cached.id)
    analysis = run_analysis(
        store.new_id(), body.image_id, repo, detector, settings,
        fallback_detector=fallback, tuning=tuning,
    )
    store.put(analysis, key)
```

(Check other `store.put(` / `latest_for(` callers: `grep -rn "latest_for\|store.put(" backend/app backend/scripts`; callers without a tuning keep the default `""` key.)

- [ ] **Step 6: Watch runs get the snapshot**

`backend/app/agent/watch/store.py`: `WatchRun.__init__` gets `tuning: AgentTuning` as the last parameter and builds `WatchRunner(repo, settings, llm, self.add, detector, tuning)`; `WatchRunStore.start(..., end_min, tuning: AgentTuning = DEFAULT_TUNING)` passes it to `WatchRun`.

`backend/app/api/routes/watch.py` `create_run`: add `tuning: Annotated[AgentTuning, Depends(get_tuning)]` and call `store.start(repo, settings, llm, detector, to_minutes(body.start), to_minutes(body.end), tuning)`.

`backend/scripts/watch_demo.py`: after `settings = get_settings().model_copy(update=overrides)`:

```python
    tuning, tuning_warning = TuningStore(settings.cache_dir / "admin_overrides.json").load()
    if tuning_warning:
        print(f"admin tuning ignored: {tuning_warning}")
```

pass `tuning` as the last argument of `WatchRunner(repo, settings, llm, on_event, detector, tuning)`, and add ` · tuning {tuning_hash(tuning)}` to the header `print`. Imports: `from app.agent.tuning_store import TuningStore`, `from app.services.tuning import tuning_hash`.

- [ ] **Step 7: Run all tests**

Run: `uv --directory backend run pytest -q`
Expected: PASS (golden and adversarial unchanged).

- [ ] **Step 8: Lint, types, and a manual smoke check**

Run: `uv --directory backend run ruff check . && uv --directory backend run ruff format . && uv --directory backend run mypy app`
Then: `uv --directory backend run python -m scripts.watch_demo --start 10:10 --end 10:15 --no-llm --no-detector`
Expected: header line shows `tuning <8 hex>`; run completes.

- [ ] **Step 9: Update backend docs**

- `docs/AGENT_DESIGN.md`: add a section "Admin tuning" (≤ 25 lines): what `AgentTuning` holds, defaults = module constants, snapshot at run/analysis start, override file location, `/api/admin/*` endpoints and error format, prompts v8 variables, "unprotected by design for the local demo".
- `backend/CLAUDE.md`: in Coding rules, after the tunables line add: "Risk thresholds are module constants that seed `DEFAULT_TUNING` (`services/tuning.py`); functions take the tuning sub-model as a defaulted keyword argument. The admin's changes live in `.cache/admin_overrides.json` and are snapshotted per run." In the architecture list add `agent/tuning_store.py` and `api/routes/admin.py`. In Agent rules replace `watcher_v7`/`supervisor_v7` mentions (if any) with `_v8`.

- [ ] **Step 10: Commit**

```bash
git add backend docs/AGENT_DESIGN.md
git commit -m "feat(api): admin tuning endpoints; runs and analyses use the saved tuning

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Frontend data layer

**Files:**
- Modify: `frontend/src/api/schema.d.ts` (generated), `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/endpoints.ts`
- Create: `frontend/src/hooks/useTuning.ts`, `frontend/src/lib/tuningFields.ts`
- Modify: `frontend/src/i18n/tr.ts`, `frontend/src/i18n/en.ts`

**Interfaces:**
- Consumes: the OpenAPI types from Task 6.
- Produces:
  - types: `AgentTuning`, `TuningView`, `PromptPreview`, `PromptName = 'watcher' | 'supervisor'`, `Tier`.
  - client: `apiPut<T>(path, body)`, `apiDelete<T>(path)`.
  - endpoints: `getTuning(): Promise<TuningView>`, `putTuning(t: AgentTuning): Promise<TuningView>`, `deleteTuning(): Promise<TuningView>`, `previewPrompt(name: PromptName, text: string, tuning: AgentTuning): Promise<PromptPreview>`.
  - hooks: `useTuning(): { query, save, reset }`, `usePromptPreview(name, text, tuning): UseQueryResult<PromptPreview>`.
  - lib: `type Unit = 'm' | 'ms' | 'deg' | 'min' | 'pts' | 'count' | 'mpm'`, `interface FieldDef { path: string; unit: Unit; nullable?: boolean }`, `interface TierDef { path: 'rubric.distance_tiers' | 'rubric.approach_rate_tiers'; unit: Unit }`, `interface SectionDef { id: SectionId; fields: FieldDef[]; tiers: TierDef[] }`, `SECTIONS: SectionDef[]`, `AGENT_FIELDS: Record<PromptName, FieldDef[]>`, `getAt(obj: unknown, path: string): unknown`, `setAt<T>(obj: T, path: string, value: unknown): T`, `changedPaths(a: AgentTuning, b: AgentTuning): string[]`, `parseProblems(detail: string): Record<string, { code: string; arg: string }>`.
  - i18n: `t.admin.*` keys listed in Step 5.

- [ ] **Step 1: Generate the API types**

Run: `make gen-types`
Expected: `frontend/src/api/schema.d.ts` now contains `AgentTuning`, `TuningView`, `PromptPreview`, `PromptPreviewRequest` and the `/api/admin/*` paths.

- [ ] **Step 2: Type aliases and client verbs**

Append to `frontend/src/api/types.ts`:

```ts
// Admin tuning
export type AgentTuning = Schemas['AgentTuning']
export type TuningView = Schemas['TuningView']
export type PromptPreview = Schemas['PromptPreview']
export type PromptName = Schemas['PromptPreviewRequest']['name']
export type Tier = Schemas['Tier']
```

Append to `frontend/src/api/client.ts`:

```ts
export const apiPut = <T>(path: string, body: unknown) =>
  request<T>(path, { method: 'PUT', body: JSON.stringify(body) })
export const apiDelete = <T>(path: string) => request<T>(path, { method: 'DELETE' })
```

Append to `frontend/src/api/endpoints.ts` (extend the `./client` and `./types` imports):

```ts
export const getTuning = () => apiGet<TuningView>('/api/admin/tuning')
export const putTuning = (tuning: AgentTuning) => apiPut<TuningView>('/api/admin/tuning', tuning)
export const deleteTuning = () => apiDelete<TuningView>('/api/admin/tuning')
export const previewPrompt = (name: PromptName, text: string, tuning: AgentTuning) =>
  apiPost<PromptPreview>('/api/admin/prompts/preview', { name, text, tuning })
```

- [ ] **Step 3: Hooks**

`frontend/src/hooks/useTuning.ts`:

```ts
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { deleteTuning, getTuning, previewPrompt, putTuning } from '@/api/endpoints'
import type { AgentTuning, PromptName, TuningView } from '@/api/types'

const KEY = ['admin', 'tuning'] as const

/** Admin tuning: the saved view plus save and reset mutations (both refresh the view). */
export function useTuning() {
  const qc = useQueryClient()
  const query = useQuery({ queryKey: KEY, queryFn: getTuning, retry: false })
  const onSuccess = (view: TuningView) => qc.setQueryData(KEY, view)
  const save = useMutation({ mutationFn: putTuning, onSuccess })
  const reset = useMutation({ mutationFn: deleteTuning, onSuccess })
  return { query, save, reset }
}

function useDebounced<T>(value: T, ms: number): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

/** Rendered prompt for the editor text, 400 ms after the last change. */
export function usePromptPreview(name: PromptName, text: string, tuning: AgentTuning) {
  const input = useDebounced({ name, text, tuning }, 400)
  return useQuery({
    queryKey: ['admin', 'preview', input],
    queryFn: () => previewPrompt(input.name, input.text, input.tuning),
    placeholderData: (prev) => prev,
    retry: false,
  })
}
```

- [ ] **Step 4: Field metadata and path helpers**

`frontend/src/lib/tuningFields.ts`:

```ts
// Presentation metadata for the admin tuning form: which fields, in which order, with which unit.
// Values, defaults and validation come from the API; nothing here decides a risk level.
import type { AgentTuning, PromptName } from '@/api/types'

export type Unit = 'm' | 'ms' | 'deg' | 'min' | 'pts' | 'count' | 'mpm'
export type SectionId = 'behavior' | 'groups' | 'rubric' | 'ceiling' | 'judgment'
export interface FieldDef {
  path: string
  unit: Unit
  nullable?: boolean
}
export interface TierDef {
  path: 'rubric.distance_tiers' | 'rubric.approach_rate_tiers'
  unit: Unit
}
export interface SectionDef {
  id: SectionId
  fields: FieldDef[]
  tiers: TierDef[]
}

const f = (path: string, unit: Unit, nullable = false): FieldDef => ({ path, unit, nullable })

export const SECTIONS: SectionDef[] = [
  {
    id: 'behavior',
    tiers: [],
    fields: [
      f('behavior.loop_sweep_deg', 'deg'),
      f('behavior.orbit_min_path_m', 'm'),
      f('behavior.orbit_max_range_m', 'm'),
      f('behavior.parked_max_path_m', 'm'),
      f('behavior.leaving_start_m', 'm'),
      f('behavior.leaving_gain_m', 'm'),
      f('behavior.approach_gain_m', 'm'),
    ],
  },
  {
    id: 'groups',
    tiers: [],
    fields: [
      f('groups.large_group', 'count'),
      f('groups.group_radius_m', 'm'),
      f('groups.group_min_move_m', 'm'),
    ],
  },
  {
    id: 'rubric',
    tiers: [
      { path: 'rubric.distance_tiers', unit: 'm' },
      { path: 'rubric.approach_rate_tiers', unit: 'mpm' },
    ],
    fields: [
      f('rubric.pattern_points.loops_around_base', 'pts'),
      f('rubric.pattern_points.fixed_range_orbit', 'pts'),
      f('rubric.group_points', 'pts'),
      f('rubric.heading_points', 'pts'),
      f('rubric.heading_tolerance_deg', 'deg'),
      f('rubric.long_stop_min', 'min'),
      f('rubric.stop_near_base_m', 'm'),
      f('rubric.stop_points_first', 'pts'),
      f('rubric.stop_points_extra', 'pts'),
      f('rubric.type_points.truck', 'pts'),
      f('rubric.type_points.bus', 'pts'),
      f('rubric.type_points.van', 'pts'),
      f('rubric.level_step', 'pts'),
    ],
  },
  {
    id: 'ceiling',
    tiers: [],
    fields: [
      f('ceiling.at_base_m', 'm'),
      f('ceiling.pattern_high_m', 'm'),
      f('ceiling.approach_heading_deg', 'deg'),
      f('ceiling.approach_high_m', 'm'),
      f('ceiling.approach_high_eta_min', 'min'),
      f('ceiling.approach_medium_ms', 'ms'),
      f('ceiling.approach_medium_m', 'm'),
      f('ceiling.approach_medium_eta_min', 'min'),
    ],
  },
  {
    id: 'judgment',
    tiers: [],
    fields: [f('judgment.closing_min_m_per_min', 'mpm'), f('agents.watcher_spot_checks', 'count', true)],
  },
]

export const AGENT_FIELDS: Record<PromptName, FieldDef[]> = {
  watcher: [f('agents.watcher_max_tool_calls', 'count', true)],
  supervisor: [f('agents.supervisor_max_tool_calls', 'count', true)],
}

export function getAt(obj: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>(
    (node, key) => (node && typeof node === 'object' ? (node as Record<string, unknown>)[key] : undefined),
    obj,
  )
}

export function setAt<T>(obj: T, path: string, value: unknown): T {
  const [head, ...rest] = path.split('.')
  const node = (obj ?? {}) as Record<string, unknown>
  if (head === undefined) return obj
  return { ...node, [head]: rest.length ? setAt(node[head], rest.join('.'), value) : value } as T
}

const LEAF_PATHS: string[] = [
  ...SECTIONS.flatMap((s) => [...s.fields.map((x) => x.path), ...s.tiers.map((x) => x.path)]),
  ...Object.values(AGENT_FIELDS).flatMap((fs) => fs.map((x) => x.path)),
  'agents.watcher_reasoning_effort',
  'agents.supervisor_reasoning_effort',
  'agents.brief_language',
  'prompts.watcher',
  'prompts.supervisor',
]

/** Leaf paths whose values differ between two tunings. */
export function changedPaths(a: AgentTuning, b: AgentTuning): string[] {
  return LEAF_PATHS.filter((p) => JSON.stringify(getAt(a, p)) !== JSON.stringify(getAt(b, p)))
}

/** "path: code arg; path: code" (backend tuning_problems) -> { path: { code, arg } }. */
export function parseProblems(detail: string): Record<string, { code: string; arg: string }> {
  const out: Record<string, { code: string; arg: string }> = {}
  for (const part of detail.split('; ')) {
    const [path, rest = ''] = part.split(': ')
    if (!path) continue
    const [code = '', ...args] = rest.split(' ')
    out[path] = { code, arg: args.join(' ') }
  }
  return out
}
```

(Also export `LEAF_PATHS` is not needed; keep it module-private.)

- [ ] **Step 5: Strings**

In `frontend/src/i18n/tr.ts`, replace `admin: { title: ..., comingSoon: ... }` with:

```ts
  admin: {
    title: 'Ajan Ayarları',
    subtitle: 'Riskli araç kuralları ve ajan promptları',
    applyNote: 'Değişiklikler sonraki analiz ve canlı izleme koşularında geçerli. /watch’taki kayıtlı oturumlar değişmez.',
    tabs: { rules: 'Risk Kuralları', prompts: 'Ajan Promptları' },
    unsaved: (n: number) => `${n} kaydedilmemiş değişiklik`,
    overriddenCount: (n: number) => `${n} alan varsayılandan farklı`,
    save: 'Kaydet',
    saving: 'Kaydediliyor…',
    revert: 'Geri al',
    resetAll: 'Hepsini varsayılana döndür',
    resetAllConfirm: 'Tüm ayarlar ve promptlar varsayılana dönecek. Emin misiniz?',
    resetField: 'Varsayılana döndür',
    defaultValue: (v: string) => `varsayılan ${v}`,
    envValue: (v: string) => `boş = ortam ayarı (${v})`,
    invalidNumber: 'Geçerli bir sayı girin',
    saveFailed: 'Kaydedilemedi',
    saveBlocked: 'Geçersiz alanlar var',
    loadFailed: 'Ayarlar yüklenemedi',
    retry: 'Tekrar dene',
    loadWarning: (w: string) => `Kayıtlı ayar dosyası kullanılamadı, varsayılanlar gösteriliyor (${w}).`,
    units: { m: 'm', ms: 'm/s', deg: '°', min: 'dk', pts: 'puan', count: 'adet', mpm: 'm/dk' },
    sections: {
      behavior: { title: '1 · Davranış sınıfı', body: 'Rotanın üs etrafında dönme, sabit menzilde yörünge, park ve yaklaşma olarak sınıflandırıldığı eşikler.' },
      groups: { title: '2 · Birlikte hareket', body: 'Hangi araçların grup sayıldığı ve kaç aracın “büyük grup” olduğu.' },
      rubric: { title: '3 · Rubrik puanı', body: 'Araç başına 0–100 taban puanı; kademe adımı puanı seviyeye çevirir.' },
      ceiling: { title: '4 · Tavan seviyesi', body: 'Aracın alabileceği en yüksek seviye; LLM ve Supervisor bunun üstüne çıkamaz.' },
      judgment: { title: '5 · LLM’e gönderim', body: 'Hangi araçların LLM’e tam satır olarak gittiği.' },
    },
    tiers: {
      'rubric.distance_tiers': { title: 'Üsse mesafe kademeleri', row: 'mesafe <' },
      'rubric.approach_rate_tiers': { title: 'Yaklaşma hızı kademeleri (60 dk)', row: 'hız >' },
    },
    fields: {
      'behavior.loop_sweep_deg': 'Üs etrafında dönüş açısı (loop)',
      'behavior.orbit_min_path_m': 'Yörünge için en az yol',
      'behavior.orbit_max_range_m': 'Yörüngede menzil bandı',
      'behavior.parked_max_path_m': 'Park sayılan en fazla yol',
      'behavior.leaving_start_m': 'Üsten ayrılma: başlangıç yakınlığı',
      'behavior.leaving_gain_m': 'Üsten ayrılma: uzaklaşma',
      'behavior.approach_gain_m': 'Sürekli yaklaşma: yaklaşma miktarı',
      'groups.large_group': 'Büyük grup (araç sayısı)',
      'groups.group_radius_m': 'Grup yarıçapı',
      'groups.group_min_move_m': 'Grupta en az hareket (15 dk)',
      'rubric.pattern_points.loops_around_base': 'Loop deseni puanı',
      'rubric.pattern_points.fixed_range_orbit': 'Yörünge deseni puanı',
      'rubric.group_points': 'Büyük grup puanı',
      'rubric.heading_points': 'Üsse yönelme puanı',
      'rubric.heading_tolerance_deg': 'Üsse yönelme toleransı',
      'rubric.long_stop_min': 'Uzun duruş süresi',
      'rubric.stop_near_base_m': 'Duruşun üsse uzaklığı',
      'rubric.stop_points_first': 'İlk uzun duruş puanı',
      'rubric.stop_points_extra': 'Ek uzun duruş puanı',
      'rubric.type_points.truck': 'Kamyon puanı',
      'rubric.type_points.bus': 'Otobüs puanı',
      'rubric.type_points.van': 'Van puanı',
      'rubric.level_step': 'Seviye adımı (puan)',
      'ceiling.at_base_m': 'Üsse yakın: her durumda HIGH',
      'ceiling.pattern_high_m': 'Desen HIGH mesafesi',
      'ceiling.approach_heading_deg': 'Üsse yönelmiş sayılma açısı',
      'ceiling.approach_high_m': 'Yaklaşma HIGH mesafesi',
      'ceiling.approach_high_eta_min': 'Yaklaşma HIGH varış süresi',
      'ceiling.approach_medium_ms': 'Yaklaşma MEDIUM en az hız',
      'ceiling.approach_medium_m': 'Yaklaşma MEDIUM mesafesi',
      'ceiling.approach_medium_eta_min': 'Yaklaşma MEDIUM varış süresi',
      'judgment.closing_min_m_per_min': 'Tam satır için son 5 dk yaklaşma hızı',
      'agents.watcher_spot_checks': 'Spot-check araç sayısı',
      'agents.watcher_max_tool_calls': 'Tick başına sorgu limiti',
      'agents.supervisor_max_tool_calls': 'Tick başına sorgu limiti',
    } as Record<string, string>,
    agents: { watcher: 'Gözcü (Watcher)', supervisor: 'Baş Denetçi (Supervisor)' },
    agentSettings: 'Ajan ayarları',
    reasoningEffort: 'Düşünme seviyesi',
    language: 'Çıktı dili',
    languages: { tr: 'Türkçe', en: 'İngilizce' },
    envOption: (v: string) => `Ortam ayarı (${v})`,
    promptTitle: 'Sistem promptu',
    promptSource: { file: 'Dosya (v8)', admin: 'Admin' },
    promptReset: 'Dosyadaki metne dön',
    variables: 'Zorunlu değişkenler (tıkla: imlece ekle)',
    preview: 'Önizleme (güncel eşiklerle)',
    previewEmpty: 'Önizleme için metin girin',
    previewProblems: 'Önizleme yok: değişkenleri düzeltin',
    errors: {
      positive: 'Sıfırdan büyük olmalı',
      range: (a: string) => `İzin verilen aralık: ${a}`,
      increasing: 'Sınırlar artan sırada olmalı',
      decreasing: 'Sınırlar azalan sırada olmalı',
      tier_count: (a: string) => `${a} kademe olmalı`,
      not_above: 'MEDIUM değerinden büyük olamaz',
      missing_vars: (a: string) => `Eksik değişken: ${a}`,
      unknown_vars: (a: string) => `Bilinmeyen değişken: ${a}`,
    },
  },
```

Mirror the same keys in `en.ts` with English values (`title: 'Agent Settings'`, `tabs: { rules: 'Risk Rules', prompts: 'Agent Prompts' }`, etc.; `units` identical except `min: 'min'`, `pts: 'pts'`, `count: 'count'`, `mpm: 'm/min'`). `en.ts` is type-checked against `Messages`, so a missing key fails `pnpm typecheck`.

Remove `comingSoon` usages: `grep -rn "comingSoon" frontend/src` must return nothing after Task 8.

- [ ] **Step 6: Typecheck and lint**

Run: `pnpm --dir frontend typecheck && pnpm --dir frontend lint`
Expected: typecheck fails only on `AdminPage.tsx` using `t.admin.comingSoon` — replace its body now with a temporary `return <div className="p-6"><h1 className="text-xl font-semibold">{t.admin.title}</h1></div>` so both pass; Task 8 replaces it.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): admin tuning API client, hooks, field metadata and strings

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Risk rules tab and page shell

**Files:**
- Create: `frontend/src/components/admin/NumberField.tsx`, `TierTable.tsx`, `RuleSection.tsx`, `RiskRulesTab.tsx`, `AdminToolbar.tsx`, `AdminEditor.tsx`
- Modify: `frontend/src/pages/AdminPage.tsx`

**Interfaces:**
- Consumes: `useTuning`, `SECTIONS`, `getAt`, `setAt`, `changedPaths`, `parseProblems` (Task 7).
- Produces (props):
  - `NumberField({ label, unit, value, defaultValue, envValue?, nullable?, error?, onChange(value: number | null), onInvalid(invalid: boolean) })`
  - `TierTable({ def, tiers, defaults, error?, onChange(tiers: Tier[]) , onInvalid(invalid: boolean) })`
  - `RuleSection({ section, draft, defaults, errors, onChange(path, value), onInvalid(path, invalid) })`
  - `RiskRulesTab({ draft, view, errors, onChange, onInvalid })`
  - `AdminToolbar({ unsaved, overridden, invalid, saving, error?, onSave, onRevert, onResetAll })`
  - `AdminEditor({ view, save, reset })` — owns the draft; `PromptsTab` is plugged in by Task 9 (until then render nothing in the second tab).
  - `type FieldErrors = Record<string, { code: string; arg: string }>` exported from `AdminEditor.tsx`; `errorText(e?: {code: string; arg: string}): string | undefined` exported from `NumberField.tsx`.

- [ ] **Step 1: NumberField**

`frontend/src/components/admin/NumberField.tsx`:

```tsx
import { RotateCcw } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { t } from '@/i18n'
import type { Unit } from '@/lib/tuningFields'
import { cn } from '@/lib/utils'

type Problem = { code: string; arg: string }

/** Turkish text for a backend problem code (see services/tuning.tuning_problems). */
export function errorText(p?: Problem): string | undefined {
  if (!p) return undefined
  const e = t.admin.errors
  switch (p.code) {
    case 'positive': return e.positive
    case 'range': return e.range(p.arg)
    case 'increasing': return e.increasing
    case 'decreasing': return e.decreasing
    case 'tier_count': return e.tier_count(p.arg)
    case 'not_above': return e.not_above
    case 'missing_vars': return e.missing_vars(p.arg)
    case 'unknown_vars': return e.unknown_vars(p.arg)
    default: return `${p.code} ${p.arg}`.trim()
  }
}

interface Props {
  label: string
  unit: Unit
  value: number | null
  defaultValue: number | null
  envValue?: number
  nullable?: boolean
  error?: Problem
  onChange: (value: number | null) => void
  onInvalid: (invalid: boolean) => void
}

/** One number with unit, default hint, changed dot and reset; keeps invalid text locally. */
export function NumberField({ label, unit, value, defaultValue, envValue, nullable, error, onChange, onInvalid }: Props) {
  const [text, setText] = useState(value === null ? '' : String(value))
  useEffect(() => setText(value === null ? '' : String(value)), [value])
  const changed = value !== defaultValue
  const localInvalid = text.trim() === '' ? !nullable : Number.isNaN(Number(text))
  const message = localInvalid ? t.admin.invalidNumber : errorText(error)
  const hint =
    nullable && envValue !== undefined
      ? t.admin.envValue(String(envValue))
      : t.admin.defaultValue(`${defaultValue ?? ''} ${t.admin.units[unit]}`)

  const handle = (next: string) => {
    setText(next)
    const empty = next.trim() === ''
    const n = Number(next)
    const bad = empty ? !nullable : Number.isNaN(n)
    onInvalid(bad)
    if (!bad) onChange(empty ? null : n)
  }

  return (
    <div className="grid grid-cols-[1fr_9rem_auto] items-center gap-x-3 gap-y-0.5 py-1.5">
      <label className="flex items-center gap-2 text-sm">
        <span className={cn('size-1.5 rounded-full', changed ? 'bg-primary' : 'bg-transparent')} aria-hidden />
        {label}
      </label>
      <div className="flex items-center gap-1.5">
        <Input
          inputMode="decimal"
          value={text}
          aria-label={label}
          aria-invalid={Boolean(message)}
          onChange={(e) => handle(e.target.value)}
          className={cn('h-8 font-mono text-right', message && 'border-destructive')}
        />
        <span className="w-8 text-xs text-muted-foreground">{t.admin.units[unit]}</span>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="size-7"
        aria-label={t.admin.resetField}
        disabled={!changed}
        onClick={() => { onInvalid(false); onChange(defaultValue) }}
      >
        <RotateCcw className="size-3.5" />
      </Button>
      <span className="col-start-1 pl-3.5 text-xs text-muted-foreground">{hint}</span>
      {message && <span className="col-span-2 col-start-2 text-xs text-destructive">{message}</span>}
    </div>
  )
}
```

(Check `Button` supports `size="icon"` and `Input` accepts `className`: `grep -n "icon\|size:" frontend/src/components/ui/button.tsx`. Run `pnpm --dir frontend exec oxlint` formatting expectations: if the project formats one `case` per line, split the `switch` accordingly.)

- [ ] **Step 2: TierTable**

`frontend/src/components/admin/TierTable.tsx`:

```tsx
import type { Tier } from '@/api/types'
import { t } from '@/i18n'
import type { TierDef } from '@/lib/tuningFields'
import { NumberField, errorText } from './NumberField'

interface Props {
  def: TierDef
  tiers: Tier[]
  defaults: Tier[]
  error?: { code: string; arg: string }
  onChange: (tiers: Tier[]) => void
  onInvalid: (key: string, invalid: boolean) => void
}

/** Rubric tiers as rows: "<limit> -> <points>"; the tier count is fixed by the backend. */
export function TierTable({ def, tiers, defaults, error, onChange, onInvalid }: Props) {
  const labels = t.admin.tiers[def.path]
  const update = (i: number, patch: Partial<Tier>) =>
    onChange(tiers.map((tier, j) => (j === i ? { ...tier, ...patch } : tier)))
  return (
    <div className="rounded-md border p-3">
      <p className="text-sm font-medium">{labels.title}</p>
      {tiers.map((tier, i) => (
        <div key={i} className="grid grid-cols-2 gap-3">
          <NumberField
            label={`${labels.row} (${i + 1})`}
            unit={def.unit}
            value={tier.limit}
            defaultValue={defaults[i]?.limit ?? null}
            onChange={(v) => update(i, { limit: v ?? 0 })}
            onInvalid={(bad) => onInvalid(`${def.path}.${i}.limit`, bad)}
          />
          <NumberField
            label={t.admin.units.pts}
            unit="pts"
            value={tier.points}
            defaultValue={defaults[i]?.points ?? null}
            onChange={(v) => update(i, { points: Math.round(v ?? 0) })}
            onInvalid={(bad) => onInvalid(`${def.path}.${i}.points`, bad)}
          />
        </div>
      ))}
      {error && <p className="mt-1 text-xs text-destructive">{errorText(error)}</p>}
    </div>
  )
}
```

- [ ] **Step 3: RuleSection and RiskRulesTab**

`frontend/src/components/admin/RuleSection.tsx`:

```tsx
import type { AgentTuning, Tier, TuningView } from '@/api/types'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { t } from '@/i18n'
import { getAt, type SectionDef } from '@/lib/tuningFields'
import type { FieldErrors } from './AdminEditor'
import { NumberField } from './NumberField'
import { TierTable } from './TierTable'

interface Props {
  section: SectionDef
  draft: AgentTuning
  view: TuningView
  errors: FieldErrors
  onChange: (path: string, value: unknown) => void
  onInvalid: (key: string, invalid: boolean) => void
}

/** One pipeline step's thresholds (spec §4, cards 1-5). */
export function RuleSection({ section, draft, view, errors, onChange, onInvalid }: Props) {
  const copy = t.admin.sections[section.id]
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{copy.title}</CardTitle>
        <CardDescription>{copy.body}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {section.tiers.map((def) => (
          <TierTable
            key={def.path}
            def={def}
            tiers={getAt(draft, def.path) as Tier[]}
            defaults={getAt(view.defaults, def.path) as Tier[]}
            error={errors[def.path]}
            onChange={(tiers) => onChange(def.path, tiers)}
            onInvalid={onInvalid}
          />
        ))}
        <div className="divide-y">
          {section.fields.map((field) => {
            const knob = field.path.startsWith('agents.') ? field.path.slice('agents.'.length) : null
            return (
              <NumberField
                key={field.path}
                label={t.admin.fields[field.path] ?? field.path}
                unit={field.unit}
                nullable={field.nullable}
                value={getAt(draft, field.path) as number | null}
                defaultValue={getAt(view.defaults, field.path) as number | null}
                envValue={knob ? (getAt(view.env_knobs, knob) as number) : undefined}
                error={errors[field.path]}
                onChange={(v) => onChange(field.path, v)}
                onInvalid={(bad) => onInvalid(field.path, bad)}
              />
            )
          })}
        </div>
      </CardContent>
    </Card>
  )
}
```

`frontend/src/components/admin/RiskRulesTab.tsx`:

```tsx
import type { AgentTuning, TuningView } from '@/api/types'
import { SECTIONS } from '@/lib/tuningFields'
import type { FieldErrors } from './AdminEditor'
import { RuleSection } from './RuleSection'

interface Props {
  draft: AgentTuning
  view: TuningView
  errors: FieldErrors
  onChange: (path: string, value: unknown) => void
  onInvalid: (key: string, invalid: boolean) => void
}

/** The five threshold cards in pipeline order. */
export function RiskRulesTab(props: Props) {
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {SECTIONS.map((section) => (
        <RuleSection key={section.id} section={section} {...props} />
      ))}
    </div>
  )
}
```

- [ ] **Step 4: AdminToolbar**

`frontend/src/components/admin/AdminToolbar.tsx`:

```tsx
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { t } from '@/i18n'

interface Props {
  unsaved: number
  overridden: number
  invalid: boolean
  saving: boolean
  error?: string
  onSave: () => void
  onRevert: () => void
  onResetAll: () => void
}

/** Title, change counters and the save / revert / reset-all actions. */
export function AdminToolbar({ unsaved, overridden, invalid, saving, error, onSave, onRevert, onResetAll }: Props) {
  const confirmReset = () => {
    if (window.confirm(t.admin.resetAllConfirm)) onResetAll()
  }
  return (
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{t.admin.title}</h1>
        <p className="text-sm text-muted-foreground">{t.admin.applyNote}</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {overridden > 0 && <Badge variant="outline">{t.admin.overriddenCount(overridden)}</Badge>}
        {unsaved > 0 && <Badge>{t.admin.unsaved(unsaved)}</Badge>}
        {error && <span className="text-sm text-destructive">{error}</span>}
        <Button variant="ghost" onClick={confirmReset}>{t.admin.resetAll}</Button>
        <Button variant="outline" disabled={unsaved === 0 || saving} onClick={onRevert}>
          {t.admin.revert}
        </Button>
        <Button
          disabled={unsaved === 0 || invalid || saving}
          title={invalid ? t.admin.saveBlocked : undefined}
          onClick={onSave}
        >
          {saving ? t.admin.saving : t.admin.save}
        </Button>
      </div>
    </div>
  )
}
```

- [ ] **Step 5: AdminEditor (draft owner) and AdminPage**

`frontend/src/components/admin/AdminEditor.tsx`:

```tsx
import type { UseMutationResult } from '@tanstack/react-query'
import { useState } from 'react'
import { ApiError } from '@/api/client'
import type { AgentTuning, TuningView } from '@/api/types'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { t } from '@/i18n'
import { changedPaths, parseProblems, setAt } from '@/lib/tuningFields'
import { AdminToolbar } from './AdminToolbar'
import { RiskRulesTab } from './RiskRulesTab'

export type FieldErrors = Record<string, { code: string; arg: string }>

interface Props {
  view: TuningView
  save: UseMutationResult<TuningView, Error, AgentTuning>
  reset: UseMutationResult<TuningView, Error, void>
}

/** Holds the unsaved draft; remounted (key = view.hash) after every save or reset. */
export function AdminEditor({ view, save, reset }: Props) {
  const [draft, setDraft] = useState<AgentTuning>(view.current)
  const [invalid, setInvalid] = useState<Set<string>>(new Set())
  const onChange = (path: string, value: unknown) => setDraft((d) => setAt(d, path, value))
  const onInvalid = (key: string, bad: boolean) =>
    setInvalid((s) => {
      if (s.has(key) === bad) return s
      const next = new Set(s)
      if (bad) next.add(key)
      else next.delete(key)
      return next
    })

  const err = save.error ?? reset.error
  const errors: FieldErrors =
    err instanceof ApiError && err.status === 422 ? parseProblems(err.detail) : {}
  const banner = err && !(err instanceof ApiError && err.status === 422) ? t.admin.saveFailed : undefined
  const tabProps = { draft, view, errors, onChange, onInvalid }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <AdminToolbar
        unsaved={changedPaths(draft, view.current).length}
        overridden={view.overridden.length}
        invalid={invalid.size > 0}
        saving={save.isPending || reset.isPending}
        error={banner}
        onSave={() => save.mutate(draft)}
        onRevert={() => { setInvalid(new Set()); setDraft(view.current) }}
        onResetAll={() => reset.mutate()}
      />
      {view.load_warning && (
        <p className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-800">
          {t.admin.loadWarning(view.load_warning)}
        </p>
      )}
      <Tabs defaultValue="rules">
        <TabsList>
          <TabsTrigger value="rules">{t.admin.tabs.rules}</TabsTrigger>
          <TabsTrigger value="prompts">{t.admin.tabs.prompts}</TabsTrigger>
        </TabsList>
        <TabsContent value="rules">
          <RiskRulesTab {...tabProps} />
        </TabsContent>
        <TabsContent value="prompts">{null}</TabsContent>
      </Tabs>
    </div>
  )
}
```

`frontend/src/pages/AdminPage.tsx`:

```tsx
import { AdminEditor } from '@/components/admin/AdminEditor'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { useTuning } from '@/hooks/useTuning'
import { t } from '@/i18n'

/** /admin (admin role): agent tuning editor. */
export function AdminPage() {
  const { query, save, reset } = useTuning()
  if (query.isPending) {
    return (
      <div className="space-y-4 p-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    )
  }
  if (query.isError) {
    return (
      <div className="flex flex-col items-start gap-3 p-6">
        <p className="text-sm text-destructive">{t.admin.loadFailed}</p>
        <Button variant="outline" onClick={() => void query.refetch()}>{t.admin.retry}</Button>
      </div>
    )
  }
  return <AdminEditor key={query.data.hash} view={query.data} save={save} reset={reset} />
}
```

- [ ] **Step 6: Typecheck and lint**

Run: `pnpm --dir frontend typecheck && pnpm --dir frontend lint`
Expected: clean. Every new file ≤ ~150 lines (`wc -l frontend/src/components/admin/*.tsx`).

- [ ] **Step 7: Browser check of the rules tab**

Start the preview (`preview_start` with the project's dev config; create `.claude/launch.json` if missing with `make dev`-equivalent entries). Log in as `admin / admin123`, open `/admin`:
- change "Üsse yakın: her durumda HIGH" 1000 → 1500 → unsaved badge shows 1, Save enabled → Save → badge "1 alan varsayılandan farklı", dot on the field;
- reload → value still 1500; ↺ → 1000, Save → no overridden badge;
- type `abc` into any field → "Geçerli bir sayı girin" and Save disabled;
- set "Yaklaşma HIGH mesafesi" 5000 → Save → Turkish "MEDIUM değerinden büyük olamaz" under that field;
- check `read_console_messages` for errors. Screenshot for the summary.

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(ui): admin risk rules editor with draft, validation and reset

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Prompts tab

**Files:**
- Create: `frontend/src/components/ui/textarea.tsx` (via shadcn CLI)
- Create: `frontend/src/components/admin/PromptsTab.tsx`, `AgentSettingsCard.tsx`, `PromptEditor.tsx`, `PromptPreview.tsx`
- Modify: `frontend/src/components/admin/AdminEditor.tsx` (render `PromptsTab`)
- Modify: `frontend/CLAUDE.md`

**Interfaces:**
- Consumes: `usePromptPreview` (Task 7), `NumberField`, `errorText`, `FieldErrors` (Task 8), `AGENT_FIELDS`, `getAt` (Task 7).
- Produces:
  - `PromptsTab({ draft, view, errors, onChange, onInvalid })`
  - `AgentSettingsCard({ agent, draft, view, errors, onChange, onInvalid })`
  - `PromptEditor({ agent, text, fileText, variables, error?, onChange(text: string | null) })` — `null` means "use the file".
  - `PromptPreview({ agent, text, tuning })`

- [ ] **Step 1: Add the textarea primitive**

Run: `pnpm --dir frontend dlx shadcn@latest add textarea`
Expected: `frontend/src/components/ui/textarea.tsx` created; no other files changed except possibly `components.json`-driven imports. (Justification for the dependency: the prompt editor needs a multi-line input; shadcn keeps it consistent with the other primitives.)

- [ ] **Step 2: AgentSettingsCard**

`frontend/src/components/admin/AgentSettingsCard.tsx`:

```tsx
import type { AgentTuning, PromptName, TuningView } from '@/api/types'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { t } from '@/i18n'
import { AGENT_FIELDS, getAt } from '@/lib/tuningFields'
import type { FieldErrors } from './AdminEditor'
import { NumberField } from './NumberField'

interface Props {
  agent: PromptName
  draft: AgentTuning
  view: TuningView
  errors: FieldErrors
  onChange: (path: string, value: unknown) => void
  onInvalid: (key: string, invalid: boolean) => void
}

const EFFORTS = ['low', 'high', 'max'] as const

function Select({ label, value, env, options, onChange }: {
  label: string
  value: string | null
  env: string
  options: { value: string; label: string }[]
  onChange: (v: string | null) => void
}) {
  return (
    <label className="flex items-center justify-between gap-3 py-1.5 text-sm">
      {label}
      <select
        className="h-8 rounded-md border bg-background px-2 text-sm"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value === '' ? null : e.target.value)}
      >
        <option value="">{t.admin.envOption(env)}</option>
        {options.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
      </select>
    </label>
  )
}

/** Lookup limit, reasoning effort and (watcher card only) output language; empty = env. */
export function AgentSettingsCard({ agent, draft, view, errors, onChange, onInvalid }: Props) {
  const effortPath = `agents.${agent}_reasoning_effort`
  const envEffort = String(getAt(view.env_knobs, `${agent}_reasoning_effort`))
  return (
    <Card>
      <CardHeader><CardTitle className="text-base">{t.admin.agentSettings}</CardTitle></CardHeader>
      <CardContent className="divide-y">
        {AGENT_FIELDS[agent].map((field) => (
          <NumberField
            key={field.path}
            label={t.admin.fields[field.path] ?? field.path}
            unit={field.unit}
            nullable
            value={getAt(draft, field.path) as number | null}
            defaultValue={null}
            envValue={getAt(view.env_knobs, field.path.slice('agents.'.length)) as number}
            error={errors[field.path]}
            onChange={(v) => onChange(field.path, v === null ? null : Math.round(v))}
            onInvalid={(bad) => onInvalid(field.path, bad)}
          />
        ))}
        <Select
          label={t.admin.reasoningEffort}
          value={getAt(draft, effortPath) as string | null}
          env={envEffort}
          options={EFFORTS.map((e) => ({ value: e, label: e }))}
          onChange={(v) => onChange(effortPath, v)}
        />
        {agent === 'watcher' && (
          <Select
            label={t.admin.language}
            value={draft.agents.brief_language}
            env={t.admin.languages[view.env_knobs.brief_language]}
            options={(['tr', 'en'] as const).map((l) => ({ value: l, label: t.admin.languages[l] }))}
            onChange={(v) => onChange('agents.brief_language', v)}
          />
        )}
      </CardContent>
    </Card>
  )
}
```

(The language knob is shared by both agents; showing it once on the watcher card avoids two controls for one value.)

- [ ] **Step 3: PromptEditor**

`frontend/src/components/admin/PromptEditor.tsx`:

```tsx
import { useRef } from 'react'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { t } from '@/i18n'
import { cn } from '@/lib/utils'
import { errorText } from './NumberField'

interface Props {
  text: string | null
  fileText: string
  variables: string[]
  error?: { code: string; arg: string }
  onChange: (text: string | null) => void
}

const VAR = /\{\{(\w+)\}\}/g

/** Monospace prompt editor; null text = the versioned file. Variable chips insert at the cursor. */
export function PromptEditor({ text, fileText, variables, error, onChange }: Props) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const value = text ?? fileText
  const present = new Set([...value.matchAll(VAR)].map((m) => m[1]))

  const insert = (name: string) => {
    const el = ref.current
    const token = `{{${name}}}`
    const at = el?.selectionStart ?? value.length
    onChange(value.slice(0, at) + token + value.slice(el?.selectionEnd ?? at))
    requestAnimationFrame(() => el?.setSelectionRange(at + token.length, at + token.length))
  }

  return (
    <div className="flex min-h-0 flex-col gap-2">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium">{t.admin.promptTitle}</span>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{text === null ? t.admin.promptSource.file : t.admin.promptSource.admin}</Badge>
          <Button variant="ghost" size="sm" disabled={text === null} onClick={() => onChange(null)}>
            {t.admin.promptReset}
          </Button>
        </div>
      </div>
      <p className="text-xs text-muted-foreground">{t.admin.variables}</p>
      <div className="flex flex-wrap gap-1">
        {variables.map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => insert(v)}
            className={cn(
              'rounded border px-1.5 py-0.5 font-mono text-xs',
              present.has(v) ? 'text-muted-foreground' : 'border-destructive text-destructive',
            )}
          >
            {`{{${v}}}`}
          </button>
        ))}
      </div>
      <Textarea
        ref={ref}
        value={value}
        spellCheck={false}
        aria-label={t.admin.promptTitle}
        onChange={(e) => onChange(e.target.value === fileText ? null : e.target.value)}
        className="min-h-[28rem] flex-1 font-mono text-xs leading-relaxed"
      />
      {error && <p className="text-xs text-destructive">{errorText(error)}</p>}
    </div>
  )
}
```

- [ ] **Step 4: PromptPreview**

`frontend/src/components/admin/PromptPreview.tsx`:

```tsx
import type { AgentTuning, PromptName } from '@/api/types'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Skeleton } from '@/components/ui/skeleton'
import { usePromptPreview } from '@/hooks/useTuning'
import { t } from '@/i18n'

interface Props {
  agent: PromptName
  text: string
  tuning: AgentTuning
}

/** Server-rendered prompt with sample scene values and the draft thresholds. */
export function PromptPreview({ agent, text, tuning }: Props) {
  const preview = usePromptPreview(agent, text, tuning)
  let body
  if (!text.trim()) body = <p className="text-sm text-muted-foreground">{t.admin.previewEmpty}</p>
  else if (preview.isPending) body = <Skeleton className="h-96 w-full" />
  else if (preview.isError) body = <p className="text-sm text-destructive">{t.admin.loadFailed}</p>
  else if (preview.data.rendered === null) {
    body = <p className="text-sm text-destructive">{t.admin.previewProblems}</p>
  } else {
    body = <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed">{preview.data.rendered}</pre>
  }
  return (
    <div className="flex min-h-0 flex-col gap-2">
      <span className="text-sm font-medium">{t.admin.preview}</span>
      <ScrollArea className="h-[34rem] rounded-md border bg-muted/30 p-3">{body}</ScrollArea>
    </div>
  )
}
```

- [ ] **Step 5: PromptsTab and wiring**

`frontend/src/components/admin/PromptsTab.tsx`:

```tsx
import type { AgentTuning, PromptName, TuningView } from '@/api/types'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { t } from '@/i18n'
import type { FieldErrors } from './AdminEditor'
import { AgentSettingsCard } from './AgentSettingsCard'
import { PromptEditor } from './PromptEditor'
import { PromptPreview } from './PromptPreview'

interface Props {
  draft: AgentTuning
  view: TuningView
  errors: FieldErrors
  onChange: (path: string, value: unknown) => void
  onInvalid: (key: string, invalid: boolean) => void
}

const AGENTS: PromptName[] = ['watcher', 'supervisor']

/** Per agent: settings card, prompt editor and live preview. */
export function PromptsTab(props: Props) {
  const { draft, view, errors, onChange } = props
  return (
    <Tabs defaultValue="watcher">
      <TabsList>
        {AGENTS.map((a) => <TabsTrigger key={a} value={a}>{t.admin.agents[a]}</TabsTrigger>)}
      </TabsList>
      {AGENTS.map((agent) => {
        const text = draft.prompts[agent]
        return (
          <TabsContent key={agent} value={agent} className="grid gap-4 xl:grid-cols-[20rem_1fr_1fr]">
            <AgentSettingsCard agent={agent} {...props} />
            <PromptEditor
              text={text}
              fileText={view.prompt_defaults[agent]}
              variables={view.prompt_variables[agent]}
              error={errors[`prompts.${agent}`]}
              onChange={(v) => onChange(`prompts.${agent}`, v)}
            />
            <PromptPreview agent={agent} text={text ?? view.prompt_defaults[agent]} tuning={draft} />
          </TabsContent>
        )
      })}
    </Tabs>
  )
}
```

In `AdminEditor.tsx`: import `PromptsTab` and replace `<TabsContent value="prompts">{null}</TabsContent>` with `<TabsContent value="prompts"><PromptsTab {...tabProps} /></TabsContent>`.

- [ ] **Step 6: Typecheck, lint, file sizes**

Run: `pnpm --dir frontend typecheck && pnpm --dir frontend lint && wc -l frontend/src/components/admin/*.tsx`
Expected: clean; each file ≤ ~150 lines.

- [ ] **Step 7: Browser check of the prompts tab**

In the preview, `/admin` → "Ajan Promptları":
- Watcher: preview shows "within 3 km or 12 minutes may be MEDIUM"; switch to "Risk Kuralları", set "Yaklaşma MEDIUM mesafesi" to 2500, back to prompts → preview shows "within 2.5 km" (draft thresholds, before saving);
- in the editor delete `{{at_base_km}}` → that chip turns red, preview says "Önizleme yok: değişkenleri düzeltin"; Save → Turkish "Eksik değişken: at_base_km" under the editor; click the red chip → token inserted, chip back to normal, Save succeeds, source badge "Admin";
- "Dosyadaki metne dön" → badge "Dosya (v8)", Save;
- type a Turkish sentence ("şüpheli araç") into the prompt, Save, reload → text intact (Review Focus 5);
- Settings card: set lookup limit to empty → hint "boş = ortam ayarı (3)"; set reasoning effort "low", Save, reload → kept;
- `read_console_messages` clean; screenshot.
Finally "Hepsini varsayılana döndür" → confirm → no overridden badge; check `backend/.cache/admin_overrides.json` no longer exists.

- [ ] **Step 8: Frontend docs**

`frontend/CLAUDE.md`: in Structure add `admin/  AdminEditor (draft owner), AdminToolbar, RiskRulesTab, RuleSection, NumberField, TierTable, PromptsTab, AgentSettingsCard, PromptEditor, PromptPreview` under components, `useTuning` under hooks, `tuningFields.ts (admin field metadata + path helpers; presentation only)` under lib; in pages change the AdminPage entry to `AdminPage (/admin, admin role only: agent tuning — risk thresholds, agent knobs, prompts; saves apply to the next analysis / live watch run)`.

- [ ] **Step 9: Final verification**

Run: `make test && make lint`
Expected: all backend tests (golden included) and frontend typecheck/lint pass.

- [ ] **Step 10: Commit**

```bash
git add frontend docs
git commit -m "feat(ui): admin prompt editor with variable chips, live preview and agent knobs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
