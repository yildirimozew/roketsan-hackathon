# Project Plan — Stage 2: Field-Report-Aware LLM Agent

Level Up AI | ROKETSAN Hackathon · Solo developer · Vibe-coded with Claude Code

Working name: **SENTINEL** (rename freely).

---

## 1. Goal (what "done" means on Sunday)

A working web app where an operator picks one of the 40 drone frames and watches an agent:

1. detect vehicles (Stage 1 model),
2. convert pixel positions to lat/lon using the frame's corner coordinates,
3. match each vehicle to a track in `tracks.csv` and derive speed, heading, route, stops and trend toward the base,
4. weigh the free-text field reports against its own findings (accept / reject / irrelevant, with reasons),
5. output a short, evidence-cited **risk brief** (LOW / MEDIUM / HIGH / CRITICAL).

Every step streams live to the UI. The demo must run on at least 2–3 of the given frames, reliably, even if the LLM API is slow or down.

### How we are scored → what we optimize

| Scorer | Criterion | Our answer |
|---|---|---|
| Mentors | Technical quality & architecture | Clean layering, deterministic tools + LLM reasoning, typed contracts, tests incl. the organizer's golden example, fallbacks, prompt-injection-safe report handling |
| Jury | Problem importance & business value | Frame the product as operator decision support: fewer false alarms, faster triage, explainable decisions |
| Jury | Working product | Live analysis on real frames + cached replay mode as safety net |
| Jury | Product thinking & UX | Ops-style dashboard, step-by-step agent timeline, map + image linked highlighting, report credibility panel |
| Jury | Presentation & demo | 3 scripted scenarios (benign / critical / misleading report) |

---

## 2. Core architectural decision

**Deterministic tools do the math, the LLM does the judgment.**

- Detection, georeferencing, track matching, motion features, spatial/temporal report matching and a baseline risk score are **pure Python, unit-tested, reproducible**.
- The LLM is used for things code cannot do well: turning free-text reports into structured claims, judging credibility and contradictions, and writing the justified brief.
- The main analysis is an **explicit, ordered pipeline (state machine)**, not a free-form ReAct loop: it is faster, cheaper (15 $ credit), streams cleanly and never "forgets" a step. A separate **tool-calling analyst chat** lets the operator ask follow-ups ("Why is T0122 high?", "Show reports near Doğu Yolu after 13:00") using the same tools — this is where the agent autonomy is showcased.
- LLM output is **schema-validated** (Pydantic). If it fails twice, a **template brief** is built from the deterministic results. The demo never shows a stack trace.

Full detail: `docs/AGENT_DESIGN.md`.

```
Frame ──► [1 Load meta] ──► [2 Detect] ──► [3 Georeference] ──► [4 Match tracks]
                                                                      │
   [8 Brief (LLM)] ◄── [7 Risk score] ◄── [6 Assess reports (LLM)] ◄── [5 Motion analysis]
```

---

## 3. Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | Python 3.11+, FastAPI, Pydantic v2, pydantic-settings, uv | Typed, fast to build, OpenAPI for free |
| Detection | Pluggable `Detector` protocol; Ultralytics adapter first, `PrecomputedDetector` (JSON) as fallback | Stage 1 model still undecided |
| Geo | Own small module (bilinear corner interpolation, haversine, bearing) | No heavy GIS deps; fully testable |
| Matching | `scipy.optimize.linear_sum_assignment` (Hungarian) with distance gate | Globally optimal 1-to-1 matching, strong mentor talking point |
| LLM | GLM via OpenAI-compatible SDK (`openai` package, custom `base_url`) | Credentials arrive on Saturday; client abstracted |
| Streaming | Server-Sent Events | Simple, one-way, perfect for step timelines |
| Frontend | Vite + React + TypeScript (strict) + Tailwind + shadcn/ui | Requested; fast to style |
| Data fetching | TanStack Query; types generated from FastAPI OpenAPI (`openapi-typescript`) | One source of truth for contracts |
| Map | react-leaflet (dark tiles) | Simple, reliable for vibe coding |
| Charts | shadcn chart (Recharts) | Distance-to-base & speed over time |

---

## 4. Repository layout

