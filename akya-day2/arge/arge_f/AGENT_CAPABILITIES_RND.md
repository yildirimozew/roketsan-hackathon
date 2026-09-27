# Agent Foundations and Capabilities — R&D Backlog

Every R&D item for the SENTINEL agent, in the order the analysis flow runs. Each item states where the
code is today, why the item matters, how hard it is, how it works technically, and what it means in
plain words.

- **Sources:** `STAGE2_DESIGN_NOTES.md`, `schemas.py` and `prompts.py` in this folder; compared against
  `docs/AGENT_DESIGN.md`, `PLAN.md` and the backend code as of 2026-09-26.
- **Measurements:** run on the real files in `data/`. The detection cache and model weights are not in
  the repo, so where a number needs detections, the in-frame track points at capture time were used as
  stand-in detections (all labelled `car`). This is the best case for the detector and has no vehicle-type
  points.
- **Relation to the current code:** these items extend the existing pipeline. They do not replace it.

---

## Decisions already taken (2026-09-26)

| Topic | Decision | Effect on this backlog |
|---|---|---|
| Orchestration | **Pipeline only.** The fixed 8-step state machine stays; no LLM tool-calling loop for the main flow | Anything the design notes gave to "the agent decides" becomes a deterministic rule inside a pipeline step, plus LLM refinement in steps 6 and 8 only |
| "Insufficient evidence" (BELIRSIZ) | **A flag, not a level.** `RiskLevel` stays `LOW / MEDIUM / HIGH / CRITICAL` | Insufficient evidence → entry in `uncertainties` + `recommended_action = VERIFY` |
| Deception | **+1 level.** If the checkable part of a threat-lowering claim ("friendly", "supply", "our patrol") contradicts our data, the vehicle's level goes up by one step | `docs/AGENT_DESIGN.md` §3 step 6 ("contradicted reports are ignored") must be updated in the same change |
| Data path | Left as is for now | Not covered here |

## Difficulty scale

| Level | Meaning for a solo developer |
|---|---|
| **Trivial** | < 1 hour, one function, no contract change |
| **Easy** | 1–3 hours, one module plus tests, maybe new optional fields |
| **Medium** | Half a day; several modules or a public contract change (domain model → OpenAPI → `gen-types` → UI) |
| **Hard** | A day or more, new external dependency, model work, or high risk of breaking the demo |

**Status labels:** Done · Partial · Missing · Dropped.
**Priority:** P1 = changes the demo's correctness, P2 = clearly improves quality, P3 = nice to have.

---

## Overview

| # | Item | Status | Difficulty | Priority |
|---|---|---|---|---|
| **F** | **Foundations** | | | |
| F1 | Evidence IDs everywhere | Partial | Easy | P1 |
| F2 | Shared geometry module | Done | – | – |
| F3 | LLM client (cache, retries, budget) | Missing | Medium | P1 |
| F4 | Graceful degradation modes | Partial | Easy | P1 |
| F5 | Scenario / adversarial tests | Partial | Easy | P1 |
| **1** | **load_frame** | | | |
| 1.1 | Frame context bundle | Partial | Easy | P2 |
| 1.2 | Metadata integrity checks | Missing | Trivial | P2 |
| 1.3 | Out-of-distribution / image quality flag | Missing | Easy | P3 |
| 1.4 | Polar position: sector + ring | Missing | Trivial | P2 |
| 1.5 | Coverage record (footprint, GSD) | Partial | Easy | P2 |
| 1.6 | Blind-spot threshold | Missing | Trivial | P3 |
| 1.7 | Base-facing edge | Missing | Easy | P3 |
| 1.8 | Sector siblings | Missing | Easy | P3 |
| **2** | **detect** | | | |
| 2.1 | Light / heavy / unknown classes | Missing | Trivial | P2 |
| 2.2 | Track recall as a quality metric + model choice | Missing | Easy | P1 |
| 2.3 | Track-guided detection and local re-detect | Missing | Medium | P2 |
| 2.4 | Confidence calibration | Missing | Medium | P3 |
| 2.5 | Blind-spot flag on small boxes | Missing | Trivial | P3 |
| 2.6 | Detector report card | Missing | Medium | P3 |
| 2.7 | Open-set filter | Missing | Hard | P3 |
| 2.8 | Ensemble disagreement | Missing | Medium | P3 |
| 2.9 | Dominant color | Missing | Easy | P3 |
| **3** | **georeference** | | | |
| 3.1 | Official formula + inverse | Done | – | – |
| 3.2 | Data-calibrated error radius | Missing | Easy | P2 |
| 3.3 | Documented projection assumption | Done | – | – |
| **4** | **match_tracks** | | | |
| 4.1 | Hungarian assignment + data-driven gate | Partial | Easy | P2 |
| 4.2 | Two-pass matching | Missing | Easy | P3 |
| 4.3 | Ambiguity test + "decision unaffected" check | Partial | Easy | P2 |
| 4.4 | Hypotheses for unmatched objects | Partial | Easy | P1 |
| 4.5 | Heading consistency tie-breaker | Missing | Easy | P3 |
| **5** | **analyze_motion** | | | |
| 5.1 | Noise-aware move / stop segmentation | Partial | Easy | P1 |
| 5.2 | Base-centric geometry (sweep, closest pass, last 30 min) | Missing | Easy | **P1** |
| 5.3 | Population percentiles | Missing | Easy | P1 |
| 5.4 | Behavior tags | Missing | Easy | P2 |
| 5.5 | Shared motion vocabulary with reports | Missing | Trivial | P2 |
| 5.6 | ETA as a range | Partial | Trivial | P3 |
| 5.7 | Physical plausibility check | Missing | Trivial | P3 |
| 5.8 | Motion for unmatched tracks | Missing | Easy | P1 |
| **6** | **assess_reports** | | | |
| 6.1 | Parser: negation, all-clear, templates | Partial | Easy | P1 |
| 6.2 | Report-time alignment with tolerance | Partial | Trivial | P2 |
| 6.3 | Atomic claim checks | Partial | Medium | P2 |
| 6.4 | Direction check ("toward the base") | Missing | Easy | P1 |
| 6.5 | Identity rule + deception indicator (+1) | Partial | Easy | **P1** |
| 6.6 | Learned source reliability | Missing | Easy | P2 |
| 6.7 | Area and general reports | Partial | Medium | P2 |
| 6.8 | Coverage-aware verdicts | Partial | Easy | P2 |
| 6.9 | Cross-report consistency | Missing | Medium | P3 |
| 6.10 | LLM extraction + verdict | Missing | Medium | P2 |
| 6.11 | Report window / radius as settings | Partial | Trivial | P2 |
| **7** | **score_risk** | | | |
| 7.1 | Action-based level definitions | Partial | Easy | P1 |
| 7.2 | Rubric redesign on motion evidence | Partial | Medium | **P1** |
| 7.3 | Deception and identity modifiers | Missing | Easy | P1 |
| 7.4 | Insufficient-evidence flag | Missing | Easy | P2 |
| 7.5 | Counterfactual explanations | Missing | Easy | P2 |
| 7.6 | Robustness over ambiguous inputs | Missing | Medium | P2 |
| 7.7 | Fuzzy rules + Dempster–Shafer | Missing | Hard | P3 |
| **8** | **write_brief** | | | |
| 8.1 | LLM brief with evidence citations | Missing | Medium | P1 |
| 8.2 | Guard (validator) | Missing | Medium | P1 |
| 8.3 | Red-team critic | Missing | Medium | P2 |
| 8.4 | Brief model extensions | Missing | Easy | P2 |
| 8.5 | Deception-aware wording | Missing | Easy | P1 |
| **9** | **Beyond one frame** | | | |
| 9.1 | Day board (40 frames, priority list, heat map) | Missing | Medium | P2 |
| 9.2 | Analyst chat tools | Missing | Medium | P3 |
| 9.3 | Live step events and overlays | Partial | Medium | P1 |
| **X** | **Dropped or deferred** | Dropped | – | – |

