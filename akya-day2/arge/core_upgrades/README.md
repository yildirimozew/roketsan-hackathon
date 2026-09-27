# core_upgrades — staged code for items Z1–Z11

Code for the items in `arge/YUKSEK_ONCELIKLI_GELISTIRME_FIKIRLERI.md`, one module per item. It
imports the live backend (`app.*`) and uses its types and services, so each module can be moved into
`backend/app/` with small edits. **Nothing under `backend/` was changed.**

## Run the tests

From `akya-day2/`, with the backend environment:

```
uv --directory backend run pytest ../arge/core_upgrades/tests -q -p no:cacheprovider
```

Status (2026-09-27): 36 tests pass on the real `data/`. The backend suite (103 tests, golden test
included) still passes. Ruff (backend config) is clean.

## Map: item → module → where it goes in the backend

| Item | Module | Integration point | Contract change |
|---|---|---|---|
| Z1 no silent LOW | `z01_detection_guard.py` | `services/detection/precomputed.py` (`detect` raises for a missing file/frame); `agent/pipeline.py` step 2 → `detect_with_fallback` | – |
| Z2 track-only vehicles | `z02_track_only.py` | pipeline step 4 (`find_track_only`), steps 5–7 (`score_track_only`) | None as staged (`TRK-<id>` as `detection_id`). Cleaner option: `VehicleRisk.detection_id: str \| None` + `source` |
| Z3 stationary | `z03_stationary.py` | `services/motion.py`; replaces `services/reports.py:_moving_at` via Z4 | – |
| Z4 capture time | `z04_capture_time.py` | pipeline step 6: `is_relevant` → `is_relevant_at_capture`, `verify_claim` → `verify_at_capture`; watch: `services/watch.py:reports_near` → `reports_near_at_capture` | `ReportLookup` docstring / field meaning ("at capture"); docs AGENT_DESIGN §3 6b, AGENT_FLOW §7 |
| Z5 absence | `z05_absence.py` | `services/reports.py:extract_claim` (order in `extract_claim_v2`); pipeline step 6 → `check_absence` | `ClaimKind` + `ABSENCE`, `CONTEXT`; `ReportClaim` + `absence`, `usual_count`; `CheckName` + `area` |
| Z6 direction + deception | `z06_deception.py` | `extract_claim` flags (`annotate`); pipeline step 6 → `assess` after Z4 | `ReportClaim` + `toward_base`, `identity_claim`; `ReportAssessment` + `deception_indicator`, `deception_track_ids`, `checked_frame_id`; `CheckName` + `direction`, `identity` |
| Z7 deception +1 | `z07_deception_level.py` | pipeline step 7 after `score_vehicle`; watch → `raise_watch_level` | – (docs: AGENT_DESIGN §3 steps 6–7, §12) |
| Z8 insufficient evidence | `z08_insufficient.py` | end of step 7 (`assess_evidence`), step 8 (`apply_to_brief`) | `Analysis` + `evidence` (`EvidenceStatus`) |
| Z9 control computer | `z09_guard.py` | step 8 (`guard_brief`, one repair, then template); watch → `check_text` + `facts_from_rows` | – |
| Z10 budget + mode | `z10_budget_mode.py` | `agent/llm_client.py` (`BudgetMonitor`), `/api/health`, `Analysis` / watch run `mode` | `Analysis` + `mode`; settings `SENTINEL_LLM_BUDGET_FLOOR_USD` |
| Z11 scenarios | `tests/test_z11_scenarios.py` | move to `backend/tests/agent/`; `_analyze` is the step 4–7 wiring reference | – |

All contract changes are staged in `contracts.py` as subclasses of the backend models. On
integration, fold the fields into `app/domain/*`, then run `make gen-types`.

## Integration order

Dependencies first, one commit per item:

1. Z1
2. Z3 → Z4 (docs in the same commit)
3. Z5, Z6
4. **Z7 only after Z4 and Z6.** With report-time matching, the +1 would punish vehicles whose
   reports are actually consistent (REP-06, REP-78, REP-120).
5. Z2, Z8
6. Z10
7. Z9
8. Z11 moves in with the items it covers.

## Open decisions and limits

- **Z7 ceiling:** `apply_deception(exceed_ceiling=True)` lets +1 pass the motion ceiling by one
  step. This is a new policy and needs approval; `False` keeps the ceiling.
- **Z1 data:** the detections file must be produced once with the team's weights; none are on this
  machine. Check it with `validate_detections_file`.
- **Z10 endpoint:** the `/key/info` path (`budget_url`) and response shape must be verified once
  against the gateway. The parser accepts a flat body and one nested under `"info"`.
- **Turkish text:** `DECEPTION_REASON` (Z6) and `UNCERTAINTY` / `REASON_TEXT` (Z8) belong in
  `agent/fallback_templates.py`, the only backend file allowed to hold Turkish.
- **Z4:** multi-vehicle claims use a minimal N−1 rule (`GROUP_M` = 80 m). Admiralty grading and
  full SALUTE parsing (arge_m R6.1, R6.10) are out of scope.
- **Not run:** mypy strict (the backend applies it to `app.*` only). Run it after moving the code.
