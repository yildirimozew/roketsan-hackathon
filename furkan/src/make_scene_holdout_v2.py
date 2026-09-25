"""Build splits/scene_holdout_v2: v1's scene groups, re-selected to match the test set per stratum.

v1 matched the test resolution mix but also forced the global class mix to equal train's, which
pulled low-bus 1400x788 scenes into validation. v2 keeps v1's scene groups unchanged and picks
1,295 validation images so that every resolution x {dark, light} stratum gets its test share,
and inside each stratum the validation images mirror the labelled pool's class, density and
object-scale mix. No global class-share constraint is imposed.

Writes splits/scene_holdout_v2/{train.txt, val.txt, groups.csv, val_strata.csv, metadata.json, README.md}.
Image features are cached in furkan/outputs/cache/ (gitignored); pass --recompute to rebuild.

Usage: python furkan/src/make_scene_holdout_v2.py   (from the repo root; needs pulp<3.1 for bundled CBC)
"""
import argparse
import hashlib
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pulp
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
V1 = ROOT / "splits/scene_holdout_v1"
OUT = ROOT / "splits/scene_holdout_v2"
CACHE = ROOT / "furkan/outputs/cache/image_features_v2.csv"

CLASSES = ["car", "van", "truck", "bus"]
SEED = 42
N_VAL = 1295
DARK_THRESHOLD = 55
TIME_LIMIT = 120
BANDS = [0.03, 0.06]
MAX_VAL_FRACTION = 0.5  # no stratum may give more than half its labelled images to validation
DENSITY_BINS = [("density_0", 0, 0), ("density_1_10", 1, 10), ("density_11_30", 11, 30),
                ("density_31_60", 31, 60), ("density_61_plus", 61, 10**9)]
AREA_BINS = ["median_area_q1", "median_area_q2", "median_area_q3", "median_area_q4"]
FEATURES = ([f"boxes_{c}" for c in CLASSES] + [f"has_{c}" for c in CLASSES] + ["background"]
            + [b[0] for b in DENSITY_BINS] + AREA_BINS)
V1_DARK = {"train": 666, "validation": 251, "test": 411}
FOCUS = "1400x788"


# ---------------------------------------------------------------- image features

def image_features(path):
    raw = Path(path).read_bytes()
    with Image.open(path) as im:
        w, h = im.size
        gray = im.convert("L")
    brightness = float(np.asarray(gray.resize((64, 64), Image.BILINEAR), dtype=np.float64).mean())
    d = np.asarray(gray.resize((9, 8), Image.LANCZOS), dtype=np.int16)  # 9x8 -> 8x8 = 64 bits
    bits = (d[:, 1:] > d[:, :-1]).flatten()
    dhash = int.from_bytes(np.packbits(bits).tobytes(), "big")
    return Path(path).stem, w, h, brightness, f"{dhash:016x}", hashlib.sha1(raw).hexdigest()


def load_features(recompute):
    if CACHE.exists() and not recompute:
        return pd.read_csv(CACHE, dtype={"dhash": str, "sha1": str})
    paths = [(p, "train") for p in sorted((DATA / "train/images").glob("*.jpg"))]
    paths += [(p, "test") for p in sorted((DATA / "test/images").glob("*.jpg"))]
    print(f"computing features for {len(paths)} images ...")
    with ProcessPoolExecutor() as ex:
        rows = list(ex.map(image_features, [str(p) for p, _ in paths], chunksize=32))
    df = pd.DataFrame(rows, columns=["image_id", "width", "height", "brightness", "dhash", "sha1"])
    df.insert(1, "source", [s for _, s in paths])
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CACHE, index=False)
    return df


def add_strata(df):
    df["resolution"] = df.width.astype(str) + "x" + df.height.astype(str)
    df["is_dark"] = (df.brightness < DARK_THRESHOLD).astype(int)
    df["stratum"] = df.resolution + np.where(df.is_dark == 1, "_dark", "_light")
    return df


# ---------------------------------------------------------------- labels

