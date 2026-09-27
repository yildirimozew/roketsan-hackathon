# ============================================================
# AR-GE ID     : R5.1, R5.2, R5.3
# Başlık       : Duruş eşiği, üs çevresinde dolanma ve izin tamamından hız/yön
# Akış adımı   : 5 – analyze_motion (hareket analizi)
# Durum        : test edildi
# Amaç         : (R5.1) "hareketsiz" eşiğini veriden türetmek; (R5.2) üssün etrafında dönen
#                araçları açı taraması (sweep) ile bulmak; (R5.3) hız ve yönü tek adımdan değil,
#                bir pencereden okumak (görev tanımı kuralı).
# Kanıt        : Park hâlindeki izler 60 dk'da en fazla 39 m kayıyor, diğer tüm izler en az 400 m
#                gidiyor → eşik 100 m. Tarama >90°: 45 iz, >270°: 5 iz (T0172 549°, T0034 544°).
# Çalıştırma   : arge/ klasöründen: python -m arge_m.hareket_analizi.hareket
# Entegrasyon  : backend/app/services/motion.py (MotionProfile'a sweep_deg ve pencere hızı eklemek);
#                sweep zaten services/watch.py:behavior_class içinde var (LOOP_SWEEP_DEG = 270)
#                ama risk puanına girmiyor (bkz. R7.2).
# Sınırlar     : İz 2 saatle sınırlı; tarama, pencere başındaki açıya göre ölçülür. 5 dk'lık
#                örneklemede ~5 m titreşim var; kısa pencerelerde hız gürültülü olabilir.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Motion measurements that the R&D proposals rely on (stationary threshold, circling, speed)."""

from ..ortak.data import Dataset, Point, Track, bearing_deg, load_dataset

STATIONARY_MAX_M = 100.0  # same value as rapor_degerlendirme.claims; see drift_gap() for the evidence
LOOP_SWEEP_DEG = 270.0  # same threshold as backend services/watch.py


def drift_m(track: Track, window_min: int) -> float:
    """Largest distance from the final position during the last `window_min` minutes."""
    start = track.end.minute - window_min
    return max(p.pos.dist_m(track.end.pos) for p in track.points if p.minute >= start)


def sweep_deg(track: Track, base: Point) -> float:
    """Largest cumulative bearing change around the base (degrees; 360 = one full loop)."""
    bearings = [bearing_deg(base.lat, base.lon, p.pos.lat, p.pos.lon) for p in track.points]
    unwrapped = peak = 0.0
    for a, b in zip(bearings, bearings[1:]):
        unwrapped += (b - a + 180) % 360 - 180
        peak = max(peak, abs(unwrapped))
    return peak


def window_speed_heading(track: Track, window_min: int = 30) -> tuple[float, float, float | None]:
    """(path speed m/s, net speed m/s, net heading deg or None) over the last `window_min`.

    Net values use start and end of the window, so a stop-and-go vehicle is not judged by one step.
    """
    pts = [p for p in track.points if p.minute >= track.end.minute - window_min]
    secs = max(1, (pts[-1].minute - pts[0].minute) * 60)
    path = sum(a.pos.dist_m(b.pos) for a, b in zip(pts, pts[1:]))
    net = pts[0].pos.dist_m(pts[-1].pos)
    heading = (
        bearing_deg(pts[0].pos.lat, pts[0].pos.lon, pts[-1].pos.lat, pts[-1].pos.lon)
        if net >= STATIONARY_MAX_M else None
    )
    return path / secs, net / secs, heading


def drift_gap(ds: Dataset, window_min: int = 60) -> tuple[float, float]:
    """(largest drift below 100 m, smallest drift above it): the gap the threshold sits in."""
    drifts = [drift_m(t, window_min) for t in ds.tracks.values()]
    return max(d for d in drifts if d < STATIONARY_MAX_M), min(d for d in drifts if d >= STATIONARY_MAX_M)


def circlers(ds: Dataset, min_sweep: float = LOOP_SWEEP_DEG) -> list[tuple[str, float]]:
    """Tracks sweeping more than `min_sweep` degrees around the base, largest first."""
    found = [(t.track_id, sweep_deg(t, ds.base)) for t in ds.tracks.values()]
    return sorted(((tid, s) for tid, s in found if s > min_sweep), key=lambda x: -x[1])


def main() -> None:
    ds = load_dataset()
    below, above = drift_gap(ds)
    print(f"60-min drift: parked tracks <= {below:.0f} m, all others >= {above:.0f} m "
          f"-> STATIONARY_MAX_M = {STATIONARY_MAX_M:.0f} m sits in the gap")
    for s in (90, 180, 270):
        print(f"tracks sweeping > {s} deg around the base: {len(circlers(ds, s))}")
    print("circling (> 270 deg):", [(tid, round(s)) for tid, s in circlers(ds)])


if __name__ == "__main__":
    main()
