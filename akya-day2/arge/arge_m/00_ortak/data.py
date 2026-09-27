# ============================================================
# AR-GE ID     : ORTAK-1
# Başlık       : Organizatör verisini yükleme ve küçük coğrafi yardımcılar
# Akış adımı   : ortak (1-8 arası tüm adımlar kullanır)
# Durum        : test edildi
# Amaç         : data/ altındaki 5 dosyayı (zones, image_meta, tracks, field_reports, isteğe bağlı tespitler)
#                sadece standart kütüphaneyle okumak; haversine, kerteriz, kare kapsama.
# Kanıt        : 40 kare, 226 iz × 25 nokta, 137 rapor (98 official, 39 third_party).
# Çalıştırma   : Doğrudan çalıştırılmaz; diğer modüller içe aktarır.
# Entegrasyon  : backend/app/data/repository.py ile aynı biçimleri okur (REP-01.. numaralandırması aynı).
#                Bölge ataması kerteriz (açı) ile yapılır; backend en yakın bölge merkezini kullanıyor.
# Sınırlar     : Veride tarih ve saat dilimi yok; saatler günün dakikası olarak tutulur.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Loaders and small geo helpers for the organizer's stage-2 files (standard library only).

Kept independent of `backend/app` so R&D here cannot break the demo; the shapes mirror the raw
files described in docs/part2_docs/stage2/gorev_tanimi.txt.
"""

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

EARTH_R_M = 6_371_000.0
REPO_DIR = Path(__file__).resolve().parents[3]  # arge/arge_m/00_ortak/data.py -> repo root
DEFAULT_DATA_DIR = REPO_DIR / "data"


def to_minutes(hhmm: str) -> int:
    """'13:25' -> 805 (minute of day; the data has no date or time zone)."""
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Initial bearing from point 1 to point 2, degrees clockwise from north."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(x, y)) % 360


@dataclass(frozen=True)
class Point:
    lat: float
    lon: float

    def dist_m(self, other: "Point") -> float:
        return haversine_m(self.lat, self.lon, other.lat, other.lon)


@dataclass(frozen=True)
class Zone:
    name: str
    center: Point
    bearing_deg: float  # from the base


@dataclass(frozen=True)
class Frame:
    """One drone frame: a north-up rectangle captured at `capture_min`."""

    image_id: str
    capture_time: str
    capture_min: int
    width_px: int
    height_px: int
    north: float
    south: float
    west: float
    east: float
    zone: str  # zone whose bearing from the base is closest to the frame's bearing

    @property
    def center(self) -> Point:
        return Point((self.north + self.south) / 2, (self.west + self.east) / 2)

    def contains(self, p: Point, margin_m: float = 0.0) -> bool:
        dlat = margin_m / 111_320
        dlon = margin_m / (111_320 * math.cos(math.radians(p.lat)))
        return (
            self.south - dlat <= p.lat <= self.north + dlat
            and self.west - dlon <= p.lon <= self.east + dlon
        )

    def pixel_to_point(self, x: float, y: float) -> Point:
        """Organizer rule: linear interpolation from the corners, (0, 0) = top-left."""
        return Point(
            self.north + (y / self.height_px) * (self.south - self.north),
            self.west + (x / self.width_px) * (self.east - self.west),
        )


@dataclass(frozen=True)
class TrackPoint:
    minute: int
    pos: Point


@dataclass
class Track:
    track_id: str
    points: list[TrackPoint] = field(default_factory=list)

    @property
    def end(self) -> TrackPoint:
        return self.points[-1]

    def position_at(self, minute: float) -> Point | None:
        """Linear interpolation between 5-min samples; None outside the track's window."""
        pts = self.points
        if not pts or minute < pts[0].minute or minute > pts[-1].minute:
            return None
        for a, b in zip(pts, pts[1:]):
            if a.minute <= minute <= b.minute:
                if b.minute == a.minute:
                    return a.pos
                f = (minute - a.minute) / (b.minute - a.minute)
                return Point(a.pos.lat + f * (b.pos.lat - a.pos.lat), a.pos.lon + f * (b.pos.lon - a.pos.lon))
        return pts[-1].pos