def load_annotations():
    raw = pd.read_csv(DATA / "train/annotations.csv")
    ann = raw.drop_duplicates().copy()
    n_dup = len(raw) - len(ann)
    assert n_dup == 1, f"expected 1 exact duplicate annotation row, found {n_dup}"
    assert set(ann.label) <= set(CLASSES), "unknown label"
    ann["area"] = ann.w * ann.h
    return ann, n_dup


def image_label_table(ids, ann):
    img = pd.DataFrame(index=pd.Index(ids, name="image_id"))
    counts = ann.groupby(["image_id", "label"]).size().unstack(fill_value=0)
    for c in CLASSES:
        img[f"boxes_{c}"] = counts[c].reindex(ids, fill_value=0) if c in counts else 0
        img[f"has_{c}"] = (img[f"boxes_{c}"] > 0).astype(int)
    img["n_boxes"] = img[[f"boxes_{c}" for c in CLASSES]].sum(axis=1)
    img["background"] = (img.n_boxes == 0).astype(int)
    for name, lo, hi in DENSITY_BINS:
        img[name] = img.n_boxes.between(lo, hi).astype(int)
    img["median_area"] = ann.groupby("image_id").area.median().reindex(ids)
    quartiles = np.quantile(img.median_area.dropna(), [0.25, 0.5, 0.75])
    area_bin = np.searchsorted(quartiles, img.median_area, side="left")  # (-inf,q1], (q1,q2], ...
    for k, name in enumerate(AREA_BINS):
        img[name] = ((area_bin == k) & img.median_area.notna()).astype(int)
    return img, quartiles


# ---------------------------------------------------------------- MILP

def capped_targets(p_test, n_pool):
    """T_s = 1295 * p_test(s), capped at MAX_VAL_FRACTION * N_s; the excess goes to uncapped test strata."""
    target = N_VAL * p_test.astype(float)
    cap = np.floor(MAX_VAL_FRACTION * n_pool).astype(float)
    capped = pd.Series(False, index=target.index)
    while True:
        over = (target > cap + 1e-9) & ~capped
        if not over.any():
            return target, cap, capped
        capped |= over
        target[capped] = cap[capped]
        free = ~capped & (p_test > 0)
        target[free] = (N_VAL - target[capped].sum()) * p_test[free] / p_test[free].sum()


def solve(img, strata, band):
    groups = sorted(img.scene_group.unique())
    x = {g: pulp.LpVariable(f"x_{i}", cat="Binary") for i, g in enumerate(groups)}
    prob = pulp.LpProblem("scene_holdout_v2", pulp.LpMinimize)
    size = img.groupby("scene_group").size()
    prob += pulp.lpSum(int(size[g]) * x[g] for g in groups) == N_VAL

    agg = img.assign(one=1).groupby(["stratum", "scene_group"])[["one"] + FEATURES].sum()
    terms, k = [], 0
    for s, row in strata.iterrows():
        if row.N == 0:
            continue
        part, t = agg.loc[s], row["T"]
        if t == 0:
            for g in part.index:
                prob += x[g] == 0
            continue
        count = pulp.lpSum(int(part.one[g]) * x[g] for g in part.index)
        tol = max(3, math.ceil(band * t))
        prob += count <= min(t + tol, row.cap)
        prob += count >= t - tol
        for f in FEATURES:
            target = row[f"pool_{f}"] * t / row.N
            expr = pulp.lpSum(int(v) * x[g] for g, v in part[f].items() if v)
            d = pulp.LpVariable(f"d_{k}", lowBound=0)
            k += 1
            prob += d >= expr - target
            prob += d >= target - expr
            terms.append(d * (1.0 / max(target, 1.0)))
    prob += pulp.lpSum(terms)

    # no `threads` flag: the bundled Windows CBC 2.10.3 deadlocks after its first incumbent with
    # "-threads 1"; its default (threads 0) is already non-parallel
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=TIME_LIMIT,
                               options=[f"randomSeed {SEED}", f"randomCbcSeed {SEED}"])
    t0 = time.time()
    prob.solve(solver)
    elapsed = time.time() - t0
    info = {
        "status": pulp.LpStatus[prob.status],
        "solution_status": pulp.LpSolution[prob.sol_status],
        "objective": None if prob.objective.value() is None else round(float(prob.objective.value()), 6),
        "seconds": round(elapsed, 1),
        "time_limit_seconds": TIME_LIMIT,
        "binary_group_variables": len(groups),
        "deviation_variables": k,
        "tolerance_band": band,
    }
    ok = prob.sol_status in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible)
    # pulp reports "Optimal" even when CBC stops on the time limit with an incumbent
    info["summary"] = ("infeasible" if not ok else
                       "integer-feasible incumbent at time limit (optimality not proven); all hard constraints satisfied"
                       if elapsed >= TIME_LIMIT - 1 else "optimal")
    if not ok or any(v.value() is None for v in x.values()):
        return None, info
    return {g for g in groups if x[g].value() > 0.5}, info


