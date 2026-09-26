#!/usr/bin/env python3
"""Fine-tune ConvNeXt-Tiny to distinguish car from van crops."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import random
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from convnext_cv_common import (
    CLASS_NAMES,
    IMAGENET_MEAN,
    IMAGENET_STD,
    build_model,
    sha256,
)
from PIL import Image
from sklearn.metrics import confusion_matrix, f1_score, precision_recall_fscore_support
from torch.optim.swa_utils import AveragedModel, get_ema_multi_avg_fn
from torch.utils.data import DataLoader, Dataset, WeightedRandomSampler
from torchvision import transforms


class CropDataset(Dataset):
    def __init__(self, root: Path, manifest: Path, transform: transforms.Compose) -> None:
        self.root = root
        with manifest.open(newline="") as handle:
            self.rows = list(csv.DictReader(handle))
        self.transform = transform

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        row = self.rows[index]
        with Image.open(self.root / row["path"]) as image:
            tensor = self.transform(image.convert("RGB"))
        return tensor, int(row["target"])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args()


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


@torch.inference_mode()
def evaluate(model: torch.nn.Module, loader: DataLoader, device: torch.device) -> dict:
    model.eval()
    predictions: list[int] = []
    targets: list[int] = []
    loss_sum = 0.0
    criterion = torch.nn.CrossEntropyLoss()
    for images, labels in loader:
        images = images.to(device, non_blocking=True)
        labels = labels.to(device, non_blocking=True)
        with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
            logits = model(images)
            loss = criterion(logits, labels)
        loss_sum += float(loss) * len(labels)
        predictions.extend(logits.argmax(1).cpu().tolist())
        targets.extend(labels.cpu().tolist())
    precision, recall, f1, _ = precision_recall_fscore_support(
        targets, predictions, labels=[0, 1], zero_division=0
    )
    return {
        "loss": loss_sum / len(targets),
        "macro_f1": float(f1_score(targets, predictions, average="macro")),
        "precision": dict(zip(CLASS_NAMES, map(float, precision), strict=True)),
        "recall": dict(zip(CLASS_NAMES, map(float, recall), strict=True)),
        "f1": dict(zip(CLASS_NAMES, map(float, f1), strict=True)),
        "confusion_matrix": confusion_matrix(targets, predictions, labels=[0, 1]).tolist(),
    }


def main() -> None:
    args = parse_args()
    seed_everything(args.seed)
    args.output.mkdir(parents=True, exist_ok=False)
    ready = json.loads((args.data / "READY.json").read_text())
    if not str(ready.get("name", "")).startswith("convnext-tiny-car-van-"):
        raise ValueError("unexpected classifier dataset marker")

    train_transform = transforms.Compose(
        [
            transforms.RandomHorizontalFlip(),
            transforms.RandomAffine(7, translate=(0.08, 0.08), scale=(0.9, 1.1), fill=tuple(round(x * 255) for x in IMAGENET_MEAN)),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1, hue=0.05),
            transforms.RandomApply([transforms.GaussianBlur(3, sigma=(0.1, 1.2))], p=0.1),
            transforms.ToTensor(),
            transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
        ]
    )
    eval_transform = transforms.Compose(
        [transforms.ToTensor(), transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD)]
    )
    train_data = CropDataset(args.data, args.data / "train.csv", train_transform)
    dev_data = CropDataset(args.data, args.data / "dev.csv", eval_transform)
    targets = [int(row["target"]) for row in train_data.rows]
    counts = Counter(targets)
    sample_weights = torch.tensor([1.0 / counts[target] for target in targets], dtype=torch.double)
    generator = torch.Generator().manual_seed(args.seed)
    sampler = WeightedRandomSampler(sample_weights, len(train_data), replacement=True, generator=generator)
    train_loader = DataLoader(
        train_data, batch_size=args.batch_size, sampler=sampler, num_workers=12,
        pin_memory=True, persistent_workers=True, prefetch_factor=3,
    )
    dev_loader = DataLoader(
        dev_data, batch_size=args.batch_size * 2, shuffle=False, num_workers=12,
        pin_memory=True, persistent_workers=True, prefetch_factor=3,
    )

    device = torch.device("cuda")
    model = build_model(args.weights).to(device)
    ema = AveragedModel(model, multi_avg_fn=get_ema_multi_avg_fn(0.999), use_buffers=True)
    head_parameters = list(model.classifier.parameters())
    head_ids = {id(parameter) for parameter in head_parameters}
    backbone_parameters = [parameter for parameter in model.parameters() if id(parameter) not in head_ids]
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone_parameters, "lr": 5e-5},
            {"params": head_parameters, "lr": 5e-4},
        ],
        weight_decay=0.05,
    )
    steps = len(train_loader) * args.epochs
    warmup = max(1, round(steps * 0.05))

    def lr_factor(step: int, minimum_factor: float) -> float:
        if step < warmup:
            return (step + 1) / warmup
        progress = (step - warmup) / max(1, steps - warmup)
        return minimum_factor + (1 - minimum_factor) * 0.5 * (1 + math.cos(math.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(
        optimizer,
        [lambda step: lr_factor(step, 0.02), lambda step: lr_factor(step, 0.002)],
    )
    criterion = torch.nn.CrossEntropyLoss(label_smoothing=0.05)
    best_f1 = -1.0
    history = []
    wandb_run = None
    if os.environ.get("WANDB_MODE"):
        import wandb

        wandb_run = wandb.init(
            project=os.environ.get("WANDB_PROJECT", "eli-training"),
            group=os.environ.get("WANDB_RUN_GROUP", "rfdetr-convnext-cv"),
            name=os.environ.get("WANDB_NAME", "convnext-cv-train"),
            config={
                "epochs": args.epochs, "batch_size": args.batch_size, "seed": args.seed,
                "backbone_lr": 5e-5, "head_lr": 5e-4, "weight_decay": 0.05,
                "dataset_ready_sha256": sha256(args.data / "READY.json"),
            },
        )

    global_step = 0
    for epoch in range(args.epochs):
        model.train()
        running_loss = 0.0
        seen = 0
        for images, labels in train_loader:
            images = images.to(device, non_blocking=True)
            labels = labels.to(device, non_blocking=True)
            optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type="cuda", dtype=torch.bfloat16):
                logits = model(images)
                loss = criterion(logits, labels)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            ema.update_parameters(model)
            running_loss += float(loss) * len(labels)
            seen += len(labels)
            global_step += 1
            if global_step % 50 == 0:
                print(f"epoch={epoch + 1} step={global_step}/{steps} loss={float(loss):.5f}", flush=True)
        metrics = evaluate(ema.module, dev_loader, device)
        metrics.update({"epoch": epoch + 1, "train_loss": running_loss / seen})
        history.append(metrics)
        print(json.dumps(metrics, sort_keys=True), flush=True)
        if wandb_run:
            confusion = metrics["confusion_matrix"]
            wandb_run.log({
                "epoch": epoch + 1, "train/loss": metrics["train_loss"],
                "dev/loss": metrics["loss"], "dev/macro_f1": metrics["macro_f1"],
                **{f"dev/{key}_{name}": metrics[key][name] for key in ("precision", "recall", "f1") for name in CLASS_NAMES},
                "dev/confusion_car_car": confusion[0][0], "dev/confusion_car_van": confusion[0][1],
                "dev/confusion_van_car": confusion[1][0], "dev/confusion_van_van": confusion[1][1],
            })
        if metrics["macro_f1"] > best_f1:
            best_f1 = metrics["macro_f1"]
            torch.save(
                {
                    "model": ema.module.state_dict(),
                    "class_names": CLASS_NAMES,
                    "epoch": epoch + 1,
                    "metrics": metrics,
                    "dataset_ready_sha256": sha256(args.data / "READY.json"),
                    "weights_sha256": sha256(args.weights),
                },
                args.output / "best_ema.pt",
            )
    (args.output / "metrics.json").write_text(json.dumps(history, indent=2) + "\n")
    if wandb_run:
        wandb_run.finish()


if __name__ == "__main__":
    main()
