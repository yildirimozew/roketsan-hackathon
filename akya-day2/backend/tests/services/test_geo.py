import pytest

from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.services.geo import (
    angle_diff_deg,
    bearing_deg,
    haversine_m,
    latlon_to_pixel,
    offset_m,
    pixel_to_latlon,
    to_enu_m,
)

TL, BR = LatLon(lat=39.925651, lon=32.870729), LatLon(lat=39.925045, lon=32.872131)
META = ImageMeta(
    image_id="img_000860",
    width_px=960,
    height_px=540,
    capture_time="14:10",
    capture_min=850,
    corners={
        "tl": TL,
        "tr": LatLon(lat=TL.lat, lon=BR.lon),
        "br": BR,
        "bl": LatLon(lat=BR.lat, lon=TL.lon),
    },
)


def test_pixel_to_latlon_matches_case_brief() -> None:
    p = pixel_to_latlon(756, 301, META)
    assert (p.lat, p.lon) == pytest.approx((39.92531, 32.87183), abs=1e-5)


@pytest.mark.parametrize("px", [(0, 0), (960, 540), (756, 301), (100, 480)])
def test_latlon_to_pixel_inverts_mapping(px: tuple[float, float]) -> None:
    assert latlon_to_pixel(pixel_to_latlon(*px, META), META) == pytest.approx(px, abs=1e-3)


def test_haversine_one_degree_latitude() -> None:
    assert haversine_m(LatLon(lat=39, lon=32), LatLon(lat=40, lon=32)) == pytest.approx(
        111_195, rel=1e-3
    )


@pytest.mark.parametrize(("dlat", "dlon", "expected"), [(1, 0, 0), (0, 1, 90), (-1, 0, 180)])
def test_bearing_cardinal(dlat: float, dlon: float, expected: float) -> None:
    o = LatLon(lat=39.9, lon=32.8)
    target = LatLon(lat=o.lat + dlat * 0.01, lon=o.lon + dlon * 0.01)
    assert bearing_deg(o, target) == pytest.approx(expected, abs=0.5)


def test_angle_diff_wraps() -> None:
    assert angle_diff_deg(350, 10) == 20
    assert angle_diff_deg(0, 180) == 180


def test_enu_round_trip() -> None:
    o = LatLon(lat=39.92184, lon=32.85306)
    p = offset_m(o, 1603, 386)
    assert to_enu_m(o, p) == pytest.approx((1603, 386), abs=1e-6)
