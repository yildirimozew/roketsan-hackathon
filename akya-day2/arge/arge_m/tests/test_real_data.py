# ============================================================
# AR-GE ID     : TEST gerçek veri
# Başlık       : Organizatör verisi üzerinde gerileme testleri
# Akış adımı   : 3, 6
# Durum        : test edildi
# Amaç         : Gerçek günde bulunan sonuçların (çelişen rapor kümesi, altın örnek) değişmediğini denetlemek.
# Kanıt        : img_000860 → (39.92531, 32.87183), T0122 < 1 m; çelişen raporlar: REP-42, 55, 61, 68, 101, 113.
# Çalıştırma   : arge/ klasöründen: python -m pytest arge_m/tests/test_real_data.py -q
# Entegrasyon  : -
# Sınırlar     : data/ yoksa atlanır (skip).
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Regression tests on the organizer's real stage-2 files (skipped when data/ is absent)."""

import pytest

from arge_m.rapor_degerlendirme.admiralty import rate_all
from arge_m.rapor_degerlendirme.claims import check_all
from arge_m.ortak.data import DEFAULT_DATA_DIR, load_dataset

pytestmark = pytest.mark.skipif(
    not (DEFAULT_DATA_DIR / "field_reports.json").exists(), reason="organizer data not in data/"
)


@pytest.fixture(scope="module")
def ds():
    return load_dataset()


@pytest.fixture(scope="module")
def results(ds):
    return {c.report.report_id: c for c in check_all(ds)}


def test_organizer_example_img_000860(ds):
    """Slide example: truck box (727, 284, 58, 34) -> (39.92531, 32.87183), T0122 under 1 m."""
    p = ds.frames["img_000860"].pixel_to_point(727 + 58 / 2, 284 + 34 / 2)
    assert p.lat == pytest.approx(39.92531, abs=1e-5)
    assert p.lon == pytest.approx(32.87183, abs=1e-5)
    nearest = min(ds.tracks_ending_at(ds.frames["img_000860"].capture_min), key=lambda t: t.end.pos.dist_m(p))
    assert nearest.track_id == "T0122"
    assert nearest.end.pos.dist_m(p) < 1


def test_every_report_gets_a_category(results):
    assert len(results) == 137
    assert not [rid for rid, c in results.items() if c.parsed.unparsed]


def test_absence_reports_are_never_read_as_sightings(results):
    for c in results.values():
        if "agir arac hareketi yok" in c.report.text:
            assert c.parsed.categories == ["ABSENCE"], c.report.report_id


def test_friendly_reports_contradicted_by_movement(results):
    # T0075 drives away from the base (4.1 -> 5.3 km); T0124 does not close in (3.4 -> 3.5 km).
    for rid in ("REP-61", "REP-113"):
        assert results[rid].status == "CONTRADICTED"
        assert results[rid].deception_indicator
    assert [rid for rid, c in results.items() if c.deception_indicator] == ["REP-61", "REP-113"]


@pytest.mark.parametrize("rid", ["REP-10", "REP-18", "REP-87", "REP-91", "REP-94"])
def test_former_false_contradictions_stay_fixed(results, rid):
    """Multi-vehicle claims and parked-vehicle jitter used to produce these false contradictions."""
    assert results[rid].status != "CONTRADICTED"


def test_contradicted_set(results):
    assert sorted(rid for rid, c in results.items() if c.status == "CONTRADICTED") == [
        "REP-101", "REP-113", "REP-42", "REP-55", "REP-61", "REP-68",
    ]


def test_identity_reports_never_graded_better_than_3(results):
    ratings = {r.report_id: r for r in rate_all(list(results.values()))}
    for rid, c in results.items():
        if "IDENTITY" in c.parsed.categories:
            assert ratings[rid].info_grade >= 3, rid
