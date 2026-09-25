"""YOLO11s on splits/scene_holdout_v2 — Kaggle kernel (2x T4, DDP). Owner: furkan.

Decisions (evidence: furkan/notebooks/01b_eda_addendum.ipynb, splits/scene_holdout_v2/README.md):
  - COCO yolo11s, imgsz 1280 (EDA: boxes with short side < 16 px = 38 % at 960, 20 % at 1280)
  - Repeat Factor Sampling (Gupta et al., LVIS, 2019): image repeat r = max over its classes of
    max(1, sqrt(t / f_c)), f_c = share of train images containing class c, t = 0.5, stochastic rounding
  - augmentation strength (mosaic p, scale, translate, hsv) follows the cosine LR schedule down to 30 %;
    mosaic fully off in the last CLOSE_N epochs (replaces Ultralytics' close_mosaic)
  - fliplr 0.5, flipud 0 (perspective: box size grows 2.4x from image top to bottom)
  - time-budgeted training (Ultralytics `time`), validation every epoch on v2 val
  - inference conf 0.001, max_det 1000 (competition rules); scored in-kernel: unweighted and test-weighted
    mAP@0.5 (weights = p_test/p_val over resolution x dark(<55) strata), per-class AP, v2 subsets

Dataset: Kaggle dataset built from furkan/outputs/kaggle_upload/*.zip (yolo_v2/ images, labels, v2 lists).

Outputs (/kaggle/working):
  runs/y11s_v2/            weights (last.pt, best.pt), results.csv, args.yaml
  preds_val_{last,best}.csv, preds_test_{last,best}.csv    image_id,label,conf,x,y,w,h
  submission_{last,best}.csv, submission.csv (= higher test-weighted val mAP), scores.json
"""
import glob
import json
import math
import os
import random
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

T0 = time.time()
TIME_H = float(os.environ.get("TIME_H", 2.5))        # training budget in hours (validation included)
IMGSZ = int(os.environ.get("IMGSZ", 1280))
BATCH = int(os.environ.get("BATCH", 16))             # total over both GPUs; Ultralytics halves it on OOM
DEVICE = os.environ.get("DEVICE", "0,1")
EPOCHS = int(os.environ.get("EPOCHS", 300))          # upper bound, `time` decides the real count
MODEL = os.environ.get("MODEL", "yolo11s.pt")
SMOKE = os.environ.get("SMOKE") == "1"               # CPU pipeline test: no time budget, few epochs
INPUT = Path(os.environ.get("INPUT_DIR", "/kaggle/input")).resolve()
WORK = Path(os.environ.get("WORK_DIR", "/kaggle/working")).resolve()
ULTRALYTICS_VERSION = "8.4.163"                      # the version the callbacks were tested against
RFS_T = 0.5
AUG_FLOOR = 0.3
CLOSE_N = int(os.environ.get("CLOSE_N", 10))
DARK_THR = 55                                        # same as scene_holdout_v1/v2
SEED = 42
CLASSES = ["car", "van", "truck", "bus"]
DS = WORK / "yolo_v2"
RUN_NAME = "y11s_v2"


def log(*a):
    print(f"[{(time.time() - T0) / 60:6.1f} min]", *a, flush=True)


# ---------------------------------------------------------------- environment
import torch  # noqa: E402

TORCH_VERSION = torch.__version__
log(f"torch {TORCH_VERSION} | cuda {torch.cuda.is_available()} | gpus {torch.cuda.device_count()}")
if not SMOKE:
    if shutil.which("nvidia-smi"):
        subprocess.run(["nvidia-smi", "-L"], check=False)
    assert torch.cuda.device_count() >= 2, "expected 2x T4: set Accelerator = GPU T4 x2"
try:
    import ultralytics
    assert ultralytics.__version__ == ULTRALYTICS_VERSION
except (ImportError, AssertionError):
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", f"ultralytics=={ULTRALYTICS_VERSION}"], check=True)
import ultralytics  # noqa: E402

assert torch.__version__ == TORCH_VERSION, "pip replaced torch"
log("ultralytics", ultralytics.__version__)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from PIL import Image  # noqa: E402

