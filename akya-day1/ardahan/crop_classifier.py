"""Car/van crop classifier as a re-scoring step on RF-DETR boxes (fold 1 predictions).

Why: on RF-DETR's fold-1 val, 35% of ground-truth vans are found but labelled car, and only 9% are missed
(ardahan/confusion.py). A classifier that relabels found boxes can only fix the first kind.

Split: splits/scene_holdout_v2 only (v1 is retired). The detector predictions are fold-1 val, so every set is
cut from fold 1 (scene groups from splits/scene_holdout_v2/groups.csv; no scene is on two sides):
  clf    fold-1 train & v2 train, minus images sharing a scene with `sweep`: the classifier's training crops
  sweep  fold-1 val & v2 train: picks crop size, head C, epoch, blend weight w and gate g
  report fold-1 val & v2 val: scored once, before vs after, in the v2 format: plain mAP, val_strata.csv-weighted
         mAP, and mAP on the 1400x788 and 1400x788-dark subsets. The detector was trained on fold-1 train, which
         holds other v2-val images, some of them scene-mates of report images; that favours the detector.

Classifier: timm convnext_tiny.in12k_ft_in1k, frozen (head-only), global-pooled features -> multinomial logistic
regression over the 4 classes. Crops are square, side = MARGIN x max(w, h) around the box centre, zero-padded.

Re-scoring: RF-DETR scores each box once per class, so a car row and a van row at IoU >= TWIN_IOU are one box.
For a box with car/van scores (s_car, s_van) (0 when a twin is absent) and total t = s_car + s_van >= g:
  d = (s_car, s_van) / t            detector's car/van split
  q = classifier (p_car, p_van) renormalised over the two
  new s_c = t * ((1 - w) d_c + w q_c)   for c in {car, van}, clipped to 1
w = 0 reproduces the detector exactly (checked). A box gains a row for the other class when w > 0; each image is
then re-capped to its top 1000 rows. Truck and bus rows are never touched.

Usage:
  python ardahan/crop_classifier.py gt-feats      # GT crop features at 96 and 128 px for clf/sweep/report
  python ardahan/crop_classifier.py head          # fit head, pick size and C on sweep, car-vs-van metrics
  python ardahan/crop_classifier.py det-feats     # features for detector car/van boxes (t >= 0.01) on fold-1 val
  python ardahan/crop_classifier.py finetune      # only if head-only loses to the detector: full fine-tune,
                                                  # then class probabilities for the same detector boxes
  python ardahan/crop_classifier.py rescore --model head|ft   # sweep w, g on sweep; before/after AP on report
  python ardahan/crop_classifier.py apply --preds P.csv --images splits/scene_holdout_v2/val.txt --name NAME
      # another detector: car/van and all-4-class re-scoring, w cross-fitted over scene halves of the manifest
  python ardahan/crop_classifier.py submit --views V1.csv [V2.csv ...] --w 0.5 --out submission.csv
      # test: WBF of the views, re-scoring with a fixed w, submission.csv checked by check_submission.py
"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ardahan"))
from confusion import iou  # noqa: E402
from evaluate import CLASSES, evaluate  # noqa: E402
from leakage_map import PerImage  # noqa: E402

SPLIT = ROOT / "splits/scene_holdout_v2"
OUT = ROOT / "ardahan/outputs/crop_clf_v2"
PREDS = ROOT / "ardahan/outputs/wbf/rfdetr_val_fold1_cap1000.csv"
ARCH = "convnext_tiny.in12k_ft_in1k"
MARGIN = 1.3          # 15% context on each side of the longer box edge
SIZES = (96, 128)
TWIN_IOU = 0.8
MIN_T = 0.01          # detector boxes below this total car+van score are never re-scored (lowest gate swept)
CAP = 1000


def ids(path):
    return set((ROOT / path).read_text().split())


def image_sets():
    g = pd.read_csv(SPLIT / "groups.csv")
    grp = dict(zip(g.image_id, g.scene_group))
    sht, shv = ids(SPLIT / "train.txt"), ids(SPLIT / "val.txt")
    assert sht == set(g.image_id[g.split_v2 == "train"]) and shv == set(g.image_id[g.split_v2 == "val"])
    f1t, f1v = ids("splits/folds/fold_1_train.txt"), ids("splits/folds/fold_1_val.txt")
    sweep, report = sht & f1v, shv & f1v
    sweep_groups = {grp[i] for i in sweep}
    clf = {i for i in sht & f1t if grp[i] not in sweep_groups}
    assert not ({grp[i] for i in clf} & {grp[i] for i in report}) and not ({grp[i] for i in clf} & sweep_groups)
    return {"clf": sorted(clf), "sweep": sorted(sweep), "report": sorted(report)}, grp


_PATHS = {}


def image_path(iid):
    if not _PATHS:                                     # train and test image ids do not overlap
        for split in ("train", "test"):
            _PATHS.update({p.stem: p for p in (ROOT / f"data/{split}/images").iterdir()})
    return _PATHS[iid]


class Extractor:
    def __init__(self):
        import timm
        self.m = timm.create_model(ARCH, pretrained=True, num_classes=0).eval().cuda().half()
        cfg = self.m.pretrained_cfg
        self.mean = torch.tensor(cfg["mean"], device="cuda").view(1, 3, 1, 1).half()
        self.std = torch.tensor(cfg["std"], device="cuda").view(1, 3, 1, 1).half()

    @torch.no_grad()
    def __call__(self, crops):  # uint8 (n, s, s, 3)
        x = torch.from_numpy(crops).cuda().permute(0, 3, 1, 2).half().div_(255)
        return self.m((x - self.mean) / self.std).float().cpu().numpy()


def crops_for_image(iid, boxes, sizes, margin=MARGIN):
    """boxes: (n, 4) xywh -> {size: uint8 (n, size, size, 3)}"""
    im = Image.open(image_path(iid)).convert("RGB")
    out = {s: np.empty((len(boxes), s, s, 3), np.uint8) for s in sizes}
    for k, (x, y, w, h) in enumerate(boxes):
        cx, cy, side = x + w / 2, y + h / 2, margin * max(w, h, 1.0)
        c = im.crop((round(cx - side / 2), round(cy - side / 2), round(cx + side / 2), round(cy + side / 2)))
        for s in sizes:
            out[s][k] = np.asarray(c.resize((s, s), Image.BICUBIC))
    return out


def extract(table, sizes, batch=512, fn=None, dim=None, margin=MARGIN, dtype=np.float16):
    """table: image_id,x,y,w,h (row order kept) -> {size: fn(crops) per row}; default fn: frozen features."""
    if fn is None:
        ex = Extractor()
        fn, dim = ex, ex.m.num_features
    groups = list(table.groupby("image_id", sort=False).indices.items())
    feats = {s: np.zeros((len(table), *np.atleast_1d(dim)), dtype) for s in sizes}
    box = table[["x", "y", "w", "h"]].to_numpy(float)
    pend_idx, pend = [], {s: [] for s in sizes}

    def flush():
        if not pend_idx:
            return
        idx = np.concatenate(pend_idx)
        for s in sizes:
            arr = np.concatenate(pend[s])
            for a in range(0, len(arr), batch):
                feats[s][idx[a:a + batch]] = fn(arr[a:a + batch])
            pend[s].clear()
        pend_idx.clear()

    with ThreadPoolExecutor(8) as pool:
        work = pool.map(lambda g: (g[1], crops_for_image(g[0], box[g[1]], sizes, margin)), groups)
        n = 0
        for k, (idx, cr) in enumerate(work):
            pend_idx.append(idx)
            for s in sizes:
                pend[s].append(cr[s])
            n += len(idx)
            if n >= 8 * batch:
                flush()
                n = 0
            if k % 200 == 0:
                print(f"  {k}/{len(groups)} images", flush=True)
        flush()
    return feats


# ---------------------------------------------------------------- GT crops and the head

def cmd_gt_feats(_):
    sets, _ = image_sets()
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    OUT.mkdir(parents=True, exist_ok=True)
    for name, iids in sets.items():
        t = gt[gt.image_id.isin(set(iids))].reset_index(drop=True)
        print(f"{name}: {len(iids)} images, {len(t)} boxes {t.label.value_counts().to_dict()}", flush=True)
        f = extract(t, SIZES)
        t.to_csv(OUT / f"gt_{name}.csv", index=False)
        for s in SIZES:
            np.save(OUT / f"gt_{name}_{s}.npy", f[s])


def load_gt(name, s):
    return pd.read_csv(OUT / f"gt_{name}.csv"), np.load(OUT / f"gt_{name}_{s}.npy").astype(np.float32)


def carvan_metrics(y, P):
    """y: labels, P: (n, 4) probs. Car-vs-van on the car and van ground truth, van prob renormalised."""
    m = np.isin(y, ["car", "van"])
    pv = P[m, 1] / (P[m, 0] + P[m, 1])
    yv = (y[m] == "van").astype(float)
    from sklearn.metrics import roc_auc_score
    ll = -np.mean(yv * np.log(np.clip(pv, 1e-7, 1)) + (1 - yv) * np.log(np.clip(1 - pv, 1e-7, 1)))
    pred_van = pv >= 0.5
    return {"n_car": int((yv == 0).sum()), "n_van": int(yv.sum()), "logloss": ll, "auc": roc_auc_score(yv, pv),
            "van_recall": pred_van[yv == 1].mean(), "car_recall": (~pred_van)[yv == 0].mean(),
            "van_as_car": int((~pred_van & (yv == 1)).sum()), "car_as_van": int((pred_van & (yv == 0)).sum())}


def fit_head(X, y, C):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), LogisticRegression(C=C, max_iter=2000)).fit(X, y)


def probs(head, X):
    P = head.predict_proba(X)
    return P[:, [list(head.classes_).index(c) for c in CLASSES]]


def cmd_head(_):
    from sklearn.metrics import log_loss
    rows, best = [], None
    for s in SIZES:
        tr, Xtr = load_gt("clf", s)
        sw, Xsw = load_gt("sweep", s)
        for C in (0.01, 0.1, 1.0):
            h = fit_head(Xtr, tr.label.to_numpy(), C)
            P = probs(h, Xsw)
            r = {"size": s, "C": C, "logloss4": log_loss(sw.label, P[:, np.argsort(CLASSES)], labels=sorted(CLASSES)),
                 "acc4": float((np.array(CLASSES)[P.argmax(1)] == sw.label).mean()),
                 **carvan_metrics(sw.label.to_numpy(), P)}
            rows.append(r)
            print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
            if best is None or r["logloss"] < best[0]["logloss"]:
                best = (r, h)
    r, h = best
    print(f"\nchosen on sweep (car-vs-van logloss): size {r['size']}, C {r['C']}")
    import joblib
    joblib.dump({"head": h, "size": r["size"], "C": r["C"]}, OUT / "head.joblib")
    pd.DataFrame(rows).to_csv(OUT / "head_sweep.csv", index=False)
    rep, Xrep = load_gt("report", r["size"])
    m = carvan_metrics(rep.label.to_numpy(), probs(h, Xrep))
    print("report GT crops, car vs van:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in m.items()})
    json.dump({"chosen": r, "report_gt_carvan": m}, open(OUT / "head_summary.json", "w"), indent=1, default=float)


# ---------------------------------------------------------------- detector boxes

def pair_twins(p):
    """Car/van rows of one image's predictions -> boxes: rows (car_idx or -1, van_idx or -1)."""
    c = p.index[p.label == "car"].to_numpy()
    v = p.index[p.label == "van"].to_numpy()
    pairs, used_v = [], np.zeros(len(v), bool)
    if len(c) and len(v):
        M = iou(p.loc[c, ["x", "y", "w", "h"]].to_numpy(float), p.loc[v, ["x", "y", "w", "h"]].to_numpy(float))
        cand = np.argwhere(M >= TWIN_IOU)
        cand = cand[np.argsort(-M[cand[:, 0], cand[:, 1]], kind="stable")]
        used_c = np.zeros(len(c), bool)
        for i, j in cand:
            if not used_c[i] and not used_v[j]:
                used_c[i] = used_v[j] = True
                pairs.append((c[i], v[j]))
        pairs += [(c[i], -1) for i in np.where(~used_c)[0]]
    else:
        pairs += [(i, -1) for i in c]
    pairs += [(-1, v[j]) for j in np.where(~used_v)[0]]
    return pairs


