"""Is there flight/scene grouping? Pixel similarity between images, by ID order and by nearest neighbour.

Thumbnails: greyscale 64x48, zero mean, unit norm, so a dot product is the Pearson correlation.
  1. consecutive IDs (train and test share one numbering) vs random pairs of the same image size
  2. runs of identical image size in ID order (a shuffled pool gives short runs)
  3. each image's nearest neighbour: its correlation and where it lands relative to fold 1
     (fold-1 val image whose nearest neighbour is in fold-1 train = a leak across the split)
Saves ardahan/outputs/grouping/*.png montages for eyeballing.

Usage: python ardahan/grouping_check.py   (from the repo root)
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "ardahan/outputs/grouping"
TW, TH = 64, 48


def thumb(p: Path) -> np.ndarray:
    with Image.open(p) as im:
        im.draft("L", (TW * 4, TH * 4))  # JPEG DCT downscale: fast
        v = np.asarray(im.convert("L").resize((TW, TH), Image.BILINEAR), dtype=np.float32).ravel()
    v -= v.mean()
    return v / (np.linalg.norm(v) + 1e-6)


def montage(pairs, path, title_rows):
    tiles = []
    for (a, b), t in zip(pairs, title_rows):
        ims = [Image.open(DATA / f"{s}/images/{i}.jpg").convert("RGB").resize((320, 200)) for s, i in (a, b)]
        row = Image.new("RGB", (650, 200), "white")
        row.paste(ims[0], (0, 0))
        row.paste(ims[1], (330, 0))
        tiles.append(row)
    canvas = Image.new("RGB", (650, 210 * len(tiles)), "white")
    for k, t in enumerate(tiles):
        canvas.paste(t, (0, 210 * k))
    canvas.save(path)
    (path.with_suffix(".txt")).write_text("\n".join(title_rows))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    sizes = pd.concat([
        pd.read_csv(ROOT / "ardahan/image_sizes_train.csv").assign(split="train"),
        pd.read_csv(ROOT / "ardahan/image_sizes_test.csv").assign(split="test"),
    ])
    sizes["num"] = sizes.image_id.str[4:].astype(int)
    sizes = sizes.sort_values("num").reset_index(drop=True)
    sizes["wh"] = sizes.width.astype(str) + "x" + sizes.height.astype(str)
    paths = [DATA / f"{s}/images/{i}.jpg" for s, i in zip(sizes.split, sizes.image_id)]
    with ThreadPoolExecutor(16) as ex:
        X = np.stack(list(ex.map(thumb, paths)))
    np.save(OUT / "thumbs.npy", X)
    n = len(X)
    print(f"{n} images, IDs {sizes.num.min()}..{sizes.num.max()} (gaps: {sizes.num.max() - sizes.num.min() + 1 - n})")

    # 1. consecutive vs random same-size pairs
    cons = np.einsum("ij,ij->i", X[:-1], X[1:])
    same = (sizes.wh.values[:-1] == sizes.wh.values[1:])
    rng = np.random.default_rng(0)
    rand = []
    for wh, g in sizes.groupby("wh").groups.items():
        g = np.asarray(g)
        if len(g) < 2:
            continue
        a, b = rng.choice(g, (2, min(4000, len(g) * 3)))
        keep = a != b
        rand.append(np.einsum("ij,ij->i", X[a[keep]], X[b[keep]]))
    rand = np.concatenate(rand)
    q = [0.5, 0.9, 0.99]
    print("\n## 1. correlation of consecutive IDs vs random same-size pairs")
    print(f"consecutive (all):       median {np.median(cons):.3f}  p90 {np.quantile(cons, .9):.3f}  p99 {np.quantile(cons, .99):.3f}")
    print(f"consecutive (same size): median {np.median(cons[same]):.3f}")
    print(f"random same-size pairs:  median {np.median(rand):.3f}  p90 {np.quantile(rand, .9):.3f}  p99 {np.quantile(rand, .99):.3f}")
    for t in [0.5, 0.7, 0.9]:
        print(f"  share > {t}: consecutive {100 * (cons > t).mean():.1f}%   random {100 * (rand > t).mean():.2f}%")
    print(f"consecutive pairs with the same image size: {100 * same.mean():.1f}% "
          f"(expected if shuffled: {100 * (sizes.wh.value_counts(normalize=True) ** 2).sum():.1f}%)")

    # 2. size runs
    run_id = (sizes.wh != sizes.wh.shift()).cumsum()
    runs = sizes.groupby(run_id).size()
    print("\n## 2. runs of identical image size in ID order")
    print(f"{len(runs)} runs, median length {runs.median():.0f}, mean {runs.mean():.1f}, max {runs.max()}")

    # 3. nearest neighbours (train <-> train, test -> train)
    tr = np.where(sizes.split.values == "train")[0]
    te = np.where(sizes.split.values == "test")[0]
    S = X[tr] @ X[tr].T
    np.fill_diagonal(S, -1)
    nn = S.argmax(1)
    nn_s = S.max(1)
    gap = np.abs(sizes.num.values[tr] - sizes.num.values[tr][nn])
    print("\n## 3. nearest neighbour within train")
    print(f"NN correlation: median {np.median(nn_s):.3f}  p10 {np.quantile(nn_s, .1):.3f}")
    for t in [0.8, 0.9, 0.95]:
        m = nn_s > t
        print(f"  NN corr > {t}: {100 * m.mean():.1f}% of train images; ID gap to NN median {np.median(gap[m]) if m.any() else float('nan'):.0f}, "
              f"within 10 IDs {100 * (gap[m] <= 10).mean() if m.any() else 0:.0f}%")
    fold1_val = set((ROOT / "splits/folds/fold_1_val.txt").read_text().split())
    ids_tr = sizes.image_id.values[tr]
    is_val = np.array([i in fold1_val for i in ids_tr])
    for t in [0.8, 0.9]:
        v = is_val & (nn_s > t)
        cross = v & ~is_val[nn]
        print(f"  fold-1 val images whose NN (corr > {t}) is in fold-1 train: {cross.sum()} of {is_val.sum()} "
              f"({100 * cross.sum() / is_val.sum():.1f}%)")

    St = X[te] @ X[tr].T
    t_s = St.max(1)
    print("\n## test -> nearest train image")
    print(f"NN correlation: median {np.median(t_s):.3f}; > 0.8: {100 * (t_s > .8).mean():.1f}%, > 0.9: {100 * (t_s > .9).mean():.1f}%")
    print(f"(train -> train for comparison: > 0.8: {100 * (nn_s > .8).mean():.1f}%, > 0.9: {100 * (nn_s > .9).mean():.1f}%)")

    # montages: consecutive pairs at several similarity levels, and random pairs
    order = np.argsort(cons)
    pick = [order[int(len(order) * f)] for f in [0.99, 0.9, 0.75, 0.5, 0.25]]
    montage([((sizes.split[i], sizes.image_id[i]), (sizes.split[i + 1], sizes.image_id[i + 1])) for i in pick],
            OUT / "consecutive_quantiles.png",
            [f"{sizes.image_id[i]} vs {sizes.image_id[i + 1]}  corr {cons[i]:.2f}" for i in pick])
    start = int(np.argmax(sizes.num.values >= 1000))
    montage([((sizes.split[i], sizes.image_id[i]), (sizes.split[i + 1], sizes.image_id[i + 1])) for i in range(start, start + 6)],
            OUT / "consecutive_run.png",
            [f"{sizes.image_id[i]} vs {sizes.image_id[i + 1]}  corr {cons[i]:.2f}" for i in range(start, start + 6)])
    k = np.argsort(-nn_s)[[0, 50, 200, 800, 2000]]
    montage([(("train", ids_tr[i]), ("train", ids_tr[nn[i]])) for i in k], OUT / "nearest_neighbours.png",
            [f"{ids_tr[i]} vs NN {ids_tr[nn[i]]}  corr {nn_s[i]:.2f}" for i in k])


if __name__ == "__main__":
    main()
