# Admin: agent tuning (prompts + risk rules) — design

Date: 2026-09-26 · Status: approved in chat, awaiting spec review

## 1. Intent

An admin can edit, from `/admin`, without touching code:

- (a) the watcher and supervisor **prompt texts** and the agent knobs that fill their template
  variables (lookup limit, reasoning effort, output language, spot-check count);
- (b) the **thresholds used to mark a vehicle risky**: behavior-class thresholds, moving-group
  thresholds, rubric points and tiers, the level ceiling (`max_level`) rules and the rule that
  decides which rows go to the LLM in full.

Constraints (user decisions):

- No change to backend architecture: the layering `api/routes → agent → services → domain` stays;
  only small additions.
- Changes apply to the **next** frame analysis and the **next** live watch run
  (`POST /api/watch/runs`, `make watch-demo`). Recorded watch sessions on `/watch` do not change.
  To show a change on stage, record a new session with `make watch-demo SAVE=<name>`.
- Values live in a **local, gitignored override file**; code constants and `.md` prompts stay the
  defaults. Making a tuned value permanent is a separate code change (constant + prompt version).

Assumptions (not confirmed by the user):

- Admin endpoints are unprotected: auth is a frontend-only mock and the demo runs locally.
- A running watch run keeps the tuning snapshot it started with.
- Threshold numbers written in the prompts become `{{variables}}` filled from the tuning.

Success criteria:

- The admin changes a threshold → the next frame analysis / watch run uses it, and the prompts show
  the same number.
- With every value at its default, behavior is byte-identical to today: all existing tests, the
  golden test and the adversarial tests pass unchanged.

Out of scope: toggling individual row fields sent to the LLM; starting a live run from the panel;
backend auth; changing the model name from the panel (stays in env).

## 2. Chosen approach

A typed `AgentTuning` object, snapshotted at run start and passed **explicitly** to the pure
service functions as a keyword argument defaulting to `DEFAULT_TUNING`.

Rejected: mutating module constants at runtime (hidden global state, mid-run changes, stale
`from x import CONST` copies); moving thresholds into `Settings` (env-backed, `lru_cache`d, and
the services would still need the values passed in).

## 3. Backend

### 3.1 Model — `app/domain/tuning.py` (Pydantic only)

```
AgentTuning (frozen)
├── behavior   parked_max_path_m, leaving_start_m, leaving_gain_m, loop_sweep_deg,
│              orbit_min_path_m, orbit_max_range_m, approach_gain_m
├── groups     large_group, group_radius_m, group_min_move_m
├── rubric     distance_tiers [(max_m, points) x3], approach_rate_tiers [(min_m_per_min, points) x2],
│              heading_points, heading_tolerance_deg, long_stop_min, stop_near_base_m,
│              stop_points_first, stop_points_extra, pattern_points {loops_around_base, fixed_range_orbit},
│              group_points, type_points {truck, bus, van}, level_step
├── ceiling    at_base_m, pattern_high_m, approach_heading_deg, approach_high_m,
│              approach_high_eta_min, approach_medium_ms, approach_medium_m, approach_medium_eta_min
├── judgment   closing_min_m_per_min
├── agents     watcher_max_tool_calls, supervisor_max_tool_calls, watcher_spot_checks,
│              watcher_reasoning_effort, supervisor_reasoning_effort, brief_language
│              (same names as Settings; each None = use Settings)
└── prompts    watcher: str | None, supervisor: str | None   (None = the .md file)
```

- Every default equals today's constant. The domain model has no defaults (models only);
  `services/behavior.py` and `services/risk.py` build `DEFAULT_BEHAVIOR`, `DEFAULT_GROUPS`,
  `DEFAULT_RUBRIC`, `DEFAULT_CEILING` from their existing constants (which stay in place), and
  `services/tuning.py` assembles `DEFAULT_TUNING`. Functions take the sub-model they need, which
  avoids an import cycle between `services/tuning.py` and the modules it reads defaults from.
