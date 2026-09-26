import argparse, os
import pandas as pd
PAIRS = {"car": ["van"], "van": ["car"], "truck": ["bus"], "bus": ["truck"]}
MAX_PER_IMAGE = 1000
SWEEP = [0.1, 0.2, 0.3, 0.5]

def read_any(path):
    df = pd.read_csv(path)
    if "PredictionString" in df.columns:
        rows, order = [], df["image_id"].astype(str).tolist()
        for iid, ps in zip(order, df["PredictionString"].astype(str)):
            if ps.strip().lower() in ("none", "nan", ""):
                continue
            t = ps.split()
            for i in range(0, len(t), 6):
                rows.append((iid, t[i].lower(), float(t[i+1]), *map(float, t[i+2:i+6])))
        return pd.DataFrame(rows, columns=["image_id","label","conf","x","y","w","h"]), "submission", order
    df["image_id"] = df["image_id"].astype(str); df["label"] = df["label"].str.lower()
    return df[["image_id","label","conf","x","y","w","h"]], "preds", None

def hedge(preds, alpha):
    extra = []
    for src, tgts in PAIRS.items():
        base = preds[preds.label == src]
        for tgt in tgts:
            c = base.copy(); c["label"] = tgt; c["conf"] = c["conf"] * alpha; extra.append(c)
    out = pd.concat([preds, *extra], ignore_index=True).sort_values(["image_id","conf"], ascending=[True, False])
    return out.groupby("image_id", sort=False).head(MAX_PER_IMAGE).reset_index(drop=True)

def write_any(preds, fmt, order, path):
    if fmt == "preds":
        preds.to_csv(path, index=False); return
    by = {}
    for r in preds.itertuples(index=False):
        by.setdefault(r.image_id, []).append(f"{r.label} {r.conf:.5f} {r.x:.1f} {r.y:.1f} {r.w:.1f} {r.h:.1f}")
    pd.DataFrame({"image_id": order, "PredictionString": [" ".join(by.get(i, [])) or "none" for i in order]}).to_csv(path, index=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--inp", required=True); ap.add_argument("--alpha", type=float)
    ap.add_argument("--sweep", action="store_true"); ap.add_argument("--out")
    a = ap.parse_args()
    preds, fmt, order = read_any(a.inp)
    print(f"Input: {a.inp} | format: {fmt} | {len(preds)} boxes")
    alphas = SWEEP if a.sweep else [a.alpha]
    if alphas == [None]: ap.error("give --alpha or --sweep")
    stem, ext = os.path.splitext(a.inp)
    for al in alphas:
        out = hedge(preds, al)
        path = a.out if (a.out and not a.sweep) else f"{stem}_hedge{al:.2f}{ext}"
        write_any(out, fmt, order, path)
        print(f"  alpha={al:.2f} -> {path} | {len(out)} boxes")

if __name__ == "__main__":
    main()
