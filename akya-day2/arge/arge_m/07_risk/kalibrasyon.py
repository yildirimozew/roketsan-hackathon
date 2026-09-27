# ============================================================
# AR-GE ID     : R7.1, R7.2, R7.3
# Başlık       : Risk puanı kalibrasyonu: duraklama, dolanma, mesafe kademeleri
# Akış adımı   : 7 – score_risk (risk puanı)
# Durum        : prototip (ölçüm kodu test edildi; önerilen ağırlıklar tartışmaya açık)
# Amaç         : Hangi risk faktörünün gerçek veride ne sıklıkla devreye girdiğini ölçmek ve
#                ayırt etmeyen faktörleri daraltmak.
# Kanıt        : Şu anki "üs yakınında duraklama" kuralı 226 izin 206'sında puan veriyor.
#                Hiçbir aracın son konumu üsse 1553 m'den yakın değil → "<1 km: 30 puan" hiç
#                çalışmıyor. >270° dolanan 5 iz puan almıyor.
# Çalıştırma   : arge/ klasöründen: python -m arge_m.risk.kalibrasyon
# Entegrasyon  : backend/app/services/risk.py:motion_factors ve distance_factor
#                (services/watch.py:track_rubric de aynı fonksiyonları kullanıyor).
# Sınırlar     : Duruş hesabı backend'in find_stops mantığının sadeleştirilmiş bir kopyası
#                (aynı 206 sonucunu veriyor). Önerilen puanlar etiketli veri olmadan ayarlandı;
#                "doğru" risk seviyesi için elde referans yok.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Measure how often each risk factor fires on the real day, today vs the proposals."""

from dataclasses import dataclass

from ..hareket_analizi.hareket import LOOP_SWEEP_DEG, sweep_deg
from ..ortak.data import Dataset, Point, Track, load_dataset

# Backend today (services/risk.py): a stop >= 20 min anywhere within 6 km scores 10-15 points.
CURRENT_STOP_MIN, CURRENT_STOP_NEAR_M = 20, 6000.0
STOP_SPEED_MS = 1.0  # backend default SENTINEL_STOP_SPEED_MS
# Proposal: only a vehicle that drove in (>= 500 m before stopping) and is stopped *now* close to the base.
PROPOSED_STOP_MIN, PROPOSED_STOP_NEAR_M, ARRIVED_MIN_PATH_M = 20, 3000.0, 500.0
DISTANCE_TIERS_NOW = ((1000, 30), (2000, 20), (4000, 10))
DISTANCE_TIERS_PROPOSED = ((2000, 25), (3000, 15), (4000, 5))  # the day's vehicles end 1.55-6 km out
CIRCLING_POINTS = 20


@dataclass(frozen=True)
class Stop:
    start_idx: int
    end_idx: int  # inclusive
    duration_min: int
    dist_to_base_m: float


def stops(track: Track, base: Point) -> list[Stop]:
    """Runs of 5-min steps slower than STOP_SPEED_MS lasting >= 10 min (3+ samples).

    Duration counts sample slots (k samples -> 5k min), like backend services/motion.py.
    """
    out: list[Stop] = []
    pts, run_start = track.points, 0
    for i in range(1, len(pts) + 1):
        slow = i < len(pts) and pts[i - 1].pos.dist_m(pts[i].pos) / 300 < STOP_SPEED_MS
        if not slow:
            if i - run_start >= 3:
                out.append(Stop(run_start, i - 1, min(5 * (i - run_start), 120),
                                pts[run_start].pos.dist_m(base)))
            run_start = i
    return out


def current_stop_rule(track: Track, base: Point) -> bool:
    return any(s.duration_min >= CURRENT_STOP_MIN and s.dist_to_base_m <= CURRENT_STOP_NEAR_M
               for s in stops(track, base))


def proposed_stop_rule(track: Track, base: Point) -> bool:
    """Drove in, then has been stopped for >= 20 min until now, within 3 km of the base."""
    found = stops(track, base)
    if not found or found[-1].end_idx != len(track.points) - 1:
        return False
    last = found[-1]
    driven = sum(a.pos.dist_m(b.pos) for a, b in zip(track.points[: last.start_idx + 1], track.points[1: last.start_idx + 1]))
    return (last.duration_min >= PROPOSED_STOP_MIN and last.dist_to_base_m <= PROPOSED_STOP_NEAR_M
            and driven >= ARRIVED_MIN_PATH_M)


def distance_points(dist_m: float, tiers: tuple[tuple[int, int], ...]) -> int:
    return next((pts for limit, pts in tiers if dist_m < limit), 0)


def firing_table(ds: Dataset) -> dict[str, int]:
    """How many of the day's tracks each factor gives points to (on the track's final position)."""
    tracks = list(ds.tracks.values())
    end_d = [t.end.pos.dist_m(ds.base) for t in tracks]
    return {
        "tracks": len(tracks),
        "stop_now": sum(current_stop_rule(t, ds.base) for t in tracks),
        "stop_proposed": sum(proposed_stop_rule(t, ds.base) for t in tracks),
        "circling_proposed": sum(sweep_deg(t, ds.base) > LOOP_SWEEP_DEG for t in tracks),
        "distance_30pt_now": sum(distance_points(d, DISTANCE_TIERS_NOW) == 30 for d in end_d),
        "distance_any_now": sum(distance_points(d, DISTANCE_TIERS_NOW) > 0 for d in end_d),
        "distance_top_proposed": sum(distance_points(d, DISTANCE_TIERS_PROPOSED) == 25 for d in end_d),
        "closest_end_m": round(min(end_d)),
    }


def main() -> None:
    ds = load_dataset()
    table = firing_table(ds)
    n = table["tracks"]
    print(f"{'factor':28} tracks it scores (of {n})")
    for key, value in table.items():
        if key not in ("tracks", "closest_end_m"):
            print(f"{key:28} {value:4}  ({value / n:.0%})")
    print(f"closest final position to the base: {table['closest_end_m']} m")
    flagged = sorted(t.track_id for t in ds.tracks.values() if proposed_stop_rule(t, ds.base))
    print("proposed stop rule flags:", flagged)


if __name__ == "__main__":
    main()
