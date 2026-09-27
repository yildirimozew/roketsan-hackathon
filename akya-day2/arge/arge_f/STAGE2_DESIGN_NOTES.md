# Stage 2 Agent — Design Notes (Furkan)

Handoff document from a design session (Cowork, 26 Sep 2026). It records every decision, data finding and
idea ranking made so far, so work can continue in Claude CLI without the original conversation.

> **Status:** design only. No tool is implemented yet. Two draft files exist next to this document:
> `schemas.py` (tool I/O contracts, Pydantic v2) and `prompts.py` (agent SOP + red-team critic prompts).
>
> **Not yet reconciled** with `docs/AGENT_DESIGN.md` / `PLAN.md` of this repo (not read during the session).
> Per root `CLAUDE.md`, `docs/AGENT_DESIGN.md` is the source of truth: compare, then merge or flag differences.
> `prompts.py` prompt text and `schemas.py` descriptions are in **Turkish** — the repo rule says prompts must be
> English. Translate before merging into `backend/`.

---

## 1. Task recap (from `gorev_tanimi.pdf` and the case brief)

- Protect a base ("Merkez Us"); 8 surrounding zones watched by drones; free-text field reports arrive.
- Inputs: 40 images, `image_meta.json` (size, capture time, 4 WGS84 corners), `zones.json` (base + 8 zones),
  `tracks.csv` (`track_id,time,lat,lon`, last 2 h per vehicle, 5-min steps), `field_reports.json`
  (`time, source ∈ {official, third_party}, text`).
