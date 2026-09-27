# ============================================================
# AR-GE ID     : TEST R3.1, R3.2
# Başlık       : Organizatör formülü altın testi ve GeoJSON eksen sırası
# Akış adımı   : 3 – georeference
# Durum        : test edildi
# Amaç         : Görev tanımındaki uçtan uca örneği ve GeoJSON'daki [boylam, enlem] sırasını sabitlemek.
# Kanıt        : 1360×765, piksel (640, 394) → (39.94439, 32.86350); img_000860 → T0122 < 1 m.
# Çalıştırma   : arge/ klasöründen: python -m pytest arge_m/tests/test_konum.py -q
# Entegrasyon  : backend/tests/services/test_geo.py'ye eklenebilecek altın test.
# Sınırlar     : img_000123 gerçek veride yok; köşeler görev tanımından elle verilir.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Tests for arge_m.konumlandirma.konum."""

import pytest

from arge_m.konumlandirma.konum import pixel_to_latlon, to_geojson
from arge_m.ortak.data import DEFAULT_DATA_DIR, load_dataset


def test_organizer_worked_example_from_the_task_definition():
    """gorev_tanimi 'Uctan uca ornek': box (610, 380, 60, 28) -> centre (640, 394) -> 39.94439, 32.86350."""
    x, y, w, h = 610, 380, 60, 28
    p = pixel_to_latlon(
        x + w / 2, y + h / 2, 1360, 765,
        top_left=(39.94510, 32.86200), top_right=(39.94510, 32.86519), bottom_left=(39.94373, 32.86200),
    )
    assert p.lat == pytest.approx(39.94439, abs=5e-6)
    assert p.lon == pytest.approx(32.86350, abs=5e-6)
    # The example's T0187 point (39.94441, 32.86353) is ~2.5 m away: inside any sensible gate.
    assert 2.0 < p.dist_m(type(p)(39.94441, 32.86353)) < 3.5


def test_top_left_pixel_is_the_top_left_corner():
    p = pixel_to_latlon(0, 0, 960, 540, (39.9, 32.8), (39.9, 32.9), (39.8, 32.8))
    assert (p.lat, p.lon) == (39.9, 32.8)


@pytest.mark.skipif(not (DEFAULT_DATA_DIR / "zones.json").exists(), reason="organizer data not in data/")
def test_geojson_uses_lon_lat_order():
    ds = load_dataset()
    gj = to_geojson(ds)
    base = next(f for f in gj["features"] if f["properties"]["kind"] == "base")
    assert base["geometry"]["coordinates"] == [round(ds.base.lon, 6), round(ds.base.lat, 6)]
    kinds = [f["properties"]["kind"] for f in gj["features"]]
    assert kinds.count("frame") == 40 and kinds.count("track") == 226 and kinds.count("report") == 72
    frame = next(f for f in gj["features"] if f["properties"]["kind"] == "frame")
    ring = frame["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]  # closed ring
    assert all(32 < lon < 33 and 39 < lat < 40 for lon, lat in ring)