```
sentinel/
├── CLAUDE.md                  # root rules (read first by Claude Code)
├── PLAN.md                    # this file
├── docs/AGENT_DESIGN.md       # agent architecture, schemas, risk rubric
├── data/                      # organizer data (committed): images/, image_meta.json, zones.json, tracks.csv, field_reports.json
├── models/                    # detector weights (gitignored)
├── backend/
│   ├── CLAUDE.md
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── core/        (config.py, logging.py, errors.py)
│   │   ├── domain/      (pydantic models: geo, detection, track, report, risk, brief, events)
│   │   ├── data/        (repository.py — loads all data once at startup)
│   │   ├── services/    (detection/, geo.py, tracks.py, motion.py, reports.py, risk.py)
│   │   ├── agent/       (llm_client.py, pipeline.py, chat_agent.py, tools.py, fallback.py, prompts/*.md)
│   │   ├── api/routes/  (health, images, zones, tracks, reports, analyses, chat)
│   │   └── cache/       (disk cache for detections, parsed reports, analyses)
│   └── tests/           (unit + golden example test)
└── frontend/
    ├── CLAUDE.md
    └── src/ (api/, hooks/, components/{ui,analysis,map,image,reports,layout}, pages/, lib/, i18n/)
```

---

## 5. API surface (v1)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Liveness + LLM/detector status |
| GET | `/api/scene` | Base, zones, bounds (for map) |
| GET | `/api/images` | 40 frames: meta, zone, capture time, cached risk level |
| GET | `/api/images/{id}/file` | Raw image |
| GET | `/api/tracks/{track_id}` | Full 2 h track + motion profile |
| GET | `/api/tracks?at=HH:MM` | All track positions at a time (map playback) |
| GET | `/api/reports` | All reports + LLM-extracted claims |
| POST | `/api/analyses` | `{image_id, force_refresh?}` → `{analysis_id}` |
| GET | `/api/analyses/{id}/events` | SSE stream of step events |
| GET | `/api/analyses/{id}` | Final analysis JSON |
| POST | `/api/batch` | Precompute all 40 frames (for dashboard + replay) |
| POST | `/api/chat` | `{analysis_id, message}` → SSE, tool-calling analyst |

---

## 6. UI plan (the demo is the product)

Dark "operations center" look. Three screens, one of them carries the demo.

**A. Operations overview (`/`)**
- Left: map with base marker, 8 zone markers, frame footprints colored by risk.
- Right: frame grid grouped by zone (thumbnail, capture time, risk badge). Filter by zone / risk / time.
- Top KPI strip: frames analyzed, CRITICAL/HIGH counts, reports rejected as unreliable.

**B. Analysis view (`/analysis/:imageId`) — demo centerpiece**
- Left (≈55%): image with bounding boxes (color = risk), hover a box → highlights the vehicle's track on the map and its row in the brief. Toggle: boxes / geo grid / track dots at capture time.
- Right top: **Agent timeline** — 8 steps appear live with a spinner → check, short summary line, expandable raw data (numbers, tool inputs/outputs).
- Right bottom tabs: **Map** (track polyline with timestamps, stops, base, distance ring) · **Motion** (distance-to-base & speed chart) · **Reports** (each relevant report with verdict chip CORROBORATED / CONTRADICTED / UNVERIFIED / IRRELEVANT and one-line reason).
- Bottom: **Brief card** — risk level, headline, 3–5 sentence justification with clickable evidence chips (`DET-2`, `TRK-T0122`, `REP-07`), uncertainties, recommended operator action (monitor / verify / escalate).
- Floating: "Ask the analyst" chat drawer.

**C. Reports inspector (`/reports`)** — cut: reports are covered by the field map's report feed and the Analysis view's Reports tab.

**Demo safety:** a `Replay` toggle streams a cached analysis with realistic step delays — identical UI, no API dependency.

---

## 7. Timeline (solo)

Adjust to the official Stage 2 / code-freeze times once announced. Kaggle is still scored until Saturday noon — do not sacrifice it for this.

| When | Phase | Output | Exit check |
|---|---|---|---|
| Fri night (max ~2 h) | **P0 Scaffold** | Repo, rules, FastAPI skeleton, Vite+shadcn shell with theme, mock fixtures built from the slide example (`img_000860`) | `make dev` runs both; UI shows mock analysis |
| Sat 12:00–15:00 | **P1 Data + deterministic core** | Data audit, loaders, geo, track matching, motion features | Golden test passes: `img_000860` → `39.92531, 32.87183`, `T0122` < 1 m, ~1.6 km to base |
| Sat 15:00–19:00 | **P2 Agent** | Report extraction (cached), report matching, risk rubric, pipeline + SSE, fallback brief | `POST /api/analyses` streams 8 steps and returns valid `Brief` for 5 frames |
| Sat 19:00–24:00 | **P3 Analysis UI** | Analysis view end-to-end with live SSE | Full flow on 3 frames in the browser |
| Sun early | **P4 Breadth + polish** | Batch precompute, overview dashboard, reports inspector, replay mode, (chat if time) | All 40 frames have cached results |
| Sun before deadline | **P5 Ship** | README, code cleanup, slides, demo script, backup screen recording | Dry run ×2 under 5 min |

