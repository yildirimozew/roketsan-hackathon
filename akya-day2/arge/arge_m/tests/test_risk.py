# ============================================================
# AR-GE ID     : TEST R7.1, R7.2, R7.3
# Başlık       : Risk faktörlerinin gerçek veride devreye girme sıklığı
# Akış adımı   : 7 – score_risk
# Durum        : test edildi
# Amaç         : Ölçüm kodunun backend kuralını birebir yeniden ürettiğini (206/226) ve önerilerin
#                ayırt edici kaldığını sabitlemek.
# Kanıt        : Şu anki duraklama kuralı 206/226; önerilen 7/226; en yakın son konum 1553 m.
# Çalıştırma   : arge/ klasöründen: python -m pytest arge_m/tests/test_risk.py -q
# Entegrasyon  : backend/tests/services/test_reports_risk.py'ye kalibrasyon testi olarak eklenebilir.
# Sınırlar     : Gerçek veri testleri data/ yoksa atlanır.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Tests for arge_m.risk.kalibrasyon."""

import pytest

from arge_m.ortak.data import DEFAULT_DATA_DIR, load_dataset
from arge_m.risk.kalibrasyon import current_stop_rule, firing_table, proposed_stop_rule
from arge_m.tests.synth import BASE, SPOT, approaching, offset, track

real_data = pytest.mark.skipif(not (DEFAULT_DATA_DIR / "tracks.csv").exists(), reason="organizer data not in data/")


def test_parked_all_window_is_not_an_arrival():
    parked = track("P1", offset(BASE, 1500, 1500), jitter_m=10)
    assert current_stop_rule(parked, BASE)  # today: any long stop within 6 km scores
    assert not proposed_stop_rule(parked, BASE)  # proposal: it never drove in


def test_driving_in_and_stopping_near_the_base_is_flagged():
    near = offset(BASE, 1500, 1500)
    t = approaching("T1", near)
    # Freeze the last 30 min at the final position: drove ~4.5 km in, then stopped.
    for i in range(18, 25):
        t.points[i] = type(t.points[i])(t.points[i].minute, near)
    assert proposed_stop_rule(t, BASE)


def test_moving_vehicle_has_no_stop():
    assert not proposed_stop_rule(approaching("T1", SPOT), BASE)


@real_data
def test_firing_rates_on_the_real_day():
    table = firing_table(load_dataset())
    assert table["tracks"] == 226
    assert table["stop_now"] == 206  # reproduces backend services/risk.py
    assert table["stop_proposed"] <= 10
    assert table["circling_proposed"] == 5
    assert table["distance_30pt_now"] == 0  # no vehicle ends within 1 km
    assert table["closest_end_m"] == 1553
