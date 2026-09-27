"""Image-level leakage check on DINOv2-small embeddings (ardahan/embed_images.py), and scene-grouped folds.

Visual calibration of nearest-neighbour pairs (ardahan/outputs/embeddings/calib_*.jpg): cosine >= 0.80 is
almost always the same scene (often seconds apart); 0.75-0.80 is mixed; below that, same-place pairs and
merely similar-looking streets can no longer be told apart.

  1. near-copies across a split: for each validation image, its most similar training image
     (committed fold 1 and scene_holdout_v1), at several thresholds
  2. test images with a near-copy in train
  3. scene clusters: connected components of pairs with cosine >= --threshold and identical native size
     Threshold 0.88 is the one whose validation-to-train near-copy profile best matches test-to-train
     (% with a match >= 0.95/0.90/0.85/0.80: test 0.4/6.8/38.3/75.0, grouped t=0.88 0.0/0.5/42.1/83.4;
     committed random fold 1 2.2/28.7/64.8/86.6). Lower thresholds chain into giant clusters.
  4. grouped 5-fold split on those clusters (StratifiedGroupKFold, stratified by which of bus/truck/van
     an image contains), written to ardahan/splits/grouped_dinov2/ in the committed folds' format.
     The committed splits/ are not touched.

Usage: python ardahan/leakage_check.py [--threshold 0.88]   (from the repo root)
"""
import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "ardahan/outputs/embeddings"
SPLITS_OUT = ROOT / "ardahan/splits/grouped_dinov2"
THRESHOLDS = [0.95, 0.90, 0.85, 0.80, 0.75]


def load():
    d = np.load(OUT / "images_dinov2s.npz", allow_pickle=True)
    df = pd.DataFrame({"image_id": d["ids"], "split": d["split"], "w": d["width"], "h": d["height"]})
    return df, d["emb"]


def cross_split(df, emb, train_ids, val_ids, name):
    idx = pd.Series(df.index, index=df.image_id)
    tr, va = idx[train_ids].values, idx[val_ids].values
    S = emb[va] @ emb[tr].T
    best = S.max(1)
    same = (df.w.values[va][:, None] == df.w.values[tr][None]) & (df.h.values[va][:, None] == df.h.values[tr][None])
    best_same = np.where(same, S, -1).max(1)
    print(f"\n## {name}: validation images ({len(va)}) with a near-copy in its training set")
    print("threshold   any size          same native size")
    for t in THRESHOLDS:
        print(f"  >= {t:.2f}   {(best >= t).sum():4d} ({100 * (best >= t).mean():4.1f}%)    "
              f"{(best_same >= t).sum():4d} ({100 * (best_same >= t).mean():4.1f}%)")
    return pd.DataFrame({"image_id": val_ids, "max_sim": best, "max_sim_same_size": best_same})


def clusters(df, emb, tr_idx, t):
    """Connected components over train images: cosine >= t and identical native size."""
    parent = np.arange(len(tr_idx))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    E = emb[tr_idx]
    wh = (df.w.astype(str) + "x" + df.h.astype(str)).values[tr_idx]
    for k in range(0, len(tr_idx), 1024):
        S = E[k:k + 1024] @ E.T
        ii, jj = np.nonzero(S >= t)
        for i, j in zip(ii + k, jj):
            if i < j and wh[i] == wh[j]:
                a, b = find(i), find(j)
                if a != b:
                    parent[a] = b
    return np.array([find(i) for i in range(len(tr_idx))])