---

## F. Foundations

Cross-cutting pieces that every step relies on.

### F1. Evidence IDs everywhere
- **Current state:** Partial. Entities already have IDs (`DET-n`, `TRK-<id>`, `REP-nn`, `ZONE-<name>`).
  The fallback brief collects them in `Brief.evidence_ids`. Derived facts (a motion feature, a risk
  factor, a report check) have no ID of their own.
- **Why:** the jury and mentors want "verifiable and explainable". The brief validator (8.2) can only
  reject invented numbers if each number can be traced to a stored fact.
- **Difficulty:** Easy.
- **Technical:** keep the existing prefixes (the UI's `EvidenceChip`, the mocks and the golden test
  depend on them). Add derived IDs in the same style: `MOT-T0122` (motion profile), `RISK-DET-1`,
  `CHK-REP-07-activity`. Do not introduce the notes' `E12` scheme. A full append-only "blackboard" is not
  needed in pipeline-only mode: the `Analysis` object already is the evidence record. It only needs these
  IDs and a helper that lists all valid IDs of an analysis.
- **In plain words:** every statement in the final report gets a label pointing to the measurement it
  came from, so anyone can click it and check.

### F2. Shared geometry module
- **Current state:** Done. `services/geo.py` has haversine, bearing, local east/north meters
  (`to_enu_m`), corner interpolation and its inverse. The golden test passes.
- **Why:** one distance function for everyone avoids small disagreements between steps.
- **Difficulty:** –
- **Technical:** new features (sector, ring, sweep, footprint) should reuse `to_enu_m` centered on the
  base.
- **In plain words:** all steps measure distances with the same ruler.

### F3. LLM client (cache, retries, budget)
- **Current state:** Missing. `agent/llm_client.py` defines only a protocol. `Settings.llm_model` still
  says `glm-4`.
- **Why:** steps 6 and 8 need it. Budget is $15, 60 requests/min, 4 concurrent, and the model always
  reasons, so cost and latency must be controlled.
- **Difficulty:** Medium.
- **Technical:** `openai` SDK with `base_url`. Model `glm-5.3-flash`, `reasoning_effort="low"` passed
  through (the critic may use `high`). Timeout, 2 retries with backoff on 429/5xx, concurrency ≤ 4. Disk
  cache keyed by `sha256(prompt_version + model + input_json)`. Log tokens and latency. Read spend from
  the gateway's `key/info`. One repair retry with the validation error, then fallback
  (AGENT_DESIGN §6–7).
- **In plain words:** a safe, cheap and repeatable way to ask the language model: same question →
  answer from the cache, errors → retry, still broken → fall back to templates.

### F4. Graceful degradation modes
- **Current state:** Partial. A detector failure falls back to `PrecomputedDetector` with a step warning.
  There is no LLM yet, so the brief always comes from the template (`generated_by="fallback"`).
- **Why:** the demo must never crash on stage.
- **Difficulty:** Easy.
- **Technical:** make the modes explicit and visible: `full` (LLM on) → `llm_off` (rules + template) →
  `detector_degraded` (tracks and reports only, uncertainty added) → `no_tracks` (low confidence,
  `VERIFY`). Store the mode in the analysis and show it as a badge.
- **In plain words:** if one part fails, the system keeps working with what is left and says so openly.

### F5. Scenario / adversarial tests
- **Current state:** Partial. The golden test, unit tests and rule-based report tests exist
  (40 tests). No test covers the deception trap on real frames.
- **Why:** the panel asked for "simulation tests". Deception is the core theme of the case.
- **Difficulty:** Easy.
- **Technical:** table-driven tests on fixtures:
  1. Inject a "friendly vehicle approaching" report on a circling vehicle (`img_006673` / T0043,
     `img_000926` / T0172) → assert the level does not drop and rises by one.
  2. Fake "all clear" → no drop.
  3. Wrong vehicle type → CONTRADICTED.
  4. Prompt injection → UNVERIFIED, trust 0.

  Keep the real LLM out of tests (`FakeLLMClient`).
- **In plain words:** before the demo we deliberately try to fool the system and prove it doesn't fall
  for it.

---

## 1. load_frame

Covers the notes' `open_image` and `place_on_map`. Everything here is deterministic metadata about the
frame.

### 1.1 Frame context bundle
- **Current state:** Partial. `ImageMeta` has size, time, corners and zone. The list of tracks that end
  at this capture time is computed later, in `match_tracks`, and only the in-frame ones are kept
  (`TrackSnapshot`).
- **Why:** knowing up front "N vehicles are expected in this frame" lets step 2 check itself (a detector
  that finds 1 of 6 expected vehicles is weak here).