# ---------------------------------------------------------------- dataset
def assemble():
    """Merge every */yolo_v2/** file under INPUT (Kaggle unzips each part into its own folder) into DS."""
    if (DS / "classes.json").exists():
        return
    unz = WORK / "_unz"
    for z in INPUT.rglob("*.zip"):              # parts Kaggle left zipped, if any
        with zipfile.ZipFile(z) as f:
            f.extractall(unz)
    n = 0
    for root in (INPUT, unz):
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and "yolo_v2" in p.parts:
                dst = DS / Path(*p.parts[p.parts.index("yolo_v2") + 1:])
                if not dst.exists():
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(p, dst)
                    n += 1
    shutil.rmtree(unz, ignore_errors=True)
    log(f"assembled {n} files into {DS}")


assemble()
counts = {k: len(list((DS / k).glob("*"))) for k in ["images/train", "labels/train", "images/test"]}
log("dataset:", counts)
if not SMOKE:
    assert counts == {"images/train": 6471, "labels/train": 6471, "images/test": 2118}, counts


def read_ids(name):
    return [Path(s).stem for s in (DS / name).read_text().split() if s.strip()]


train_ids, val_ids, test_ids = read_ids("train.txt"), read_ids("val.txt"), read_ids("test.txt")
assert not set(train_ids) & set(val_ids)
log(f"train {len(train_ids)} | val {len(val_ids)} | test {len(test_ids)}")

# ---------------------------------------------------------------- repeat factor sampling
cls_of = {}
for i in train_ids:
    txt = (DS / "labels/train" / f"{i}.txt").read_text().splitlines()
    cls_of[i] = {int(s.split()[0]) for s in txt if s.strip()}
f_c = [sum(c in s for s in cls_of.values()) / len(train_ids) for c in range(4)]
r_c = [max(1.0, math.sqrt(RFS_T / f)) if f > 0 else 1.0 for f in f_c]
rng = random.Random(SEED)
lines, extra = [], 0
for i in train_ids:
    r = max((r_c[c] for c in cls_of[i]), default=1.0)
    k = int(r) + (1 if rng.random() < r - int(r) else 0)
    lines.append(f"./images/train/{i}.jpg")
    for j in range(1, k):
        name = f"{i}__rfs{j}"
        for sub, ext in (("images/train", ".jpg"), ("labels/train", ".txt")):
            dst = DS / sub / f"{name}{ext}"
            if not dst.exists():
                os.link(DS / sub / f"{i}{ext}", dst)
        lines.append(f"./images/train/{name}.jpg")
        extra += 1
(DS / "train_rfs.txt").write_text("\n".join(lines) + "\n")
log("RFS image frequency", dict(zip(CLASSES, np.round(f_c, 3))), "repeat", dict(zip(CLASSES, np.round(r_c, 3))),
    f"-> +{extra} images ({extra / len(train_ids):.1%})")

data_yaml = WORK / "data_v2.yaml"
data_yaml.write_text(f"path: {DS}\ntrain: train_rfs.txt\nval: val.txt\nnames:\n"
                     + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES)))

# ---------------------------------------------------------------- augmentation-decay trainer
# Lives in its own module so the DDP subprocesses can import it.
(WORK / "aug_decay.py").write_text(f'''
import json
import os
from copy import copy
from ultralytics.models.yolo.detect import DetectionTrainer
from ultralytics.utils import DEFAULT_CFG, LOGGER, RANK

KEYS = ("mosaic", "scale", "translate", "hsv_h", "hsv_s", "hsv_v")
FLOOR = {AUG_FLOOR}


def on_epoch_start(tr):
    if not hasattr(tr, "_aug_base"):
        tr._aug_base = {{k: float(getattr(tr.args, k)) for k in KEYS}}
    e, E, lrf = tr.epoch, tr.epochs, float(tr.args.lrf)
    lf = float(tr.lf(e)) if tr.lf is not None else 1.0
    fac = FLOOR + (1 - FLOOR) * min(max((lf - lrf) / (1 - lrf), 0.0), 1.0)
    closed = e >= E - tr._close_n
    hyp = copy(tr.args)
    for k, v in tr._aug_base.items():
        setattr(hyp, k, v * fac)
    ds = tr.train_loader.dataset
    if closed:
        hyp.mosaic = hyp.copy_paste = hyp.mixup = hyp.cutmix = 0.0
        if hasattr(ds, "mosaic"):
            ds.mosaic = False
    ds.transforms = ds.build_transforms(hyp=hyp)
    tr.train_loader.reset()
    tr._aug_log = dict(epoch=e + 1, epochs=E, lr_factor=round(lf, 4), factor=round(fac, 3),
                       mosaic=round(hyp.mosaic, 3), scale=round(hyp.scale, 3), translate=round(hyp.translate, 3),
                       hsv_h=round(hyp.hsv_h, 4), hsv_s=round(hyp.hsv_s, 3), hsv_v=round(hyp.hsv_v, 3), closed=closed)
    if RANK in (-1, 0):
        LOGGER.info(f"[aug-decay] {{tr._aug_log}}")
        with open(os.path.join(str(tr.save_dir), "aug_log.jsonl"), "a") as f:
            f.write(json.dumps(tr._aug_log) + "\\n")


class AugDecayTrainer(DetectionTrainer):
    def __init__(self, cfg=DEFAULT_CFG, overrides=None, _callbacks=None):
        super().__init__(cfg, overrides, _callbacks)
        # read from the environment so DDP subprocesses (which receive the already-zeroed args) agree
        self._close_n = int(os.environ["AUG_CLOSE_N"])
        self.args.close_mosaic = 0          # mosaic closing is handled in on_epoch_start
        if not any(getattr(c, "__name__", "") == "on_epoch_start" for c in self.callbacks["on_train_epoch_start"]):
            self.add_callback("on_train_epoch_start", on_epoch_start)
''')
sys.path.insert(0, str(WORK))
os.environ["AUG_CLOSE_N"] = str(CLOSE_N)
os.environ["PYTHONPATH"] = f"{WORK}{os.pathsep}{os.environ.get('PYTHONPATH', '')}"
from aug_decay import AugDecayTrainer  # noqa: E402
from ultralytics import YOLO  # noqa: E402

