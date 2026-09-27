"""YOLO11m on splits/scene_holdout_v2 (Kaggle kernel, 2x T4, DDP). Same recipe as the fold-1 run
(ardahan/kaggle/yolo11m_baseline, 0.751 on fold 1), so only the split changes.

COCO weights, imgsz 1280, 35 epochs, batch 4 per T4 (8 ran out of memory), fliplr/flipud 0.5, degrees 0, scale 0.4,
mosaic 1.0, close_mosaic 10, cos_lr, patience 10, AMP, save_period 5.
Train: scene_holdout_v2/train.txt; validation: scene_holdout_v2/val.txt (from the roketsan-splits dataset).
From the nano run: the dataset is copied to /kaggle/working first (/kaggle/input read at ~40 MB/s), the AMP
check uses a local yolo26n.pt, PYTORCH_ALLOC_CONF=expandable_segments:True.

Time budget: a watcher thread reads results.csv; after epoch 1 it prints s/epoch and the projected
training time. Over BUDGET_H it kills the DDP run and relaunches in the same session with the most
epochs that fit at 1280 (if >= MIN_EPOCHS_1280), else at imgsz 1024. Epoch 1 includes warm-up, so
the projection is on the pessimistic side.

Predictions come from last.pt, not best.pt: best.pt is picked by Ultralytics' own mAP on the
validation fold, which reads high and selects on the fold we score on. Inference: conf 0.001, max_det 1000.

Outputs in /kaggle/working:
  runs/<name>/weights/  last.pt, best.pt, epoch5.pt, epoch10.pt, ... ; results.csv, args.yaml
  preds_val_sh2.csv     image_id,label,conf,x,y,w,h for every scene_holdout_v2 validation image
  preds_test.csv        same, for the test images
  submission.csv        competition format, from preds_test.csv
"""
import glob
import os

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"  # before torch loads; DDP workers inherit it
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

# Fail in seconds if the kernel came up without both T4s or with CPU-only torch
# (version 2 ran on the CPU image: torch 2.10.0+cpu, 0 GPUs).
import torch  # noqa: E402

if shutil.which("nvidia-smi"):
    subprocess.run(["nvidia-smi", "-L"], check=False)
print(f"torch {torch.__version__} | cuda build {torch.version.cuda} | available {torch.cuda.is_available()} "
      f"| devices {torch.cuda.device_count()}", flush=True)
assert torch.cuda.is_available(), "no CUDA: check machine_shape and the docker image (GPU image, not CPU)"
assert torch.cuda.device_count() >= 2, f"expected 2x T4, got {torch.cuda.device_count()} GPU(s)"
TORCH_VERSION = torch.__version__

# Offline: ultralytics wheels, COCO weights, yolo11n.pt (Ultralytics' AMP check) and its font
# come from the roketsan-yolo-deps dataset.
DEPS = Path(glob.glob("/kaggle/input/**/yolo11m.pt", recursive=True)[0]).parent
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index",
                "--find-links", str(DEPS / "wheels"), "ultralytics"], check=True)
os.environ["YOLO_CONFIG_DIR"] = "/kaggle/working/ultralytics_cfg"
os.makedirs(os.environ["YOLO_CONFIG_DIR"], exist_ok=True)
shutil.copy(DEPS / "Arial.ttf", os.environ["YOLO_CONFIG_DIR"])
for w in ["yolo11m.pt", "yolo11n.pt"]:
    shutil.copy(DEPS / w, Path.cwd() / w)

import pandas as pd  # noqa: E402
import psutil  # noqa: E402
from ultralytics import YOLO  # noqa: E402
from ultralytics.utils import WEIGHTS_DIR  # noqa: E402

assert torch.__version__ == TORCH_VERSION, "pip replaced torch"
WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
shutil.copy(DEPS / "yolo26n.pt", WEIGHTS_DIR / "yolo26n.pt")  # AMP check without a download

CLASSES = ["car", "van", "truck", "bus"]
WORK = Path("/kaggle/working")
SRC = Path(glob.glob("/kaggle/input/**/yolo_ds/classes.json", recursive=True)[0]).parent
SPLITS = Path(glob.glob("/kaggle/input/**/scene_holdout_v2_train.txt", recursive=True)[0]).parent
ROOT = WORK / "yolo_ds"
BUDGET_H = 3.5
MIN_EPOCHS_1280 = 25
_t = time.time()
shutil.copytree(SRC, ROOT, dirs_exist_ok=True)
print(f"copied dataset to {ROOT} in {time.time() - _t:.0f} s", flush=True)

TRAIN_IDS = (SPLITS / "scene_holdout_v2_train.txt").read_text().split()
VAL_IDS = (SPLITS / "scene_holdout_v2_val.txt").read_text().split()
assert len(TRAIN_IDS) == 5176 and len(VAL_IDS) == 1295 and not set(TRAIN_IDS) & set(VAL_IDS)
for name, ids in [("train", TRAIN_IDS), ("val", VAL_IDS)]:
    (ROOT / f"sh2_{name}.txt").write_text("".join(f"./images/train/{i}.jpg\n" for i in ids))

data_yaml = WORK / "data.yaml"
data_yaml.write_text(
    f"path: {ROOT}\n"
    f"train: {ROOT}/sh2_train.txt\n"
    f"val: {ROOT}/sh2_val.txt\n"
    "names:\n" + "".join(f"  {i}: {c}\n" for i, c in enumerate(CLASSES))
)