# ---------------------------------------------------------------- reporting helpers

def split_stats(ids, img, ann):
    sub, a = img.loc[ids], ann[ann.image_id.isin(ids)]
    counts = a.label.value_counts()
    return {
        "annotation_box_counts": {c: int(counts.get(c, 0)) for c in sorted(CLASSES)},
        "annotation_class_shares": {c: round(counts.get(c, 0) / len(a), 6) for c in sorted(CLASSES)},
        "annotations": int(len(a)),
        "box_area_percentiles": {f"p{p}": float(np.percentile(a.area, p)) for p in (10, 50, 90)},
        "dark_images_below_55": int(sub.is_dark.sum()),
        "image_class_presence": {"background": int(sub.background.sum()),
                                 **{c: int(sub[f"has_{c}"].sum()) for c in sorted(CLASSES)}},
        "images": int(len(sub)),
        "mean_brightness": round(float(sub.brightness.mean()), 4),
        "objects_per_image_percentiles": {f"p{p}": float(np.percentile(sub.n_boxes, p))
                                          for p in (0, 10, 25, 50, 75, 90, 99, 100)},
        "resolution_counts": dict(sorted(sub.resolution.value_counts().astype(int).items())),
    }


def box_shares(sub, weight=None):
    boxes = sub[[f"boxes_{c}" for c in CLASSES]]
    if weight is not None:
        boxes = boxes.mul(weight.reindex(sub.index), axis=0)
    boxes = boxes.sum()
    total = boxes.sum()
    return {c: (round(float(boxes[f"boxes_{c}"] / total), 4) if total else None) for c in CLASSES}


def summary_row(sub, labelled=True, weight=None):
    """Distribution summary; with `weight` (per image) every share and mean is importance-weighted."""
    w = pd.Series(1.0, index=sub.index) if weight is None else weight.reindex(sub.index)
    focus = sub.resolution == FOCUS
    shares = w.groupby(sub.stratum).sum() / w.sum()
    row = {
        "images": int(len(sub)),
        "stratum_shares": {s: round(float(v), 4) for s, v in shares.sort_index().items()},
        "mean_brightness": round(float((sub.brightness * w).sum() / w.sum()), 2),
        f"{FOCUS}_dark_rate": round(float((sub.is_dark * w)[focus].sum() / w[focus].sum()), 4) if focus.any() else None,
    }
    if labelled:
        row["global_box_class_shares"] = box_shares(sub, weight)
        row[f"{FOCUS}_bus_box_share"] = box_shares(sub[focus], weight)["bus"] if focus.any() else None
    return row


