"""YOLO11l on splits/scene_holdout_v2 (Kaggle kernel, 2x T4, DDP). Same recipe as ardahan/kaggle/yolo11m_sh2 with the
larger model, so only the model size changes.

COCO weights (yolo11l.pt from the roketsan-yolo-deps dataset), imgsz 1280, batch 4 total (2 per T4: l needs more
memory than m, which ran out at 16 and needed 8), fliplr/flipud 0.5, degrees 0, scale 0.4, mosaic 1.0,
close_mosaic 10, cos_lr, patience 15, amp=True, save_period 5, checkpoints under /kaggle/working/runs.
Train: scene_holdout_v2/train.txt; validation: scene_holdout_v2/val.txt. v1 is never used.
Offline: the dataset is copied to /kaggle/working first (/kaggle/input reads at ~38 MB/s), the AMP check uses a
local yolo26n.pt (no download), PYTORCH_ALLOC_CONF=expandable_segments:True.

Time budget (KERNEL_BUDGET_H = 6 h for the whole kernel): the epoch count sets the cosine schedule, so it is fixed
from a measured epoch time rather than by stopping early. The first launch asks for PROBE_EPOCHS; after epoch 1 a
watcher prints s/epoch and the projected total, kills the run if it projects past the budget (it will, by design),
and the run is relaunched with the most epochs that fit the time left, minus a reserve for inference. Epoch 1
includes warm-up, so the fit errs short. If batch 4 fails before finishing an epoch (taken as out of memory), the
run is retried at batch 2; imgsz is never lowered.

Predictions come from last.pt (best.pt is picked by Ultralytics' own mAP on the validation set, which reads high).
Inference: imgsz 1280, conf 0.001, iou 0.7, max_det 1000.

Outputs in /kaggle/working:
  runs/<name>/weights/  last.pt, best.pt, epoch5.pt, epoch10.pt, ... ; results.csv, args.yaml
  preds_val_sh2.csv     image_id,label,conf,x,y,w,h for every scene_holdout_v2 validation image
  preds_test.csv        same, for the test images
  submission.csv        competition format, from preds_test.csv
"""
import os

os.environ["PYTORCH_ALLOC_CONF"] = "expandable_segments:True"  # before torch loads; DDP workers inherit it
import time  # noqa: E402

KERNEL_T0 = time.time()
import torch  # noqa: E402

# Fail in seconds if the kernel came up on the CPU image or without both T4s.
assert torch.cuda.is_available(), "no CUDA: check machine_shape and the docker image (GPU image, not CPU)"
assert torch.cuda.device_count() >= 2, f"expected 2x T4, got {torch.cuda.device_count()} GPU(s)"
print(f"torch {torch.__version__} | cuda {torch.version.cuda} | "
      f"{[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}", flush=True)
TORCH_VERSION = torch.__version__

import glob  # noqa: E402
import shutil  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import threading  # noqa: E402
from pathlib import Path  # noqa: E402

DEPS = Path(glob.glob("/kaggle/input/**/yolo11l.pt", recursive=True)[0]).parent
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-index",
                "--find-links", str(DEPS / "wheels"), "ultralytics"], check=True)
os.environ["YOLO_CONFIG_DIR"] = "/kaggle/working/ultralytics_cfg"
os.makedirs(os.environ["YOLO_CONFIG_DIR"], exist_ok=True)
shutil.copy(DEPS / "Arial.ttf", os.environ["YOLO_CONFIG_DIR"])
for w in ["yolo11l.pt", "yolo11n.pt"]:
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
KERNEL_BUDGET_H = 6.0
INFER_RESERVE_H = 0.4      # val + test prediction with l at 1280, one image at a time, plus cleanup
PROBE_EPOCHS = 100         # first launch only measures epoch 1; the real epoch count comes from it
IMGSZ = 1280
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


def hours_left():
    return KERNEL_BUDGET_H - (time.time() - KERNEL_T0) / 3600 - INFER_RESERVE_H


