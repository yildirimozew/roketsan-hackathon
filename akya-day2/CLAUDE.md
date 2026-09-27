# CLAUDE.md — SENTINEL (root)

Hackathon project: an LLM agent that assesses base-security risk from a drone frame, vehicle tracks and untrusted field reports. Solo developer, vibe-coded, hard deadline Sunday.

## Read first
- `PLAN.md` — scope, phases, cut list. Stay inside the current phase.
- `docs/AGENT_DESIGN.md` — agent architecture, domain models, risk rubric, SSE contract, golden example. It is the source of truth; if code must deviate, update the doc in the same change.
- `backend/CLAUDE.md` and `frontend/CLAUDE.md` — layer-specific rules.

## Language
- All code, identifiers, comments, commit messages, docs, prompts and rulesets are in **English**.
- The only Turkish text allowed: UI strings in `frontend/src/i18n/tr.ts`, LLM output when `BRIEF_LANGUAGE=tr`, and the fallback brief templates in `backend/app/agent/fallback_templates.py` (they replace LLM output). Organizer/mock data may contain Turkish.

## Working agreement
- Work in small, verifiable steps. After each step: run the relevant tests/lint, then summarize what changed in ≤ 5 bullets.
- Before a change touching > 3 files or any public contract (API schema, domain model, SSE event), state a short plan first.
- Never invent data formats. If the real files in `data/` differ from the docs, report the difference and adapt the loader only.
- Prefer boring, explicit code over clever code. No new dependency without a one-line justification.
- Do not delete or rewrite working code to "clean up" unless asked.
- If a requirement is ambiguous and a wrong guess is expensive, ask; otherwise choose the simplest option and write the assumption in the summary.

## Demo-first priorities
1. The analysis flow for one frame works end to end, live, and looks good.
2. It never crashes on stage: every external dependency (LLM, detector) has a fallback and a cached replay path.
3. Breadth (all 40 frames, extra pages, chat) comes after 1 and 2.

## Repo conventions
- This project is the `akya-day2/` folder of the `roketsan-hackathon` repo (Stage 1 lives in `../akya-day1/`). "Root" and every relative path in these docs mean `akya-day2/`.
- Monorepo: `backend/` (FastAPI, uv), `frontend/` (Vite React TS, pnpm).
- `data/` (organizer data, ~10 MB) is committed so every checkout can run the demo; add new data there. `models/` is gitignored; never commit weights, `.env` or API keys.
- Makefile targets in `akya-day2/`: `install`, `dev`, `test`, `lint`, `format`, `gen-types`, `mock`, `precompute`. Recipes must work from Git Bash and PowerShell on Windows (use `uv --directory` / `pnpm --dir`, no `cd`).
- API contract flows one way: Pydantic models → OpenAPI → `pnpm gen-types` → `frontend/src/api/schema.d.ts`. Never hand-write API types in the frontend.
- Commits: Conventional Commits (`feat(agent): ...`, `fix(ui): ...`), one logical change each.

## Definition of done (any task)
- Tests/lint/typecheck pass for the touched layer.
- No `TODO` without an owner phase (`TODO(P4): ...`).
- Golden test (`backend/tests/test_golden_img_000860.py`) still passes.
