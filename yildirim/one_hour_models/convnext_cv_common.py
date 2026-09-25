"""Shared crop and ConvNeXt helpers for the car/van reclassifier."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torchvision.models import convnext_tiny

CLASS_NAMES = ("car", "van")
IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)
PAD_RGB = tuple(round(value * 255) for value in IMAGENET_MEAN)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dev_group(scene_group: str, seed: int = 42) -> bool:
    value = hashlib.sha256(f"{seed}:{scene_group}".encode()).digest()
    return int.from_bytes(value[:8], "big") % 10 == 0


def object_crop(
    image: Image.Image,
    box_xywh: tuple[float, float, float, float] | list[float] | np.ndarray,
    context: float = 1.75,
    output_size: int = 224,
) -> Image.Image:
    x, y, width, height = (float(value) for value in box_xywh)
    side = max(32, math.ceil(context * max(width, height)))
    center_x = x + width / 2
    center_y = y + height / 2
    left = math.floor(center_x - side / 2)
    top = math.floor(center_y - side / 2)
    right = left + side
    bottom = top + side

    source_left = max(0, left)
    source_top = max(0, top)
    source_right = min(image.width, right)
    source_bottom = min(image.height, bottom)
    crop = Image.new("RGB", (side, side), PAD_RGB)
    if source_right > source_left and source_bottom > source_top:
        region = image.crop((source_left, source_top, source_right, source_bottom))
        crop.paste(region, (source_left - left, source_top - top))
    return crop.resize((output_size, output_size), Image.Resampling.BICUBIC)


def build_model(weights_path: Path | None = None) -> torch.nn.Module:
    model = convnext_tiny(weights=None)
    if weights_path is not None:
        state = torch.load(weights_path, map_location="cpu", weights_only=True)
        model.load_state_dict(state)
    in_features = model.classifier[2].in_features
    model.classifier[2] = torch.nn.Linear(in_features, len(CLASS_NAMES))
    return model
