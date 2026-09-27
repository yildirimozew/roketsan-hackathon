"""Crop embeddings per class (DINOv2-small, same backbone as the leakage check), with a validity gate.

Crops: square around each box (side = 1.1 x max(w, h), centred, zero-padded past the image edge),
resized to 224. Class-balanced sample, N boxes per class.

Neighbours never come from the same image or the same scene cluster (ardahan/splits/grouped_dinov2/groups.csv):
otherwise a crop's nearest neighbour is often the same vehicle one frame later, which inflates purity
and hides label noise.

Step 1, sanity gate (run first, alone):  truck vs bus, balanced. They look different at almost any
  resolution, so if the embeddings can't separate them, the embeddings are noise.
  Pass rule, fixed before looking: kNN (k=10) balanced accuracy >= 0.80 overall (chance 0.50).
  Also reported per size quartile and by a grouped 5-fold logistic probe.
Step 2 (only after a pass): UMAP by class; kNN purity per class and the neighbour-class matrix;
  car vs van separability next to truck vs bus; the same on each class's largest area quartile;
  suspected label noise ranked by how many neighbours carry a different label.

Usage:
  python ardahan/crop_embeddings.py embed [--n 1500]
  python ardahan/crop_embeddings.py sanity
  python ardahan/crop_embeddings.py analyse
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ardahan/outputs/embeddings"
CLASSES = ["car", "van", "truck", "bus"]
K = 10
SIZE = 224


def embed(n):
    import timm

    from embed_images import MODEL, load_model
    ann = pd.read_csv(ROOT / "data/train/annotations.csv")
    ann["area"] = ann.w * ann.h
    ann["box_id"] = np.arange(len(ann))
    sample = pd.concat([g.sample(n, random_state=0) for _, g in ann.groupby("label")]).reset_index(drop=True)
    model, mean, std = load_model()
    print(f"{MODEL}: {len(sample)} crops", flush=True)

    def crop(r):
        with Image.open(ROOT / f"data/train/images/{r.image_id}.jpg") as im:
            s = 1.1 * max(r.w, r.h)
            cx, cy = r.x + r.w / 2, r.y + r.h / 2
            c = im.convert("RGB").crop((round(cx - s / 2), round(cy - s / 2), round(cx + s / 2), round(cy + s / 2)))
            a = np.asarray(c.resize((SIZE, SIZE), Image.BICUBIC), np.float32) / 255
        return ((a - mean) / std).transpose(2, 0, 1)

    # group crops by image so each JPEG is decoded once per batch of its boxes
    sample = sample.sort_values("image_id").reset_index(drop=True)
    rows = list(sample.itertuples())
    embs = []
    with ThreadPoolExecutor(12) as ex, torch.no_grad():
        for k in range(0, len(rows), 128):
            x = torch.from_numpy(np.stack(list(ex.map(crop, rows[k:k + 128])))).cuda().half()
            embs.append(torch.nn.functional.normalize(model(x).float(), dim=1).cpu().numpy())
    sample.to_csv(OUT / "crops_meta.csv", index=False)
    np.save(OUT / "crops_dinov2s.npy", np.concatenate(embs))
    print(f"saved {len(sample)} crop embeddings", flush=True)
    _ = timm


def load():
    meta = pd.read_csv(OUT / "crops_meta.csv").astype({"image_id": object, "label": object})  # numpy, not Arrow
    emb = np.load(OUT / "crops_dinov2s.npy")
    groups = pd.read_csv(ROOT / "ardahan/splits/grouped_dinov2/groups.csv").set_index("image_id").scene_cluster
    meta["scene"] = meta.image_id.map(groups).values
    return meta, emb


def knn(emb, meta, idx, k=K):
    """k nearest neighbours of each crop in idx, among idx, excluding same image and same scene cluster."""
    E = emb[idx]
    S = E @ E.T
    img = meta.image_id.values[idx]
    sc = meta.scene.values[idx]
    S[(img[:, None] == img[None]) | (sc[:, None] == sc[None])] = -np.inf
    nb = np.argsort(-S, axis=1)[:, :k]
    return nb, np.take_along_axis(S, nb, 1)


def knn_bal_acc(meta, emb, idx):
    lab = meta.label.values[idx]
    nb, _ = knn(emb, meta, idx)
    pred = np.array([pd.Series(lab[n]).value_counts().index[0] for n in nb])
    return float(np.mean([np.mean(pred[lab == c] == c) for c in np.unique(lab)]))


def probe_bal_acc(meta, emb, idx):
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import GroupKFold
    y, X, g = meta.label.values[idx], emb[idx], meta.scene.values[idx]
    pred = np.empty(len(y), dtype=object)
    for tr, te in GroupKFold(5).split(X, y, g):
        pred[te] = LogisticRegression(max_iter=2000, C=1.0).fit(X[tr], y[tr]).predict(X[te])
    return float(balanced_accuracy_score(y, pred))


def pair(meta, a, b):
    return np.where(meta.label.isin([a, b]).values)[0]


def sanity():
    meta, emb = load()
    idx = pair(meta, "truck", "bus")
    acc = knn_bal_acc(meta, emb, idx)
    print(f"## sanity gate: truck vs bus ({len(idx)} crops, balanced; chance 0.50)")
    print(f"kNN (k={K}) balanced accuracy: {acc:.3f}   -> {'PASS' if acc >= 0.80 else 'FAIL'} (rule: >= 0.80)")
    print(f"grouped 5-fold logistic probe:  {probe_bal_acc(meta, emb, idx):.3f}")
    sub = meta.iloc[idx]
    q = sub.groupby("label").area.transform(lambda s: pd.qcut(s, 4, labels=False))
    print("per area quartile (within class):   kNN    probe   median box side px")
    for k in range(4):
        ii = idx[(q == k).values]
        side = np.sqrt(meta.area.values[ii]).round()
        print(f"  Q{k + 1}                               {knn_bal_acc(meta, emb, ii):.3f}  {probe_bal_acc(meta, emb, ii):.3f}   {np.median(side):.0f}")
    return acc >= 0.80


def analyse():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import umap

    meta, emb = load()
    meta["q"] = meta.groupby("label").area.transform(lambda s: pd.qcut(s, 4, labels=False))
    for name, idx in [("all crops", np.arange(len(meta))), ("largest area quartile per class", np.where(meta.q == 3)[0])]:
        lab = meta.label.values[idx]
        nb, _ = knn(emb, meta, idx)
        nl = lab[nb]
        print(f"\n## {name} ({len(idx)} crops, balanced across classes; chance purity 0.25)")
        print("neighbour-class matrix (row: crop class, columns: share of its k=10 neighbours)")
        print("         " + "".join(f"{c:>7s}" for c in CLASSES) + "   median side px")
        for c in CLASSES:
            m = lab == c
            print(f"  {c:6s} " + "".join(f"{(nl[m] == d).mean():7.3f}" for d in CLASSES)
                  + f"   {np.median(np.sqrt(meta.area.values[idx][m])):.0f}")
        print("pairwise separability (balanced accuracy, chance 0.50):   kNN    probe")
        for a, b in [("car", "van"), ("truck", "bus"), ("van", "truck"), ("car", "truck")]:
            ii = idx[np.isin(lab, [a, b])]
            print(f"  {a} vs {b}:{'':<34s}{knn_bal_acc(meta, emb, ii):.3f}  {probe_bal_acc(meta, emb, ii):.3f}")

    xy = umap.UMAP(n_neighbors=15, min_dist=0.1, metric="cosine", random_state=0).fit_transform(emb)
    colours = {"car": "#4C78A8", "van": "#F58518", "truck": "#54A24B", "bus": "#E45756"}
    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, (title, m) in zip(axes, [("all crops", np.ones(len(meta), bool)), ("largest area quartile per class", meta.q.values == 3)]):
        for c in CLASSES:
            s = m & (meta.label.values == c)
            ax.scatter(xy[s, 0], xy[s, 1], s=3, alpha=0.5, c=colours[c], label=c)
        ax.set_title(f"DINOv2-small crop embeddings, UMAP: {title}")
        ax.set_xticks([]), ax.set_yticks([])
        ax.legend(markerscale=4)
    fig.tight_layout()
    fig.savefig(OUT / "crops_umap.png", dpi=110)

    lab = meta.label.values
    nb, sim = knn(emb, meta, np.arange(len(meta)))
    nl = lab[nb]
    other = (nl != lab[:, None]).mean(1)
    maj = [pd.Series(r).value_counts().index[0] for r in nl]
    maj_share = np.array([(r == m).mean() for r, m in zip(nl, maj)])
    susp = meta.assign(neighbours_other_label=other, majority_neighbour_label=maj, majority_share=maj_share,
                       mean_neighbour_sim=sim.mean(1).round(4), box_side_px=np.sqrt(meta.area).round())
    susp = susp[(susp.majority_neighbour_label != susp.label) & (susp.neighbours_other_label >= 0.7)]
    susp = susp.sort_values(["majority_share", "mean_neighbour_sim"], ascending=False)
    cols = ["image_id", "x", "y", "w", "h", "label", "majority_neighbour_label", "majority_share",
            "neighbours_other_label", "mean_neighbour_sim", "box_side_px"]
    susp[cols].to_csv(OUT / "suspected_label_noise.csv", index=False)
    print(f"\n## suspected label noise: {len(susp)} of {len(meta)} sampled boxes have >= 70% of their "
          f"neighbours with another label -> {OUT / 'suspected_label_noise.csv'}")
    print(susp.groupby(["label", "majority_neighbour_label"]).size().rename("n").to_string())
    print(susp[cols].head(25).to_string(index=False))

    # montage of the top 24 for eyeballing
    tiles = []
    for r in susp.head(24).itertuples():
        with Image.open(ROOT / f"data/train/images/{r.image_id}.jpg") as im:
            s = 1.6 * max(r.w, r.h)
            cx, cy = r.x + r.w / 2, r.y + r.h / 2
            tiles.append((im.convert("RGB").crop((round(cx - s / 2), round(cy - s / 2), round(cx + s / 2),
                                                   round(cy + s / 2))).resize((160, 160)), r))
    from PIL import ImageDraw
    canvas = Image.new("RGB", (6 * 165, 4 * 180), "white")
    for k, (t, r) in enumerate(tiles):
        x0, y0 = (k % 6) * 165, (k // 6) * 180
        canvas.paste(t, (x0, y0))
        ImageDraw.Draw(canvas).text((x0 + 2, y0 + 162), f"{r.label}->{r.majority_neighbour_label} {r.majority_share:.1f}", fill=(0, 0, 0))
    canvas.save(OUT / "suspected_label_noise_top24.jpg", quality=90)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["embed", "sanity", "analyse"])
    ap.add_argument("--n", type=int, default=1500)
    a = ap.parse_args()
    {"embed": lambda: embed(a.n), "sanity": sanity, "analyse": analyse}[a.step]()


if __name__ == "__main__":
    main()