- Output: a short, justified brief on whether vehicles pose a risk to the base.
- Official 8-step flow (from the organizer's end-to-end example on `img_000860`):
  1 open image → 2 place on map → 3 detect vehicle → 4 pixel→coordinate → 5 find track →
  6 extract motion → 7 compare with reports → 8 evaluate.
- Rules from the PDF: images are treated as top-down (top = north, left = west, perspective corrected);
  pixel → coordinate by linear interpolation of corners using the **box center**; a track's last point is at
  the image's capture time; match "nearest within a reasonable distance"; parked cars may have no track; some
  reports are wrong or irrelevant and are **not** marked.
- The final decision ("does this need attention, and why") is explicitly left to **the agent**.
- LLM: `glm-5.3-flash` via an OpenAI-compatible gateway. $15 budget total, 60 req/min, 4 concurrent requests,
  ~1M context. Always reasons; tune with `reasoning_effort` (low/high/max). No embeddings endpoint.
  Supports tool calling and image input.
- Scoring: Kaggle private LB + mentor code review (technical quality, architecture) + jury (business value,
  working product, product/UX, presentation/demo). Live demo on at least 1–2 given images.

Panel notes that shaped the design: AI must be verifiable and explainable; an independent "control computer"
checks the AI's decision; simulation tests; open-set ("the model can say I don't know"); graceful degradation;
modular components that can cover for each other; operational efficiency; the differentiator is what you
build around the model.

---

## 2. Data findings (measured on the real stage-2 files)

These are verified numbers, not assumptions.

**Images and geometry**
- 40 images: 19 × 1360×765, 16 × 960×540, 5 × 1920×1080. All corners axis-aligned; pixels square
  (GSD x/y ≈ 0.99). GSD 0.11–0.20 m/px.
- Every capture time is unique → a track's end time identifies its image.
- The 40 images are **not** in the Kaggle train/test sets (dhash + pixel correlation ≤ 0.49) → no labels.
- The 8 zones are compass directions: all centers exactly 3.2 km from the base at 0°, 45°, …, 315°.
- Frames form a polar grid: **8 sectors × 5 rings** (~1.7 / 2.6 / 3.5 / 4.4 / 5.3 km), exactly one frame per
  cell. "Nearest zone center" is misleading (up to 2.4 km away; 9 frames ambiguous) → use bearing sector.
- 200 px² detection threshold = 2.3–7.9 m² on the ground; a car is ~8 m², so in coarse frames even cars sit
  near the threshold; motorcycles / three-wheelers are never counted.
- Brightness: only 1 dark frame (`img_008589`, gray mean 45), 1 borderline (`img_004416`, 70). Stage-1 dark
  threshold ≈ 60. The dark-scene story from stage 1 is minor here.
- Three 1920×1080 frames (`img_003880`, `img_003189`, `img_000267`) have brightness 182–187 vs stage-1 p95 of
  145 for that resolution → likely out-of-distribution (verify visually).

**Tracks**
- 226 tracks × 25 points each. Every track ends at one of the 40 capture times (3–10 tracks per image).
- 206 / 226 track endpoints lie inside their frame at capture time; the other 20 are 7–26 m outside an edge.
- Official example reproduced: box (727,284,58,34) on `img_000860` → (39.925313, 32.871833), which is
  **0.02 m** from T0122 at 14:10; second nearest is 40 m. ⇒ Track points were generated from box centers with
  the linear formula. Do **not** use homography or bottom-center points; they would break matching.
- In-frame track endpoints are close to each other: nearest-neighbour distance min 1.7 m, p5 3.1 m, median
  17 m; 31 points have a neighbour within 5 m ⇒ greedy nearest matching with a 15 m gate would swap vehicles.
- Motion is stop-and-go: 57% of 5-min steps move < 5 m (jitter floor); moves are bursts at 5–9 m/s
  (max 9.3 m/s, no impossible jumps). 30 tracks never move > 30 m per step (waiting vehicles). No track is
  fully static for 2 h.
- "Approaching the base" is **not discriminative**: 129 / 226 tracks get > 0.8 km closer over 2 h
  (structural: all tracks end in frames 1.6–5.4 km from base).
- Circling exists (PDF mentions it): 41 tracks sweep > 90° around the base; T0172 sweeps 549°.
- Four tracks stand out clearly (sweep > 300°, came within < 0.9 km, moved > 1.8 km inward in the last 30 min,
  now in ring 1):

  | Track | Image | Now | Closest ever | Sweep | Last 30 min inward |
  |---|---|---|---|---|---|
  | T0043 | img_006673 | 1.76 km | 0.63 km | 441° | 2.5 km |
  | T0158 | img_005672 | 1.70 km | 0.69 km | 323° | 1.8 km |
  | T0172 | img_000926 | 1.69 km | 0.87 km | 549° | 1.8 km |
  | T0198 | img_002900 | 1.61 km | 0.82 km | 320° | 2.1 km |

**Field reports**
- 137 reports (98 official, 39 third_party), times 08:35–15:15. 34 surface templates, a few one-offs
  ("üzeri örtülü", "3 araçlık konvoy", "panelvan", "(kamyon/otobus)").
- 72 reports carry coordinates; **all 72** fall within ±50 m of some frame footprint.
- Reports appear to be generated from track positions **at report time**: 47 / 72 have a track within 60 m
  at the report timestamp (e.g. R001 13:05 "1 kamyon" is 1 m from T0182 at 13:05).
- Friendly / supply identity claims ("planli ikmal araci", "bize bagli unsur", "dost devriye"): 18 reports,
  **all official**. Of the 15 that also claim "moving toward the base": 8 have no vehicle at that place and
  time, 7 match a vehicle that is **stopped** ⇒ **0 / 15 consistent**.
- By contrast official "vehicle is stationary" sightings: 16 / 17 consistent with tracks.
- Two of the four top threat candidates (`img_006673`, `img_000926`) are in frames covered by official
  "friendly/supply vehicle" claims. This is very likely the case's intended trap.
- Other report kinds: area all-clear ("no heavy vehicles, only cars"), traffic-normal / "usual traffic is N
  vehicles", weather, "last night unverified tip" (out of time window), "planned exercise, friendly units
  today" (blanket claim), "radio contact with patrol lost for N minutes" (unverifiable, raises attention).

Caveat: these patterns come from our analysis, not from organizer ground truth.

---

## 3. Architecture decisions

1. **The LLM is the main engine.** The PDF asks for an "LLM agent" that decides; the organizer example is a
   first-person tool-calling agent. A tool-calling loop (OpenAI-compatible) drives the 8 steps.
2. **Tools are deterministic and do all math.** The LLM never computes distances, speeds or angles.
3. **The 8 steps are an SOP in the system prompt, not a hard-coded state machine.** The agent picks order,
   decides when to re-detect, when to stop. It may not skip mandatory steps (enforced by the guard).
4. **Rule-based risk advisor (fuzzy rules + Dempster–Shafer) is an advisor, not the judge.** The agent may
   deviate but must justify with evidence IDs; deviations are shown to the operator.
5. **Guard = the panel's "control computer".** Checks every final decision: schema, mandatory-step checklist,
   grounding (every number/ID in the brief exists in tool outputs), policy (asymmetric trust), advisor
   deviation reason, loop/budget limits. On failure → feedback to the agent → retry; after N → labelled
   "unverified".
6. **Red-team critic (one extra LLM call).** Sees only the final assessment + evidence pack (no conversation
   history). Fixed checklist derived from the data traps. Only level-changing issues are blocking; at most one
   revision round. Chosen over a single agent because deception is the case's core theme.
7. **Blackboard / evidence ledger.** Append-only store; every value has an evidence ID, source tool,
   confidence and provenance. Enables grounding checks, UI step replay and audit.
8. **Graceful degradation.** Full → LLM off (same tools in SOP order, advisor decides, template brief) →
   detector weak/failed (tracks + reports only) → no tracks (low confidence). Never returns empty.
9. **Image model only in step 3.** Detector runs only inside `detect`. Re-looking = calling `detect` again with
   `region_center` (max 2 per frame). Detector report card and crop color live in step 3 output. The GLM
   vision "second look" was dropped. Other steps only read detection outputs. Tracks are the backbone of
   motion, position and risk reasoning; if detector and tracks disagree, prefer tracks and state it.
10. **Asymmetric trust.** A report may raise attention easily; lowering it needs independent verification.
    Identity claims can never lower the level. If the verifiable part of an identity claim contradicts the
    data → deception indicator → level +1.
11. **Modes.** Single-frame evaluation (demo core), day board (40 frames, ≤ 4 concurrent, then sector fusion
    and a priority list), operator Q&A (read-only tools over the blackboard).
12. **Reproducibility and budget.** Cache LLM calls by input hash, `reasoning_effort="low"`, track spend via
    the gateway `key/info`, hard cap on agent steps (e.g. 25).

Conceptual framing for the presentation: JDL data-fusion levels (object → situation → threat → process
refinement) and a blackboard architecture; defense-in-depth rings.

---

## 4. Capabilities per step (ideas ranked by importance × feasibility, with build order)

### Step 1 — `open_image`
1. **Context bundle** (high / trivial): tracks ending at capture time, which are inside the frame
   (→ "expected moving vehicles"), reports in the time window.
2. **Metadata integrity checks** (medium / trivial): file exists, size matches meta, corners axis-aligned,
   square pixels, time format. Failure → `status=failed` → degraded mode. Protects the linear-formula assumption.
3. **Out-of-distribution flag** (medium / easy): brightness/contrast z-score vs same-resolution stage-1
   distribution (`data/cache/image_features_v1.csv` in the old repo has brightness/contrast/dhash for 8,589
   images). Pixel statistics only, no model.
4. Image quality (blur via Laplacian variance, over-exposure ratio) — fold into 3.
Build order: 1+2 → 3.

### Step 2 — `place_on_map`
1. **Polar position: sector (bearing ±22.5°) + ring (1–5)** (high / trivial). Links "X bölgesinde" reports,
   gives the advisor a ring input, defense-in-depth vocabulary.
2. **Coverage record** (high / easy): footprint polygon + capture time on the blackboard; step 7's
   "contradicted vs unverifiable" depends on it; also enables cross-frame checks.
3. **Blind-spot threshold** (medium-high / trivial): `min_detectable_area_m2`.
4. Base-facing edge (low-medium / easy) — UI arrows, "entered from base side".
5. Sector siblings (medium; value in day layer).
Build order: 1+2+3 → 4 → 5.

### Step 3 — `detect` (only step that runs the image model)
1. **Track-guided detection (candidate → fact)** (high / easy): a low-confidence box next to a track point is
   promoted; a track point without a box triggers a local low-threshold re-detect; big gap between expected
   and found → `low_confidence`.
2. **Hierarchical class light / heavy / unknown** (high / trivial). Reports themselves say "agir arac";
   the organizer example maps it to truck.
3. **Track recall as a label-free quality metric** (medium-high / easy): share of the 206 in-frame track
   points covered by a detection → choose model / threshold / TTA for stage 2. Measures recall on moving
   vehicles only.
4. **Confidence calibration** (medium): isotonic per class on stage-1 val.
5. **Blind-spot flag** on boxes near 200 px² (medium / trivial).
6. **Open-set embedding filter** (medium / medium): out-of-class objects (three-wheelers, motorbikes).
   `Downloads/ardahan_embedding.pt` and Yıldırım's ConvNeXt reranker exist.
7. Ensemble disagreement (low-medium).
8. **Detector report card** (moved here from step 1): per-resolution class AP from stage-1 val; dark strata
   have 1–6 val images → empirical-Bayes shrinkage `AP = (n·AP_stratum + k·AP_global)/(n + k)`.
Build order: 2 → (after step 4) 1 + 3 → pick model → 4 → 5 → 6/7 if time.
Weights on the laptop (`Downloads/`): `hakan_yolo11m.pt`, `yolo11l_ardahan.pt`, `last.pt`, `last (1).pt`.
Stage-1 best ensemble was hakan 11m + ardahan 11m RFS — **confirm which file is ardahan's RFS 11m**.

### Step 4 — `pixel_to_geo`
1. **Official formula + inverse** (high / trivial): box center, linear corners. Unit tests: PDF example
   (`img_000123` → 39.94439, 32.86350), `img_000860` (→ 39.925313, 32.871833, 0.02 m from T0122), round trip.
2. **Shared metric plane** (high / trivial): local ENU meters centered on the base; one distance function
   for everyone.
3. **Data-calibrated error radius** (medium-high, after detector choice): center-offset distribution of
   matched boxes → `error_radius_m` and step-5 gate (p95).
4. **Document the assumption** for mentors: images look oblique, but the data contract (and the tracks) use
   the linear center formula.
Build order: `geo.py` (1+2, ~50 lines + tests) is the **first shared code**.

### Step 5 — `find_tracks`
1. **Global assignment (Hungarian, `scipy.linear_sum_assignment`) + tight gate** (high / easy). Start
   `gate = max(3 m, 0.5 × box diagonal × GSD)`; final value from step-4 calibration.
2. **ByteTrack-style two passes** (high / easy): pass 1 fact boxes, pass 2 candidate boxes to remaining
   track points.
3. **Lowe ratio test + decision-invariant ambiguity** (medium-high / easy): `d1/d2 > 0.7` → ambiguous; run
   step 6 for both candidates; if the level does not change, state "ambiguous but decision unaffected".
4. **Hypotheses for unmatched objects** (medium-high / easy): detection without track → parked-likely or
   false-positive-likely; in-frame track without detection → missed (re-detect) or blind spot; out-of-frame
   track ≤ 26 m from edge → just outside view (still counts for risk; try extended gate for edge-clipped boxes).
5. Heading consistency (box long axis vs track heading) as a tie-breaker only (low-medium).
Build order: 1+2 → 4 → 3 (after step 6) → 5.

### Step 6 — `analyze_motion`
1. **Noise-aware move/stop segmentation** (high / easy): 5 m per step noise floor; speed from moving
   segments only; dwell list; last-30-min summary.
2. **Base-centric geometry** (high / easy): radial speed, angular sweep around base (circling), closest-ever
   distance and time.
3. **Population-referenced anomaly** (high / easy): percentile / robust z of each feature vs all 226 tracks
   ("circled more than 98% of vehicles"). Removes arbitrary thresholds. Freeze `population_features.csv`.
4. **Behavior tags** (medium-high): approaching, loitering, circling, waiting, stop_and_go, transit, leaving.
5. **Shared motion vocabulary with reports** (moving / stopped / parked / approaching / leaving / transit).
6. ETA if moving, as a range (Kalman/CPA dropped: stop-and-go makes constant-velocity projection unreliable).
7. Physical plausibility check (low; main use in step 7).
Build order: 1+2+5 → 3+4 → 6 → 7.

### Step 7 — `search_reports`
0. **Prerequisite: template parser (regex) + LLM fallback** for the long tail (schema-validated JSON).
   Vocabulary: panelvan → van (light), agir arac → heavy, otomobil → car, kamyon → truck.
1. **Report-time alignment** (high / easy): compare a report with the track state at the report timestamp
   (±15 min), not with the capture time.
2. **Atomic claim verification** (high / medium): existence, count, class, motion, direction, identity,
   color, area status → supported / contradicted / unverifiable each.
3. **Identity-claim rule** (high / easy): identity cannot be sensed (no IFF) → never lowers level; if the
   verifiable part contradicts data → deception indicator → +1 level.
4. **Learned reliability per (source × claim kind)** (high / easy): Beta–Bernoulli from verifiable claims
   during the day; used as DS discount for unverifiable ones. Example: official stationary sightings 16/17,
   official friendly-approaching 0/15.
5. **Area / general reports** (medium): check "no heavy vehicles" against sector detections; traffic counts;
   weather vs brightness; "last night" → irrelevant; "planned exercise" → cannot lower; "radio contact lost"
   → attention context for that sector.
6. Tool gives `auto_status`; the agent gives the verdict; in-frame contradiction → re-detect first.
7. Color check from `dominant_color` (step 3 output).
8. Cross-report consistency (DS conflict K).
Build order: 0 → 1 → 2+3 → 4 → 5 → (6 with orchestrator) → 7/8.

### Step 8 — `risk_advisor` + agent decision + brief
1. **Action-based level definitions** (team decision; draft in `schemas.LEVEL_POLICY`, version `v0-taslak`):

   | Level | Operator action | Draft criterion |
   |---|---|---|
   | KRITIK | Confirm and respond now | (sweep > 180° or closest < 1 km) AND ring 1 AND inward in last 30 min; or heavy + approaching inner ring + deception indicator |
   | DIKKAT | Notify, check on next drone pass | Two strong signals (population top 10%) or a deception indicator in frame |
   | IZLE | Routine watch | One unusual signal |
   | DUSUK | None | No signal |
   | BELIRSIZ | Request more data | Evidence insufficient |

   Modifiers: deception indicator +1; identity claims cannot lower; "sensitive" robustness → pick higher.
   Rough expected distribution on 40 frames: 4 KRITIK, 6–10 DIKKAT, rest IZLE/DUSUK (avoids alert fatigue;
   a naive "approaching = alarm" rule would fire 129 times).
2. **Explainable advisor**: fuzzy rules over population percentiles; DS for report influence; returns fired
   rules as text.
3. **Deception-aware decision and wording** (the likely demo highlight: `img_006673`, `img_000926`).
4. **Evidence-cited, action-oriented brief**: Status / Reasons (2–3 evidence items) / Reports / Uncertainty +
   recommended action. ≤ 5 sentences, every sentence cites an evidence ID.
5. **Counterfactual explanations** from the deterministic advisor ("without circling this would be DIKKAT").
6. **Robustness test** over ambiguous matches and class alternatives.
7. Red-team checklist derived from the data (in `prompts.CRITIC`).
8. Day layer: priority list by level, then ring / ETA; sector × ring heat map (8 × 5).
Build order: 1 (team) → 4+2 → 3 → 6+5 → 7 → 8.

---

## 5. Orchestrator (pseudocode)

```python
def run_image(image_id):
    bb = Blackboard(image_id)
    msgs = [system(SOP_MAIN), user(user_task(image_id))]
    for step in range(MAX_STEPS):                      # e.g. 25
        resp = llm(msgs, tools=openai_tools(), reasoning_effort="low")
        msgs.append(resp.msg)
        if not resp.tool_calls:
            msgs.append(user("Send the assessment with submit_assessment."))
            continue
        for call in resp.tool_calls:
            err = guard.pre_tool(call, bb)             # args, budget, re-detect limit (2)
            if err: msgs.append(tool_result(call, err)); continue
            if call.name == "submit_assessment":
                verdict = guard.pre_final(call.args, bb)   # checklist, grounding, policy, deviation
                if verdict.ok:
                    verdict = critic.review(call.args, bb) # red team, no history
                if verdict.ok or bb.revisions >= 1:
                    return finalize(call.args, bb, verdict)
                bb.revisions += 1
                msgs.append(tool_result(call, verdict.feedback))
            else:
                out = TOOLS_IMPL[call.name](**call.args, bb=bb)
                bb.emit_event(call, out)                   # UI step player (UIEvent)
                msgs.append(tool_result(call, out.compact()))
    return fallback(bb)                                    # LLM-off path
```

Guard checks: `schema`, `checklist` (detect, find_tracks, search_reports, risk_advisor called),
`grounding`, `policy_asymmetric_trust`, `advisor_deviation`, `budget`, `loop`. Errors: SDK retries +
exponential backoff on 429/5xx; concurrency ≤ 4.

---

## 6. Files in this folder

- `schemas.py` — Pydantic v2 contracts for 9 tools
  (`open_image, place_on_map, detect, pixel_to_geo, find_tracks, analyze_motion, search_reports,
  risk_advisor, submit_assessment`), plus `Evidence`, `GuardVerdict`, `CriticReview`, `RunResult`, `UIEvent`,
  `DaySummary`, `LEVEL_POLICY`, and `openai_tools()` that emits the tool definitions.
  `python schemas.py` writes `tools_schema.json`. Needs `pip install pydantic`.
  ID formats: image `img_000860`, detection `D1`, track `T0122`, report `R017` (file order, 1-based),
  evidence `E12`.
- `prompts.py` — `SOP_MAIN` (agent system prompt, embeds `LEVEL_POLICY`), `user_task`, `guard_feedback`,
  `CRITIC`, `critic_input`, `critic_feedback`. Loads fine; **not yet tested against GLM**.

Stage-2 data used in the analysis lived at `C:\Users\Furkanpc\Desktop\stage2\` (the repo expects
`data/stage2/`). Earlier copies of the two files are in
`C:\Users\Furkanpc\Documents\GitHub\roketsan-hackathon\furkan\stage2\`.

---

## 7. Open decisions

1. Freeze `LEVEL_POLICY` thresholds (team).
2. Confirm which weight file is ardahan's RFS YOLO11m; then choose the stage-2 detector via track recall.
3. Default gates/windows: match gate (data-driven, start 3 m rule above), report time window (150 min),
   report search radius (500 m).
4. Demo entry point: single frame first (recommended) vs day board first.
5. Reconcile with `docs/AGENT_DESIGN.md`, translate Turkish prompt/description text to English, and move
   contracts into `backend/` per repo conventions.

## 8. Suggested next steps

1. `geo.py` + tests (official examples above) — first shared code.
2. Report parser + `population_features.csv` (226 tracks).
3. Scenario tests early, especially: inject a fake "friendly" report on an approaching/circling vehicle and
   assert the level does not drop (use `img_006673`, `img_000926`).
4. Then detector integration (step 3), matching (step 5), advisor (step 8), orchestrator + guard + critic.
