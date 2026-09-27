"""The only module that reads organizer files. Loads everything once into domain objects.

Raw formats (case brief slides 13-14):
- image_meta.json: {image_id: {width_px, height_px, capture_time, corner_coordinates:
  {top_left, top_right, bottom_left, bottom_right: [lat, lon]}}}
- zones.json: {base: {name, lat, lon}, zones: [{name, center: [lat, lon]}]}
- tracks.csv: track_id,time,lat,lon (last 2 h per track, 5 min steps)
- field_reports.json: [{time, source, text}]  (no ids; REP-nn assigned by file order)
- images/<image_id>.(jpg|jpeg|png)
"""

import csv
import json
from pathlib import Path
from typing import Any

from app.core.errors import DataUnavailableError, NotFoundError
from app.core.timefmt import to_minutes
from app.domain.geo import CornerName, LatLon
from app.domain.image import ImageMeta
from app.domain.report import FieldReport
from app.domain.scene import Base, Scene, Zone
from app.domain.track import Track, TrackPoint
from app.services.geo import frame_center, haversine_m

EXPECTED_FILES = ("image_meta.json", "zones.json", "tracks.csv", "field_reports.json")
_CORNER_KEYS: dict[str, CornerName] = {
    "top_left": "tl",
    "top_right": "tr",
    "bottom_right": "br",
    "bottom_left": "bl",
}
_IMAGE_SUFFIXES = (".jpg", ".jpeg", ".png")


def data_status(data_dir: Path) -> tuple[bool, str]:
    """Report which organizer files are present (no parsing)."""
    missing = [name for name in EXPECTED_FILES if not (data_dir / name).is_file()]
    if not (data_dir / "images").is_dir():
        missing.append("images/")
    if missing:
        return False, f"{data_dir.name}/ missing: " + ", ".join(missing)
    return True, f"all files present in {data_dir.name}/"


def _latlon(pair: list[float]) -> LatLon:
    return LatLon(lat=float(pair[0]), lon=float(pair[1]))


def _load_scene(raw: dict[str, Any]) -> Scene:
    base = raw["base"]
    return Scene(
        base=Base(name=base["name"], position=LatLon(lat=base["lat"], lon=base["lon"])),
        zones=[Zone(name=z["name"], center=_latlon(z["center"])) for z in raw["zones"]],
    )


def _nearest_zone(p: LatLon, zones: list[Zone]) -> str | None:
    """Frames carry no zone field; a frame belongs to the zone with the nearest center."""
    return min(zones, key=lambda z: haversine_m(p, z.center)).name if zones else None


def _load_images(raw: dict[str, Any], zones: list[Zone]) -> dict[str, ImageMeta]:
    images: dict[str, ImageMeta] = {}
    for image_id, m in raw.items():
        corners = {_CORNER_KEYS[k]: _latlon(v) for k, v in m["corner_coordinates"].items()}
        meta = ImageMeta(
            image_id=image_id,
            width_px=int(m["width_px"]),
            height_px=int(m["height_px"]),
            capture_time=m["capture_time"],
            capture_min=to_minutes(m["capture_time"]),
            corners=corners,
        )
        images[image_id] = meta.model_copy(
            update={"zone": _nearest_zone(frame_center(meta), zones)}
        )
    return images


def _load_tracks(path: Path) -> dict[str, Track]:
    points: dict[str, list[TrackPoint]] = {}
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            points.setdefault(row["track_id"], []).append(
                TrackPoint(
                    time=row["time"],
                    time_min=to_minutes(row["time"]),
                    position=LatLon(lat=float(row["lat"]), lon=float(row["lon"])),
                )
            )
    return {
        tid: Track(track_id=tid, points=sorted(pts, key=lambda p: p.time_min))
        for tid, pts in sorted(points.items())
    }


def _load_reports(raw: Any) -> list[FieldReport]:
    items = raw if isinstance(raw, list) else next(v for v in raw.values() if isinstance(v, list))
    return [
        FieldReport(
            report_id=f"REP-{i + 1:02d}",
            time=r["time"],
            time_min=to_minutes(r["time"]),
            source=r["source"],
            text=r["text"],
        )
        for i, r in enumerate(items)
    ]


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class Repository:
    """In-memory view of one day's data pool."""

    def __init__(self, data_dir: Path) -> None:
        ok, detail = data_status(data_dir)
        if not ok:
            raise DataUnavailableError(detail)
        self.data_dir = data_dir
        self.scene = _load_scene(_read_json(data_dir / "zones.json"))
        self.images = _load_images(_read_json(data_dir / "image_meta.json"), self.scene.zones)
        self.tracks = _load_tracks(data_dir / "tracks.csv")
        self.reports = _load_reports(_read_json(data_dir / "field_reports.json"))

    def get_image_meta(self, image_id: str) -> ImageMeta:
        """Metadata of one frame; raises NotFoundError."""
        try:
            return self.images[image_id]
        except KeyError:
            raise NotFoundError(f"image {image_id} not found") from None

    def image_path(self, image_id: str) -> Path:
        """File path of one frame; raises NotFoundError if the file is missing."""
        self.get_image_meta(image_id)
        for suffix in _IMAGE_SUFFIXES:
            path = self.data_dir / "images" / f"{image_id}{suffix}"
            if path.is_file():
                return path
        raise NotFoundError(f"image file for {image_id} not found")

    def list_images(self) -> list[ImageMeta]:
        """All frames sorted by capture time."""
        return sorted(self.images.values(), key=lambda m: (m.capture_min, m.image_id))

    def reports_between(self, start_min: int, end_min: int) -> list[FieldReport]:
        """Reports with time in [start_min, end_min]."""
        return [r for r in self.reports if start_min <= r.time_min <= end_min]
