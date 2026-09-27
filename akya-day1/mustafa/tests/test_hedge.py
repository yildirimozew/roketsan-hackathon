import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from hedge_classes import hedge  # noqa: E402


def test_hedge_adds_paired_copies():
    preds = pd.DataFrame({
        "image_id": ["img_1", "img_1"], "label": ["car", "truck"], "conf": [0.9, 0.8],
        "x": [10.0, 50.0], "y": [20.0, 60.0], "w": [30.0, 40.0], "h": [15.0, 25.0],
    })
    out = hedge(preds, alpha=0.5)

    assert len(out) == 4
    got = {(r.label, round(r.conf, 6)): (r.x, r.y, r.w, r.h) for r in out.itertuples()}
    assert set(got) == {("car", 0.9), ("truck", 0.8), ("van", 0.45), ("bus", 0.4)}
    assert got[("van", 0.45)] == got[("car", 0.9)]      # copies keep the same box
    assert got[("bus", 0.4)] == got[("truck", 0.8)]
    assert out.conf.is_monotonic_decreasing              # sorted by conf within image
