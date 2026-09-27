#!/usr/bin/env python3
"""Train one arm of the matched RF-DETR scene-holdout A/B experiment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections import Counter
from pathlib import Path

from rfdetr import RFDETRLarge


CLASS_NAMES = ("car", "van", "truck", "bus")


def parse_weights(value: str) -> list[float]:
    weights = [float(item) for item in value.split(",")]
    if len(weights) != len(CLASS_NAMES) or any(weight <= 0 for weight in weights):
        raise argparse.ArgumentTypeError("weights must be four positive comma-separated values")
    return weights


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", required=True)
    parser.add_argument("--raw-class-weights", type=parse_weights, required=True)
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--eval-interval", type=int)
    parser.add_argument("--batch-size", type=int, default=19)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--init-weights", type=Path)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--lr-encoder", type=float, default=1e-5)
    return parser.parse_args()


def normalized_weights(annotation_path: Path, raw: list[float]) -> tuple[list[float], list[int]]:
    payload = json.loads(annotation_path.read_text())
    counts = Counter(int(annotation["category_id"]) for annotation in payload["annotations"])
    ordered_counts = [counts[index] for index in range(len(CLASS_NAMES))]
    total = sum(ordered_counts)
    if total == 0 or any(count == 0 for count in ordered_counts):
        raise ValueError(f"Invalid prepared class counts: {ordered_counts}")
    mean_weight = sum(count * weight for count, weight in zip(ordered_counts, raw, strict=True)) / total
    return [weight / mean_weight for weight in raw], ordered_counts


def main() -> None:
    args = parse_args()
    if args.resume is not None and args.init_weights is not None:
        raise ValueError("--resume and --init-weights are mutually exclusive")
    if args.resume is None:
        args.output.mkdir(parents=True, exist_ok=False)
    else:
        if not args.output.is_dir():
            raise FileNotFoundError(f"Resume output directory does not exist: {args.output}")
        if not args.resume.is_file():
            raise FileNotFoundError(f"Resume checkpoint does not exist: {args.resume}")
    if args.init_weights is not None and not args.init_weights.is_file():
        raise FileNotFoundError(f"Initialization checkpoint does not exist: {args.init_weights}")
    ready_path = args.data.parent / "READY.json"
    ready = json.loads(ready_path.read_text())
    if ready.get("name") not in {
        "rfdetr-scene-holdout-v1-ab",
        "rfdetr-scene-holdout-v2-ab",
        "rfdetr-full-train-v1-ab",
    }:
        raise ValueError(f"Unexpected prepared dataset marker: {ready.get('name')}")

    weights, counts = normalized_weights(
        args.data / "train" / "_annotations.coco.json", args.raw_class_weights
    )
    config = {
        "run": args.run,
        "dataset": ready["name"],
        "dataset_ready_sha256": hashlib.sha256(ready_path.read_bytes()).hexdigest(),
        "split_hashes": ready["source_hashes"],
        "epochs": args.epochs,
        "eval_interval": args.eval_interval or args.epochs,
        "batch_size": args.batch_size,
        "grad_accum_steps": 1,
        "seed": args.seed,
        "raw_class_weights": dict(zip(CLASS_NAMES, args.raw_class_weights, strict=True)),
        "normalized_class_weights": dict(zip(CLASS_NAMES, weights, strict=True)),
        "prepared_tile_annotation_counts": dict(zip(CLASS_NAMES, counts, strict=True)),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID"),
        "git_commit": os.environ.get("ELI_GIT_COMMIT"),
        "resume": str(args.resume.resolve()) if args.resume else None,
        "init_weights": str(args.init_weights.resolve()) if args.init_weights else None,
        "lr": args.lr,
        "lr_encoder": args.lr_encoder,
    }
    config_name = (
        f"experiment_config_job-{os.environ.get('SLURM_JOB_ID', 'local')}.json"
        if args.resume
        else "experiment_config.json"
    )
    (args.output / config_name).write_text(
        json.dumps(config, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(config, indent=2, sort_keys=True), flush=True)

    model_kwargs = {"resolution": 704}
    if args.init_weights is not None:
        model_kwargs["pretrain_weights"] = str(args.init_weights.resolve())
        model_kwargs["num_classes"] = len(CLASS_NAMES)
    model = RFDETRLarge(**model_kwargs)
    model.train(
        dataset_dir=str(args.data.resolve()),
        output_dir=str(args.output.resolve()),
        epochs=args.epochs,
        batch_size=args.batch_size,
        grad_accum_steps=1,
        lr=args.lr,
        lr_encoder=args.lr_encoder,
        weight_decay=1e-4,
        resolution=704,
        amp_dtype="bf16",
        use_ema=True,
        checkpoint_interval=1,
        eval_interval=args.eval_interval or args.epochs,
        eval_max_dets=500,
        log_per_class_metrics=True,
        early_stopping=False,
        seed=args.seed,
        num_workers=12,
        tensorboard=True,
        wandb=True,
        project=os.environ.get("WANDB_PROJECT", "eli-training"),
        run=args.run,
        progress_bar="tqdm",
        class_loss_weights=weights,
        notes=config,
        resume=str(args.resume.resolve()) if args.resume else None,
    )


if __name__ == "__main__":
    main()