def hamming_pairs(a_hex, b_hex, threshold=4):
    a = np.array([int(h, 16) for h in a_hex], dtype=np.uint64)
    b = np.array([int(h, 16) for h in b_hex], dtype=np.uint64)
    pairs, a_hit, b_hit = 0, np.zeros(len(a), bool), np.zeros(len(b), bool)
    for i in range(0, len(a), 512):
        close = np.bitwise_count(a[i:i + 512, None] ^ b[None, :]) <= threshold
        pairs += int(close.sum())
        a_hit[i:i + 512] |= close.any(axis=1)
        b_hit |= close.any(axis=0)
    return {"pairs": pairs, "first_split_images": int(a_hit.sum()), "second_split_images": int(b_hit.sum())}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pct(v):
    return "–" if v is None else f"{100 * v:.1f}%"


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--recompute", action="store_true", help="recompute cached image features")
    args = ap.parse_args()
    np.random.seed(SEED)

    groups = pd.read_csv(V1 / "groups.csv")
    feats = add_strata(load_features(args.recompute))
    ann, n_dup = load_annotations()
    train_f = feats[feats.source == "train"].set_index("image_id")
    test = feats[feats.source == "test"].set_index("image_id")
    assert len(train_f) == 6471 and len(test) == 2118, "unexpected image counts in data/"
    assert set(groups.image_id) == set(train_f.index), "groups.csv does not cover data/train/images"

    # 1. groups: v1 scene groups as-is, one native resolution each
    per_group = groups.groupby("scene_group")[["width", "height"]].nunique()
    assert (per_group.max(axis=1) == 1).all(), "a v1 scene group spans several resolutions"
    g = groups.set_index("image_id")
    assert (g.width == train_f.width.reindex(g.index)).all() and \
           (g.height == train_f.height.reindex(g.index)).all(), "groups.csv size differs from image header"

    # 2. brightness sanity check against v1 metadata
    v1_split = g.split
    mine = {"train": int(train_f.is_dark[v1_split[v1_split == "train"].index].sum()),
            "validation": int(train_f.is_dark[v1_split[v1_split == "val"].index].sum()),
            "test": int(test.is_dark.sum())}
    brightness_check = {k: {"v1": V1_DARK[k], "recomputed": mine[k],
                            "relative_difference": round(abs(mine[k] - V1_DARK[k]) / V1_DARK[k], 4)}
                        for k in V1_DARK}
    print("dark-image check (v1 vs recomputed):", {k: (v["v1"], v["recomputed"]) for k, v in brightness_check.items()})
    if any(v["relative_difference"] > 0.03 for v in brightness_check.values()):
        raise SystemExit("STOP: recomputed dark counts differ from v1 metadata by more than 3%")

    labels, area_quartiles = image_label_table(sorted(train_f.index), ann)
    img = labels.join(train_f[["width", "height", "brightness", "dhash", "sha1", "resolution", "is_dark", "stratum"]])
    img = img.join(g[["scene_group", "split"]].rename(columns={"split": "split_v1"}))
    assert int(img.n_boxes.sum()) == 165348 and int(img.background.sum()) == 290

    # 3. strata and test-derived targets
    p_test = test.stratum.value_counts(normalize=True)
    names = sorted(set(img.stratum) | set(test.stratum))
    strata = pd.DataFrame(index=pd.Index(names, name="stratum"))
    strata["p_test"] = p_test.reindex(names, fill_value=0.0)
    strata["test_images"] = test.stratum.value_counts().reindex(names, fill_value=0).astype(int)
    strata["N"] = img.stratum.value_counts().reindex(names, fill_value=0).astype(int)
    strata["T_uncapped"] = N_VAL * strata.p_test
    strata["T"], strata["cap"], strata["capped"] = capped_targets(strata.p_test, strata.N)
    for s in strata.index[strata.capped]:
        print(f"capped {s}: T {strata.T_uncapped[s]:.1f} -> {strata['T'][s]:.1f} (pool {strata.N[s]})")
    pool = img.groupby("stratum")[FEATURES].sum().reindex(names, fill_value=0)
    for f in FEATURES:
        strata[f"pool_{f}"] = pool[f]
    missing = strata[(strata.N == 0) & (strata["T"] > 0)]
    if len(missing):
        print("WARNING: test strata with no labelled images:", list(missing.index))

    # 4. MILP, widening the band once if needed
    val_groups, solver_runs = None, []
    for band in BANDS:
        val_groups, info = solve(img, strata, band)
        solver_runs.append(info)
        print(f"solver (band {band}): {info}")
        if val_groups is not None:
            break
    if val_groups is None:
        raise SystemExit("STOP: no feasible split even with the widened band")
    band = solver_runs[-1]["tolerance_band"]

    img["split_v2"] = np.where(img.scene_group.isin(val_groups), "val", "train")
    val_ids = sorted(img.index[img.split_v2 == "val"])
    train_ids = sorted(img.index[img.split_v2 == "train"])
    val, trn = img.loc[val_ids], img.loc[train_ids]

    # audit: integrity
    crossing = int((img.groupby("scene_group").split_v2.nunique() > 1).sum())
    assert crossing == 0
    assert len(val_ids) == N_VAL and len(set(val_ids) | set(train_ids)) == 6471 and not set(val_ids) & set(train_ids)
    strata["val"] = val.stratum.value_counts().reindex(names, fill_value=0).astype(int)
    strata["tolerance"] = [0 if t == 0 else max(3, math.ceil(band * t)) for t in strata["T"]]
    strata["within_tolerance"] = ((strata.val - strata["T"]).abs() <= strata.tolerance) & (strata.val <= strata.cap)
    assert strata.within_tolerance.all(), "a stratum is outside its tolerance band or cap"

    # stratum importance weights p_test(s) / p_val(s), normalised to mean 1 over validation
    p_val = val.stratum.value_counts(normalize=True)
    weight = val.stratum.map(strata.p_test) / val.stratum.map(p_val)
    weight = weight / weight.mean()

    dup = img[img.duplicated("sha1", keep=False)]
    dup_groups = dup.groupby("sha1").split_v2.nunique()
    exact_dup_crossing = int((dup_groups > 1).sum())
    assert exact_dup_crossing == 0

    # within-stratum class shares: validation vs pool (and v1 validation for reference)
    v1_val = img[img.split_v1 == "val"]
    within = {}
    for s in names:
        if strata.loc[s, "T"] == 0 or strata.loc[s, "N"] == 0:
            continue
        within[s] = {"pool": box_shares(img[img.stratum == s]),
                     "v2_validation": box_shares(val[val.stratum == s]),
                     "v1_validation": box_shares(v1_val[v1_val.stratum == s])}
    within[FOCUS + "_all"] = {"pool": box_shares(img[img.resolution == FOCUS]),
                              "v2_validation": box_shares(val[val.resolution == FOCUS]),
                              "v1_validation": box_shares(v1_val[v1_val.resolution == FOCUS])}

    comparison = {"v1_validation": summary_row(v1_val), "v1_train": summary_row(img[img.split_v1 == "train"]),
                  "v2_validation": summary_row(val), "v2_validation_weighted": summary_row(val, weight=weight),
                  "v2_train": summary_row(trn),
                  "labelled_pool": summary_row(img), "test": summary_row(test, labelled=False)}

    dhash = {"method": "dHash, 9x8 grayscale Lanczos resize, horizontal gradient sign, 64 bits",
             "threshold_hamming": 4, "informational_only": True,
             "v2_train_vs_validation": hamming_pairs(trn.dhash, val.dhash),
             "v1_train_vs_validation": hamming_pairs(img[img.split_v1 == "train"].dhash, v1_val.dhash)}

    # 5. outputs
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "train.txt").write_text("".join(f"{i}\n" for i in train_ids), newline="\n")
    (OUT / "val.txt").write_text("".join(f"{i}\n" for i in val_ids), newline="\n")

    out_groups = groups.copy()
    out_groups["stratum"] = out_groups.image_id.map(img.stratum)
    out_groups["is_dark"] = out_groups.image_id.map(img.is_dark)
    out_groups["brightness"] = out_groups.image_id.map(img.brightness).round(4)
    out_groups["split_v2"] = out_groups.image_id.map(img.split_v2)
    out_groups.to_csv(OUT / "groups.csv", index=False, lineterminator="\n")

    vs = pd.DataFrame({"image_id": val_ids, "resolution": val.resolution.values, "stratum": val.stratum.values,
                       "is_dark": val.is_dark.values, "is_1400x788": (val.resolution == FOCUS).astype(int).values,
                       "is_1400x788_dark": ((val.resolution == FOCUS) & (val.is_dark == 1)).astype(int).values,
                       "scene_group": val.scene_group.values, "weight": weight.round(6).values})
    vs.to_csv(OUT / "val_strata.csv", index=False, lineterminator="\n")

    strata_table = {s: {"test_images": int(r.test_images), "test_share": round(float(r.p_test), 4),
                        "labelled_pool_images": int(r.N), "target_T_uncapped": round(float(r.T_uncapped), 2),
                        "cap": int(r.cap), "capped": bool(r.capped), "target_T": round(float(r["T"]), 2),
                        "validation_images": int(r.val), "validation_share": round(r.val / N_VAL, 4),
                        "tolerance": int(r.tolerance), "within_tolerance": bool(r.within_tolerance)}
                    for s, r in strata.iterrows()}

    v1_meta = json.loads((V1 / "metadata.json").read_text())
    ann_sha = sha256(DATA / "train/annotations.csv")
    files = {n: {"lines": sum(1 for _ in open(OUT / n)) - (1 if n.endswith(".csv") else 0), "sha256": sha256(OUT / n)}
             for n in ["groups.csv", "train.txt", "val.txt", "val_strata.csv"]}
    meta = {
        "annotations_sha256": ann_sha,
        "annotations_sha256_matches_v1": ann_sha == v1_meta["annotations_sha256"],
        "audit": {
            "scene_groups_crossing_train_validation": crossing,
            "exact_duplicate_groups": int(len(dup_groups)),
            "exact_duplicate_groups_crossing_train_validation": exact_dup_crossing,
            "cross_split_cosine_guarantee": ("inherited from v1: scene groups are v1's connected components of the "
                                             "same-resolution cosine >= 0.90 graph and none crosses the split, so every "
                                             "same-resolution train/validation pair has cosine < 0.90 (v1 measured max "
                                             f"{v1_meta['audit']['maximum_same_resolution_cross_split_cosine_similarity']:.4f} "
                                             "over its 50-NN graph)"),
            "train_plus_validation_images": len(train_ids) + len(val_ids),
            "train_validation_intersection": 0,
            "strata_within_tolerance": bool(strata.within_tolerance.all()),
            "brightness_check_against_v1": brightness_check,
            "dhash_near_duplicates": dhash,
        },
        "created_on": date.today().isoformat(),
        "files": files,
        "name": "fixed scene-held-out split v2",
        "purpose": ("Validation split for model selection whose resolution x brightness strata follow the unlabeled "
                    "test set and whose within-stratum class mix follows the labelled pool; supersedes the class-mix "
                    "compromise in v1 for 1400x788."),
        "seed": SEED,
        "strategy": {
            "scene_grouping": {**v1_meta["strategy"]["scene_grouping"],
                               "source": "splits/scene_holdout_v1/groups.csv, used unchanged (no new embeddings or edges)"},
            "selection": {
                "hard_constraints": [
                    "exactly 1,295 validation images",
                    "each scene group wholly train or validation",
                    f"per stratum |val_s - T_s| <= max(3, ceil({band} * T_s)), T_s = 1295 * p_test(s)",
                    f"per stratum val_s <= floor({MAX_VAL_FRACTION} * N_s); a capped stratum gets T_s = cap and its "
                    "excess is redistributed to uncapped test strata in proportion to p_test",
                    "strata absent from test contribute 0 validation images",
                ],
                "method": "mixed-integer group assignment (pulp + CBC 2.10.3, default non-parallel mode)",
                "objective": ("sum over strata s and features f of |val_sf - pool_sf * T_s / N_s| / max(target, 1); "
                              "mixed dark/light groups contribute per image"),
                "solver_status": solver_runs[-1]["summary"],
                "supervised_balance_features": [
                    "per-class box counts", "per-class image presence", "background images",
                    "object-density bins (0, 1-10, 11-30, 31-60, 61+ boxes)",
                    "median-box-area quartile bins (quartiles over all labelled images)",
                ],
                "median_box_area_quartiles": [float(q) for q in area_quartiles],
                "global_class_share_constraint": False,
                "stratification": "native resolution x (64x64 grayscale mean brightness < 55)",
                "test_image_features_used": ["native resolution", "64x64 grayscale mean brightness < 55"],
                "test_labels_used": False,
            },
        },
        "strata": strata_table,
        "within_stratum_class_box_shares": within,
        "solver": {"runs": solver_runs, "final_tolerance_band": band,
                   "band_widened": band != BANDS[0]},
        "tolerance_band": band,
        "comparison": comparison,
        "assumptions": [
            "dark threshold 55 (64x64 grayscale mean) is taken from v1",
            f"the +-{int(band * 100)}% (min 3 images) stratum tolerance exists to keep the MILP feasible under whole-group assignment",
            "the within-stratum class mix of the test set is assumed equal to the labelled pool's; this cannot be verified without test labels",
            (f"no stratum gives more than {int(MAX_VAL_FRACTION * 100)}% of its labelled images to validation, so train keeps "
             "every test domain (without the cap all 224 dark 1400x788 images would go to validation); capped strata are "
             "under-represented in unweighted validation and restored by the val_strata.csv weights"),
            "annotation statistics exclude 1 exact duplicate annotation row (v1 counted it)",
            "CBC stops at a 120 s wall-clock limit, so a rerun on a different machine may return a different incumbent",
        ],
        "train": split_stats(train_ids, img, ann),
        "validation": split_stats(val_ids, img, ann),
        "unlabeled_test_reference": {
            "dark_images_below_55": int(test.is_dark.sum()), "images": int(len(test)), "labels_used": False,
            "mean_brightness": round(float(test.brightness.mean()), 4),
            "resolution_counts": dict(sorted(test.resolution.value_counts().astype(int).items())),
        },
        "validation_fraction": round(N_VAL / 6471, 8),
        "duplicate_annotation_rows_removed": n_dup,
    }
    (OUT / "metadata.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", newline="\n")
    write_readme(meta, strata)
    print_report(meta, strata)


