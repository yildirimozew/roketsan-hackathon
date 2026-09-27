"""Sweep hedge v2 settings on one validation prediction CSV (scene_holdout_v2), in-process.

  python mustafa/sweep_hedge_v2.py mustafa/preds/X_val.csv [--out-json mustafa/hedge_v2_best.json]
"""
import argparse, json, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hedge_classes import read_any  # noqa: E402
from hedge_classes_v2 import DIRS, hedge  # noqa: E402
from score_hedge import CLASSES, load_context, score  # noqa: E402

ALPHAS = [0.05, 0.1, 0.2, 0.3, 0.5]
MIN_GAIN = 0.002
t0 = time.time()


def fmt(r):
    return f"{r['map']:.4f} | {r['wmap']:.4f} | " + " | ".join(f"{r[c]:.4f}" for c in CLASSES)


def log(msg):
    print(f"[{time.time() - t0:6.0f}s] {msg}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("preds"); ap.add_argument("--out-json", default=str(Path(__file__).parent / "hedge_v2_best.json"))
    a = ap.parse_args()
    ctx = load_context()
    preds = read_any(a.preds)[0]
    run = lambda cfg: score(hedge(preds, cfg), ctx)  # noqa: E731
    base = score(preds, ctx)
    log(f"baseline: map {base['map']:.4f} wmap {base['wmap']:.4f}")
    md = ["| setting | mAP@0.5 | test-weighted | car | van | truck | bus |", "|---|---|---|---|---|---|---|", f"| no hedge | {fmt(base)} |"]

    chosen = {}
    for d, (_, tgt) in DIRS.items():
        md += ["", f"**{d}** (target: {tgt}, baseline {tgt} AP {base[tgt]:.4f})", "",
               f"| alpha | {tgt} AP | Δ{tgt} | mAP@0.5 | ΔmAP | test-weighted |", "|---|---|---|---|---|---|"]
        best_a, best_gain = 0.0, MIN_GAIN - 1e-12
        for al in ALPHAS:
            r = run({d: al})
            g = r[tgt] - base[tgt]
            md.append(f"| {al} | {r[tgt]:.4f} | {g:+.4f} | {r['map']:.4f} | {r['map'] - base['map']:+.4f} | {r['wmap']:.4f} |")
            log(f"{d} alpha={al}: {tgt} {r[tgt]:.4f} ({g:+.4f}) map {r['map']:.4f}")
            if g > best_gain and r["map"] >= base["map"]:
                best_a, best_gain = al, g
        chosen[d] = best_a
        md.append(f"→ chosen {d} = {best_a}")
    log(f"chosen alphas: {chosen}")

    md += ["", "**Combined (chosen alphas) × min-conf × dedup-iou**", "",
           "| min_conf | dedup_iou | mAP@0.5 | test-weighted | car | van | truck | bus |", "|---|---|---|---|---|---|---|---|"]
    best_cfg, best_r = None, None
    for mc in [0.0, 0.05, 0.1]:
        for dd in [0.5, 0.7, None]:
            cfg = {**chosen, "min_conf": mc, "dedup_iou": dd}
            r = run(cfg) if any(chosen.values()) else base
            md.append(f"| {mc} | {dd or 'off'} | {fmt(r)} |")
            log(f"combo min_conf={mc} dedup={dd}: map {r['map']:.4f} wmap {r['wmap']:.4f}")
            if best_r is None or (r["map"], r["wmap"]) > (best_r["map"], best_r["wmap"]):
                best_cfg, best_r = cfg, r
    out = {**best_cfg, "source": Path(a.preds).name, "val": "splits/scene_holdout_v2/val.txt",
           "baseline": base, "result": best_r}
    Path(a.out_json).write_text(json.dumps(out, indent=2))
    md += ["", f"| best combined | {fmt(best_r)} |", f"| no hedge | {fmt(base)} |", "", f"Saved → `{a.out_json}`"]
    log(f"best {best_cfg}: map {best_r['map']:.4f} ({best_r['map'] - base['map']:+.4f}), wmap {best_r['wmap']:.4f}")
    md_path = Path(a.preds).with_name(Path(a.preds).stem + "_sweep_v2.md")
    md_path.write_text("\n".join(md), encoding="utf-8")
    log(f"markdown tables -> {md_path}")


if __name__ == "__main__":
    main()