# ---------------------------------------------------------------- training
device = [int(d) for d in DEVICE.split(",")] if DEVICE not in ("cpu", "") else "cpu"
common = dict(data=str(data_yaml), imgsz=IMGSZ, epochs=EPOCHS, batch=BATCH, device=device,
              workers=0 if SMOKE else 4, cos_lr=True, close_mosaic=CLOSE_N, fliplr=0.5, flipud=0.0,
              degrees=0.0, seed=SEED, amp=not SMOKE, val=True, plots=True, save_period=5, patience=1000,
              project=str(WORK / "runs"), name=RUN_NAME, exist_ok=True)


def find_run():
    """Ultralytics may nest project dirs (runs/detect/...): locate the run by its name."""
    hits = sorted(WORK.glob(f"**/{RUN_NAME}/weights/last.pt"), key=lambda p: p.stat().st_mtime)
    return hits[-1].parent.parent if hits else None

train_t0 = time.time()
attempts = [("aug-decay", AugDecayTrainer), ("default (close_mosaic)", None)]
for label, trainer_cls in attempts:
    if find_run() is not None:
        log(f"last.pt exists after a failed attempt: skipping further training, predicting with it")
        break
    left_h = TIME_H - (time.time() - train_t0) / 3600
    kw = dict(common, time=None if SMOKE else round(left_h, 3))
    if trainer_cls is not None:
        kw["trainer"] = trainer_cls
    log(f"training [{label}] time={kw['time']} h")
    try:
        YOLO(MODEL).train(**kw)
        break
    except Exception as e:  # noqa: BLE001
        log(f"training [{label}] failed: {type(e).__name__}: {e}")
log(f"training wall time {(time.time() - train_t0) / 3600:.2f} h")
RUN = find_run()
assert RUN is not None, "no weights produced"
log("run dir:", RUN)


def write_history():
    """results.csv (per-epoch metrics, cumulative time) + epoch duration + augmentation factors -> history.csv"""
    try:
        h = pd.read_csv(RUN / "results.csv")
        h.columns = h.columns.str.strip()
        h["epoch_time_s"] = h["time"].diff().fillna(h["time"])
        aug_path = RUN / "aug_log.jsonl"
        if aug_path.exists():
            aug = pd.DataFrame([json.loads(s) for s in aug_path.read_text().splitlines() if s.strip()])
            aug = aug.drop_duplicates("epoch", keep="last").drop(columns=["epochs"], errors="ignore")
            h = h.merge(aug.add_prefix("aug_").rename(columns={"aug_epoch": "epoch"}), on="epoch", how="left")
        h.to_csv(WORK / "history.csv", index=False)
        log(f"history.csv: {len(h)} epochs, mean {h.epoch_time_s.mean():.0f} s/epoch, "
            f"checkpoints: {sorted(p.name for p in (RUN / 'weights').glob('*.pt'))}")
    except Exception as e:  # noqa: BLE001  (analysis aid only; never block the submission)
        log(f"history.csv skipped: {type(e).__name__}: {e}")


