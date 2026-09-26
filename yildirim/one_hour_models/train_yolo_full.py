#!/usr/bin/env python3
"""Resume the selected YOLO sliced pilot for a full, early-stopped run."""

from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import time
from pathlib import Path

import torch
import wandb
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--initial-best", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--patience", type=int, default=6)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--wandb-project", default="eli-training")
    parser.add_argument("--wandb-run", default="yolo26-sliced-full-v2-train")
    parser.add_argument("--wandb-group", default="yolo26-sliced-full-v2")
    return parser.parse_args()


def resume_state(checkpoint: Path) -> tuple[int, int, float | None]:
    saved = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if saved.get("optimizer") is None:
        raise ValueError(
            f"{checkpoint} has no optimizer state; resume from an unstripped epoch checkpoint"
        )
    epoch = int(saved.get("epoch", -1))
    planned_epochs = int(saved.get("train_args", {}).get("epochs", 0))
    if epoch < 0 or planned_epochs <= epoch + 1:
        raise ValueError(
            f"Invalid resume state: completed epoch={epoch}, planned epochs={planned_epochs}"
        )
    metrics = saved.get("train_metrics") or {}
    map50 = metrics.get("metrics/mAP50(B)")
    return epoch, planned_epochs, float(map50) if map50 is not None else None


def final_epoch(results_path: Path, fallback: int) -> int:
    if not results_path.exists():
        return fallback
    with results_path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return fallback
    epoch_key = next((key for key in rows[-1] if key.strip() == "epoch"), None)
    return int(float(rows[-1][epoch_key])) if epoch_key else fallback + len(rows)


def main() -> None:
    args = parse_args()
    args.data = args.data.resolve()
    args.checkpoint = args.checkpoint.resolve()
    args.initial_best = args.initial_best.resolve()
    args.output = args.output.resolve()
    if not args.data.exists():
        raise FileNotFoundError(args.data)
    if not args.checkpoint.exists():
        raise FileNotFoundError(args.checkpoint)
    if not args.initial_best.exists():
        raise FileNotFoundError(args.initial_best)
    args.output.mkdir(parents=True, exist_ok=True)
    train_dir = args.output / "train"
    resumed_from, planned_epochs, initial_map50 = resume_state(args.checkpoint)
    best_map50_checkpoint = train_dir / "weights" / "best_map50.pt"
    best_map50_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    if not best_map50_checkpoint.exists():
        shutil.copy2(args.initial_best, best_map50_checkpoint)
    run_id = f"{args.wandb_run}-{os.environ.get('SLURM_JOB_ID', 'local')}"
    config = {
        "model": "yolo26s-p2",
        "dataset": str(args.data),
        "split": "scene_holdout_v2",
        "tile_size": 704,
        "tile_overlap": 0.25,
        "centered_ratio": 0.25,
        "lr0": 5e-4,
        "epochs_planned": planned_epochs,
        "early_stopping_patience": args.patience,
        "early_stopping_metric": "native validation mAP50",
        "source_checkpoint": str(args.checkpoint),
        "initial_best_checkpoint": str(args.initial_best),
        "initial_best_native_map50": initial_map50,
        "resumed_after_epoch": resumed_from + 1,
        "git_commit": os.environ.get("ELI_GIT_COMMIT", "unknown"),
    }
    run = wandb.init(
        project=args.wandb_project,
        name=args.wandb_run,
        group=args.wandb_group,
        job_type="training-full",
        id=run_id,
        resume="allow",
        config=config,
    )
    started = time.monotonic()
    early_stop = {
        "best": initial_map50 if initial_map50 is not None else float("-inf"),
        "best_epoch": resumed_from,
        "bad_epochs": 0,
        "training_epoch": None,
        "triggered": False,
    }

    def on_train_epoch_end(trainer) -> None:
        early_stop["training_epoch"] = trainer.epoch

    def on_fit_epoch_end(trainer) -> None:
        # final_eval() also emits on_fit_epoch_end; only process actual training epochs.
        if trainer.epoch != early_stop["training_epoch"]:
            return
        metrics = trainer.label_loss_items(trainer.tloss, prefix="train")
        metrics.update({str(key): float(value) for key, value in trainer.metrics.items()})
        metrics.update(trainer.lr)
        metrics["train/elapsed_minutes"] = (time.monotonic() - started) / 60
        map50 = float(trainer.metrics["metrics/mAP50(B)"])
        if map50 > early_stop["best"] + 1e-6:
            early_stop["best"] = map50
            early_stop["best_epoch"] = trainer.epoch
            early_stop["bad_epochs"] = 0
            shutil.copy2(train_dir / "weights" / "last.pt", best_map50_checkpoint)
        else:
            early_stop["bad_epochs"] += 1
        metrics["early_stop/best_native_map50"] = early_stop["best"]
        metrics["early_stop/bad_epochs"] = early_stop["bad_epochs"]
        run.log(metrics, step=trainer.epoch + 1)
        if early_stop["bad_epochs"] >= args.patience:
            early_stop["triggered"] = True
            trainer.stop = True

    model = YOLO(str(args.checkpoint))
    model.add_callback("on_train_epoch_end", on_train_epoch_end)
    model.add_callback("on_fit_epoch_end", on_fit_epoch_end)
    model.train(
        resume=str(args.checkpoint),
        data=str(args.data),
        device=0,
        workers=args.workers,
        cache=False,
        # The custom stopper targets mAP50 (the competition metric), while the
        # built-in stopper targets mAP50-95. Keep the latter out of the way.
        patience=100,
        val=True,
        plots=False,
        save_period=1,
        save_dir=str(train_dir),
        verbose=True,
    )

    last = train_dir / "weights" / "last.pt"
    if not last.exists():
        raise FileNotFoundError(f"Training completed without {last}")
    completed_epoch = final_epoch(train_dir / "results.csv", resumed_from)
    selected = best_map50_checkpoint
    summary = {
        **config,
        "selected_checkpoint": str(selected),
        "last_checkpoint": str(last),
        "final_epoch_index": completed_epoch,
        "completed_epochs_total": completed_epoch + 1,
        "best_native_map50": early_stop["best"],
        "best_native_map50_epoch_index": early_stop["best_epoch"],
        "early_stopping_triggered": early_stop["triggered"],
        "stopped_early": completed_epoch + 1 < config["epochs_planned"],
        "elapsed_minutes": (time.monotonic() - started) / 60,
    }
    summary_path = args.output / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    run.log(
        {
            "training/completed_epochs_total": completed_epoch + 1,
            "training/stopped_early": int(summary["stopped_early"]),
        }
    )
    artifact = wandb.Artifact(f"{args.wandb_run}-training-summary", type="training-summary")
    artifact.add_file(str(summary_path))
    run.log_artifact(artifact)
    run.finish()
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
