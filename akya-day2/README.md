# SENTINEL

**Field-report-aware base-security agent** — Level Up AI | ROKETSAN Hackathon, Stage 2.

An operator picks a drone frame and watches an agent, step by step:

1. **detect** vehicles (Stage 1 YOLO model),
2. **georeference** them from the frame's corner coordinates,
3. **match** each one to a vehicle track and analyze its last 2 hours (speed, heading, stops, trend toward the base),
4. **weigh untrusted field reports** against its own findings (corroborated / contradicted / unverified),
5. write an **evidence-cited risk brief**: LOW / MEDIUM / HIGH / CRITICAL.

> Core idea: **deterministic tools do the math, the LLM does the judgment.** Every number in a brief comes from tested code; reports are data, never instructions; every external dependency (model, LLM) has a fallback, so the demo never crashes.

---

## Status

| Phase | Scope | State |
|---|---|---|
| P0 | Scaffold: FastAPI + Vite/React/shadcn, domain models, contracts | ✅ |
| P1 | Data loader, georeferencing, Hungarian track matching, motion analysis, golden test | ✅ |
| P2 | LLM report extraction/verdicts + LLM brief with validator, SSE streaming | 🟡 rule-based fallback path works end to end; LLM + SSE pending (credentials arrive Saturday) |
| P3 | Analysis UI | 🟡 step-player UI working on the synchronous API |
| P4 | Batch precompute, replay mode, reports inspector, analyst chat | ⏳ |

The organizer's data is committed in `data/` (see [Organizer data](#organizer-data)). A **synthetic day in the exact raw formats** can still be generated for tests and demos (see [Mock data](#mock-data)).

---

## Architecture

```
Frame ──► [1 Load meta] ──► [2 Detect] ──► [3 Georeference] ──► [4 Match tracks]
                                                                      │
   [8 Brief] ◄── [7 Risk score] ◄── [6 Assess reports] ◄── [5 Motion analysis]
```

| Layer | Stack | Notes |
|---|---|---|
| Backend | Python 3.12, FastAPI, Pydantic v2, uv | `api → agent → services → domain`, one-way dependencies |
| Detection | `Detector` protocol: Ultralytics YOLO (CUDA) or precomputed JSON | Live model falls back to precomputed boxes on failure |
| Matching | `scipy.optimize.linear_sum_assignment` + 25 m gate | Globally optimal 1-to-1 assignment |
| LLM | OpenAI-compatible client (GLM) | P2; until then a rule-based path with the same contracts |
| Frontend | Vite, React 19, TypeScript (strict), Tailwind v4, shadcn/ui, TanStack Query | Types generated from OpenAPI, never hand-written |

Key documents:

- [`PLAN.md`](PLAN.md): scope, phases, cut list
- [`docs/AGENT_DESIGN.md`](docs/AGENT_DESIGN.md): pipeline, domain models, risk rubric, SSE contract, golden example (source of truth)
- [`CLAUDE.md`](CLAUDE.md), [`backend/CLAUDE.md`](backend/CLAUDE.md), [`frontend/CLAUDE.md`](frontend/CLAUDE.md): working rules per layer

```
backend/app/
  domain/     Pydantic models only (no I/O)
  data/       repository.py: the only reader of organizer files
  services/   geo, tracks, motion, reports, risk, detection (pure, unit-tested)
  agent/      pipeline (8-step state machine), fallback brief, LLM client, store
  api/routes/ health, scene/images, analyses
backend/scripts/  mock data generator, fixtures, detection precompute, OpenAPI export
frontend/src/
  components/scene/     one stage visual per agent step
  components/analysis/  timeline, step cards, playback, brief
  lib/narrative.ts      Turkish step narration built from API data
```

---

## Quick start