class BudgetWatcher(threading.Thread):
    """Polls results.csv (written by rank 0 after every epoch). After epoch 1: prints s/epoch and the projected
    total kernel time; if `enforce` and the run cannot finish inside the budget, kills it."""

    def __init__(self, run_dir: Path, epochs: int, enforce: bool):
        super().__init__(daemon=True)
        self.csv, self.epochs, self.enforce = run_dir / "results.csv", epochs, enforce
        self.killed_at = None  # measured seconds per epoch when the run was killed
        self.epochs_done = 0
        self.stop = threading.Event()

    def run(self):
        while not self.stop.wait(15):
            try:
                df = pd.read_csv(self.csv)
            except Exception:
                continue
            df.columns = df.columns.str.strip()
            if len(df) <= self.epochs_done or "time" not in df.columns:
                continue
            self.epochs_done = len(df)
            t = float(df["time"].iloc[-1])
            per = t / self.epochs_done
            left = per * (self.epochs - self.epochs_done) / 3600
            total = (time.time() - KERNEL_T0) / 3600 + left + INFER_RESERVE_H
            print(f"[budget] epoch {self.epochs_done}/{self.epochs}: {per:.0f} s/epoch; projected kernel total "
                  f"{total:.2f} h (budget {KERNEL_BUDGET_H} h)", flush=True)
            if self.epochs_done == 1 and self.enforce and total > KERNEL_BUDGET_H:
                self.killed_at = per
                print("[budget] projects past the budget: killing the run to relaunch with fewer epochs", flush=True)
                for c in psutil.Process().children(recursive=True):
                    c.kill()
                return


def train(epochs: int, batch: int, name: str, enforce: bool):
    run_dir = WORK / "runs" / name
    watcher = BudgetWatcher(run_dir, epochs, enforce)
    watcher.start()
    t0, error = time.time(), None
    try:
        YOLO("yolo11l.pt").train(
            data=str(data_yaml),
            imgsz=IMGSZ,
            epochs=epochs,
            batch=batch,  # total across the 2 GPUs
            device=[0, 1],
            workers=4,
            fliplr=0.5,
            flipud=0.5,
            degrees=0.0,
            scale=0.4,
            mosaic=1.0,
            close_mosaic=10,
            cos_lr=True,
            patience=15,
            amp=True,
            save_period=5,
            seed=0,
            project=str(WORK / "runs"),
            name=name,
            exist_ok=True,
            plots=False,
        )
    except Exception as e:
        error = e
    watcher.stop.set()
    print(f"[{name}] wall time {(time.time() - t0) / 3600:.2f} h, epochs done {watcher.epochs_done}", flush=True)
    return run_dir, watcher, error


def launch(epochs, name, enforce):
    """batch 4; if it fails before finishing an epoch and was not killed by the budget, retry at batch 2."""
    for batch in (4, 2):
        run_dir, w, err = train(epochs, batch, f"{name}_b{batch}", enforce)
        if err is None or w.killed_at is not None:
            return run_dir, w, batch
        if w.epochs_done > 0:
            raise err                     # failed mid-run: not a first-epoch OOM, do not mask it
        print(f"[oom?] batch {batch} failed before epoch 1 ({type(err).__name__}: {err}); retrying at batch 2",
              flush=True)
        torch.cuda.empty_cache()
    raise RuntimeError("batch 2 also failed before epoch 1")


run_dir, w, batch = launch(PROBE_EPOCHS, "probe", enforce=True)
if w.killed_at is not None:
    epochs = int(hours_left() * 3600 / w.killed_at)
    print(f"[budget] measured {w.killed_at:.0f} s/epoch at batch {batch}; {hours_left():.2f} h left for training "
          f"-> relaunching with {epochs} epochs", flush=True)
    if epochs <= 10:
        print("[budget] WARNING: fewer than close_mosaic + 1 epochs fit; running anyway at imgsz 1280", flush=True)
    shutil.rmtree(run_dir / "weights", ignore_errors=True)  # the probe's epoch-1 weights are not an output
    run_dir, w, batch = launch(max(epochs, 1), f"yolo11l_sh2_1280_e{epochs}", enforce=False)

weights = run_dir / "weights/last.pt"
print(f"[done] training finished at {(time.time() - KERNEL_T0) / 3600:.2f} h; predicting with {weights}", flush=True)


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
pd.DataFrame({"image_id": ids, "PredictionString": [strings.get(i, "none") for i in ids]}).to_csv(
    WORK / "submission.csv", index=False)
print(f"inference took {(time.time() - t0) / 60:.1f} min; kernel total {(time.time() - KERNEL_T0) / 3600:.2f} h",
      flush=True)

shutil.rmtree(WORK / "ultralytics_cfg", ignore_errors=True)
shutil.rmtree(ROOT, ignore_errors=True)  # the dataset copy is not an output
for f in ["yolo11l.pt", "yolo11n.pt"]:
    (Path.cwd() / f).unlink(missing_ok=True)
print("done", flush=True)