- **Difficulty:** Easy.
- **Technical:** in step 1, list the tracks whose last point equals the capture time (every capture time
  is unique, so this identifies the frame's 3–10 tracks). Split them into inside / outside the frame and
  count the reports in the time window. Put this in `StepResult.data`, plus an `expected_vehicles` field.
- **In plain words:** before looking at the picture, the system already knows how many moving vehicles
  should be in it.

### 1.2 Metadata integrity checks
- **Current state:** Missing.
- **Why:** the pixel-to-coordinate formula is only valid if the corners are axis-aligned and the pixels
  square. A broken metadata row would silently place vehicles in the wrong place.
- **Difficulty:** Trivial.
- **Technical:**
  - Checks: file exists, image size equals meta, corners axis-aligned, GSD x/y ≈ 1 (measured 0.99 on all
    40 frames), time format.
  - Failure → step `warning` and degraded mode.
- **In plain words:** a quick sanity check that the frame's map data is trustworthy.

### 1.3 Out-of-distribution / image quality flag
- **Current state:** Missing.
- **Why:** the detector was trained on stage-1 images.
  - Three 1920×1080 frames (`img_003880`, `img_003189`, `img_000267`) are much brighter (182–187) than the
    stage-1 p95 of 145 for that resolution.
  - One frame is dark (`img_008589`).
  - On such frames, detections deserve less trust.
- **Difficulty:** Easy.
- **Technical:** z-scores of brightness and contrast against the same-resolution stage-1 distribution
  (`image_features_v1.csv` from the old repo). Add Laplacian-variance blur and an over-exposure ratio.
  Flag if |z| > 2. Pixel statistics only, no model.
- **In plain words:** the system notices when a photo looks unlike the ones the detector learned from,
  and lowers its confidence.

### 1.4 Polar position: sector + ring
- **Current state:** Missing. The frame's zone is the zone with the nearest center.
- **Why:** frames form an exact 8 sectors × 5 rings grid around the base (~1.7 / 2.6 / 3.5 / 4.4 /
  5.3 km). The ring is a natural "how close to home" input for the risk rules ("ring 1" in the level
  definitions). It also gives defense-in-depth vocabulary for the UI.
- **Measured:** nearest-center zone and bearing sector agree on **40/40** frames, so the zone assignment
  itself does not need to change.
- **Difficulty:** Trivial.
- **Technical:** add `sector_index`, `bearing_from_base_deg`, `ring` and `base_distance_km` to
  `ImageMeta`. Optional fields → `gen-types`.
- **In plain words:** each photo gets an address like "east, first ring", which says at once which
  direction it is and how close to the base.

### 1.5 Coverage record (footprint, GSD)
- **Current state:** Partial. Frame width and height in meters are computed in step 3 (`frame_size_m`).
  There is no footprint polygon or GSD field.
- **Why:** step 6 needs to know whether a report location was actually visible in this frame. "We looked
  and saw nothing" (contradicted) is different from "we could not look" (unverifiable).
- **Difficulty:** Easy.
- **Technical:** footprint polygon (TL, TR, BR, BL), `gsd_m_per_px` (x, y), capture time. Expose a
  `covers(point, time)` helper for step 6.
- **In plain words:** we record exactly which patch of ground this photo shows, so we never claim to
  have "seen" something outside it.

### 1.6 Blind-spot threshold
- **Current state:** Missing.
- **Why:** the 200 px² detection floor equals 2.3–7.9 m² on the ground. A car is ~8 m², so in coarse
  frames even cars sit near the limit, and motorcycles are never counted.
- **Difficulty:** Trivial.
- **Technical:** `min_detectable_area_m2 = 200 × gsd_x × gsd_y`, stored per frame and used by 2.5 and 4.4.
- **In plain words:** the system knows the smallest thing it can see in each photo and admits it may
  miss smaller vehicles.

### 1.7 Base-facing edge
- **Current state:** Missing.
- **Why:** UI arrows toward the base; "entered from the base side" is a useful phrase in the brief.
- **Difficulty:** Easy.
- **Technical:** bearing from the frame center to the base → one of 8 edges/corners.
- **In plain words:** an arrow on the photo showing which way the base is.

### 1.8 Sector siblings
- **Current state:** Missing.
- **Why:** mainly for the day board (9.1): other frames in the same direction and when they were taken.
- **Difficulty:** Easy.
- **Technical:** frames with the same `sector_index`, sorted by ring, with capture times.
- **In plain words:** "other photos looking in the same direction".

---

## 2. detect

The only step that runs the image model.

### 2.1 Light / heavy / unknown classes
- **Current state:** Missing. Detections carry a fine label (`car`, `van`, `truck`, `bus`) and a
  confidence.
- **Why:** reports themselves say "ağır araç" (heavy vehicle), and fine classes are unreliable on small
  boxes. Comparing at the light/heavy level avoids false contradictions.
- **Difficulty:** Trivial.
- **Technical:** add `super_class` (car+van → light, truck+bus → heavy) and `class_decision`
  (`fine | super | unknown`) to `Detection`. The report type check already treats truck/bus as the same
  family (`_same_kind`); make it use `super_class`.
- **In plain words:** when we are not sure if it is a truck or a bus, we still confidently say "heavy
  vehicle".

### 2.2 Track recall as a quality metric + model choice
- **Current state:** Missing. The live detector uses one `.pt` file at conf 0.35 / imgsz 960. Which
  weight file is ardahan's RFS YOLO11m is not confirmed (`Downloads/`: `hakan_yolo11m.pt`,
  `yolo11l_ardahan.pt`, `last.pt`, `last (1).pt`).
- **Why:** the 40 stage-2 frames have no labels (they are not in the Kaggle sets). But 206 track
  endpoints lie inside their frames, and each one marks a real moving vehicle. That gives a label-free
  recall measure for choosing the model, threshold and TTA.
- **Difficulty:** Easy.
- **Technical:** for each candidate configuration, run all 40 frames and count the in-frame track points
  covered by a box within the gate. Report recall per resolution. Pick the configuration, then cache it
  with `make detections`.
- **In plain words:** the vehicle routes tell us where cars really are, so we can grade each detector
  without hand-labelling any photo.

### 2.3 Track-guided detection and local re-detect
- **Current state:** Missing.
- **Why:** a low-confidence box right on a track point is almost certainly a real vehicle. A track point
  with no box is a likely miss.
- **Difficulty:** Medium. Needs a `Detector` protocol change.
- **Technical:**
  1. Run at a low threshold (e.g. 0.05), keeping boxes as `candidate`.
  2. Promote a candidate to `fact` when it lies within the gate of a track point at capture time.
  3. For an in-frame track point without any box, re-run on a crop around it (low threshold, optional
     SAHI tiling), at most 2 per frame.
  4. In pipeline-only mode the trigger is a rule (orphan in-frame track, or an in-frame report
     contradiction) instead of an LLM decision.

  `PrecomputedDetector` cannot re-detect, so it just reports "not available".

  **Risk:** circular evidence (the track "confirms" a box that was only kept because of the track).
  Mark such boxes (`from_local_redetect`, `promoted_by_track`) and never count them as independent
  confirmation of that track.
- **In plain words:** when the route data says "a car should be here", the system looks again more
  carefully at that exact spot.

### 2.4 Confidence calibration
- **Current state:** Missing.
- **Why:** raw YOLO scores are not probabilities. A calibrated 0.8 should mean "right 80% of the time".
- **Difficulty:** Medium.
- **Technical:** per-class isotonic regression fitted on stage-1 validation predictions. Store
  `confidence_raw` and `confidence_calibrated`.
- **In plain words:** we translate the detector's internal score into an honest "how sure are we".

### 2.5 Blind-spot flag on small boxes
- **Current state:** Missing.
- **Why:** the class of a box close to the 200 px² floor is unreliable.
- **Difficulty:** Trivial.
- **Technical:** `near_blind_threshold = area_px < 1.5 × 200` → `class_decision = super`.
- **In plain words:** very small vehicles get a note: "we see something, but can't tell exactly what".

### 2.6 Detector report card
- **Current state:** Missing.
- **Why:** it tells the operator and the brief how good the detector is on this kind of frame (resolution,
  darkness).