- The number of rubric tiers is fixed; only thresholds and points are editable.
- `GROUP_SAMPLES` (15 min) and `MOVING_MS` stay constants (tied to the tick length / track data).
- Validation is a pure function `tuning_problems(t)` in `services/tuning.py` (not Pydantic field
  constraints), so every rule returns the same `{error, detail}` shape. Each problem is
  `"<dotted.path>: <code> [arg]"`, problems joined with `"; "`; codes: `positive`, `range lo-hi`,
  `increasing`, `decreasing`, `tier_count n`, `not_above <path>`, `missing_vars a,b`,
  `unknown_vars a,b`. The UI translates codes to Turkish. Rules:
  - bounds: distances and speeds > 0, angles 0–360, points 0–100, `large_group` ≥ 2,
    `max_tool_calls` 0–10, `level_step` 1–50;
  - order: distance tiers strictly increasing, approach-rate tiers strictly decreasing,
    `approach_high_m ≤ approach_medium_m`, `approach_high_eta_min ≤ approach_medium_eta_min`.

### 3.2 Store — `app/agent/tuning_store.py`

- Reads/writes `settings.cache_dir / "admin_overrides.json"` (under the gitignored `.cache`).
- Stores only fields that differ from `DEFAULT_TUNING`; `load()` merges them onto the defaults.
- `save(tuning)` validates (model + prompt variables, §3.4) and writes atomically
  (temp file + replace). Write failure → `TuningStoreError` (typed, mapped to 503).
- `reset()` deletes the file.
- A missing file → defaults. An unreadable or invalid file → log a warning, return defaults and
  expose `load_warning` so the UI can show it. Never raises into a run.
- `tuning_hash(t)` = short hash of the canonical JSON; logged at run start with the prompt source.

### 3.3 Flow

- Snapshot at start: `routes/analyses.py` and `routes/watch.py` get the tuning from the store
  (FastAPI dependency) and pass it to `run_analysis(..., tuning)` / `WatchRunner(..., tuning)`.
  `scripts/watch_demo.py` loads it the same way.
- Service functions gain `tuning: AgentTuning = DEFAULT_TUNING`:
  `behavior_class`, `moving_groups`, `level_ceiling`, `motion_ceiling`, `distance_factor`,
  `motion_factors`, `pattern_factor`, `group_factor`, `level_for`, `score_vehicle`,
  `track_rubric`, `row_ceiling`, `vehicle_row` (services/watch.py); in the agent layer `WatchContext` carries the snapshot (used by `get_route` in `agent/watch/tools.py`),
  `needs_judgment`, spot-check count in `runner.py`, and the prompt renders.
- Agent knobs: `tuning.agents.x if not None else settings.x`, resolved once in the runner.
- No new global state; services stay pure.
- `AnalysisStore` reuses a finished analysis only when its tuning hash matches
  (`latest_for(image_id, config_key)`), so a tuning change shows on `/analysis` after re-analysis.
- Tests: `tests/conftest.py` points the tuning store at `tmp_path` for every client, so a
  developer's own `backend/.cache/admin_overrides.json` never leaks into tests or the golden test.

### 3.4 Prompts

- Copy `watcher_v7.md` → `watcher_v8.md`, `supervisor_v7.md` → `supervisor_v8.md`; replace the
  threshold numbers written in the text with variables (e.g. `{{approach_medium_ms}}`,
  `{{approach_medium_km}}`, `{{approach_medium_eta_min}}`, `{{approach_high_km}}`,
  `{{approach_high_eta_min}}`, `{{large_group}}`, `{{group_radius_m}}`, `{{at_base_km}}`).
  Values are formatted exactly as the v7 text writes them (e.g. `3 km`, `4 m/s`).
  The meaning does not change; the version bumps because the variable set changes.
- `PROMPT = "watcher_v8"` / `"supervisor_v8"`. v7 files stay for the equality test and history.
- `render()` takes an optional override text; with an override it renders that instead of the file.
- Required variables of a prompt = the `{{vars}}` in its `.md` file. An override must contain
  exactly that set (no missing, no unknown); otherwise `save` is rejected (422).
- If an override still fails at render time, the agent falls back to the file, emits a `warning`
  event and the run continues.

### 3.5 API — `app/api/routes/admin.py` (thin)