def det_boxes(preds):
    """One row per car/van box: image_id, car_row, van_row, s_car, s_van, t, and the box of the stronger row."""
    out = []
    for iid, p in preds[preds.label.isin(["car", "van"])].groupby("image_id"):
        for ci, vi in pair_twins(p):
            sc = preds.at[ci, "conf"] if ci >= 0 else 0.0
            sv = preds.at[vi, "conf"] if vi >= 0 else 0.0
            b = ci if sc >= sv else vi
            out.append((iid, ci, vi, sc, sv, sc + sv, *preds.loc[b, ["x", "y", "w", "h"]]))
    return pd.DataFrame(out, columns=["image_id", "car_row", "van_row", "s_car", "s_van", "t", "x", "y", "w", "h"])


def cmd_det_feats(_):
    import joblib
    size = joblib.load(OUT / "head.joblib")["size"]
    preds = pd.read_csv(PREDS)
    boxes = det_boxes(preds)
    print(f"{len(boxes)} car/van boxes from {len(preds)} rows; twins paired: "
          f"{((boxes.car_row >= 0) & (boxes.van_row >= 0)).sum()}", flush=True)
    boxes["scored"] = boxes.t >= MIN_T
    sel = boxes[boxes.scored]
    print(f"extracting {len(sel)} boxes with t >= {MIN_T} at {size}px", flush=True)
    f = extract(sel.reset_index(drop=True), (size,))[size]
    boxes.to_csv(OUT / "det_boxes.csv", index=False)
    np.save(OUT / f"det_{size}.npy", f)