- **Difficulty:** Medium.
- **Technical:** per-stratum class AP from stage-1 validation. Dark strata have only 1–6 images, so
  shrink toward the global value: `AP = (n·AP_stratum + k·AP_global)/(n + k)`. Attach it to the step
  output.
- **In plain words:** a small "grade card" of the detector for this type of photo.

### 2.7 Open-set filter
- **Current state:** Missing.
- **Why:** three-wheelers, motorbikes and other objects get forced into one of the 4 classes.
- **Difficulty:** Hard.
- **Technical:** crop embeddings (existing `ardahan_embedding.pt` or the ConvNeXt reranker). Cosine
  similarity to class prototypes; a low score → `unknown`.
- **In plain words:** the detector learns to say "this is not one of the vehicles I know".

### 2.8 Ensemble disagreement
- **Current state:** Missing.
- **Why:** when two models disagree on a box, that box is uncertain.
- **Difficulty:** Medium. Two models = double inference time.
- **Technical:** IoU × class agreement between models → `ensemble_agreement` 0–1.
- **In plain words:** ask two detectors. If they disagree, be careful.

### 2.9 Dominant color
- **Current state:** Missing.
- **Why:** some reports mention a color ("mavi araç", "sarı araç").
- **Difficulty:** Easy.
- **Technical:** k-means or an HSV histogram on the box crop → a small color vocabulary that matches the
  report parser's colors.
- **In plain words:** the system notes each vehicle's color so it can check reports that mention one.

---

## 3. georeference

### 3.1 Official formula + inverse
- **Current state:** Done. Box center + linear corner interpolation, and its inverse (Newton). The golden
  check reproduces `img_000860` → (39.925313, 32.871833), which is **0.02 m** from T0122. Track points
  were generated with exactly this formula.
- **Why:** –
- **Difficulty:** –
- **Technical:** do not switch to homography or the bottom-center point; that would break matching.
  Add the PDF example (`img_000123` → 39.94439, 32.86350) as a second unit test.
- **In plain words:** pixel → map position works and matches the organizer's example.

### 3.2 Data-calibrated error radius
- **Current state:** Missing.
- **Why:** it gives each position an honest uncertainty and gives step 4 a gate based on data, not on
  guesswork.
- **Difficulty:** Easy (after 2.2 fixes the detector).
- **Technical:** distances between matched box centers and their track points → p50 / p95 per
  resolution. `error_radius_m` per detection = p95 (or `0.5 × box diagonal × GSD`, whichever is larger).
- **In plain words:** "this vehicle is here, give or take N meters", with N measured from real data.

### 3.3 Documented projection assumption
- **Current state:** Done. The brief always lists "oblique frames treated as top-down" as an
  uncertainty. PLAN and AGENT_DESIGN record the decision.
- **Why:** mentors will ask why the oblique images are not corrected.
- **Difficulty:** –
- **Technical:** add the 0.02 m result as the justification: the data contract uses the linear center
  formula.
- **In plain words:** we explain openly why we treat the photos as seen from straight above.

---

## 4. match_tracks

### 4.1 Hungarian assignment + data-driven gate
- **Current state:** Partial. Global one-to-one matching is in place (`scipy.linear_sum_assignment`),
  with a 25 m gate and the second-best distance kept.
- **Why:** in-frame track endpoints are close together (nearest-neighbour min 1.7 m, p5 3.1 m, median
  17 m; 31 points have a neighbour within 5 m). A wide gate lets vehicles swap identities.
- **Difficulty:** Easy.
- **Technical:** replace the fixed 25 m with `gate = max(3 m, error_radius_m)` from 3.2 (per detection,
  or per resolution). Keep `match_max_m` as an upper cap in `Settings`. The golden test (T0122 < 1 m,
  second T0032 ≈ 41 m) stays valid.
- **In plain words:** each car on the photo is paired with the route that best explains it, and pairs
  that are too far apart are refused.

### 4.2 Two-pass matching
- **Current state:** Missing. It depends on 2.3 (candidate vs fact boxes).
- **Why:** confident boxes should claim tracks first. Weak boxes may only take what is left.
- **Difficulty:** Easy.
- **Technical:** pass 1 matches `fact` boxes. Pass 2 matches `candidate` boxes to the remaining track
  points. A matched candidate becomes `fact`. Record `pass_no`.
- **In plain words:** sure detections pick their routes first; doubtful ones only get what remains.

### 4.3 Ambiguity test + "decision unaffected" check
- **Current state:** Partial. `TrackMatch.confidence` (high/medium/low) uses distance and the margin to
  the second-best track. There is no explicit "ambiguous" status and no check of whether the ambiguity
  matters.
- **Why:** an operator needs to know "we're not sure which route this car belongs to — but it doesn't
  change the answer" versus "…and it changes the answer".
- **Difficulty:** Easy (the robustness part is in 7.6).
- **Technical:**
  - Lowe ratio `d1/d2 > 0.7` → `status = ambiguous`, with `alternatives`.
  - Step 7 scores both alternatives. If the frame level is the same, write "ambiguous but decision
    unaffected".
  - Otherwise pick the higher level and add an uncertainty.
- **In plain words:** when two routes could fit the same car, we check both. If both lead to the same
  conclusion, we say so; if not, we take the safer one.

### 4.4 Hypotheses for unmatched objects
- **Current state:** Partial. In-frame tracks without a detection are listed as `TrackSnapshot` with
  `matched_detection_id = None`. Unmatched detections get `track_id = None` and a "no track" factor.
  Neither gets an explanation.
- **Why:** the most dangerous vehicle may be one the detector missed, or one just outside the photo.
  Measured: 20 of 226 track endpoints are 7–26 m outside their frame edge. Today such vehicles take no
  part in the risk score.
- **Difficulty:** Easy.
- **Technical:**
  - Track without detection: `missed` (inside frame → trigger 2.3), `blind_spot` (small-GSD frame, 1.6),
    or `outside_near_edge` (≤ 30 m outside).
  - Detection without track: `parked_likely` (parked cars have no track) or `false_positive_likely`
    (low confidence, near the blind-spot threshold).
  - Orphan tracks go to step 5 (see 5.8).
- **In plain words:** for every car without a route and every route without a car, the system gives the
  most likely reason instead of silently ignoring it.

### 4.5 Heading consistency tie-breaker
- **Current state:** Missing.
- **Why:** it can break a tie between two nearby tracks.
- **Difficulty:** Easy.
- **Technical:** compare the box's long axis with the track heading. Use only when the ratio test says
  `ambiguous`.
- **In plain words:** a car pointing the same way as a route is the better match.

---

## 5. analyze_motion

The measured weak spot of the current system (see 7.2).

### 5.1 Noise-aware move / stop segmentation
- **Current state:** Partial. A stop is a run of steps slower than 1.0 m/s lasting ≥ 10 min.
  1.0 m/s = 300 m per 5-minute step.
- **Measured:** 57% of 5-minute steps move < 5 m (GPS jitter level), but the current threshold calls
  **76%** of steps "stopped". A vehicle crawling 250 m every 5 minutes counts as parked.
