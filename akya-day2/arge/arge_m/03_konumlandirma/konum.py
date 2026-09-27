# ============================================================
# AR-GE ID     : R3.1, R3.2
# Başlık       : Organizatörün piksel→koordinat formülü (altın test) ve GeoJSON çıktısı
# Akış adımı   : 3 – georeference (konumlandırma)
# Durum        : test edildi
# Amaç         : (R3.1) Görev tanımındaki uçtan uca örneği birebir yeniden üretmek; (R3.2) harita
#                verisini GeoJSON (RFC 7946) olarak vermek; GeoJSON [boylam, enlem] sırası kullanır.
# Kanıt        : Görev tanımı örneği: 1360×765, piksel (640, 394) → (39.94439, 32.86350).
#                Organizatör verisi [enlem, boylam] sırasında; GeoJSON'da ters sıra gerekir.
# Çalıştırma   : arge/ klasöründen: python -m arge_m.konumlandirma.konum --out harita.geojson
# Entegrasyon  : backend/app/services/geo.py:pixel_to_latlon için ek altın test;
#                GeoJSON için /api/scene yanında olası bir /api/scene.geojson uç noktası.
# Sınırlar     : Görev tanımındaki img_000123 gerçek veride yok ("temsilidir"); bu yüzden test,
#                köşe koordinatları doğrudan verilerek yapılır. T0187 eşleşmesi gerçek veride denenemez.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Organizer's linear pixel-to-coordinate rule and a GeoJSON export of the day's data."""

import argparse
import json
from pathlib import Path
from typing import Any

from ..ortak.data import DEFAULT_DATA_DIR, Dataset, Point, load_dataset


def pixel_to_latlon(
    x: float, y: float, width_px: int, height_px: int,
    top_left: tuple[float, float], top_right: tuple[float, float], bottom_left: tuple[float, float],
) -> Point:
    """Exactly the formula in gorev_tanimi (corners as [lat, lon], pixel (0, 0) = top-left):

    lon = TL.lon + (x / width)  * (TR.lon - TL.lon)
    lat = TL.lat + (y / height) * (BL.lat - TL.lat)
    """
    lon = top_left[1] + (x / width_px) * (top_right[1] - top_left[1])
    lat = top_left[0] + (y / height_px) * (bottom_left[0] - top_left[0])
    return Point(lat, lon)


def _lonlat(p: Point) -> list[float]:
    """GeoJSON position order is [longitude, latitude] (RFC 7946 §3.1.1)."""
    return [round(p.lon, 6), round(p.lat, 6)]


def _feature(geometry: dict[str, Any], **properties: Any) -> dict[str, Any]:
    return {"type": "Feature", "geometry": geometry, "properties": properties}


def to_geojson(ds: Dataset) -> dict[str, Any]:
    """Base, zones, frame footprints, full tracks and located reports as one FeatureCollection."""
    from ..rapor_degerlendirme.claims import parse_report  # local import: step 6 is optional here

    features = [_feature({"type": "Point", "coordinates": _lonlat(ds.base)}, kind="base")]
    features += [
        _feature({"type": "Point", "coordinates": _lonlat(z.center)}, kind="zone", name=z.name)
        for z in ds.zones
    ]
    for f in ds.frames.values():
        ring = [Point(f.north, f.west), Point(f.north, f.east), Point(f.south, f.east),
                Point(f.south, f.west), Point(f.north, f.west)]  # closed, counter-clockwise is optional
        features.append(_feature({"type": "Polygon", "coordinates": [[_lonlat(p) for p in ring]]},
                                 kind="frame", image_id=f.image_id, capture_time=f.capture_time, zone=f.zone))
    for t in ds.tracks.values():
        features.append(_feature({"type": "LineString", "coordinates": [_lonlat(p.pos) for p in t.points]},
                                 kind="track", track_id=t.track_id,
                                 start_min=t.points[0].minute, end_min=t.end.minute))
    zone_names = [z.name for z in ds.zones]
    for r in ds.reports:
        loc = parse_report(r, zone_names).location
        if loc is not None:
            features.append(_feature({"type": "Point", "coordinates": _lonlat(loc)},
                                     kind="report", report_id=r.report_id, time=r.time,
                                     source=r.source, text=r.text))
    return {"type": "FeatureCollection", "features": features}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--out", type=Path, required=True, help="GeoJSON file to write (outside the repo is fine)")
    args = ap.parse_args()
    gj = to_geojson(load_dataset(args.data))
    args.out.write_text(json.dumps(gj, ensure_ascii=False), encoding="utf-8")
    kinds: dict[str, int] = {}
    for f in gj["features"]:
        kinds[f["properties"]["kind"]] = kinds.get(f["properties"]["kind"], 0) + 1
    print(f"wrote {args.out}: {kinds}")


if __name__ == "__main__":
    main()