def presence(ann, ids):
    p = pd.crosstab(ann.image_id, ann.label).clip(upper=1).reindex(ids, fill_value=0)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=0.88)
    a = ap.parse_args()
    df, emb = load()
    ann = pd.read_csv(ROOT / "data/train/annotations.csv")
    S_ = lambda p: (ROOT / p).read_text().split()  # noqa: E731

    f1 = cross_split(df, emb, S_("splits/folds/fold_1_train.txt"), S_("splits/folds/fold_1_val.txt"),
                     "committed fold 1 (random)")
    f1.to_csv(OUT / "fold1_val_max_sim.csv", index=False)
    cross_split(df, emb, S_("splits/scene_holdout_v1/train.txt"), S_("splits/scene_holdout_v1/val.txt"),
                "scene_holdout_v1 (teammates', ResNet-18 >= 0.90 groups)")

    tr_idx = np.where(df.split.values == "train")[0]
    te_idx = np.where(df.split.values == "test")[0]
    St = emb[te_idx] @ emb[tr_idx].T
    tb = St.max(1)
    same = np.stack([(df.w.values[tr_idx] == df.w.values[i]) & (df.h.values[tr_idx] == df.h.values[i]) for i in te_idx])
    tbs = np.where(same, St, -1).max(1)
    Str = emb[tr_idx] @ emb[tr_idx].T
    np.fill_diagonal(Str, -1)
    trb = Str.max(1)
    print(f"\n## test images ({len(te_idx)}) with a near-copy in train   (train->train shown for comparison)")
    print("threshold   test, any size    test, same size    train->train, any size")
    for t in THRESHOLDS:
        print(f"  >= {t:.2f}   {(tb >= t).sum():4d} ({100 * (tb >= t).mean():4.1f}%)    "
              f"{(tbs >= t).sum():4d} ({100 * (tbs >= t).mean():4.1f}%)     {100 * (trb >= t).mean():4.1f}%")

    print("\n## scene clusters on train (cosine >= t, identical native size)")
    for t in sorted({0.75, 0.80, 0.85, a.threshold}):
        c = pd.Series(clusters(df, emb, tr_idx, t)).value_counts()
        print(f"  t={t:.2f}: {len(c)} clusters, {int((c > 1).sum())} with >1 image, "
              f"largest {c.iloc[0]}, {c.iloc[1]}, {c.iloc[2]}; images in clusters >1: {int(c[c > 1].sum())}")

    comp = clusters(df, emb, tr_idx, a.threshold)
    ids = df.image_id.values[tr_idx]
    groups = pd.Series(comp, index=ids)
    pres = presence(ann, ids)
    strat = (pres.get("bus", 0).astype(str) + pres.get("truck", 0).astype(str) + pres.get("van", 0).astype(str)).values
    sgkf = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42)
    SPLITS_OUT.mkdir(parents=True, exist_ok=True)
    meta = {"method": "StratifiedGroupKFold(5, shuffle, seed 42) on DINOv2-small scene clusters",
            "embedding": "timm vit_small_patch14_dinov2.lvd142m, 224x224, CLS token, L2-normalised",
            "cluster_rule": f"connected components of train pairs with cosine >= {a.threshold} and identical native size",
            "stratify_by": "presence pattern of bus/truck/van in the image",
            "n_clusters": int(len(set(comp))), "folds": []}
    print(f"\n## grouped folds (t={a.threshold}) -> {SPLITS_OUT}")
    print("fold  val   bus  truck  van  car  background  max cross-fold sim (same size)")
    idx = pd.Series(df.index, index=df.image_id)
    for k, (tri, vai) in enumerate(sgkf.split(ids, strat, groups.values), 1):
        tr_ids, va_ids = ids[tri], ids[vai]
        assert not set(groups.values[tri]) & set(groups.values[vai])
        (SPLITS_OUT / f"fold_{k}_train.txt").write_text("".join(i + "\n" for i in sorted(tr_ids)))
        (SPLITS_OUT / f"fold_{k}_val.txt").write_text("".join(i + "\n" for i in sorted(va_ids)))
        pv = pres.loc[va_ids]
        S = emb[idx[va_ids].values] @ emb[idx[tr_ids].values].T
        sm = (df.w.values[idx[va_ids].values][:, None] == df.w.values[idx[tr_ids].values][None]) & \
             (df.h.values[idx[va_ids].values][:, None] == df.h.values[idx[tr_ids].values][None])
        mx = float(np.where(sm, S, -1).max())
        row = {"fold": k, "validation_images": len(va_ids), "train_images": len(tr_ids),
               "validation_image_class_presence": {c: int(pv[c].sum()) for c in ["bus", "truck", "van", "car"]}
               | {"background": int((pv.sum(1) == 0).sum())}, "max_cross_split_same_size_cosine": round(mx, 4)}
        meta["folds"].append(row)
        p = row["validation_image_class_presence"]
        print(f"  {k}   {len(va_ids)}  {p['bus']:4d}  {p['truck']:4d}  {p['van']:4d}  {p['car']:4d}  {p['background']:4d}        {mx:.3f}")
    pd.DataFrame({"image_id": ids, "scene_cluster": comp}).to_csv(SPLITS_OUT / "groups.csv", index=False)
    (SPLITS_OUT / "metadata.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
