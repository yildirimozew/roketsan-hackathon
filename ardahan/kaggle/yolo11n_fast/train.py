"""YOLO11n fast first run on fold 1 (Kaggle kernel, 2x T4, DDP): a working end-to-end run and a first
submission, not the final model (yolo11m is). Insurance.

COCO weights, imgsz 1280, 35 epochs, batch 16 (8 per T4), fliplr/flipud 0.5, degrees 0, scale 0.4,
mosaic 1.0, close_mosaic 10, cos_lr, patience 10, amp=True, save_period 5. Validation: fold 1.
The dataset is copied to /kaggle/working first: reading /kaggle/input ran at ~40 MB/s in v4/v5.
AMP check runs against a local yolo26n.pt (no internet, and it otherwise waits ~96 s to give up).
PYTORCH_ALLOC_CONF=expandable_segments:True is set before torch loads (inherited by the DDP workers).

A watcher thread reads results.csv and prints s/epoch and the projected total after every epoch.
Predictions come from last.pt, not best.pt. Inference: conf 0.001, max_det 1000.

Outputs in /kaggle/working: runs/<name>/weights/ (last, best, epoch5, ...), results.csv,
preds_val_fold1.csv, preds_test.csv, submission.csv
"""
import glob
import os

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"
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
for w in ["yolo11n.pt"]:
    shutil.copy(DEPS / w, Path.cwd() / w)

import pandas as pd  # noqa: E402
import psutil  # noqa: E402
from ultralytics import YOLO  # noqa: E402
from ultralytics.utils import WEIGHTS_DIR  # noqa: E402

WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)
shutil.copy(DEPS / "yolo26n.pt", WEIGHTS_DIR / "yolo26n.pt")  # AMP check, no download
print("AMP check weights:", WEIGHTS_DIR / "yolo26n.pt", flush=True)

assert torch.__version__ == TORCH_VERSION, "pip replaced torch"

FOLD = 1
CLASSES = ["car", "van", "truck", "bus"]
WORK = Path("/kaggle/working")
SRC = Path(glob.glob("/kaggle/input/**/yolo_ds/classes.json", recursive=True)[0]).parent
ROOT = WORK / "yolo_ds"
_t = time.time()
shutil.copytree(SRC, ROOT, dirs_exist_ok=True)
print(f"copied dataset to {ROOT} in {time.time() - _t:.0f} s", flush=True)
print("dataset root:", ROOT, flush=True)

data_yaml = WORK / "data.yaml"
data_yaml.write_text(
    f"path: {ROOT}\n"
    f"train: {ROOT}/fold_{FOLD}_train.txt\n"
    f"val: {ROOT}/fold_{FOLD}_val.txt\n"
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
            print(f"[timing] epoch {seen}/{self.epochs}: {t:.0f} s elapsed, {per:.0f} s/epoch, "
                  f"projected training {proj:.2f} h", flush=True)


def train(imgsz: int, epochs: int, name: str, enforce: bool):
    run_dir = WORK / "runs" / name
    watcher = BudgetWatcher(run_dir, epochs, enforce)
    watcher.start()
    t0 = time.time()
    try:
        YOLO("yolo11n.pt").train(
            data=str(data_yaml),
            imgsz=imgsz,
            epochs=epochs,
            batch=16,  # total across the 2 GPUs: 8 per T4
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
run_dir, _ = train(IMGSZ, EPOCHS, "yolo11n_fold1_1280", enforce=False)

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
val_ids = (ROOT / f"fold_{FOLD}_val.txt").read_text().split()
predict([str(ROOT / p) for p in val_ids], WORK / "preds_val_fold1.csv")

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
for w in ["yolo11n.pt"]:
    (Path.cwd() / w).unlink(missing_ok=True)
shutil.rmtree(ROOT, ignore_errors=True)  # the dataset copy is not an output
print("done", flush=True)