@dataclass(frozen=True)
class Report:
    report_id: str  # "REP-07", file order, same scheme as backend/app/data/repository.py
    time: str
    time_min: int
    source: str
    text: str


@dataclass(frozen=True)
class Detection:
    """A detected vehicle placed on the map (optional input; tracks carry no vehicle type)."""

    image_id: str
    label: str  # car / van / truck / bus
    confidence: float
    pos: Point


@dataclass
class Dataset:
    base: Point
    zones: list[Zone]
    frames: dict[str, Frame]
    tracks: dict[str, Track]
    reports: list[Report]
    detections: dict[str, list[Detection]] = field(default_factory=dict)  # image_id -> detections

    def frames_in_zone(self, zone: str) -> list[Frame]:
        return [f for f in self.frames.values() if f.zone == zone]

    def tracks_ending_at(self, minute: int) -> list[Track]:
        """Tracks whose last point is at `minute`, i.e. the vehicles of the frame captured then."""
        return [t for t in self.tracks.values() if t.end.minute == minute]


def _zone_for(p: Point, base: Point, zones: list[Zone]) -> str:
    b = bearing_deg(base.lat, base.lon, p.lat, p.lon)
    return min(zones, key=lambda z: abs((b - z.bearing_deg + 180) % 360 - 180)).name


def load_dataset(data_dir: Path = DEFAULT_DATA_DIR, detections_file: Path | None = None) -> Dataset:
    raw_zones = json.loads((data_dir / "zones.json").read_text(encoding="utf-8"))
    base = Point(raw_zones["base"]["lat"], raw_zones["base"]["lon"])
    zones = [
        Zone(
            name=z["name"],
            center=Point(*z["center"]),
            bearing_deg=bearing_deg(base.lat, base.lon, *z["center"]),
        )
        for z in raw_zones["zones"]
    ]

    frames: dict[str, Frame] = {}
    for image_id, m in json.loads((data_dir / "image_meta.json").read_text(encoding="utf-8")).items():
        c = m["corner_coordinates"]
        north, west = c["top_left"]
        south, east = c["bottom_left"][0], c["top_right"][1]
        center = Point((north + south) / 2, (west + east) / 2)
        frames[image_id] = Frame(
            image_id=image_id,
            capture_time=m["capture_time"],
            capture_min=to_minutes(m["capture_time"]),
            width_px=m["width_px"],
            height_px=m["height_px"],
            north=north,
            south=south,
            west=west,
            east=east,
            zone=_zone_for(center, base, zones),
        )

    tracks: dict[str, Track] = {}
    with (data_dir / "tracks.csv").open(encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            tracks.setdefault(row["track_id"], Track(row["track_id"])).points.append(
                TrackPoint(to_minutes(row["time"]), Point(float(row["lat"]), float(row["lon"])))
            )
    for t in tracks.values():
        t.points.sort(key=lambda p: p.minute)

    raw_reports = json.loads((data_dir / "field_reports.json").read_text(encoding="utf-8"))
    reports = [
        Report(f"REP-{i + 1:02d}", r["time"], to_minutes(r["time"]), r["source"], r["text"])
        for i, r in enumerate(raw_reports)
    ]

    ds = Dataset(base=base, zones=zones, frames=frames, tracks=tracks, reports=reports)
    if detections_file is not None:
        ds.detections = load_detections(detections_file, frames)
    return ds


def load_detections(path: Path, frames: dict[str, Frame]) -> dict[str, list[Detection]]:
    """Read the backend's PrecomputedDetector JSON: {image_id: [{label, confidence, bbox: [x, y, w, h]}]}."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[Detection]] = {}
    for image_id, dets in raw.items():
        frame = frames.get(image_id)
        if frame is None:
            continue
        out[image_id] = [
            Detection(
                image_id=image_id,
                label=d["label"],
                confidence=float(d.get("confidence", 1.0)),
                pos=frame.pixel_to_point(d["bbox"][0] + d["bbox"][2] / 2, d["bbox"][1] + d["bbox"][3] / 2),
            )
            for d in dets
        ]
    return out