- **Why:** "moving vs stopped" is the core of report verification ("the vehicle is coming toward the
  base" vs a vehicle that is not moving).
- **Difficulty:** Easy.
- **Technical:** keep the existing `stops` (the golden test's ≈40 and ≈45 min stops are calibrated on
  it) and add a separate notion:
  - `moving` = step > 5 m (noise floor).
  - Speed computed from moving steps only.
  - Dwell list.
  - `moving_share`.
  - A last-30-minute summary.
- **In plain words:** we separate "really standing still" from "tiny GPS wobble", and "slow driving"
  from "parked".

### 5.2 Base-centric geometry (sweep, closest pass, last 30 min)
- **Current state:** Missing. There is distance now / 30 / 60 minutes ago, the minimum distance, the
  approach rate and the heading–bearing angle. There is nothing about circling.
- **Measured:**
  - "Getting > 0.8 km closer over 2 h" is true for **129 / 226** tracks, so approaching is **not
    discriminative**. It is structural, because all frames lie 1.6–5.4 km from the base.
  - 41 tracks circle more than 90° around the base.
  - Four stand out: T0043 441°, T0158 323°, T0172 549°, T0198 320°. Each came within < 0.9 km and moved
    1.8–2.5 km inward in the last 30 min.
- **Why:** circling plus a close pass is the real threat signal in this data. Without it the rubric
  picks the wrong vehicle (see 7.2).
- **Difficulty:** Easy.
- **Technical:**
  - `sweep_deg` = **net signed** sum of bearing changes around the base. Do not use the sum of absolute
    changes: T0047 would then score 1029° although it only goes back and forth (net 60°).
  - `closest_ever_m` and `closest_ever_time`.
  - `inward_last30_m`.
  - Radial speed.
- **In plain words:** instead of only asking "is it getting closer?", we ask "has it been going around
  the base, how close did it ever get, and did it just move in fast?".

### 5.3 Population percentiles
- **Current state:** Missing.
- **Why:** fixed thresholds ("> 20 m/min") are arbitrary. "Circled more than 98% of all vehicles today"
  is self-explaining and robust.
- **Difficulty:** Easy.
- **Technical:** compute the features of all 226 tracks once at startup (or freeze them as
  `population_features.csv` in the cache). Store per-track percentiles of `sweep`, `closest_ever`,
  `inward_last30`, `approach_rate` and `moving_share` in `MotionProfile.population_percentiles`.
- **In plain words:** each vehicle is compared with all other vehicles of the day, so "unusual" means
  unusual in this data, not in someone's guess.

### 5.4 Behavior tags
- **Current state:** Missing.
- **Why:** short tags are what the operator scans first, and the brief can use them.
- **Difficulty:** Easy.
- **Technical:** rules over 5.1–5.3: `approaching`, `loitering`, `circling`, `waiting`, `stop_and_go`,
  `transit`, `leaving`.
- **In plain words:** one or two words per vehicle, like "circling" or "waiting".

### 5.5 Shared motion vocabulary with reports
- **Current state:** Missing. The report parser has its own activity words (`moving`, `stationary`,
  `loading`), and motion has no "state now".
- **Why:** comparing a report with the data only works if both use the same words with the same
  definitions.
- **Difficulty:** Trivial.
- **Technical:** `state_now ∈ {moving, stopped, parked}` from 5.1. The report `activity` is mapped to the
  same set.
- **In plain words:** the report and the sensor speak the same language, so we can compare them.

### 5.6 ETA as a range
- **Current state:** Partial. A single ETA = distance / last-10-min speed, when approaching.
- **Why:** stop-and-go traffic makes a single number misleading.
- **Difficulty:** Trivial.
- **Technical:** give a range using the slowest and fastest recent moving segments. A constant-velocity
  / Kalman projection was rejected for this data.
- **In plain words:** "could arrive in 10–25 minutes" instead of a falsely precise "17 minutes".

### 5.7 Physical plausibility check
- **Current state:** Missing.
- **Why:** it catches corrupted or spoofed tracks. Measured: max 9.3 m/s, no impossible jumps today.
- **Difficulty:** Trivial.
- **Technical:** flag steps above ~40 m/s or position jumps.
- **In plain words:** if a car seems to teleport, we flag the data instead of believing it.

### 5.8 Motion for unmatched tracks
- **Current state:** Missing. Motion is computed only for tracks matched to a detection.
- **Why:** a circling vehicle the detector missed, or one just outside the frame (4.4), is still a
  threat.
- **Difficulty:** Easy.
- **Technical:** run 5.1–5.4 for orphan tracks with the hypothesis `missed` or `outside_near_edge`. They
  enter step 7 as track-only vehicles with a "not seen in image" uncertainty.
- **In plain words:** a vehicle does not become harmless just because the camera missed it.

---

## 6. assess_reports

### 6.1 Parser: negation, all-clear, templates
- **Current state:** Partial. The rule-based extractor finds coordinates, zone names, vehicle words,
  colors, activity and claim kind (`SIGHTING`, `ALL_CLEAR`, `FRIENDLY_PRESENCE`, `TRAFFIC_NORMAL`,
  `OTHER`).
  - Measured on 137 reports: 57 SIGHTING, 22 FRIENDLY_PRESENCE, 10 TRAFFIC_NORMAL, 8 ALL_CLEAR, 40 OTHER.
  - It does not handle negation. REP-92 "Kuzeydoğu Kavşağı bölgesinde ağır araç hareketi yok" is parsed
    as a heavy-vehicle *sighting*. If a truck is detected there, the code would call the report
    CORROBORATED although it says the opposite.
- **Why:** the reports come from 34 surface templates plus a few one-offs, so a template parser covers
  almost everything cheaply and deterministically.
- **Difficulty:** Easy.
- **Technical:**
  - Negation patterns ("… yok", "görülmedi", "sadece otomobil") → `ALL_CLEAR` / area status.
  - Add claim kinds `UNVERIFIED_TIP` ("dün gece", "ihbar") and `IRRELEVANT`.
  - Vocabulary: panelvan → van (light), ağır araç → heavy, otomobil → car, kamyon → truck.
  - Record a `template_id` per match. The LLM (6.10) only handles the long tail.
- **In plain words:** the system reads "no heavy vehicles here" as a statement that the area is clear,
  not as "heavy vehicle here".

### 6.2 Report-time alignment with tolerance
- **Current state:** Partial. The presence check already interpolates tracks at the report's own time.
  The activity check uses the 5 minutes before the report time.
- **Why:** reports seem to be generated from track positions at report time: 47 / 72 located reports
  have a track within 60 m at that minute.
- **Difficulty:** Trivial.
- **Technical:** search ±15 min around the report time and take the best-matching state. Store
  `track_at_report_time` (track, distance, state, radial direction).
- **In plain words:** we compare a report with where vehicles were when it was written, not when the
  photo was taken.

### 6.3 Atomic claim checks
- **Current state:** Partial. The checks are `location`, `presence`, `type`, `activity` and
  `instructions`.
- **Why:** one report can be half right (the location is right, the claimed identity cannot be checked).
  Splitting it lets us trust the checkable part and flag the rest.
- **Difficulty:** Medium (touches `ReportCheck` and the UI chips).
- **Technical:** extend `CheckName` with `count`, `color`, `direction`, `identity` and `area_status`.
  Each gets `supported / contradicted / unverifiable` + how + evidence IDs. Keep the existing
  verdict names (`CORROBORATED / CONTRADICTED / UNVERIFIED / IRRELEVANT`).
- **In plain words:** we check a report sentence by sentence: this part is true, this part is false,
  this part cannot be known.

### 6.4 Direction check ("toward the base")
- **Current state:** Missing. "Üsse doğru ilerleyen" only sets `activity = moving`.
- **Measured:** of the 15 located "friendly vehicle moving toward the base" reports, 8 have no track
  within 60 m and 7 match a vehicle that is stopped under the current 1 m/s rule. Under the 5 m noise
  floor (5.1), REP-78 and REP-83 would count as moving, so they would look consistent unless the
  direction is also checked.
- **Why:** it keeps the deception detection correct once 5.1 lands.
- **Difficulty:** Easy.
- **Technical:** radial speed of the matched track at report time (from 5.2) → `toward_base / away /
  none`. Compare with the claimed direction.
- **In plain words:** "coming toward the base" is checked for both parts: is it moving, and is it
  actually moving toward us?

### 6.5 Identity rule + deception indicator (+1)
- **Current state:** Partial.
  - Threat-lowering claims (`ALL_CLEAR`, `FRIENDLY_PRESENCE`) are already UNVERIFIED and never lower the
    score.
  - When their checkable part contradicts the data they become CONTRADICTED with trust 0, and are then
    simply ignored.
  - Measured on key frames: REP-06 on `img_006673`, REP-78 on `img_000926` and REP-120 on the golden
    frame `img_000860` all come out CONTRADICTED today and have no effect.
- **Why:** 18 friendly/supply identity claims, all from "official" sources, and 0 / 15 of the checkable
  ones are consistent. Two of the four most suspicious vehicles sit in frames covered by such claims.
  This is very likely the case's intended trap and the strongest demo moment.
- **Difficulty:** Easy. Decided: +1 level.
- **Technical:**
  - `deception_indicator = lowers_threat and verdict == CONTRADICTED`, linked to the vehicle(s) near the
    claimed location.
  - Step 7 applies +1 level to those vehicles (7.3).
  - Update AGENT_DESIGN §3 step 6 in the same change.
  - Identity itself stays unverifiable: no sensor can confirm "friendly".
- **In plain words:** if someone says "that's our supply truck coming in" but the data shows no vehicle
  coming in, that is not just a wrong report, it is a warning sign, and the alert goes up.

### 6.6 Learned source reliability
- **Current state:** Missing. Trust weights are fixed: official 0.8, third party 0.5.
- **Why:** "official" is not automatically reliable here. Measured: official "vehicle is stationary"
  sightings are 16/17 consistent, official "friendly vehicle approaching" 0/15.
- **Difficulty:** Easy.
- **Technical:** a Beta–Bernoulli count per (source × claim kind) over the day's checkable claims:
  `mean = (1 + supported) / (2 + supported + contradicted)`. Use it as the trust weight for the
  uncheckable claims of that kind. Compute it once over all reports at startup (deterministic).
- **In plain words:** each type of report earns or loses trust based on how often it turned out true
  today.

### 6.7 Area and general reports
- **Current state:** Partial. General reports without coordinates are relevant only if they name this
  frame's zone, and then they mostly end up UNVERIFIED.
- **Why:** several report kinds need their own rule:
  - "No heavy vehicles, only cars"
  - "Usual traffic is N vehicles"
  - Weather
  - "Last night, unverified tip" (outside the time window)
  - "Planned exercise, friendly units today" (blanket claim)
  - "Radio contact with patrol lost for N minutes" (raises attention)
- **Difficulty:** Medium.
- **Technical:**
  - Area claims are checked against the frame's detections by super class.
  - Traffic counts are checked against the number of detections plus orphan tracks.
  - Weather is checked against 1.3 brightness.
  - "Last night" → `IRRELEVANT`.
  - "Planned exercise" → can never lower the level.
  - "Radio contact lost" → attention note for that sector (uncertainty, no points).
- **In plain words:** each kind of general message is handled with common sense instead of being
  lumped together.

### 6.8 Coverage-aware verdicts
- **Current state:** Partial. A location mismatch counts as a contradiction only if no track was near at
  the report time either. There is no explicit "outside what we can see" status.
- **Why:** a report about a place the drone did not see is unverifiable, not false.
- **Difficulty:** Easy (after 1.5).
- **Technical:** coverage status `in_frame / near_frame / out_of_coverage / no_location` from 1.5. Only
  `in_frame` absences can be CONTRADICTED, and only after a local re-detect (2.3) when available.
- **In plain words:** we only call a report wrong if we actually looked at that place.

### 6.9 Cross-report consistency
- **Current state:** Missing.
- **Why:** two reports that contradict each other about the same place and time lower the trust in
  both.
- **Difficulty:** Medium.
- **Technical:** group reports by location and time bucket, then compute a conflict score (Dempster–
  Shafer conflict K or a simple disagreement ratio) and add it as an uncertainty.
- **In plain words:** if two messages disagree about the same spot, we point that out.

### 6.10 LLM extraction + verdict
- **Current state:** Missing (planned for P2 in AGENT_DESIGN §3 6a/6c; the rules are the fallback).
- **Why:** it covers the long tail of phrasings the templates miss and gives a readable one-sentence
  reason per report.
- **Difficulty:** Medium.
- **Technical:** English prompt files `report_extraction_v1.md` and `report_verdict_v1.md`. Reports go
  inside `<untrusted_reports>` tags. JSON validated by Pydantic, one repair retry, then the rules.
  - The code-side verdict is passed as a hint.
  - The trust policy stays enforced in code: the LLM cannot lower a level through a report.
  - The Turkish prompt text in `prompts.py` must be translated before use.
- **In plain words:** the language model helps read unusual messages, but the safety rules are still
  checked by code.

### 6.11 Report window / radius as settings
- **Current state:** Partial. `report_radius_m = 300` is a setting. The 120-minute window is hard-coded
  in `is_relevant` and in the pipeline (`motion.WINDOW_MIN`).
- **Why:** the design notes suggest 150 min / 500 m. The right value should be testable without code
  edits.
- **Difficulty:** Trivial.
- **Technical:** add `report_window_min` to `Settings` and pass it through.
- **In plain words:** how far back and how far around we look for reports becomes a simple setting.

---

## 7. score_risk

### 7.1 Action-based level definitions
- **Current state:** Partial. The levels are defined by score bands (0–24 LOW … 75–100 CRITICAL). The
  recommended action is derived from the level (`MONITOR / VERIFY / ESCALATE`).
- **Why:** an operator needs to know what to do, not a number. Mapping of the notes' draft to our
  4 levels:

  | Level | Operator action | Draft criterion |
  |---|---|---|
  | CRITICAL | Confirm and respond now (`ESCALATE`) | (net sweep > 180° or closest pass < 1 km) AND ring 1 AND moved inward in the last 30 min; or heavy + approaching the inner ring + deception indicator |
  | HIGH | Notify, check on the next drone pass (`VERIFY`) | Two strong signals (population top 10%) or a deception indicator in the frame |
  | MEDIUM | Routine watch (`MONITOR`) | One unusual signal |
  | LOW | None (`MONITOR`) | No signal |

  "Insufficient evidence" is a flag (7.4), not a level.
- **Difficulty:** Easy (the thresholds are a team decision).
- **Technical:** write the table into AGENT_DESIGN §3 step 7 with a policy version. The rubric (7.2)
  must produce these levels.
- **In plain words:** every alert level comes with a clear instruction for the operator.

### 7.2 Rubric redesign on motion evidence
- **Current state:** Partial. An additive 0–100 score: distance (30/20/10), approach rate (25/15/5),
  heading to base (10), long stops (10/+5), vehicle type (10/8/5), corroborated report (10).
- **Measured** (stand-in detections, no type points):
  - Frame levels under the current 4-level scoring (LOW / MEDIUM / HIGH / CRITICAL): **22 HIGH,
    17 MEDIUM, 1 LOW, 0 CRITICAL**. The operator is told "verify" (`VERIFY`) 22 times, but "respond now"
    (`ESCALATE`) never appears.
  - Real detections add type points. Some frames may reach CRITICAL, but because they contain a truck,
    not because of circling behavior.
  - The four suspicious vehicles do **not** come out on top in their own frames:

    | Track | Frame | Score | Rank in frame |
    |---|---|---|---|
    | T0043 | `img_006673` | 50 | 5 / 6 |
    | T0158 | `img_005672` | 45 | 3 / 4 |
    | T0172 | `img_000926` | 50 | 3 / 5 |
    | T0198 | `img_002900` | 50 | 4 / 4 |

    The brief headlines the top-scoring vehicle, so today it describes the wrong one.
- **Why:** alert fatigue (more than half the frames HIGH, so the "verify" alarm fires so often that it
  stops being taken seriously) and a wrong focus (the truly urgent frames do not stand out). A naive "approaching =
  alarm" rule would fire 129 times.
- **Difficulty:** Medium (contract stays: `VehicleRisk.factors`; weights and factors change; the golden
  expectations must be re-checked).
- **Technical:**
  - Keep the factor-breakdown structure.
  - Add `circling` (net sweep percentile), `closest_pass` (closest-ever percentile / < 1 km) and
    `inward_last30`.
  - Reduce the weight of `approach_rate` and `distance_to_base`, which are structural in this data.
  - Target distribution on 40 frames: ~4 CRITICAL, 6–10 HIGH, the rest MEDIUM/LOW, with the four
    candidates ranked first in their frames.
  - Add a `pytest -m eval` check that prints the distribution.
- **In plain words:** the scoring currently rewards "is near and getting closer", which nearly every car
  in this data does. It should reward what is actually unusual: circling the base and a close pass.

### 7.3 Deception and identity modifiers
- **Current state:** Missing. Unverifiable lowering claims already cannot lower the score.
- **Why:** it implements the decided +1 rule (6.5).
- **Difficulty:** Easy.
- **Technical:** after the base level, apply +1 step (capped at CRITICAL) to vehicles linked to a
  `deception_indicator`. Add a factor line `deception_indicator: REP-xx` so it shows in the breakdown.
  Identity claims never lower. If robustness is `sensitive` (7.6), take the higher level.
- **In plain words:** a false "it's one of ours" message makes the system more alert, never less.

### 7.4 Insufficient-evidence flag
- **Current state:** Missing. Nothing is detected → LOW.
- **Why:** "we don't know" is a valid and safer answer than a confident LOW (the panel's open-set point).
- **Difficulty:** Easy.
- **Technical:** set `insufficient_evidence = true` when, for example, the detector is degraded and
  there are no tracks, recall 2.2 is very low on this frame, or the OOD flag 1.3 is set with no track
  support. Effect: an uncertainty line + `recommended_action = VERIFY`; the level is unchanged.
- **In plain words:** when the system can't see well enough, it says "send another look" instead of
  "all fine".

### 7.5 Counterfactual explanations
- **Current state:** Missing.
- **Why:** "without the circling this would be MEDIUM" is the clearest possible explanation, and it
  comes almost for free because the scorer is deterministic.
- **Difficulty:** Easy.
- **Technical:** rerun `score_vehicle` with one factor removed or one report flipped. Keep the 1–2
  changes that change the level. Store them as `Counterfactual(subject, change, level_before,
  level_after)`.
- **In plain words:** the system explains which single fact made the difference.

### 7.6 Robustness over ambiguous inputs
- **Current state:** Missing.
- **Why:** an ambiguous match (4.3) or an uncertain class (2.1) should not silently decide the level.
- **Difficulty:** Medium.
- **Technical:** enumerate the alternatives (other track candidates, light vs heavy) up to a small cap.
  Score each one. `robustness = robust` if all give the same frame level, else `sensitive` (then pick
  the higher level and state why).
- **In plain words:** we check whether the answer would change if our uncertain guesses were wrong.

### 7.7 Fuzzy rules + Dempster–Shafer
- **Current state:** Missing.
- **Why:** a principled way to combine uncertain evidence and show "unknown" mass. Good for mentor
  questions, but it adds complexity and is not needed for a correct demo.
- **Difficulty:** Hard.
- **Technical:** fuzzy memberships over the population percentiles. DS masses {threat, benign, unknown}
  per evidence source with reliability discounting (6.6), then combination. Show the fired rules as text.
- **In plain words:** a more formal way to combine "partly sure" clues. Optional, after everything else.

---

## 8. write_brief

### 8.1 LLM brief with evidence citations
- **Current state:** Missing. A deterministic Turkish/English template is used (`fallback.py`,
  `generated_by = "fallback"`).
- **Why:** a natural, short, well-argued brief is what the jury sees first.
- **Difficulty:** Medium.
- **Technical:** `brief_v1.md` (English prompt, output language from `BRIEF_LANGUAGE`). It gets all facts
  as JSON and reports in `<untrusted_reports>`. Structure, at most 5 sentences:
  1. Status (level + one line).
  2. Reasons (2–3 strongest evidence items).
  3. Reports (supported / contradicted / deception).
  4. Uncertainty + action.

  Every sentence cites at least one ID. The LLM may move the frame level by at most one step, with a
  cited reason. The template stays as the fallback.
- **In plain words:** the language model writes the final summary, but only from verified facts and
  with a source for every sentence.

### 8.2 Guard (validator)
- **Current state:** Missing (the brief validator is planned in AGENT_DESIGN and backend/CLAUDE.md).
- **Why:** this is the panel's "independent control computer" that checks the AI's decision.
- **Difficulty:** Medium.
- **Technical:** deterministic checks on the LLM brief:
  - **schema:** required fields are non-empty.
  - **grounding:** every ID exists in the analysis (F1), and every number in the text matches a stored
    value within rounding.
  - **level:** within ±1 of the rubric.
  - **policy:** no report lowered the level, a deception indicator is mentioned if present.
  - **deviation reason:** present whenever the level differs from the rubric.

  On failure: one repair round with the failed checks, then the template brief, marked "unverified" in
  the UI.
- **In plain words:** a strict proof-reader made of plain code checks the AI's report before anyone
  sees it.

### 8.3 Red-team critic
- **Current state:** Missing. A Turkish draft exists in `prompts.py` (`CRITIC`).
- **Why:** deception is the case's core theme. A second, independent look that tries to find how the
  analyst was fooled catches mistakes the guard's fixed rules cannot.
- **Difficulty:** Medium (one extra LLM call per frame, one revision round at most).
- **Technical:** input = final brief + evidence pack, with **no** conversation history. Fixed checklist:
  1. A deceptive report was relied on.
  2. The level is inconsistent with circling / closest pass.
  3. An ambiguous match was treated as certain.
  4. An in-coverage report was ignored, or an out-of-coverage report was called contradicted.
  5. An unsupported number was used.

  Only level-changing issues block. The output is `CriticReview` JSON. Translate the prompt to
  English, add `<untrusted_reports>`, and use it after the guard passes.
- **In plain words:** a second AI plays the "devil's advocate" and looks only for ways the first
  conclusion could be wrong.

### 8.4 Brief model extensions
- **Current state:** Missing. `Brief` has headline, summary, vehicle lines, report notes, uncertainties,
  action and evidence IDs.
- **Why:** it carries the new explanations (7.3–7.6, 8.3) to the UI without replacing the contract.
- **Difficulty:** Easy (additive contract change → `gen-types`).
- **Technical:** add optional `rubric_level`, `deviation_reason`, `counterfactuals`, `robustness`,
  `deception_report_ids`, `insufficient_evidence`, `critic_notes`. Do not adopt the notes' separate
  `Assessment` model.
- **In plain words:** the report card gets a few extra boxes: "why it differs from the rule", "what
  would change the answer", "how sure we are".

### 8.5 Deception-aware wording
- **Current state:** Missing.
- **Why:** in the demo, the sentence "an official report claims this is a friendly supply vehicle
  approaching, but our tracks show no vehicle moving there — treated as a deception indicator" is the
  highlight (`img_006673`, `img_000926`, and REP-120 on the golden frame).
- **Difficulty:** Easy.
- **Technical:** a dedicated template sentence (TR/EN in `fallback_templates.py`) and a rule in
  `brief_v1.md`: mention every deception indicator with the report and track IDs. The guard checks that
  it is mentioned.
- **In plain words:** when the system catches a misleading message, it says so clearly and shows the
  proof.

---

## 9. Beyond one frame

### 9.1 Day board (40 frames, priority list, heat map)
- **Current state:** Missing (PLAN P4: batch precompute, overview dashboard).
- **Why:** operational value. The operator sees which 4–10 frames need attention now instead of opening
  40 photos.
- **Difficulty:** Medium.
- **Technical:** run the pipeline on all frames (≤ 4 concurrent LLM calls, cached). Sort by level, then
  ring, then ETA. Show an 8 × 5 sector × ring heat map, cross-frame notes (1.8), and a short shift brief.
- **In plain words:** one screen that ranks the whole day's photos by urgency.

### 9.2 Analyst chat tools
- **Current state:** Missing (`agent/tools.py` and `chat_agent.py` are placeholders, P4).
- **Why:** agent autonomy is showcased here (operator follow-up questions), per AGENT_DESIGN §2.
- **Difficulty:** Medium.
- **Technical:** reuse the tool I/O design in `schemas.py` as read-only tools over a finished analysis
  (track, motion, reports, risk queries), converted to `DomainModel` + `Literal` style. At most 6 tool
  calls per turn.
- **In plain words:** the operator can ask "why is this truck high risk?" and get an answer backed by
  the same data.

### 9.3 Live step events and overlays
- **Current state:** Partial. Steps are recorded as `StepResult` with a summary and data. The SSE event
  models exist, but `POST /analyses` runs synchronously (SSE streaming is P2).
- **Why:** watching the reasoning step by step is the core of the demo.
- **Difficulty:** Medium.
- **Technical:** implement SSE per AGENT_DESIGN §5 with the 8 existing step names. Re-detect, guard and
  critic are reported inside the relevant step's `data` / warnings, or as one new event type if needed
  (public contract change → plan first). Put the drawing data (boxes, orphan points, route) into
  `StepResult.data` for the UI overlays.
- **In plain words:** the screen shows each step as it happens, with the boxes and routes drawn live.

---

## X. Dropped or deferred

| Item from the design notes | Status | Reason |
|---|---|---|
| LLM tool-calling loop drives all steps | Dropped | Decision: pipeline only (reproducibility, cost, latency) |
| BELIRSIZ as a 5th level | Dropped | Decision: flag + `VERIFY` (7.4) |
| Changing the zone assignment to bearing sectors | Dropped | Measured 40/40 agreement; sector/ring added only as information (1.4) |
| GLM vision "second look" (`VISION_SECOND_LOOK`) | Dropped | Already dropped in the notes; the image model runs only in `detect` |
| Kalman / CPA-TCPA projection | Dropped | Stop-and-go motion makes constant-velocity projection unreliable; ETA range instead (5.6) |
| `E12` evidence IDs and the separate blackboard store | Dropped | Keep `DET-/TRK-/REP-` IDs and the `Analysis` object (F1) |
| Turkish identifiers, prompts and descriptions in `schemas.py` / `prompts.py` | To translate | Repo rule: code and prompts in English |
| Camera re-sighting, tracker lifecycle, watcher dispatch | Deferred | PLAN §10 backlog |

---

## Suggested build order

Dependencies first, demo correctness before breadth:

1. **5.1 → 5.2 → 5.3 → 5.8**: motion features.
2. **7.2 + 7.1**: rubric on motion evidence. Target: the four candidates ranked first, a sane level
   distribution.
3. **6.1, 6.4, 6.5, 7.3, 8.5**: the deception chain end to end, with the F5 scenario tests.
4. **F3 → 6.10 → 8.1 → 8.2 → 8.3**: the LLM path with the guard and the critic.
5. **1.x, 4.3–4.4, 7.4–7.6, 8.4**: explanations and uncertainty.
6. **2.x**: detector improvements (2.2 early if the model choice is still open).
7. **9.x**: day board, chat.

After every step: golden test green, `gen-types` when a domain model changed, AGENT_DESIGN updated for
every policy change.
