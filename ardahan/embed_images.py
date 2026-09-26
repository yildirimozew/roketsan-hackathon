"""Embed every train and test image with DINOv2-small (timm), 224x224, for the leakage analysis.

Writes ardahan/outputs/embeddings/images_dinov2s.npz: ids, split ("train"/"test"), width, height,
emb (L2-normalised CLS features, float32).

Usage: python ardahan/embed_images.py   (from the repo root)
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import timm
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "ardahan/outputs/embeddings"
MODEL = "vit_small_patch14_dinov2.lvd142m"
SIZE = 224


def load_model():
    try:
        import truststore  # this machine re-signs some TLS traffic; use the Windows store for the download

        truststore.inject_into_ssl()
    except ImportError:
        pass
    m = timm.create_model(MODEL, pretrained=True, num_classes=0, img_size=SIZE).eval().cuda().half()
    cfg = timm.data.resolve_data_config({}, model=m)
    return m, np.array(cfg["mean"], np.float32), np.array(cfg["std"], np.float32)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = pd.concat([
        pd.read_csv(ROOT / "ardahan/image_sizes_train.csv").assign(split="train"),
        pd.read_csv(ROOT / "ardahan/image_sizes_test.csv").assign(split="test"),
    ]).reset_index(drop=True)
    model, mean, std = load_model()

    def load(row):
        with Image.open(DATA / f"{row.split}/images/{row.image_id}.jpg") as im:
            im.draft("RGB", (SIZE * 2, SIZE * 2))
            a = np.asarray(im.convert("RGB").resize((SIZE, SIZE), Image.BICUBIC), np.float32) / 255
        return ((a - mean) / std).transpose(2, 0, 1)

    embs = []
    rows = list(sizes.itertuples())
    with ThreadPoolExecutor(12) as ex, torch.no_grad():
        for k in range(0, len(rows), 64):
            x = torch.from_numpy(np.stack(list(ex.map(load, rows[k:k + 64])))).cuda().half()
            embs.append(torch.nn.functional.normalize(model(x).float(), dim=1).cpu().numpy())
            if k % 1280 == 0:
                print(f"{k}/{len(rows)}", flush=True)
    emb = np.concatenate(embs)
    np.savez(OUT / "images_dinov2s.npz", ids=sizes.image_id.values, split=sizes.split.values,
             width=sizes.width.values, height=sizes.height.values, emb=emb)
    print(f"saved {emb.shape} -> {OUT / 'images_dinov2s.npz'}")


if __name__ == "__main__":
    main()