def write_readme(meta, strata):
    c = meta["comparison"]
    cols = [("v1 val", c["v1_validation"]), ("v2 val", c["v2_validation"]),
            ("v2 val weighted", c["v2_validation_weighted"]), ("v2 train", c["v2_train"]),
            ("pool", c["labelled_pool"]), ("test", c["test"])]
    capped = [s for s in strata.index if strata.loc[s, "capped"] and strata.loc[s, "T_uncapped"] > 0]
    cap_text = ", ".join(f"{s} (test target {strata.loc[s, 'T_uncapped']:.0f}, pool {strata.loc[s, 'N']}, "
                         f"val {strata.loc[s, 'val']})" for s in capped) or "none"
    head = "| | " + " | ".join(n for n, _ in cols) + " |\n|---|" + "---:|" * len(cols) + "\n"
    rows = []
    for s in strata.index:
        if strata.loc[s, "test_images"] or strata.loc[s, "val"]:
            rows.append(f"| share {s} | " + " | ".join(pct(r["stratum_shares"].get(s, 0.0)) for _, r in cols) + " |")
    rows.append(f"| {FOCUS} bus box share | " + " | ".join(pct(r.get(f"{FOCUS}_bus_box_share")) for _, r in cols) + " |")
    rows.append(f"| {FOCUS} dark rate | " + " | ".join(pct(r[f"{FOCUS}_dark_rate"]) for _, r in cols) + " |")
    for k in CLASSES:
        rows.append(f"| global {k} box share | " + " | ".join(pct(r.get("global_box_class_shares", {}).get(k)) for _, r in cols) + " |")
    rows.append("| mean brightness | " + " | ".join(f"{r['mean_brightness']:.1f}" for _, r in cols) + " |")
    band = meta["tolerance_band"]
    text = f"""# Scene holdout v2

Fixed 5,176 / 1,295 train/validation split. Use `val.txt` for validation only.
Built by `furkan/src/make_scene_holdout_v2.py` (seed 42); `metadata.json` holds the full audit.

## Why v2

v1 matched the test resolution mix but also forced the global class mix to equal train's. The two
goals conflict, so the optimiser filled 1400x788 (44% of test) with low-bus, mostly bright scenes.
v2 matches the test distribution per resolution x brightness stratum and, inside each stratum,
the labelled pool's class mix. The global class mix is whatever that implies (bus rises).

## Method

1. **Groups.** v1's 4,891 scene groups (ResNet-18 cosine >= 0.90, same resolution, connected
   components) are reused unchanged; each group is wholly train or validation.
2. **Brightness.** 64x64 grayscale mean; dark = brightness < 55, as in v1 (dark counts reproduce v1's).
3. **Strata.** native resolution x {{dark, light}}. Target T_s = 1295 * p_test(s) from unlabeled test
   images; strata absent from test get 0 validation images. No stratum may give more than
   {int(MAX_VAL_FRACTION * 100)}% of its labelled images to validation, so train keeps every test domain; a capped
   stratum's excess target goes to the other test strata in proportion to p_test.
   Capped: {cap_text}.
4. **Selection.** Binary MILP over groups (pulp + CBC, 120 s): exactly 1,295 images,
   |val_s - T_s| <= max(3, ceil({band} * T_s)) and val_s <= cap_s, minimising the normalised deviation from
   pool_sf * T_s / N_s for per-class boxes, per-class presence, background, density bins and
   median-box-area quartile bins. No global class-share constraint.
5. **Audit.** Zero group crossings, exact image partition, every stratum within tolerance,
   exact-duplicate images on one side; dHash near-duplicates reported for information only.

## v1 / v2 / test

{head}{chr(10).join(rows)}

"v2 val weighted" applies the `val_strata.csv` weights. `val_strata.csv` gives each validation
image's stratum flags and an importance weight p_test(s) / p_val(s) (mean 1): about 2 for the capped
1400x788_dark stratum and about 0.9 elsewhere. Report the weighted score, or per-stratum scores, next to
plain mAP, because unweighted v2 validation under-represents dark 1400x788 (8.6% vs 17.9% of test).
`groups.csv` extends v1's file with `stratum`, `is_dark`, `brightness`, `split_v2`
(its `split` column is v1's assignment).

Assumption: the test set's class mix inside each stratum equals the labelled pool's; this cannot be
checked without test labels.
"""
    (OUT / "README.md").write_text(text, newline="\n")


