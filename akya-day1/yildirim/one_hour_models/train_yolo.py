#!/usr/bin/env python3
"""Run and validate one time-bounded Ultralytics pilot."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import wandb
from ultralytics import YOLO


def log_train_epoch(trainer) -> None:
    """Record YOLO losses and learning rates without relying on global settings."""
    metrics = trainer.label_loss_items(trainer.tloss, prefix="train")
    metrics.update(trainer.lr)
    wandb.log(metrics, step=trainer.epoch + 1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=("yolo26s-p2", "yolo12l"), required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--hours", type=float, default=1.0)
    parser.add_argument("--imgsz", type=int, default=1280)
    parser.add_argument("--wandb-project", default="eli-training")
    parser.add_argument("--wandb-run", required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    run_id = f"{args.wandb_run}-{os.environ.get('SLURM_JOB_ID', 'local')}"
    wandb.init(
        project=args.wandb_project,
        name=args.wandb_run,
        group="one-hour-pilots",
        job_type="architecture-pilot",
        id=run_id,
        resume="allow",
        config={"variant": args.variant, "imgsz": args.imgsz, "hours": args.hours, "fold": 1},
    )
    if args.variant == "yolo26s-p2":
        model = YOLO("yolo26s-p2.yaml").load("yolo26s.pt")
    else:
        model = YOLO("yolo12l.pt")
    model.add_callback("on_train_epoch_end", log_train_epoch)

    train_result = model.train(
        data=str(args.data.resolve()),
        epochs=999,
        time=args.hours,
        imgsz=args.imgsz,
        batch=0.80,
        device=0,
        workers=12,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        weight_decay=0.0005,
        warmup_epochs=1.0,
        cos_lr=True,
        amp=True,
        seed=42,
        deterministic=True,
        cache="disk",
        rect=False,
        mosaic=0.5,
        mixup=0.05,
        translate=0.10,
        scale=0.40,
        fliplr=0.5,
        flipud=0.5,
        degrees=10.0,
        close_mosaic=0,
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

    validator = YOLO(str(last))
    metrics = validator.val(
        data=str(args.data.resolve()),
        split="val",
        imgsz=args.imgsz,
        conf=0.001,
        iou=0.65,
        max_det=500,
        batch=8,
        device=0,
        workers=12,
        plots=True,
        save_json=True,
        project=str(args.output.resolve()),
        name="validation",
        exist_ok=True,
    )
    summary = {
        "variant": args.variant,
        "checkpoint": str(last),
        "map50": float(metrics.box.map50),
        "map50_95": float(metrics.box.map),
        "per_class_map50_95": [float(value) for value in metrics.box.maps],
        "class_names": [metrics.names[index] for index in sorted(metrics.names)],
    }
    (args.output / "metrics.json").write_text(json.dumps(summary, indent=2) + "\n")
    if wandb.run is None:
        wandb.init(
            project=args.wandb_project,
            name=args.wandb_run,
            group="one-hour-pilots",
            job_type="architecture-pilot",
            id=run_id,
            resume="must",
        )
    wandb.log(
        {
            "pilot/map50": summary["map50"],
            "pilot/map50_95": summary["map50_95"],
        }
    )
    wandb.finish()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