def rescore(preds, boxes, w, g):
    """preds: original rows; boxes: det_boxes with q_van (NaN where not scored). Returns new prediction rows.
    Each class keeps its own row's box; a class with no row takes its twin's box."""
    b = boxes[(boxes.t >= g) & boxes.q_van.notna()]
    d_van = b.s_van / b.t
    p_van = (1 - w) * d_van + w * b.q_van
    new_van, new_car = np.minimum(b.t * p_van, 1), np.minimum(b.t * (1 - p_van), 1)
    keep = preds.drop(index=np.concatenate([b.car_row[b.car_row >= 0], b.van_row[b.van_row >= 0]]))
    xywh = preds[["x", "y", "w", "h"]].to_numpy()
    car_src = np.where(b.car_row >= 0, b.car_row, b.van_row)
    van_src = np.where(b.van_row >= 0, b.van_row, b.car_row)
    add = pd.concat([pd.DataFrame(xywh[preds.index.get_indexer(src)], columns=["x", "y", "w", "h"])
                     .assign(image_id=b.image_id.to_numpy(), label=lab, conf=conf.to_numpy())
                     for lab, src, conf in (("car", car_src, new_car), ("van", van_src, new_van))])
    add = add[add.conf > 0]
    out = pd.concat([keep, add[keep.columns]], ignore_index=True)
    out = out.sort_values("conf", ascending=False, kind="stable").groupby("image_id").head(CAP)
    return out


def boot(a, b, iids, grp, weights=None, n=2000, seed=0):
    """a, b: PerImage before/after. Point values and a scene-group bootstrap of the per-class AP differences
    (b - a) over the images `iids`, optionally importance-weighted."""
    by = pd.Series(iids).groupby(pd.Series([grp[i] for i in iids])).apply(list).tolist()
    rng = np.random.default_rng(seed)
    cols = CLASSES + ["mAP"]
    ra, rb = a.ap(iids, weights), b.ap(iids, weights)
    d = []
    for _ in range(n):
        sample = [i for k in rng.integers(0, len(by), len(by)) for i in by[k]]
        sa, sb = a.ap(sample, weights), b.ap(sample, weights)
        d.append([sb[c] - sa[c] for c in cols])
    d = pd.DataFrame(d, columns=cols)
    return {c: {"before": ra[c], "after": rb[c], "delta": rb[c] - ra[c],
                "ci": [float(np.nanpercentile(d[c], 2.5)), float(np.nanpercentile(d[c], 97.5))]} for c in cols}


