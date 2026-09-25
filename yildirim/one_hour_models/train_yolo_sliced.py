#!/usr/bin/env python3
"""Train one time-bounded YOLO26-S-P2 sliced-data pilot."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import wandb
from ultralytics import YOLO


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pilot", type=int, choices=(1, 2, 3), required=True)
    parser.add_argument("--lr0", type=float, required=True)
    parser.add_argument("--centered-ratio", type=float, required=True)
    parser.add_argument("--minutes", type=float, default=48.0)
    parser.add_argument("--epochs", type=int, default=40)
    parser.add_argument("--wandb-project", default="eli-training")
    parser.add_argument("--wandb-run", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    run_id = f"{args.wandb_run}-{os.environ.get('SLURM_JOB_ID', 'local')}"
    config = {
        "model": "yolo26s-p2",
        "pilot": args.pilot,
        "dataset": str(args.data.resolve()),
        "split": "scene_holdout_v2",
        "tile_size": 704,
        "tile_overlap": 0.25,
        "centered_ratio": args.centered_ratio,
        "lr0": args.lr0,
        "epochs_planned": args.epochs,
        "training_minutes": args.minutes,
        "git_commit": os.environ.get("ELI_GIT_COMMIT", "unknown"),
    }
    run = wandb.init(
        project=args.wandb_project,
        name=args.wandb_run,
        group="yolo26-sliced-pilots",
        job_type="training-pilot",
        id=run_id,
        resume="allow",
        config=config,
    )
    started = time.monotonic()
    deadline = started + args.minutes * 60

    def on_epoch_end(trainer) -> None:
        metrics = trainer.label_loss_items(trainer.tloss, prefix="train")
        metrics.update(trainer.lr)
        metrics["train/elapsed_minutes"] = (time.monotonic() - started) / 60
        run.log(metrics, step=trainer.epoch + 1)
        if time.monotonic() >= deadline:
            trainer.stop = True

    model = YOLO("yolo26s-p2.yaml").load("yolo26s.pt")
    model.add_callback("on_train_epoch_end", on_epoch_end)
    model.train(
        data=str(args.data.resolve()),
        epochs=args.epochs,
        imgsz=704,
        batch=0.80,
        device=0,
        workers=12,
        optimizer="AdamW",
        lr0=args.lr0,
        lrf=0.01,
        weight_decay=0.0005,
        warmup_epochs=1.0,
        cos_lr=True,
        amp="bf16",
        seed=42,
        deterministic=True,
        cache="disk",
        rect=False,
        mosaic=0.30,
        mixup=0.0,
        translate=0.08,
        scale=0.30,
        fliplr=0.5,
        flipud=0.0,
        degrees=3.0,
        close_mosaic=5,
        val=False,
        save=True,
        save_period=1,
        plots=False,
        project=str(args.output.resolve()),
        name="train",
        exist_ok=True,
        verbose=True,
    )
    last = args.output / "train" / "weights" / "last.pt"
    if not last.exists():
        raise FileNotFoundError(f"Training completed without {last}")
    results_path = args.output / "train" / "results.csv"
    completed_epochs = max(0, len(results_path.read_text().splitlines()) - 1)
    summary = {
        **config,
        "checkpoint": str(last),
        "completed_epochs": completed_epochs,
        "elapsed_minutes": (time.monotonic() - started) / 60,
    }
    (args.output / "training_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    run.log({"pilot/completed_epochs": completed_epochs})
    artifact = wandb.Artifact(f"{args.wandb_run}-training-summary", type="training-summary")
    artifact.add_file(str(args.output / "training_summary.json"))
    run.log_artifact(artifact)
    run.finish()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
