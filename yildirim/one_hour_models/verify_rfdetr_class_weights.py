#!/usr/bin/env python3
"""Small numerical contract test for the pinned RF-DETR class-weight patch."""

from __future__ import annotations

import torch

from rfdetr.config import TrainConfig
from rfdetr.models.criterion import SetCriterion, _batched_detection_loss_tensors


def criterion(weights: list[float] | None) -> SetCriterion:
    return SetCriterion(
        num_classes=5,
        matcher=None,  # loss_labels does not invoke the matcher
        weight_dict={"loss_ce": 1.0},
        focal_alpha=0.25,
        losses=["labels"],
        ia_bce_loss=True,
        class_loss_weights=weights,
    )


def main() -> None:
    torch.manual_seed(42)
    logits = torch.tensor(
        [[[0.2, -0.3, 0.1, -0.4, -0.7], [0.5, 0.2, -0.1, -0.2, -0.8], [-0.2, 0.4, 0.3, 0.1, -0.9]]],
        dtype=torch.float32,
    )
    boxes = torch.tensor(
        [[[0.30, 0.30, 0.20, 0.20], [0.60, 0.60, 0.25, 0.25], [0.80, 0.20, 0.10, 0.10]]],
        dtype=torch.float32,
    )
    targets = [{"labels": torch.tensor([1]), "boxes": torch.tensor([[0.31, 0.31, 0.20, 0.20]])}]
    indices = [(torch.tensor([0]), torch.tensor([0]))]
    outputs = {"pred_logits": logits, "pred_boxes": boxes}
    default_loss = criterion(None).loss_labels(outputs, targets, indices, torch.tensor(1.0))["loss_ce"]
    ones_loss = criterion([1.0] * 5).loss_labels(outputs, targets, indices, torch.tensor(1.0))["loss_ce"]
    torch.testing.assert_close(default_loss, ones_loss, rtol=0, atol=0)

    weights = [1.0, 1.25, 1.20, 1.10, 1.0]
    weighted_loss = criterion(weights).loss_labels(outputs, targets, indices, torch.tensor(1.0))["loss_ce"]
    assert weighted_loss > ones_loss
    batched = _batched_detection_loss_tensors(
        logits.unsqueeze(0),
        boxes.unsqueeze(0),
        torch.tensor([[0]]),
        torch.tensor([[0]]),
        torch.tensor([[1]]),
        targets[0]["boxes"].unsqueeze(0),
        torch.ones((1, 1)),
        torch.tensor([1]),
        torch.tensor(1.0),
        0.25,
        torch.tensor(weights),
    )[0][0]
    torch.testing.assert_close(weighted_loss, batched, rtol=1e-6, atol=1e-6)

    config = TrainConfig(dataset_dir=".", class_loss_weights=weights[:4])
    assert config.class_loss_weights == weights[:4]
    print(
        {
            "default_loss": float(default_loss),
            "weighted_loss": float(weighted_loss),
            "batched_loss": float(batched),
        }
    )


if __name__ == "__main__":
    main()
