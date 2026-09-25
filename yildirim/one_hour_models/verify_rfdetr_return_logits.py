#!/usr/bin/env python3
"""Smoke-test opt-in RF-DETR logit output and default prediction parity."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from PIL import Image
from rfdetr import RFDETRLarge


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--image", type=Path, required=True)
    args = parser.parse_args()
    model = RFDETRLarge(pretrain_weights=str(args.checkpoint), resolution=704, num_classes=4)
    with Image.open(args.image) as source:
        image = source.convert("RGB").crop((0, 0, 704, 704))
    ordinary = model.predict(image, threshold=0.001, include_source_image=False)
    extended = model.predict(image, threshold=0.001, include_source_image=False, return_logits=True)
    if "class_logits" in ordinary.data or "query_index" in ordinary.data:
        raise AssertionError("default prediction unexpectedly includes logits")
    np.testing.assert_array_equal(ordinary.xyxy, extended.xyxy)
    np.testing.assert_array_equal(ordinary.class_id, extended.class_id)
    np.testing.assert_array_equal(ordinary.confidence, extended.confidence)
    logits = np.asarray(extended.data["class_logits"])
    labels = np.asarray(extended.class_id)
    expected = 1 / (1 + np.exp(-logits[np.arange(len(labels)), labels]))
    np.testing.assert_allclose(expected, extended.confidence, atol=2e-5, rtol=2e-5)
    if logits.shape != (len(extended), 4) or extended.data["query_index"].shape != (len(extended),):
        raise AssertionError("invalid extended prediction shapes")
    print(f"RF-DETR logit interface verified on {len(extended)} detections")


if __name__ == "__main__":
    main()
