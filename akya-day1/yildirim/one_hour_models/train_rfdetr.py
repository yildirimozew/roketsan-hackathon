#!/usr/bin/env python3
"""Train RF-DETR Large; the Slurm wrapper enforces the 3,600-second limit."""

from __future__ import annotations

import argparse
from pathlib import Path

from rfdetr import RFDETRLarge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    model = RFDETRLarge(resolution=704)
    model.train(
        dataset_dir=str(args.data.resolve()),
        output_dir=str(args.output.resolve()),
        epochs=999,
        batch_size="auto",
        auto_batch_target_effective=16,
        lr=1e-4,
        lr_encoder=1e-5,
        weight_decay=1e-4,
        resolution=704,
        amp_dtype="bf16",
        use_ema=True,
        checkpoint_interval=1,
        eval_interval=5,
        eval_max_dets=500,
        log_per_class_metrics=True,
        early_stopping=False,
        seed=42,
        num_workers=12,
        tensorboard=True,
        wandb=True,
        project="eli-training",
        run="eli-training-3",
        progress_bar="tqdm",
    )


if __name__ == "__main__":
    main()