**Prerequisites:** [uv](https://docs.astral.sh/uv/), Node 20+, [pnpm](https://pnpm.io/), GNU make. On Windows: `winget install ezwinports.make`; recipes work from Git Bash and PowerShell.

This project lives in the `akya-day2/` folder of the `roketsan-hackathon` repo. Run every command below from `akya-day2/`; all relative paths in this project's docs (and "repo root" in `.env`, scripts and tests) mean that folder.

```bash
cd akya-day2
make install          # backend (uv) + frontend (pnpm) dependencies
cp .env.example .env  # defaults point at the synthetic day
make mock-data        # synthetic day -> data/stage2_mock/
make mock             # pipeline on demo frames -> frontend/src/mocks/
make dev              # API :8000 + web :5173
```

Open http://localhost:5173/analysis/img_000860 and press **Oynat** (or use the arrow keys).

Optional, to rebuild `img_000860` from the case-brief slides instead of drawing it:

```bash
make mock-data PPTX="path/to/case-brief.pptx"
```

### Live YOLO detector (optional)

```bash
make install-detector   # ultralytics + CUDA 12.8 torch (~2.5 GB)
```

Put the weights at `models/detector.pt` (the default; or point `SENTINEL_DETECTOR_WEIGHTS` at another file) and set `SENTINEL_DETECTOR_KIND=ultralytics` in `.env`. `/api/health` shows the device (GPU/CPU).

- Inference runs at `imgsz` 960 (~55 ms on a GTX 1650), FP32 only: FP16 returned no boxes on GTX 16xx cards.
- If the model fails at load or inference, the pipeline uses the precomputed boxes and marks the step as a warning.
- `make detections` runs the model once over all frames and caches the boxes, so a demo can run without a GPU.

### Organizer data

The files are committed in `data/` (`images/`, `image_meta.json`, `zones.json`, `tracks.csv`, `field_reports.json`), the default `SENTINEL_DATA_DIR`. Only the loader (`backend/app/data/repository.py`) knows raw formats.

---

## Make targets

| Target | What it does |
|---|---|
| `install` / `install-detector` | Dependencies; the second adds YOLO + CUDA torch |
| `dev` / `dev-api` / `dev-web` | Run both servers or one |
| `test` | Backend tests, golden test included |
| `lint` / `format` | ruff + mypy (strict core), oxlint + tsc |
| `gen-types` | Pydantic → OpenAPI → `frontend/src/api/schema.d.ts` (no server needed) |
| `mock-data` / `mock` | Synthetic day; frontend fixtures from the real pipeline |
| `detections` | Cache YOLO boxes for every frame |
| `precompute` | P4, not implemented yet |

---

## Mock data

`make mock-data` writes a synthetic day in the organizer's exact formats (case brief slides 13-14): 8 zones on a ~3.2 km ring, 40 frames, ~100 two-hour tracks at 5-minute steps and 24 reports. Three sample reports from the slides are included verbatim. Demo scenarios:

| Frame | Scenario | Result |
|---|---|---|
| `img_000860` | Organizer example: truck T0122 closing on the base after long stops | **CRITICAL** |
| `img_001204` | Truck convoy + "friendly exercise, no concern" + a wrong official report + prompt injection | **CRITICAL**; no report lowers the score |
| `img_000517` | Parked truck confirmed by the 13:05 official report | **HIGH** |
| `img_000412` | Normal traffic with a matching report | **LOW** |

The same generator writes `backend/tests/fixtures/golden/` for the golden test.

---

## Testing

```bash
make test
make lint
```

- **Golden test** ([`backend/tests/test_golden_img_000860.py`](backend/tests/test_golden_img_000860.py)): the case-brief example must always hold: georeference ≈ 39.92531, 32.87183; ≈ 1.6 km to base; T0122 at < 1 m (second best T0032 ≈ 41 m); stops ≈ 40 and 45 min; the 12:35 official report corroborated; CRITICAL.
- **Adversarial:** threat-lowering and instruction-like reports never lower a vehicle's score.
- **Contract:** frontend mock fixtures are validated against the backend `Analysis` model.
- The real LLM is never called in tests.

---

## Configuration

All settings use the `SENTINEL_` prefix and live in [`backend/app/core/config.py`](backend/app/core/config.py); see [`.env.example`](.env.example). Never commit `.env`, data or weights.