def cmd_rescore(a):
    import joblib
    hd = joblib.load(OUT / "head.joblib")
    size = hd["size"]
    sets, grp = image_sets()
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    preds = pd.read_csv(PREDS)
    boxes = pd.read_csv(OUT / "det_boxes.csv")
    if a.model == "head":
        P = probs(hd["head"], np.load(OUT / f"det_{size}.npy").astype(np.float32))
    else:
        P, size = np.load(OUT / "det_probs_ft.npy"), FT_SIZE
    boxes["q_van"] = np.nan
    boxes.loc[boxes.scored, "q_van"] = P[:, 1] / (P[:, 0] + P[:, 1])

    def score(pr, name):
        return evaluate(gt, pr, sets[name])

    base = {n: score(preds, n) for n in ("sweep", "report")}
    zero = score(rescore(preds, boxes, 0.0, MIN_T), "sweep")
    assert all(abs(zero["AP"][c] - base["sweep"]["AP"][c]) < 1e-6 for c in CLASSES), (zero, base["sweep"])
    print("w = 0 reproduces the detector on sweep: ok")
    print(f"sweep baseline mAP {base['sweep']['mAP50']:.4f}  " +
          "  ".join(f"{c} {v:.4f}" for c, v in base["sweep"]["AP"].items()), flush=True)

    rows = []
    for g in (0.01, 0.02, 0.05, 0.1, 0.25):
        for w in (0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0):
            r = score(rescore(preds, boxes, w, g), "sweep")
            rows.append({"gate": g, "w": w, "mAP": r["mAP50"], **{c: r["AP"][c] for c in CLASSES}})
            print(f"  g {g:<5} w {w:<4} mAP {r['mAP50']:.4f}  car {r['AP']['car']:.4f}  van {r['AP']['van']:.4f}"
                  f"  (d {r['mAP50'] - base['sweep']['mAP50']:+.4f})", flush=True)
    sw = pd.DataFrame(rows)
    sw.to_csv(OUT / f"blend_sweep_{a.model}.csv", index=False)
    best = sw.loc[sw.mAP.idxmax()]
    g, w = float(best.gate), float(best.w)
    print(f"\nchosen on sweep: gate {g}, w {w} (sweep mAP {best.mAP:.4f}, "
          f"{best.mAP - base['sweep']['mAP50']:+.4f})")

    after = rescore(preds, boxes, w, g)
    rep = sets["report"]
    pa, pb = PerImage(gt, preds, rep), PerImage(gt, after, rep)
    ra = score(after, "report")
    assert abs(pb.ap(rep)["mAP"] - ra["mAP50"]) < 1e-6 and abs(pa.ap(rep)["mAP"] - base["report"]["mAP50"]) < 1e-6
    st = pd.read_csv(SPLIT / "val_strata.csv").set_index("image_id").loc[rep]
    views = {"v2 val, unweighted": (rep, None),
             "v2 val, val_strata-weighted": (rep, st.weight.to_dict()),
             "1400x788": (list(st.index[st.is_1400x788 == 1]), None),
             "1400x788 dark": (list(st.index[st.is_1400x788_dark == 1]), None)}
    res = {}
    print(f"\nREPORT (fold-1 val & v2 val, {len(rep)} images, scored once; 95% scene-bootstrap CI on the change)")
    for name, (iids, wts) in views.items():
        r = res[name] = boot(pa, pb, iids, grp, wts, n=a.boot)
        print(f"\n  {name} ({len(iids)} images, {gt.image_id.isin(set(iids)).sum()} boxes)")
        print(f"  {'':6s} {'before':>8s} {'after':>8s} {'change':>8s}  95% CI")
        for c in CLASSES + ["mAP"]:
            x = r[c]
            print(f"  {c:6s} {x['before']:8.4f} {x['after']:8.4f} {x['delta']:+8.4f}  "
                  f"[{x['ci'][0]:+.4f}, {x['ci'][1]:+.4f}]")
        net = r["van"]["delta"] + r["car"]["delta"]
        print(f"  car + van AP change: {net:+.4f} ({'positive' if net > 0 else 'negative'})")
    after.to_csv(OUT / f"rescored_val_fold1_{a.model}.csv", index=False)
    json.dump({"model": a.model, "gate": g, "w": w, "size": size, "C": hd["C"], "report": res,
               "sweep_baseline": base["sweep"], "sweep_best": best.to_dict()},
              open(OUT / f"rescore_summary_{a.model}.json", "w"), indent=1, default=float)


# ---------------------------------------------------------------- fine-tuning (only if head-only underperforms)

FT_SIZE = 128
FT_CACHE_MARGIN, FT_CACHE = 1.6, 160   # training crops cached wider, then jittered back to MARGIN on the GPU
FT_EPOCHS, FT_BATCH, FT_LR = 4, 64, 1e-4


def ft_cache(name, margin, size):
    """GT crops of an image set as a uint8 array on disk (n, size, size, 3), built once, memory-mapped."""
    t = pd.read_csv(OUT / f"gt_{name}.csv")
    path = OUT / f"crops_{name}_{size}_m{margin}.npy"
    if not path.exists():
        tmp = path.with_name(path.stem + "_tmp.npy")
        a = np.lib.format.open_memmap(tmp, "w+", np.uint8, (len(t), size, size, 3))
        box = t[["x", "y", "w", "h"]].to_numpy(float)
        with ThreadPoolExecutor(8) as pool:
            for idx, cr in pool.map(lambda g: (g[1], crops_for_image(g[0], box[g[1]], (size,), margin)[size]),
                                    t.groupby("image_id", sort=False).indices.items()):
                a[idx] = cr
        a.flush()
        del a
        tmp.rename(path)
    return t, np.load(path, mmap_mode="r")