write_history()

# ---------------------------------------------------------------- strata weights (resolution x dark)
def image_info(folder, ids):
    rows = []
    for i in ids:
        with Image.open(DS / folder / f"{i}.jpg") as im:
            w, h = im.size
            im.draft("L", (128, 128))
            b = float(np.asarray(im.convert("L").resize((64, 64))).mean())
        rows.append((i, w, h, f"{w}x{h}" + ("|dark" if b < DARK_THR else "|light")))
    return pd.DataFrame(rows, columns=["image_id", "W", "H", "stratum"]).set_index("image_id")


val_info, test_info = image_info("images/train", val_ids), image_info("images/test", test_ids)
p_test = test_info.stratum.value_counts(normalize=True)
p_val = val_info.stratum.value_counts(normalize=True)
w_img = val_info.stratum.map((p_test / p_val).fillna(0.0)).fillna(0.0)
w_img = w_img * len(w_img) / w_img.sum()
log(f"test weights: ESS {w_img.sum() ** 2 / (w_img ** 2).sum():.0f}, zero-weight images {(w_img == 0).sum()}")

gt_rows = []
for i in val_ids:
    W, H = val_info.loc[i, ["W", "H"]]
    for s in (DS / "labels/train" / f"{i}.txt").read_text().splitlines():
        if s.strip():
            c, cx, cy, bw, bh = s.split()
            cx, cy, bw, bh = float(cx) * W, float(cy) * H, float(bw) * W, float(bh) * H
            gt_rows.append((i, CLASSES[int(c)], cx - bw / 2, cy - bh / 2, bw, bh))
gt = pd.DataFrame(gt_rows, columns=["image_id", "label", "x", "y", "w", "h"])


def _iou(b, B):
    x1 = np.maximum(b[0], B[:, 0]); y1 = np.maximum(b[1], B[:, 1])
    x2 = np.minimum(b[0] + b[2], B[:, 0] + B[:, 2]); y2 = np.minimum(b[1] + b[3], B[:, 1] + B[:, 3])
    inter = np.clip(x2 - x1, 0, None) * np.clip(y2 - y1, 0, None)
    return inter / np.maximum(b[2] * b[3] + B[:, 2] * B[:, 3] - inter, 1e-9)


def evaluate(pred, ids, weights=None, min_area=200.0):
    """Kaggle-style mAP@0.5: per-class, confidence-ranked, greedy IoU>=0.5 matching, all-point AP.
    Unmatched predictions under 200 px^2 are ignored (as the competition does). Optional image weights."""
    ids = list(ids)
    w = pd.Series(1.0, index=ids) if weights is None else weights.reindex(ids).fillna(0.0)
    keep = set(w.index[w > 0])
    g_all, p_all = gt[gt.image_id.isin(keep)], pred[pred.image_id.isin(keep)]
    ap = {}
    for c in CLASSES:
        g = g_all[g_all.label == c]
        p = p_all[p_all.label == c].sort_values("conf", ascending=False, kind="mergesort")
        boxes = {k: v[["x", "y", "w", "h"]].to_numpy(float) for k, v in g.groupby("image_id")}
        used = {k: np.zeros(len(v), bool) for k, v in boxes.items()}
        npos = float(w.reindex(g.image_id).sum())
        if npos == 0:
            ap[c] = float("nan")
            continue
        tp, fp = np.zeros(len(p)), np.zeros(len(p))
        pw = w.reindex(p.image_id).to_numpy()
        for k, (img, b) in enumerate(zip(p.image_id.to_numpy(), p[["x", "y", "w", "h"]].to_numpy(float))):
            B = boxes.get(img)
            j, best = -1, 0.0
            if B is not None:
                ious = _iou(b, B)
                ious[used[img]] = -1.0
                j = int(np.argmax(ious)); best = ious[j]
            if best >= 0.5:
                used[img][j] = True; tp[k] = pw[k]
            elif b[2] * b[3] >= min_area:
                fp[k] = pw[k]
        ctp, cfp = np.cumsum(tp), np.cumsum(fp)
        rec = np.concatenate([[0.0], ctp / npos, [1.0]])
        prec = np.concatenate([[0.0], ctp / np.maximum(ctp + cfp, 1e-12), [0.0]])
        prec = np.maximum.accumulate(prec[::-1])[::-1]
        idx = np.where(rec[1:] != rec[:-1])[0]
        ap[c] = float(np.sum((rec[idx + 1] - rec[idx]) * prec[idx + 1]))
    vals = [v for v in ap.values() if not np.isnan(v)]
    return {"mAP": float(np.mean(vals)) if vals else float("nan"), **ap}