class BudgetWatcher(threading.Thread):
    """Polls results.csv (written by rank 0 after every epoch); may kill the run after epoch 1."""

    def __init__(self, run_dir: Path, epochs: int, enforce: bool):
        super().__init__(daemon=True)
        self.csv, self.epochs, self.enforce = run_dir / "results.csv", epochs, enforce
        self.killed_at = None  # seconds per epoch that triggered the kill
        self.stop = threading.Event()

    def run(self):
        seen = 0
        while not self.stop.wait(15):
            try:
                df = pd.read_csv(self.csv)
            except Exception:
                continue
            df.columns = df.columns.str.strip()
            if len(df) <= seen or "time" not in df.columns:
                continue
            seen = len(df)
            t = float(df["time"].iloc[-1])
            per = t / seen
            proj = per * self.epochs / 3600
            print(f"[budget] epoch {seen}/{self.epochs}: {t:.0f} s elapsed, {per:.0f} s/epoch, "
                  f"projected training {proj:.2f} h (budget {BUDGET_H} h)", flush=True)
            if seen == 1 and self.enforce and proj > BUDGET_H:
                self.killed_at = per
                print(f"[budget] over budget: killing the run", flush=True)
                for c in psutil.Process().children(recursive=True):
                    c.kill()
                return


def train(imgsz: int, epochs: int, name: str, enforce: bool):
    run_dir = WORK / "runs" / name
    watcher = BudgetWatcher(run_dir, epochs, enforce)
    watcher.start()
    t0 = time.time()
    try:
        YOLO("yolo11m.pt").train(
            data=str(data_yaml),
            imgsz=imgsz,
            epochs=epochs,
            batch=8,  # total across the 2 GPUs: 4 per T4 (8 per T4 ran out of memory at 1280, v4)
            device=[0, 1],
            workers=4,
            fliplr=0.5,
            flipud=0.5,
            degrees=0.0,
            scale=0.4,
            mosaic=1.0,
            close_mosaic=10,
            cos_lr=True,
            patience=10,
            amp=True,
            save_period=5,
            seed=0,
            project=str(WORK / "runs"),
            name=name,
            exist_ok=True,
            plots=False,
        )
    except Exception as e:
        if watcher.killed_at is None:
            raise
        print(f"[budget] run stopped after epoch 1 ({type(e).__name__})", flush=True)
    watcher.stop.set()
    print(f"[{name}] wall time {(time.time() - t0) / 3600:.2f} h", flush=True)
    return run_dir, watcher.killed_at


IMGSZ, EPOCHS = 1280, 35
run_dir, per_epoch = train(IMGSZ, EPOCHS, "yolo11m_sh2_1280", enforce=True)
if per_epoch is not None:
    fit = int(BUDGET_H * 3600 / per_epoch)
    if fit >= MIN_EPOCHS_1280:
        EPOCHS = min(fit, 35)
    else:
        # time per epoch scales roughly with pixels: (1024/1280)^2 = 0.64
        IMGSZ, EPOCHS = 1024, min(35, int(BUDGET_H * 3600 / (per_epoch * 0.64)))
    print(f"[budget] relaunching: imgsz {IMGSZ}, {EPOCHS} epochs", flush=True)
    run_dir, _ = train(IMGSZ, EPOCHS, f"yolo11m_sh2_{IMGSZ}_e{EPOCHS}", enforce=False)

weights = run_dir / "weights/last.pt"


def predict(image_paths, out_csv):
    m = YOLO(str(weights))
    rows = []
    for p in image_paths:  # one at a time: a list source is predicted as a single batch
        r = m.predict(p, imgsz=IMGSZ, conf=0.001, iou=0.7, max_det=1000, device=0, half=True, verbose=False)[0]
        iid = Path(r.path).stem
        b = r.boxes
        for (x1, y1, x2, y2), c, s in zip(b.xyxy.tolist(), b.cls.tolist(), b.conf.tolist()):
            if x2 - x1 < 1 or y2 - y1 < 1:  # clipped at the image edge to zero size: invalid in a submission
                continue
            rows.append((iid, CLASSES[int(c)], round(s, 5), round(x1, 1), round(y1, 1),
                         round(x2 - x1, 1), round(y2 - y1, 1)))
    df = pd.DataFrame(rows, columns=["image_id", "label", "conf", "x", "y", "w", "h"])
    df.to_csv(out_csv, index=False)
    print(f"{out_csv.name}: {len(df)} boxes on {df.image_id.nunique()} images", flush=True)
    return df


t0 = time.time()
predict([str(ROOT / f"images/train/{i}.jpg") for i in VAL_IDS], WORK / "preds_val_sh2.csv")

test_paths = sorted(glob.glob(str(ROOT / "images/test/*.jpg")))
test = predict(test_paths, WORK / "preds_test.csv")

test["s"] = (test.label + " " + test.conf.astype(str) + " " + test.x.astype(str) + " "
             + test.y.astype(str) + " " + test.w.astype(str) + " " + test.h.astype(str))
strings = test.groupby("image_id").s.agg(" ".join)
ids = [Path(p).stem for p in test_paths]
sub = pd.DataFrame({"image_id": ids, "PredictionString": [strings.get(i, "none") for i in ids]})
sub.to_csv(WORK / "submission.csv", index=False)
print(f"inference took {(time.time() - t0) / 60:.1f} min", flush=True)

shutil.rmtree(WORK / "ultralytics_cfg", ignore_errors=True)
shutil.rmtree(ROOT, ignore_errors=True)  # the dataset copy is not an output
for w in ["yolo11m.pt", "yolo11n.pt"]:
    (Path.cwd() / w).unlink(missing_ok=True)
print("done", flush=True)
