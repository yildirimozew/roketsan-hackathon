"""Audit the organizer's Stage 2 files: schema, counts, time ranges, consistency checks, samples.

Reads the raw files directly (not through the repository) so format surprises show up here.
Usage: uv run python -m scripts.audit_data [--data data] [--json out.json]
"""

import argparse
import csv
import json
import re
import statistics
from collections import Counter, defaultdict
from itertools import pairwise
from pathlib import Path
from typing import Any

from PIL import Image

from app.core.config import get_settings
from app.core.timefmt import to_hhmm, to_minutes
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.services.geo import bearing_deg, frame_size_m, haversine_m, latlon_to_pixel
from app.services.reports import normalize, parse_coordinates

CORNERS = {"top_left": "tl", "top_right": "tr", "bottom_left": "bl", "bottom_right": "br"}
COORD_ANY = re.compile(r"\d{1,2}\.\d+\s*°?\s*[NS]", re.IGNORECASE)


def pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[min(len(s) - 1, round(q * (len(s) - 1)))]


def summary(values: list[float]) -> str:
    return (
        f"min {min(values):.1f} · p50 {statistics.median(values):.1f} · "
        f"p90 {pct(values, 0.9):.1f} · max {max(values):.1f}"
    )


def audit(data: Path) -> dict[str, Any]:
    out: dict[str, Any] = {}
    zones_raw = json.loads((data / "zones.json").read_text(encoding="utf-8"))
    base = LatLon(lat=zones_raw["base"]["lat"], lon=zones_raw["base"]["lon"])
    zones = {z["name"]: LatLon(lat=z["center"][0], lon=z["center"][1]) for z in zones_raw["zones"]}
    out["zones"] = {
        name: {
            "dist_to_base_m": round(haversine_m(base, c)),
            "bearing_deg": round(bearing_deg(base, c)),
        }
        for name, c in zones.items()
    }

    # ---- images
    meta_raw: dict[str, Any] = json.loads((data / "image_meta.json").read_text(encoding="utf-8"))
    metas: dict[str, ImageMeta] = {}
    axis_aligned = 0
    size_mismatch: list[str] = []
    missing_files: list[str] = []
    for iid, m in meta_raw.items():
        c = {CORNERS[k]: LatLon(lat=v[0], lon=v[1]) for k, v in m["corner_coordinates"].items()}
        meta = ImageMeta(
            image_id=iid,
            width_px=m["width_px"],
            height_px=m["height_px"],
            capture_time=m["capture_time"],
            capture_min=to_minutes(m["capture_time"]),
            corners=c,
        )
        metas[iid] = meta
        axis_aligned += int(
            c["tl"].lat == c["tr"].lat
            and c["tl"].lon == c["bl"].lon
            and c["br"].lat == c["bl"].lat
            and c["br"].lon == c["tr"].lon
        )
        path = data / "images" / f"{iid}.jpg"
        if not path.is_file():
            missing_files.append(iid)
            continue
        with Image.open(path) as im:
            if im.size != (m["width_px"], m["height_px"]):
                size_mismatch.append(
                    f"{iid}: file {im.size} vs meta {m['width_px']}x{m['height_px']}"
                )
    extra_files = sorted(p.stem for p in (data / "images").glob("*") if p.stem not in meta_raw)

    def center(meta: ImageMeta) -> LatLon:
        c = meta.corners
        return LatLon(lat=(c["tl"].lat + c["br"].lat) / 2, lon=(c["tl"].lon + c["br"].lon) / 2)

    frame_rows = []
    for meta in sorted(metas.values(), key=lambda x: x.capture_min):
        cen = center(meta)
        zone, zdist = min(((n, haversine_m(cen, z)) for n, z in zones.items()), key=lambda t: t[1])
        w_m, h_m = frame_size_m(meta)
        frame_rows.append(
            {
                "image_id": meta.image_id,
                "time": meta.capture_time,
                "size_px": f"{meta.width_px}x{meta.height_px}",
                "ground_m": f"{w_m:.0f}x{h_m:.0f}",
                "m_per_px": round(w_m / meta.width_px, 3),
                "zone": zone,
                "zone_dist_m": round(zdist),
                "base_dist_m": round(haversine_m(cen, base)),
            }
        )
    out["images"] = {
        "count": len(metas),
        "files": len(list((data / "images").glob("*"))),
        "axis_aligned": axis_aligned,
        "missing_files": missing_files,
        "extra_files": extra_files,
        "size_mismatch": size_mismatch,
        "pixel_sizes": dict(Counter(r["size_px"] for r in frame_rows)),
        "capture_range": (frame_rows[0]["time"], frame_rows[-1]["time"]),
        "per_zone": dict(Counter(r["zone"] for r in frame_rows)),
        "frames": frame_rows,
    }

    # ---- tracks
    points: dict[str, list[tuple[int, LatLon]]] = defaultdict(list)
    rows = 0
    header: list[str] = []
    with (data / "tracks.csv").open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        header = list(reader.fieldnames or [])
        for r in reader:
            rows += 1
            points[r["track_id"]].append(
                (to_minutes(r["time"]), LatLon(lat=float(r["lat"]), lon=float(r["lon"])))
            )
    lengths: Counter[int] = Counter()
    spans: Counter[int] = Counter()
    steps: Counter[int] = Counter()
    dup_times = 0
    ends: Counter[int] = Counter()
    max_speeds, path_km, approach, final_dist = [], [], [], []
    stationary = 0
    for pts in points.values():
        pts.sort(key=lambda t: t[0])
        times = [t for t, _ in pts]
        dup_times += len(times) - len(set(times))
        lengths[len(pts)] += 1
        spans[times[-1] - times[0]] += 1
        steps.update(b - a for a, b in pairwise(times))
        ends[times[-1]] += 1
        seg = [haversine_m(a, b) for (_, a), (_, b) in pairwise(pts)]
        max_speeds.append(max(seg) / 300)
        path_km.append(sum(seg) / 1000)
        stationary += int(sum(seg) < 50)
        d_start, d_end = haversine_m(pts[0][1], base), haversine_m(pts[-1][1], base)
        final_dist.append(d_end)
        approach.append((d_start - d_end) / max(1, times[-1] - times[0]))

    captures = Counter(m.capture_min for m in metas.values())
    ending_at_capture = sum(n for t, n in ends.items() if t in captures)
    per_frame: dict[str, dict[str, int]] = {}
    matched_track_ids: set[str] = set()
    for meta in metas.values():
        at = [(tid, p[-1][1]) for tid, p in points.items() if p[-1][0] == meta.capture_min]
        inside = []
        for tid, pos in at:
            x, y = latlon_to_pixel(pos, meta)
            if 0 <= x <= meta.width_px and 0 <= y <= meta.height_px:
                inside.append(tid)
        matched_track_ids.update(inside)
        per_frame[meta.image_id] = {"ending_at_capture": len(at), "inside_frame": len(inside)}
    out["tracks"] = {
        "header": header,
        "rows": rows,
        "tracks": len(points),
        "duplicate_times": dup_times,
        "points_per_track": dict(lengths),
        "span_min": dict(spans),
        "step_min": dict(steps),
        "time_range": (
            to_hhmm(min(t for p in points.values() for t, _ in p)),
            to_hhmm(max(t for p in points.values() for t, _ in p)),
        ),
        "end_times": {to_hhmm(t): n for t, n in sorted(ends.items())},
        "ending_at_a_capture_time": ending_at_capture,
        "ending_inside_their_frame": len(matched_track_ids),
        "per_frame": per_frame,
        "max_step_speed_ms": summary(max_speeds),
        "path_km": summary(path_km),
        "final_dist_to_base_m": summary(final_dist),
        "approach_m_per_min": summary(approach),
        "closing_over_20_m_per_min": sum(a > 20 for a in approach),
        "near_stationary_tracks": stationary,
    }

    # ---- reports
    reports: list[dict[str, str]] = json.loads(
        (data / "field_reports.json").read_text(encoding="utf-8")
    )
    keys = Counter(tuple(sorted(r)) for r in reports)
    zone_norm = {normalize(z): z for z in zones}
    with_coord = with_zone = with_any_coord = 0
    by_zone: Counter[str] = Counter()
    coord_near = []
    for r in reports:
        text = r["text"]
        coord = parse_coordinates(text)
        with_coord += coord is not None
        with_any_coord += bool(COORD_ANY.search(text))
        z = next((orig for n, orig in zone_norm.items() if n in normalize(text)), None)
        with_zone += z is not None
        if z:
            by_zone[z] += 1
        if coord:
            coord_near.append(haversine_m(coord, base))
    times = sorted(to_minutes(r["time"]) for r in reports)
    out["reports"] = {
        "count": len(reports),
        "keys": {"/".join(k): n for k, n in keys.items()},
        "sources": dict(Counter(r["source"] for r in reports)),
        "time_range": (to_hhmm(times[0]), to_hhmm(times[-1])),
        "with_parsed_coordinates": with_coord,
        "with_any_coordinate_text": with_any_coord,
        "with_zone_name": with_zone,
        "with_neither": sum(
            1
            for r in reports
            if parse_coordinates(r["text"]) is None
            and not any(n in normalize(r["text"]) for n in zone_norm)
        ),
        "by_zone": dict(by_zone),
        "coord_dist_to_base_m": summary(coord_near) if coord_near else "-",
        "duplicates": len(reports) - len({(r["time"], r["text"]) for r in reports}),
        "text_len": summary([len(r["text"]) for r in reports]),
    }
    out["report_texts"] = sorted(reports, key=lambda r: to_minutes(r["time"]))
    return out


def main() -> None:
    """Print the audit; optionally write it as JSON."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=get_settings().data_dir)
    ap.add_argument("--json", type=Path, default=None)
    ap.add_argument("--reports", action="store_true", help="print every report text")
    args = ap.parse_args()

    result = audit(args.data)
    for section in ("zones", "images", "tracks", "reports"):
        print(f"\n=== {section}")
        for k, v in result[section].items():
            if k in ("frames", "per_frame"):
                continue
            print(f"  {k}: {v}")
    print("\n=== frames")
    for r in result["images"]["frames"]:
        pf = result["tracks"]["per_frame"][r["image_id"]]
        print(
            f"  {r['image_id']} {r['time']} {r['size_px']:>9} ground {r['ground_m']:>7} m "
            f"{r['zone']:<24} base {r['base_dist_m']:>5} m  tracks end/inside "
            f"{pf['ending_at_capture']}/{pf['inside_frame']}"
        )
    if args.reports:
        print("\n=== reports (by time)")
        for r in result["report_texts"]:
            print(f"  {r['time']} {r['source']:<11} {r['text']}")
    if args.json:
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