**Cut order if late:** chat drawer → reports inspector → overview map (keep grid) → motion chart. Never cut: analysis view, timeline, brief, replay mode.

---

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Stage 1 model weak / not ready | `Detector` protocol; tune a higher confidence threshold for the agent (precision > recall here, unlike Kaggle); `PrecomputedDetector` cache |
| Real data schema differs from slides | P1 starts with a data audit script; loaders are the only place that knows raw formats |
| GLM API slow / errors / credit burn | Timeouts + 2 retries, disk cache keyed by input hash, token logging, template fallback brief, replay mode |
| LLM hallucinates numbers | LLM never computes; prompt receives precomputed facts; validator rejects briefs citing unknown evidence IDs |
| Malicious report text ("ignore previous instructions…") | Reports passed as quoted data in a delimited block; system prompt states they are untrusted; output schema-constrained |
| Frame is oblique, not true nadir | **Decided:** treat as bird's-eye, linear corner mapping only, no perspective transform (organizer rule); state it as an assumption in the brief's uncertainties |
| Solo time pressure | Strict phase exits, cut list above, mock-first frontend |

---

## 9. Kickoff prompts for Claude Code

Paste one per phase. Each assumes Claude reads `CLAUDE.md` files automatically.

**P0 — scaffold**
> Read PLAN.md and docs/AGENT_DESIGN.md. Scaffold the backend (FastAPI app factory, config, health route, domain models from AGENT_DESIGN §4, empty service modules) and the frontend (Vite React TS, Tailwind, shadcn init with the dark theme tokens from frontend/CLAUDE.md, router with the three pages, app shell). Add a root Makefile with `dev`, `test`, `lint`, `gen-types`. Create a mock `Analysis` fixture for img_000860 using the numbers in AGENT_DESIGN §9 and render it statically in the Analysis page. Stop after that and show me the tree.

**P1 — data + core**
> Write `backend/scripts/audit_data.py` that prints schema, counts, time ranges and 3 samples for every file in data/stage2. Run it and summarize surprises. Then implement repository.py, geo.py, tracks.py, motion.py with unit tests, plus the golden test in AGENT_DESIGN §9. Do not touch the LLM yet.

**P2 — agent**
> Implement the agent per AGENT_DESIGN §3–§8: llm_client, report extraction with cache, report matching, risk rubric, pipeline with SSE events, validator and fallback brief. Add the POST/GET analyses endpoints. Run it on img_000860 and two other frames and show me the briefs.

**P3 — analysis UI**
> Run `make gen-types`. Build the Analysis page per frontend/CLAUDE.md §Layout: image overlay, agent timeline driven by the SSE hook, map/motion/reports tabs, brief card with evidence chips and linked highlighting. Replace the mock with the live API.

**P4 — breadth**
> Add batch precompute, replay mode, the overview dashboard and the reports inspector. Then the chat drawer if everything else is green.

---

## 10. Backlog (not in the first plan)

- **Camera re-sighting (mock only).** In the real data no track ever appears in a second frame (checked across all 226 tracks × 25 points against all 40 frames). A "check the cameras ahead of this car" tool can therefore only list frames in the direction of travel with their capture times; re-finding the car there needs synthetic sightings, clearly labelled `SIMULATED` in UI and slides. Owner phase: after the watch-mode MVP.
- **Mock track extension + tracker lifecycle.** Extend tracks past their frame's capture time as mock data (no new images). Trackers then follow a car through DISPATCHED → FOLLOWING (real track) → EXTRAPOLATING (mock, growing uncertainty radius) → LOST / RECALLED / HANDED TO AUTHORITIES; each authority report carries `{coords, speed, heading, uncertainty_m, source: REAL | SIMULATED}`. Owner phase: when the mock track data is added.
- **Dispatching watchers by talking to the supervisor.** The operator chats with the head supervisor ("put an extra watcher on T0122", "double-watch Doğu Yolu until 15:00") and the supervisor acts through a tool: `dispatch_watcher(target, reason, until?)` → `watcher_id`, where `target` is a sector, a `track_id` or an area (lat/lon + radius), plus `recall_watcher(watcher_id, reason)`. The supervisor must state the reason, a cap on active watchers bounds cost, and the operator's request goes through the same validator as the supervisor's own dispatches. Owner phase: after the watch-mode MVP (replaces the per-frame analyst chat).