| Method | Path | Behavior |
|---|---|---|
| GET | `/api/admin/tuning` | `TuningView`: `defaults`, `current`, `overridden` (dotted field paths), `env_knobs` (Settings values used when an agent knob is null), `prompt_defaults` {watcher, supervisor}, `prompt_variables` {watcher, supervisor}, `hash`, `load_warning` |
| PUT | `/api/admin/tuning` | body: full `AgentTuning`; validate, store the diff, return `TuningView` |
| DELETE | `/api/admin/tuning` | reset to defaults, return `TuningView` |
| POST | `/api/admin/prompts/preview` | body: `{name, text, tuning}`; returns `{rendered}` with sample scene values, or `{missing, unknown}` |

- Per-field reset: the UI writes the default into the draft and PUTs; no extra endpoint.
- Errors: `{error, detail}` with the dotted field path in `detail`; 422 validation, 503 store.
- `response_model=` on every route; then `make gen-types`.

## 4. Frontend — `/admin`

- Header: title, "N fields changed" badge, **Revert** (discard draft), **Save**; an info line that
  changes apply to the next analysis / live run and recordings do not change;
  **Reset all to defaults**; a yellow banner when `load_warning` is set.
- Tabs: **Risk Kuralları** and **Ajan Promptları**.
- Risk tab: five cards in pipeline order — 1 Behavior class, 2 Moving together, 3 Rubric points,
  4 Level ceiling, 5 Sent to the LLM. Each card starts with a one-line explanation. Each field:
  Turkish label, unit (m, m/s, °, min, points), "default X", a changed dot and a ↺ reset button.
  Rubric tiers render as rows ("< [1000] m → [30] points").
- Prompts tab: sub-tabs Watcher / Supervisor.
  - Agent settings card: lookup limit, reasoning effort (native `<select>`), output language.
  - Monospace editor with source badge ("File (v8)" / "Admin"); required-variable chips (missing
    ones red; click inserts at the cursor).
  - Preview pane: `/prompts/preview`, debounced 400 ms, shows the rendered text with current
    thresholds.
- State: `useTuning` (TanStack Query: GET, PUT, DELETE, preview); the draft is page-local state;
  422 errors map to the field by path and show under it in Turkish; skeleton while loading; error
  state with retry.
- Files: `components/admin/` — `AdminToolbar`, `RuleSection`, `NumberField`, `TierTable`,
  `AgentSettingsCard`, `PromptEditor`, `PromptPreview` (each ≤ ~150 lines); `lib/tuningFields.ts`
  (field path → label key + unit; presentation only); strings in `i18n/tr.ts` and `en.ts`.
- New dependency: shadcn `textarea` (via CLI) — needed for the prompt editor.

## 5. Error handling

| Case | Behavior |
|---|---|
| Override file corrupt / off-schema | warn log, defaults, `load_warning` in GET, UI banner; runs unaffected |
| File write fails | `TuningStoreError` → 503; UI "could not save", draft kept |
| Prompt override fails at render | file prompt used, `warning` event, run continues |
| Save during a run | the run keeps its start snapshot |

## 6. Testing

- `tests/services/`: for each changed function, default tuning = old result; table tests where one
  threshold changes the outcome (e.g. `at_base_m=2000` lets a parked car at 1.5 km reach HIGH;
  `large_group=3` makes a 3-vehicle group MEDIUM; `loop_sweep_deg=180` reclassifies a half loop).
- `tests/agent/test_prompts_v8.py`: v8 rendered with defaults == v7 rendered, for both prompts.
- `tests/agent/test_tuning_store.py`: diff-only persistence, reset, corrupt file → defaults +
  warning, order/bounds rejections, missing/unknown prompt variable rejections.
- `tests/api/test_admin.py`: GET/PUT/DELETE/preview and 422 paths, store pointed at `tmp_path`.
- Golden and adversarial tests unchanged and green.
- Frontend: no test runner (none in the project); `pnpm typecheck && pnpm lint`, then browser
  check: change a threshold → save → reload → value kept → ↺ reset; delete a variable from a
  prompt → red chip and 422 on save.

## 7. Docs updated in the same change

- `docs/AGENT_DESIGN.md`: tuning section (model, snapshot rule, admin API, unprotected-by-design
  note for the demo).
- `backend/CLAUDE.md`: tunables line (thresholds now defaults for `AgentTuning`).
- `frontend/CLAUDE.md`: `components/admin/` and the `/admin` page description.
