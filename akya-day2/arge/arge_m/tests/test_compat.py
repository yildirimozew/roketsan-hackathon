# ============================================================
# AR-GE ID     : TEST R6.11 + uyumluluk
# Başlık       : arge_m ile SENTINEL backend arasında veri, geo ve model uyumu
# Akış adımı   : 1, 3, 6
# Durum        : test edildi
# Amaç         : Aynı dosyaları iki yükleyicinin aynı okuduğunu, geo fonksiyonlarının aynı sonucu
#                verdiğini ve adaptörün 137 rapor için geçerli backend modeli ürettiğini sabitlemek.
# Kanıt        : 40 kare, 226 iz × 25 nokta, 137 rapor; görev tanımı örneği (640, 394) → 39.94439, 32.86350.
# Çalıştırma   : arge/ klasöründen: python -m pytest arge_m/tests/test_compat.py -q
# Entegrasyon  : backend salt okunur içe aktarılır (backend/ sys.path'in SONUNA eklenir).
# Sınırlar     : Backend bağımlılıkları (pydantic) yoksa ya da data/ yoksa atlanır.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Compatibility tests between arge_m and the SENTINEL backend (backend used read-only)."""

import sys

import pytest

from arge_m.compat import BACKEND_DIR, to_backend_assessment, to_backend_claim, verdict
from arge_m.ortak.data import DEFAULT_DATA_DIR, bearing_deg, haversine_m, load_dataset
from arge_m.rapor_degerlendirme.admiralty import rate_all
from arge_m.rapor_degerlendirme.claims import check_all

pytest.importorskip("pydantic")
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))
pytestmark = pytest.mark.skipif(not (DEFAULT_DATA_DIR / "tracks.csv").exists(), reason="organizer data not in data/")


@pytest.fixture(scope="module")
def both():
    from app.data.repository import Repository

    return load_dataset(), Repository(DEFAULT_DATA_DIR)


def test_data_parity(both):
    ds, repo = both
    assert (len(ds.frames), len(ds.tracks), len(ds.reports)) == (len(repo.images), len(repo.tracks), len(repo.reports)) == (40, 226, 137)
    assert all(len(t.points) == 25 for t in ds.tracks.values())
    for image_id, f in ds.frames.items():
        m = repo.images[image_id]
        assert (f.capture_time, f.capture_min, f.width_px, f.height_px) == (m.capture_time, m.capture_min, m.width_px, m.height_px)
        # corners are [lat, lon] in both: top-left = (north, west), bottom-right = (south, east)
        assert (f.north, f.west, f.south, f.east) == (m.corners["tl"].lat, m.corners["tl"].lon, m.corners["br"].lat, m.corners["br"].lon)
        assert f.zone == m.zone
    for tid, t in ds.tracks.items():
        bt = repo.tracks[tid]
        assert [(p.minute, p.pos.lat, p.pos.lon) for p in t.points] == [(p.time_min, p.position.lat, p.position.lon) for p in bt.points]
    assert [(r.report_id, r.time, r.time_min, r.source, r.text) for r in ds.reports] == [
        (r.report_id, r.time, r.time_min, r.source, r.text) for r in repo.reports
    ]


def test_geo_parity(both):
    from app.domain.geo import LatLon
    from app.services import geo

    ds, _ = both
    points = [z.center for z in ds.zones] + [t.end.pos for t in list(ds.tracks.values())[:20]]
    b = ds.base
    for p in points:
        assert haversine_m(b.lat, b.lon, p.lat, p.lon) == pytest.approx(geo.haversine_m(LatLon(lat=b.lat, lon=b.lon), LatLon(lat=p.lat, lon=p.lon)), abs=0.5)
        assert bearing_deg(b.lat, b.lon, p.lat, p.lon) == pytest.approx(geo.bearing_deg(LatLon(lat=b.lat, lon=b.lon), LatLon(lat=p.lat, lon=p.lon)), abs=0.5)


def test_worked_example_in_both_implementations():
    from app.domain.geo import LatLon
    from app.domain.image import ImageMeta
    from app.services import geo

    from arge_m.konumlandirma.konum import pixel_to_latlon

    tl, tr, bl = (39.94510, 32.86200), (39.94510, 32.86519), (39.94373, 32.86200)
    meta = ImageMeta(image_id="img_000123", width_px=1360, height_px=765, capture_time="13:25", capture_min=805,
                     corners={"tl": LatLon(lat=tl[0], lon=tl[1]), "tr": LatLon(lat=tr[0], lon=tr[1]),
                              "bl": LatLon(lat=bl[0], lon=bl[1]), "br": LatLon(lat=bl[0], lon=tr[1])})
    backend = geo.pixel_to_latlon(640, 394, meta)
    ours = pixel_to_latlon(640, 394, 1360, 765, tl, tr, bl)
    for p in (backend, ours):
        assert p.lat == pytest.approx(39.94439, abs=5e-6) and p.lon == pytest.approx(32.86350, abs=5e-6)


def test_adapter_builds_valid_backend_models_for_all_reports(both):
    ds, _ = both
    checked = check_all(ds)
    ratings = {r.report_id: r for r in rate_all(checked)}
    verdicts = {}
    for c in checked:
        claim = to_backend_claim(c.parsed)  # pydantic validates on construction
        assessment = to_backend_assessment(c, ratings[c.report.report_id])
        assert claim.report_id == assessment.report_id == c.report.report_id
        verdicts[c.report.report_id] = assessment.verdict
    assert len(verdicts) == 137
    assert verdicts["REP-61"] == verdicts["REP-113"] == "CONTRADICTED"
    # friendly claims never come out CORROBORATED, context reports are IRRELEVANT
    for c in checked:
        if "IDENTITY" in c.parsed.categories:
            assert verdict(c) != "CORROBORATED"
        if c.parsed.categories == ["CONTEXT"]:
            assert verdicts[c.report.report_id] == "IRRELEVANT"
