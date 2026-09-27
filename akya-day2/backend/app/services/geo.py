"""Georeferencing and spherical helpers. Distances in meters, angles in degrees."""

import math

from app.domain.geo import LatLon
from app.domain.image import ImageMeta

EARTH_RADIUS_M = 6_371_000.0


def haversine_m(a: LatLon, b: LatLon) -> float:
    """Great-circle distance in meters."""
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dp, dl = p2 - p1, math.radians(b.lon - a.lon)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(min(1.0, h)))


def bearing_deg(a: LatLon, b: LatLon) -> float:
    """Initial bearing from `a` to `b` in degrees clockwise from north, in [0, 360)."""
    p1, p2 = math.radians(a.lat), math.radians(b.lat)
    dl = math.radians(b.lon - a.lon)
    x = math.sin(dl) * math.cos(p2)
    y = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def angle_diff_deg(a: float, b: float) -> float:
    """Smallest absolute difference between two bearings, in [0, 180]."""
    d = abs(a - b) % 360
    return 360 - d if d > 180 else d


def to_enu_m(origin: LatLon, p: LatLon) -> tuple[float, float]:
    """Local (east, north) offset in meters of `p` from `origin` (equirectangular, < ~20 km)."""
    k = math.pi / 180 * EARTH_RADIUS_M
    return (p.lon - origin.lon) * k * math.cos(math.radians(origin.lat)), (p.lat - origin.lat) * k


def offset_m(origin: LatLon, east_m: float, north_m: float) -> LatLon:
    """Position `east_m`/`north_m` meters from `origin` (inverse of `to_enu_m`)."""
    k = math.pi / 180 * EARTH_RADIUS_M
    return LatLon(
        lat=origin.lat + north_m / k,
        lon=origin.lon + east_m / (k * math.cos(math.radians(origin.lat))),
    )


def _bilinear(meta: ImageMeta, u: float, v: float) -> tuple[float, float]:
    c = meta.corners
    tl, tr, bl, br = c["tl"], c["tr"], c["bl"], c["br"]
    top = (tl.lat + (tr.lat - tl.lat) * u, tl.lon + (tr.lon - tl.lon) * u)
    bottom = (bl.lat + (br.lat - bl.lat) * u, bl.lon + (br.lon - bl.lon) * u)
    return top[0] + (bottom[0] - top[0]) * v, top[1] + (bottom[1] - top[1]) * v


def pixel_to_latlon(x_px: float, y_px: float, meta: ImageMeta) -> LatLon:
    """Map a pixel (origin top-left, y grows southward) to lat/lon by bilinear corner mapping."""
    lat, lon = _bilinear(meta, x_px / meta.width_px, y_px / meta.height_px)
    return LatLon(lat=lat, lon=lon)


def latlon_to_pixel(p: LatLon, meta: ImageMeta) -> tuple[float, float]:
    """Inverse of `pixel_to_latlon` via Newton iteration; may fall outside the frame."""
    u, v = 0.5, 0.5
    eps = 1e-6
    for _ in range(20):
        lat, lon = _bilinear(meta, u, v)
        f_lat, f_lon = lat - p.lat, lon - p.lon
        lat_u, lon_u = _bilinear(meta, u + eps, v)
        lat_v, lon_v = _bilinear(meta, u, v + eps)
        a, b = (lat_u - lat) / eps, (lat_v - lat) / eps
        c, d = (lon_u - lon) / eps, (lon_v - lon) / eps
        det = a * d - b * c
        if det == 0:
            break
        du = (d * f_lat - b * f_lon) / det
        dv = (a * f_lon - c * f_lat) / det
        u, v = u - du, v - dv
        if abs(du) < 1e-10 and abs(dv) < 1e-10:
            break
    return u * meta.width_px, v * meta.height_px


def frame_center(meta: ImageMeta) -> LatLon:
    """Ground position of the frame's center pixel."""
    return pixel_to_latlon(meta.width_px / 2, meta.height_px / 2, meta)


def frame_size_m(meta: ImageMeta) -> tuple[float, float]:
    """Ground width (top edge) and height (left edge) of the frame in meters."""
    c = meta.corners
    return haversine_m(c["tl"], c["tr"]), haversine_m(c["tl"], c["bl"])


def in_frame(x_px: float, y_px: float, meta: ImageMeta) -> bool:
    """True when the pixel lies inside the image bounds."""
    return 0 <= x_px <= meta.width_px and 0 <= y_px <= meta.height_px
