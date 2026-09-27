# ============================================================
# AR-GE ID     : TEST R5.1, R5.2, R5.3
# Başlık       : Duruş eşiği, dolanma taraması ve pencere hızı
# Akış adımı   : 5 – analyze_motion
# Durum        : test edildi
# Amaç         : Dolanma ölçümünü yapay bir çemberle, eşik boşluğunu gerçek veriyle sabitlemek.
# Kanıt        : Park ≤ 39 m / diğerleri ≥ 400 m; >270° dolanan 5 iz (T0172 en büyük).
# Çalıştırma   : arge/ klasöründen: python -m pytest arge_m/tests/test_hareket.py -q
# Entegrasyon  : backend/tests/services/test_tracks_motion.py'ye eklenebilir.
# Sınırlar     : Gerçek veri testleri data/ yoksa atlanır.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Tests for arge_m.hareket_analizi.hareket."""

import math

import pytest

from arge_m.hareket_analizi.hareket import (
    STATIONARY_MAX_M, circlers, drift_gap, sweep_deg, window_speed_heading,
)
from arge_m.ortak.data import DEFAULT_DATA_DIR, Track, TrackPoint, load_dataset
from arge_m.tests.synth import BASE, CAP, SPOT, approaching, offset, track

real_data = pytest.mark.skipif(not (DEFAULT_DATA_DIR / "tracks.csv").exists(), reason="organizer data not in data/")


def _circle(turns: float, radius_m: float = 2000) -> Track:
    pts = []
    for i in range(25):
        a = 2 * math.pi * turns * i / 24
        pts.append(TrackPoint(CAP - 120 + 5 * i, offset(BASE, radius_m * math.sin(a), radius_m * math.cos(a))))
    return Track("C1", pts)


@pytest.mark.parametrize(("turns", "expected"), [(1.0, 360), (0.5, 180), (1.5, 540)])
def test_sweep_counts_degrees_around_the_base(turns, expected):
    assert sweep_deg(_circle(turns), BASE) == pytest.approx(expected, abs=1)


def test_straight_approach_does_not_sweep():
    assert sweep_deg(approaching("T1", SPOT), BASE) < 5


def test_window_speed_ignores_single_step_noise():
    parked = track("P1", SPOT, jitter_m=35)
    path_speed, net_speed, heading = window_speed_heading(parked)
    assert net_speed < 0.1 and heading is None  # jitter adds path, but no net movement or heading
    assert path_speed > net_speed
    _, net, heading = window_speed_heading(approaching("T1", SPOT))
    assert net == pytest.approx(1500 / 1800, rel=0.05)  # 1.5 km in 30 min
    assert heading is not None


@real_data
def test_stationary_threshold_sits_in_the_data_gap():
    below, above = drift_gap(load_dataset())
    assert below <= 40 and above >= 400
    assert below < STATIONARY_MAX_M < above


@real_data
def test_circling_tracks_on_the_real_day():
    found = circlers(load_dataset())
    assert [tid for tid, _ in found] == ["T0172", "T0034", "T0043", "T0158", "T0198"]
