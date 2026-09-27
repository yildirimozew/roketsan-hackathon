from app.data.repository import Repository
from app.domain.geo import LatLon
from app.domain.track import Track, TrackPoint

from core_upgrades.z03_stationary import (
    STATIONARY_MAX_M,
    closing_m,
    drift_gap,
    is_moving,
    is_stationary,
)


def _track(points: list[tuple[int, float, float]]) -> Track:
    return Track(
        track_id="T9999",
        points=[
            TrackPoint(
                time=f"{m // 60:02d}:{m % 60:02d}", time_min=m, position=LatLon(lat=lat, lon=lon)
            )
            for m, lat, lon in points
        ],
    )


def test_threshold_sits_in_the_real_data_gap(repo: Repository) -> None:
    below, above = drift_gap(list(repo.tracks.values()))
    assert below < 50 < STATIONARY_MAX_M < 1000 < above


def test_jitter_is_stationary_and_a_slow_crawl_is_not() -> None:
    jitter = _track([(600 + 5 * i, 39.9 + (i % 2) * 2e-5, 32.8) for i in range(13)])  # ~2 m wobble
    crawl = _track([(600 + 5 * i, 39.9 + i * 2e-3, 32.8) for i in range(13)])  # ~220 m per step
    assert is_stationary(jitter, 660) is True and is_moving(jitter, 660) is False
    assert is_stationary(crawl, 660) is False and is_moving(crawl, 660) is True
    assert is_stationary(crawl, 900) is None  # outside the track: no data, not "stationary"


def test_closing_is_positive_toward_the_base() -> None:
    base = LatLon(lat=39.9, lon=32.8)
    inbound = _track([(600 + 5 * i, 39.95 - i * 2e-3, 32.8) for i in range(13)])
    assert (closing_m(inbound, 660, base) or 0) > 1000