def jitter_rois(n, rng):
    """Random windows (x1, y1, x2, y2) in cache pixels: MARGIN-sized around the box, scale +-15%, shift +-8%."""
    side = FT_CACHE * MARGIN / FT_CACHE_MARGIN * rng.uniform(0.85, 1.15, n)
    c = FT_CACHE / 2 + rng.uniform(-0.08, 0.08, (n, 2)) * side[:, None]
    return np.stack([c[:, 0] - side / 2, c[:, 1] - side / 2, c[:, 0] + side / 2, c[:, 1] + side / 2], 1)


def ft_model():
    import timm
    m = timm.create_model(ARCH, pretrained=True, num_classes=len(CLASSES)).cuda().to(memory_format=torch.channels_last)
    cfg = m.pretrained_cfg
    norm = (torch.tensor(cfg["mean"], device="cuda").view(1, 3, 1, 1),
            torch.tensor(cfg["std"], device="cuda").view(1, 3, 1, 1))
    return m, norm


def ft_predict(m, norm, crops, batch=512):
    m.eval()
    out = []
    with torch.no_grad(), torch.autocast("cuda", torch.float16):
        for a in range(0, len(crops), batch):
            x = torch.from_numpy(np.ascontiguousarray(crops[a:a + batch])).cuda().permute(0, 3, 1, 2).float() / 255
            x = ((x - norm[0]) / norm[1]).contiguous(memory_format=torch.channels_last)
            out.append(torch.softmax(m(x).float(), 1).cpu().numpy())
    return np.concatenate(out)


