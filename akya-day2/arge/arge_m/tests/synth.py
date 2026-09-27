# ============================================================
# AR-GE ID     : TEST
# Başlık       : Kurallar için elle kurulmuş küçük veri setleri
# Akış adımı   : tümü (özellikle 5 ve 6)
# Durum        : test edildi
# Amaç         : Organizatör dosyaları olmadan her kuralı tek başına sınamak (yaklaşan, uzaklaşan, park eden izler).
# Kanıt        : Park titreşimi gerçek veriye göre seçildi (≈35 m, gerçekte ≤39 m).
# Çalıştırma   : Doğrudan çalıştırılmaz; testler içe aktarır.
# Entegrasyon  : -
# Sınırlar     : Kare ve bölge yapay; yalnızca kural testleri için.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Tiny hand-built datasets for rule tests (no organizer files needed)."""

import math

from arge_m.ortak.data import Dataset, Detection, Frame, Point, Report, Track, TrackPoint, Zone, bearing_deg

BASE = Point(39.92184, 32.85306)
ZONE = "Kuzeydogu Kavsagi"
CAP = 14 * 60  # 14:00
# A ~130 x 110 m frame about 2.3 km north-east of the base.
FRAME = Frame(
    image_id="img_test", capture_time="14:00", capture_min=CAP, width_px=1360, height_px=765,
    north=39.9300, south=39.9290, west=32.8700, east=32.8715, zone=ZONE,
)
SPOT = FRAME.center


def offset(p: Point, east_m: float, north_m: float) -> Point:
    return Point(
        p.lat + north_m / 111_320,
        p.lon + east_m / (111_320 * math.cos(math.radians(p.lat))),
    )


def track(track_id: str, end: Point, start_offset_m: tuple[float, float] = (0.0, 0.0), jitter_m: float = 0.0) -> Track:
    """25 points over 2 h ending at `end` at capture time, moving linearly from end + offset.

    `jitter_m` adds an alternating east-west wobble to mimic a parked vehicle's position noise.
    """
    start = offset(end, *start_offset_m)
    pts = []
    for i in range(25):
        f = i / 24
        p = Point(start.lat + f * (end.lat - start.lat), start.lon + f * (end.lon - start.lon))
        if jitter_m and i < 24:
            p = offset(p, jitter_m if i % 2 else -jitter_m, 0)
        pts.append(TrackPoint(CAP - 120 + 5 * i, p))
    return Track(track_id, pts)


def approaching(track_id: str, end: Point) -> Track:
    """Drives 6 km straight at the base (1.5 km closer every 30 min)."""
    b = math.radians(bearing_deg(BASE.lat, BASE.lon, end.lat, end.lon))
    return track(track_id, end, (6000 * math.sin(b), 6000 * math.cos(b)))


def receding(track_id: str, end: Point) -> Track:
    """Drives 2 km straight away from the base (0.5 km farther every 30 min)."""
    b = math.radians(bearing_deg(BASE.lat, BASE.lon, end.lat, end.lon))
    return track(track_id, end, (-2000 * math.sin(b), -2000 * math.cos(b)))


def coord(p: Point) -> str:
    return f"{p.lat:.5f}N {p.lon:.5f}E"


def report(text: str, source: str = "official", minute: int = CAP - 30, rid: str = "REP-01") -> Report:
    return Report(rid, f"{minute // 60:02d}:{minute % 60:02d}", minute, source, text)


def dataset(
    tracks: list[Track],
    reports: list[Report] | None = None,
    detections: list[tuple[str, Point]] | None = None,
) -> Dataset:
    ds = Dataset(
        base=BASE,
        zones=[Zone(ZONE, offset(BASE, 2263, 2263), 45.0)],
        frames={FRAME.image_id: FRAME},
        tracks={t.track_id: t for t in tracks},
        reports=reports or [],
    )
    if detections is not None:
        ds.detections = {
            FRAME.image_id: [Detection(FRAME.image_id, label, 0.9, pos) for label, pos in detections]
        }
    return ds
