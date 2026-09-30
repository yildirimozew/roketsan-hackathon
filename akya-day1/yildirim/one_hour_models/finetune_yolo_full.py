#!/usr/bin/env python3
"""Fine-tune a finished YOLO sliced run on the full (train + validation) dataset."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import torch
import wandb
from ultralytics import YOLO


# Optimizer and augmentation settings carried over from the source run so the
# fine-tune differs only in data, learning-rate schedule, and mosaic.
CARRIED_ARGS = (
    "imgsz", "batch", "optimizer", "momentum", "weight_decay", "cos_lr", "amp",
    "seed", "deterministic", "box", "cls", "dfl", "nbs", "hsv_h", "hsv_s", "hsv_v",
    "degrees", "translate", "scale", "shear", "perspective", "flipud", "fliplr",
    "bgr", "mosaic", "mixup", "cutmix", "copy_paste", "copy_paste_mode",
    "auto_augment", "erasing",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--lr0", type=float, default=1e-4)
    parser.add_argument("--lrf", type=float, default=0.1)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--wandb-project", default="eli-training")
    parser.add_argument("--wandb-run", default="yolo26-full-v2-finetune")
    parser.add_argument("--wandb-group", default="yolo26-full-v2-finetune")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    args.data = args.data.resolve()
    args.weights = args.weights.resolve()
    args.output = args.output.resolve()
    if not args.data.exists():
        raise FileNotFoundError(args.data)
    if not args.weights.exists():
        raise FileNotFoundError(args.weights)
    train_dir = args.output / "train"
    if train_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing run: {train_dir}")
    args.output.mkdir(parents=True, exist_ok=True)

    saved = torch.load(args.weights, map_location="cpu", weights_only=False)
    source_args = saved.get("train_args") or {}
    missing = [key for key in CARRIED_ARGS if key not in source_args]
    if missing:
        raise KeyError(f"{args.weights} train_args lacks {missing}")
    carried = {key: source_args[key] for key in CARRIED_ARGS}
    config = {
        "model": "yolo26s-p2",
        "dataset": str(args.data),
        "source_weights": str(args.weights),
        "source_epoch_index": saved.get("epoch"),
        "epochs": args.epochs,
        "lr0": args.lr0,
        "lrf": args.lrf,
        "warmup_epochs": 0,
        "mosaic_closed_for_all_epochs": True,
        "carried_args": carried,
        "git_commit": os.environ.get("ELI_GIT_COMMIT", "unknown"),
    }
    print(json.dumps(config, indent=2, default=str), flush=True)
    run = wandb.init(
        project=args.wandb_project,
        name=args.wandb_run,
        group=args.wandb_group,
        job_type="training-finetune",
        id=f"{args.wandb_run}-{os.environ.get('SLURM_JOB_ID', 'local')}",
        resume="allow",
        config=config,
    )
    started = time.monotonic()

    def on_fit_epoch_end(trainer) -> None:
        metrics = trainer.label_loss_items(trainer.tloss, prefix="train")
        metrics.update({str(key): float(value) for key, value in trainer.metrics.items()})
        metrics.update(trainer.lr)
        metrics["train/elapsed_minutes"] = (time.monotonic() - started) / 60
        run.log(metrics, step=trainer.epoch + 1)

    model = YOLO(str(args.weights))
    model.add_callback("on_fit_epoch_end", on_fit_epoch_end)
    model.train(
        **carried,
        data=str(args.data),
        epochs=args.epochs,
        lr0=args.lr0,
        lrf=args.lrf,
        warmup_epochs=0,
        # Mosaic is off for the whole fine-tune, like the source run's final epochs.
        close_mosaic=args.epochs,
        # Validation images are part of training, so validation is a sanity
        # check only and nothing may stop or select on it.
        patience=args.epochs + 1,
        device=0,
        workers=args.workers,
        cache=False,
        val=True,
        plots=False,
        save_period=1,
        project=str(args.output),
        name="train",
        exist_ok=False,
        verbose=True,
    )

    last = train_dir / "weights" / "last.pt"
    if not last.exists():
        raise FileNotFoundError(f"Training completed without {last}")
    summary = {
        **config,
        "selected_checkpoint": str(last),
        "selection": "final epoch; validation overlaps training",
        "elapsed_minutes": (time.monotonic() - started) / 60,
    }
    summary_path = args.output / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, default=str) + "\n")
    artifact = wandb.Artifact(f"{args.wandb_run}-training-summary", type="training-summary")
    artifact.add_file(str(summary_path))
    run.log_artifact(artifact)
    run.finish()
    print(json.dumps(summary, indent=2, default=str), flush=True)


if __name__ == "__main__":
    main()