def cmd_finetune(_):
    import time
    from torchvision.ops import roi_align
    tr, X = ft_cache("clf", FT_CACHE_MARGIN, FT_CACHE)
    sw, Xsw = ft_cache("sweep", MARGIN, FT_SIZE)          # cropped exactly as detector boxes will be
    print(f"crops cached: clf {X.shape}, sweep {Xsw.shape}", flush=True)
    y = torch.tensor([CLASSES.index(c) for c in tr.label], device="cuda")
    m, norm = ft_model()
    head = [p for n, p in m.named_parameters() if n.startswith("head.fc")]
    body = [p for n, p in m.named_parameters() if not n.startswith("head.fc")]
    opt = torch.optim.AdamW([{"params": body, "lr": FT_LR}, {"params": head, "lr": FT_LR * 10}], weight_decay=0.05)
    per_ep = len(tr) // FT_BATCH
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, [FT_LR, FT_LR * 10], total_steps=FT_EPOCHS * per_ep,
                                                pct_start=0.05)
    scaler = torch.amp.GradScaler()
    rng = np.random.default_rng(0)
    best, log = None, []
    for ep in range(FT_EPOCHS):
        m.train()
        order = rng.permutation(len(tr))
        t0, tot = time.time(), 0.0
        for k in range(per_ep):
            idx = np.sort(order[k * FT_BATCH:(k + 1) * FT_BATCH])
            x = torch.from_numpy(X[idx]).cuda().permute(0, 3, 1, 2).float() / 255
            rois = torch.tensor(np.c_[np.arange(len(idx)), jitter_rois(len(idx), rng)], device="cuda",
                                dtype=torch.float)
            x = roi_align(x, rois, FT_SIZE, aligned=True, sampling_ratio=2)
            flip = torch.rand(len(idx), device="cuda") < 0.5
            x[flip] = x[flip].flip(3)
            x = ((x - norm[0]) / norm[1]).contiguous(memory_format=torch.channels_last)
            with torch.autocast("cuda", torch.float16):
                loss = torch.nn.functional.cross_entropy(m(x), y[idx])
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            sched.step()
            tot += loss.item()
            if k % 200 == 0:
                print(f"  ep {ep} step {k}/{per_ep} loss {tot / (k + 1):.4f} {time.time() - t0:.0f}s", flush=True)
        P = ft_predict(m, norm, Xsw)
        r = {"epoch": ep, "train_loss": tot / per_ep, **carvan_metrics(sw.label.to_numpy(), P),
             "acc4": float((np.array(CLASSES)[P.argmax(1)] == sw.label).mean())}
        log.append(r)
        print({k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
        if best is None or r["logloss"] < best:
            best = r["logloss"]
            torch.save(m.state_dict(), OUT / "ft_best.pt")
    pd.DataFrame(log).to_csv(OUT / "ft_log.csv", index=False)
    m.load_state_dict(torch.load(OUT / "ft_best.pt"))
    rep, Xrep = ft_cache("report", MARGIN, FT_SIZE)
    mr = carvan_metrics(rep.label.to_numpy(), ft_predict(m, norm, Xrep))
    print("report GT crops, car vs van:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in mr.items()})
    boxes = pd.read_csv(OUT / "det_boxes.csv")
    sel = boxes[boxes.scored].reset_index(drop=True)
    print(f"predicting {len(sel)} detector boxes", flush=True)
    P = extract(sel, (FT_SIZE,), fn=lambda c: ft_predict(m, norm, c), dim=len(CLASSES), dtype=np.float32)[FT_SIZE]
    np.save(OUT / "det_probs_ft.npy", P)
    json.dump({"log": log, "report_gt_carvan": mr}, open(OUT / "ft_summary.json", "w"), indent=1, default=float)


# ---------------------------------------------------------------- any detector, any class set (apply)

def group_rows(preds, classes):
    """Rows of `classes` -> one group per box: rows of different classes at IoU >= TWIN_IOU with the group's seed
    (its highest-confidence row), at most one row per class. Returns image_id, row_<c> (-1 if absent), s_<c>, t,
    and the seed box."""
    K = len(classes)
    out = []
    sub = preds[preds.label.isin(classes)]
    for iid, p in sub.groupby("image_id"):
        p = p.sort_values("conf", ascending=False, kind="stable")
        idx, lab = p.index.to_numpy(), p.label.map(classes.index).to_numpy()
        conf, box = p.conf.to_numpy(), p[["x", "y", "w", "h"]].to_numpy(float)
        M = iou(box, box)
        seeds, rows = [], []                       # rows[g]: array of K row positions (-1 = none)
        for r in range(len(idx)):
            if seeds:
                cand = M[r, seeds]
                free = np.array([rows[g][lab[r]] < 0 for g in range(len(seeds))])
                cand = np.where(free & (cand >= TWIN_IOU), cand, -1)
                g = int(cand.argmax())
                if cand[g] >= 0:
                    rows[g][lab[r]] = r
                    continue
            seeds.append(r)
            rows.append(np.full(K, -1))
            rows[-1][lab[r]] = r
        for sd, rw in zip(seeds, rows):
            sc = [conf[j] if j >= 0 else 0.0 for j in rw]
            out.append((iid, *[idx[j] if j >= 0 else -1 for j in rw], *sc, sum(sc), *box[sd]))
    return pd.DataFrame(out, columns=["image_id", *[f"row_{c}" for c in classes], *[f"s_{c}" for c in classes],
                                      "t", "x", "y", "w", "h"])


def rescore_groups(preds, groups, Q, classes, w):
    """Q: classifier probabilities over CLASSES for each group (NaN rows = not scored). For a scored group with
    total t over `classes`: new s_c = t * ((1 - w) s_c / t + w q_c), q renormalised over `classes`. Rows of other
    classes are untouched; each image is re-capped to CAP rows. w = 0 returns the input scores bit for bit, and
    ties keep the input's row order (pycocotools breaks score ties by it; YOLO scores are rounded, so ties are common)."""
    ok = ~np.isnan(Q[:, 0])
    g, q = groups[ok], Q[ok][:, [CLASSES.index(c) for c in classes]]
    q = q / q.sum(1, keepdims=True)
    S = g[[f"s_{c}" for c in classes]].to_numpy()
    t = g.t.to_numpy()[:, None]
    new = np.minimum(S + w * (t * q - S), 1)          # = t((1-w) s/t + w q), exact at w = 0
    R = g[[f"row_{c}" for c in classes]].to_numpy()
    xywh = preds[["x", "y", "w", "h"]].to_numpy()
    pos = {r: k for k, r in enumerate(preds.index)}
    seed = g[["x", "y", "w", "h"]].to_numpy()
    keep = preds.drop(index=R[R >= 0]).assign(_src=lambda d: [pos[r] for r in d.index])
    any_row = np.where(R >= 0, R, -1).max(1)           # a class with no row sorts at one of its group's rows
    parts = []
    for k, c in enumerate(classes):
        src = np.where(R[:, k] >= 0, R[:, k], any_row)
        bx = np.where((R[:, k] >= 0)[:, None], xywh[[pos[r] for r in src]], seed)
        parts.append(pd.DataFrame(bx, columns=["x", "y", "w", "h"]).assign(
            image_id=g.image_id.to_numpy(), label=c, conf=new[:, k], _src=[pos[r] for r in src]))
    add = pd.concat(parts)
    add = add[add.conf > 0]
    out = pd.concat([keep, add[keep.columns]], ignore_index=True)
    out = out.sort_values(["conf", "_src"], ascending=[False, True], kind="stable")
    return out.groupby("image_id").head(CAP).drop(columns="_src")


def scene_halves(iids, seed=0):
    """Two halves of `iids` by scene group, alternating within each v2 stratum (so both halves keep the mix)."""
    g = pd.read_csv(SPLIT / "groups.csv").set_index("image_id").loc[iids]
    rng = np.random.default_rng(seed)
    half = {}
    for _, gs in g.groupby("stratum"):
        groups = rng.permutation(np.asarray(gs.scene_group.unique(), dtype=object))
        sizes = gs.groupby("scene_group").size().loc[groups]
        n = [0, 0]
        for sg, sz in sizes.items():                  # greedy: the half with fewer images of this stratum
            h = int(n[1] < n[0])
            half[sg] = h
            n[h] += sz
    out = [[i for i in iids if half[g.scene_group[i]] == h] for h in (0, 1)]
    assert sorted(out[0] + out[1]) == sorted(iids) and not ({g.scene_group[i] for i in out[0]} &
                                                            {g.scene_group[i] for i in out[1]})
    return out


def cmd_apply(a):
    """Re-score another detector's predictions on a manifest: w chosen by 2-fold cross-fitting over scene-group
    halves of the manifest (each half's predictions re-scored with the w picked on the other half), then one
    report in the v2 format on the whole manifest."""
    out = OUT / f"apply_{a.name}"
    out.mkdir(parents=True, exist_ok=True)
    iids = (ROOT / a.images).read_text().split()
    _, grp = image_sets()
    clf_imgs = set(pd.read_csv(OUT / "gt_clf.csv").image_id)
    assert not ({grp[i] for i in clf_imgs} & {grp[i] for i in iids}), "classifier trained on a scene in the manifest"
    gt = pd.read_csv(ROOT / "data/train/annotations.csv")
    preds = pd.read_csv(ROOT / a.preds)
    preds = preds[preds.image_id.isin(set(iids))].reset_index(drop=True)
    print(f"{a.preds}: {len(preds)} rows on {preds.image_id.nunique()}/{len(iids)} images", flush=True)
    from confusion import match
    M = match(gt[gt.image_id.isin(set(iids))], preds, iids, 0.25)
    print("confusion at conf >= 0.25 (row %):")
    print((M.loc[CLASSES].div(M.loc[CLASSES].sum(axis=1), axis=0) * 100).round(1).to_string())

    m = norm = None
    halves = scene_halves(iids)
    print(f"scene halves: {len(halves[0])} / {len(halves[1])} images")
    st = pd.read_csv(SPLIT / "val_strata.csv").set_index("image_id").loc[iids]
    summary = {}
    for tag, classes in (("carvan", ["car", "van"]), ("all4", list(CLASSES))):
        if tag not in a.sets:
            continue
        gpath, qpath = out / f"groups_{tag}.csv", out / f"probs_{tag}.npy"
        if not qpath.exists():
            groups = group_rows(preds, classes)
            groups["scored"] = groups.t >= MIN_T
            sel = groups[groups.scored].reset_index(drop=True)
            print(f"[{tag}] {len(groups)} boxes, classifying {len(sel)} with t >= {MIN_T}", flush=True)
            if m is None:
                m, norm = ft_model()
                m.load_state_dict(torch.load(OUT / "ft_best.pt"))
            P = extract(sel, (FT_SIZE,), fn=lambda c: ft_predict(m, norm, c), dim=len(CLASSES),
                        dtype=np.float32)[FT_SIZE]
            Q = np.full((len(groups), len(CLASSES)), np.nan, np.float32)
            Q[groups.scored.to_numpy()] = P
            groups.to_csv(gpath, index=False)
            np.save(qpath, Q)
        groups, Q = pd.read_csv(gpath), np.load(qpath)
        zero = rescore_groups(preds, groups, Q, classes, 0.0)
        r0, rz = evaluate(gt, preds, iids), evaluate(gt, zero, iids)
        assert all(abs(r0["AP"][c] - rz["AP"][c]) < 1e-6 for c in CLASSES), (r0, rz)
        print(f"\n[{tag}] w = 0 reproduces the detector: ok")

        ws = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
        pick, curve = [], []
        for h in (0, 1):
            ids_h = set(halves[h])
            ph, gh, qh = preds[preds.image_id.isin(ids_h)], groups.image_id.isin(ids_h).to_numpy(), None
            base = evaluate(gt, ph, halves[h])["mAP50"]
            scores = {}
            for w in ws:
                scores[w] = evaluate(gt, rescore_groups(ph, groups[gh], Q[gh], classes, w), halves[h])["mAP50"]
                curve.append({"half": h, "w": w, "mAP": scores[w], "delta": scores[w] - base})
            best = max(scores, key=scores.get)
            if scores[best] <= base:
                best = 0.0
            pick.append(best)
            print(f"[{tag}] half {h}: base {base:.4f}; " +
                  "  ".join(f"w{w}:{scores[w] - base:+.4f}" for w in ws) + f"  -> picked w {best}")
        pd.DataFrame(curve).to_csv(out / f"curve_{tag}.csv", index=False)
        after = []
        for h in (0, 1):                              # half h gets the w picked on the other half
            ids_h = set(halves[h])
            gh = groups.image_id.isin(ids_h).to_numpy()
            after.append(rescore_groups(preds[preds.image_id.isin(ids_h)], groups[gh], Q[gh], classes, pick[1 - h]))
        after = pd.concat(after, ignore_index=True)
        after.to_csv(out / f"rescored_{tag}.csv", index=False)
        pa, pb = PerImage(gt, preds, iids), PerImage(gt, after, iids)
        views = {"v2 val, unweighted": (iids, None), "v2 val, val_strata-weighted": (iids, st.weight.to_dict()),
                 "1400x788": (list(st.index[st.is_1400x788 == 1]), None),
                 "1400x788 dark": (list(st.index[st.is_1400x788_dark == 1]), None)}
        res = {}
        print(f"\n[{tag}] REPORT ({len(iids)} images; w cross-fitted: half 0 uses {pick[1]}, half 1 uses {pick[0]}; "
              "95% scene-bootstrap CI on the change)")
        for name, (ids_v, wts) in views.items():
            r = res[name] = boot(pa, pb, ids_v, grp, wts, n=a.boot)
            print(f"\n  {name} ({len(ids_v)} images, {gt.image_id.isin(set(ids_v)).sum()} boxes)")
            print(f"  {'':6s} {'before':>8s} {'after':>8s} {'change':>8s}  95% CI")
            for c in CLASSES + ["mAP"]:
                x = r[c]
                print(f"  {c:6s} {x['before']:8.4f} {x['after']:8.4f} {x['delta']:+8.4f}  "
                      f"[{x['ci'][0]:+.4f}, {x['ci'][1]:+.4f}]")
            worst = min(CLASSES, key=lambda c: r[c]["delta"])
            print(f"  largest class drop: {worst} {r[worst]['delta']:+.4f}; sum of class changes "
                  f"{sum(r[c]['delta'] for c in CLASSES):+.4f}")
        summary[tag] = {"w_picked_per_half": pick, "report": res}
    json.dump(summary, open(out / f"summary_{'_'.join(a.sets)}.json", "w"), indent=1, default=float)


def alpha_car_to_van(rows, alpha):
    """Optional last step: for every "car" row add a "van" row at the same coordinates with confidence
    alpha * conf (the detector labels vans as car far more often than the reverse), then re-cap each image to CAP
    rows. alpha = 0 returns the rows unchanged. The duplicate lands at the tail of van's ranked list."""
    if alpha <= 0:
        return rows
    dup = rows[rows.label == "car"].assign(label="van", conf=lambda d: d.conf * alpha)
    out = pd.concat([rows, dup], ignore_index=True).sort_values("conf", ascending=False, kind="stable")
    return out.groupby("image_id").head(CAP)


# ---------------------------------------------------------------- test submission (fixed settings, no labels)

def cmd_submit(a):
    """WBF of prediction views (if more than one), then the classifier re-scoring with a fixed w chosen on v2 val,
    then submission.csv in the competition format, validated by check_submission.py."""
    from check_submission import check
    from fuse_wbf import fuse
    classes = ["car", "van"] if a.set == "carvan" else list(CLASSES)
    ids = (ROOT / "data/sample_submission.csv").open().read().split("\n")[1:]
    ids = [line.split(",")[0] for line in ids if line.strip()]
    views = [pd.read_csv(ROOT / v) for v in a.views]
    for v, p in zip(a.views, views):
        assert set(p.image_id) <= set(ids), f"{v} has image ids outside the test set"
        print(f"{v}: {len(p)} rows on {p.image_id.nunique()} images", flush=True)
    if len(views) > 1:
        sz = pd.read_csv(ROOT / "ardahan/image_sizes_test.csv").set_index("image_id")
        preds = fuse(views, [1.0] * len(views), a.iou, ids, {i: (int(sz.width[i]), int(sz.height[i])) for i in ids})
        print(f"WBF of {len(views)} views at IoU {a.iou}: {len(preds)} rows", flush=True)
    else:
        preds = views[0]
    preds = preds.reset_index(drop=True)
    out = ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    preds.to_csv(out.with_name(out.stem + "_detector_rows.csv"), index=False)
    groups = group_rows(preds, classes)
    groups["scored"] = groups.t >= MIN_T
    sel = groups[groups.scored].reset_index(drop=True)
    print(f"[{a.set}] {len(groups)} boxes, classifying {len(sel)} with t >= {MIN_T}", flush=True)
    m, norm = ft_model()
    m.load_state_dict(torch.load(OUT / "ft_best.pt"))
    P = extract(sel, (FT_SIZE,), fn=lambda c: ft_predict(m, norm, c), dim=len(CLASSES), dtype=np.float32)[FT_SIZE]
    Q = np.full((len(groups), len(CLASSES)), np.nan, np.float32)
    Q[groups.scored.to_numpy()] = P
    zero = rescore_groups(preds, groups, Q, classes, 0.0)
    key = ["image_id", "label", "conf", "x", "y", "w", "h"]
    assert zero[key].sort_values(key).reset_index(drop=True).equals(
        preds[key].sort_values(key).reset_index(drop=True)), "w = 0 does not reproduce the input rows"
    after = alpha_car_to_van(rescore_groups(preds, groups, Q, classes, a.w), a.alpha)
    after.to_csv(out.with_name(out.stem + "_rows.csv"), index=False)
    s = (after.label + " " + after.conf.round(5).astype(str) + " " + after.x.round(1).astype(str) + " " +
         after.y.round(1).astype(str) + " " + after.w.round(1).astype(str) + " " + after.h.round(1).astype(str))
    strings = s.groupby(after.image_id).agg(" ".join)
    pd.DataFrame({"image_id": ids, "PredictionString": [strings.get(i, "none") for i in ids]}).to_csv(out, index=False)
    errs = check(out)
    print(f"{out}: {len(after)} boxes on {after.image_id.nunique()} of {len(ids)} images; "
          f"max per image {after.groupby('image_id').size().max()}; check_submission: "
          f"{'OK' if not errs else errs[:5]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("gt-feats", "head", "det-feats"):
        sub.add_parser(n)
    r = sub.add_parser("rescore")
    r.add_argument("--boot", type=int, default=2000)
    r.add_argument("--model", choices=["head", "ft"], required=True)
    sub.add_parser("finetune")
    ap_ = sub.add_parser("apply")
    ap_.add_argument("--preds", required=True, help="image_id,label,conf,x,y,w,h CSV, relative to the repo root")
    ap_.add_argument("--images", required=True, help="manifest to score, e.g. splits/scene_holdout_v2/val.txt")
    ap_.add_argument("--name", required=True)
    ap_.add_argument("--boot", type=int, default=2000)
    ap_.add_argument("--sets", nargs="+", default=["carvan", "all4"], choices=["carvan", "all4"])
    sb = sub.add_parser("submit")
    sb.add_argument("--views", nargs="+", required=True, help="test prediction CSVs, fused by WBF if several")
    sb.add_argument("--iou", type=float, default=0.6)
    sb.add_argument("--set", choices=["carvan", "all4"], default="all4")
    sb.add_argument("--w", type=float, required=True, help="blend weight chosen on v2 val")
    sb.add_argument("--out", required=True)
    sb.add_argument("--alpha", type=float, default=0.0,
                    help="optional last step: a van copy of every car box at alpha * conf (0 = off)")
    a = ap.parse_args()
    {"gt-feats": cmd_gt_feats, "head": cmd_head, "det-feats": cmd_det_feats, "finetune": cmd_finetune, "apply": cmd_apply, "submit": cmd_submit,
     "rescore": cmd_rescore}[a.cmd](a)


if __name__ == "__main__":
    main()