def print_report(meta, strata):
    print("\nstrata (T_s, val, test share, val share, tol):")
    for s, r in strata.iterrows():
        if r.test_images or r.val:
            print(f"  {s:18s} T={r['T']:7.1f} val={r.val:4d} test={r.p_test:.3f} val={r.val / N_VAL:.3f} "
                  f"tol={r.tolerance} ok={r.within_tolerance}")
    print("\nwithin-stratum bus box share (pool / v2 val / v1 val):")
    for s, v in meta["within_stratum_class_box_shares"].items():
        print(f"  {s:18s} {pct(v['pool']['bus'])} / {pct(v['v2_validation']['bus'])} / {pct(v['v1_validation']['bus'])}")
    c = meta["comparison"]
    for k in ["v1_validation", "v2_validation", "v2_validation_weighted", "v2_train", "labelled_pool", "test"]:
        r = c[k]
        print(f"\n{k}: brightness {r['mean_brightness']}, {FOCUS} dark {pct(r[f'{FOCUS}_dark_rate'])}, "
              f"{FOCUS} bus {pct(r.get(f'{FOCUS}_bus_box_share'))}, global {r.get('global_box_class_shares')}")
    print("\naudit:", json.dumps({k: v for k, v in meta["audit"].items() if k != "cross_split_cosine_guarantee"}, indent=1))
    print("solver:", meta["solver"])


if __name__ == "__main__":
    main()