# ---------------------------------------------------------------- inference, scoring, submission
def predict(weights, folder, ids, out_csv):
    m = YOLO(str(weights))
    rows = []
    for i in ids:  # one image at a time: a list source is predicted as a single batch
        r = m.predict(str(DS / folder / f"{i}.jpg"), imgsz=IMGSZ, conf=0.001, iou=0.7, max_det=1000,
                      device=0 if torch.cuda.is_available() else "cpu", half=torch.cuda.is_available(),
                      verbose=False)[0]
        for (x1, y1, x2, y2), c, s in zip(r.boxes.xyxy.tolist(), r.boxes.cls.tolist(), r.boxes.conf.tolist()):
            if x2 - x1 < 1 or y2 - y1 < 1:  # clipped to zero size at the image edge: invalid in a submission
                continue
            rows.append((i, CLASSES[int(c)], round(s, 5), round(x1, 1), round(y1, 1),
                         round(x2 - x1, 1), round(y2 - y1, 1)))
    df = pd.DataFrame(rows, columns=["image_id", "label", "conf", "x", "y", "w", "h"])
    df.to_csv(out_csv, index=False)
    log(f"{out_csv.name}: {len(df)} boxes on {df.image_id.nunique()}/{len(ids)} images")
    return df


def write_submission(test_pred, path):
    s = (test_pred.label + " " + test_pred.conf.astype(str) + " " + test_pred.x.astype(str) + " "
         + test_pred.y.astype(str) + " " + test_pred.w.astype(str) + " " + test_pred.h.astype(str))
    strings = s.groupby(test_pred.image_id).agg(" ".join)
    ids = sorted(test_ids)
    sub = pd.DataFrame({"image_id": ids, "PredictionString": [strings.get(i, "none") for i in ids]})
    # format checks (competition page): one row per test image, `none` when empty, groups of 6, 0<=conf<=1, w,h>0
    assert len(sub) == len(set(test_ids)) and sub.PredictionString.str.len().gt(0).all()
    for ps in sub.PredictionString:
        if ps != "none":
            t = ps.split()
            assert len(t) % 6 == 0
            for k in range(0, len(t), 6):
                assert t[k] in CLASSES and 0 <= float(t[k + 1]) <= 1 and float(t[k + 4]) > 0 and float(t[k + 5]) > 0
    sub.to_csv(path, index=False)
    log(f"{path.name}: {len(sub)} rows, {int((sub.PredictionString == 'none').sum())} with none")


subsets = {name: read_ids(f"{name}.txt") for name in ["val_1400x788", "val_dark", "val_1400x788_dark"]
           if (DS / f"{name}.txt").exists()}
scores = {}
for tag in ["last", "best"]:
    wpath = RUN / "weights" / f"{tag}.pt"
    if not wpath.exists():
        continue
    pv = predict(wpath, "images/train", val_ids, WORK / f"preds_val_{tag}.csv")
    sc = {"val (unweighted)": evaluate(pv, val_ids), "val (test-weighted)": evaluate(pv, val_ids, w_img)}
    for name, ids in subsets.items():
        sc[name] = evaluate(pv, ids)
    scores[tag] = sc
    pt = predict(wpath, "images/test", test_ids, WORK / f"preds_test_{tag}.csv")
    write_submission(pt, WORK / f"submission_{tag}.csv")

table = pd.DataFrame({(t, k): v for t, sc in scores.items() for k, v in sc.items()}).T.round(4)
print(table.to_string(), flush=True)
chosen = max(scores, key=lambda t: scores[t]["val (test-weighted)"]["mAP"])
shutil.copy(WORK / f"submission_{chosen}.csv", WORK / "submission.csv")
json.dump({"chosen": chosen, "scores": scores, "rfs": {"t": RFS_T, "f_c": f_c, "r_c": r_c, "extra_images": extra},
           "imgsz": IMGSZ, "time_h": TIME_H, "ultralytics": ultralytics.__version__},
          open(WORK / "scores.json", "w"), indent=2)
log(f"submission.csv <- {chosen}.pt (test-weighted val mAP {scores[chosen]['val (test-weighted)']['mAP']:.4f})")

if not SMOKE:
    shutil.rmtree(DS, ignore_errors=True)  # keep the kernel output small (weights, csv, json only)
log("done")
