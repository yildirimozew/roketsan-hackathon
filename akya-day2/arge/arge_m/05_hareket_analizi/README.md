# 05_hareket_analizi — Adım 5: analyze_motion

- **R5.1** Hareketsiz eşiği 100 m (park ≤ 39 m, diğerleri ≥ 1087 m) — `hareket.py:drift_m, drift_gap`
- **R5.2** Üs çevresinde dolanma — `hareket.py:sweep_deg, circlers` (>270°: 5 iz)
- **R5.3** Pencereden hız ve yön — `hareket.py:window_speed_heading`
- Çalıştırma (arge/ klasöründen): `python -m arge_m.hareket_analizi.hareket`
- Test: `tests/test_hareket.py`
