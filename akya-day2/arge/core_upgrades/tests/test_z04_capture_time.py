from app.data.repository import Repository
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.services.geo import haversine_m
from app.services.reports import extract_claim, parse_coordinates
from app.services.tracks import match_detections, tracks_at

from core_upgrades.tests.conftest import located_detection, report
from core_upgrades.z04_capture_time import (
    frame_for,
    is_relevant_at_capture,
    reports_near_at_capture,
    verify_at_capture,
)


def test_every_located_report_belongs_to_one_frame_captured_after_it(
    repo: Repository, images: list[ImageMeta]
) -> None:
    located = [(r, p) for r in repo.reports if (p := parse_coordinates(r.text))]
    assert len(located) == 72
    for r, p in located:
        frame = frame_for(p, images)
        assert frame is not None, r.report_id
        assert 0 <= frame.capture_min - r.time_min <= 120, r.report_id


def test_reports_describe_the_vehicle_at_capture_time(
    repo: Repository, images: list[ImageMeta]
) -> None:
    at_capture = 0
    for r in repo.reports:
        p = parse_coordinates(r.text)
        if p is None:
            continue
        cap = frame_for(p, images).capture_min  # type: ignore[union-attr]
        near = [
            q
            for q in tracks_at(list(repo.tracks.values()), cap).values()
            if haversine_m(p, q) <= 15
        ]
        at_capture += bool(near)
    assert at_capture >= 60  # vs 17 at the report's own time


def test_consistent_friendly_reports_are_no_longer_contradicted(
    repo: Repository, images: list[ImageMeta]
) -> None:
    for rid in ("REP-06", "REP-78", "REP-120"):
        claim = extract_claim(report(repo, rid), repo.scene.zones)
        meta = frame_for(claim.location, images)  # type: ignore[arg-type]
        assert meta is not None and is_relevant_at_capture(claim, meta, images)
        result = verify_at_capture(claim, meta, [], [], repo.tracks, detector_available=False)
        assert result.verdict != "CONTRADICTED", (rid, result.checks)
        assert any(c.name == "presence" and c.status == "match" for c in result.checks)


def test_golden_heavy_vehicle_report_is_corroborated_by_the_truck(
    repo: Repository, base: LatLon
) -> None:
    meta = repo.get_image_meta("img_000860")
    truck = located_detection(1, "truck", (727, 284, 58, 34), meta, base)
    positions = tracks_at(list(repo.tracks.values()), meta.capture_min)
    matches = match_detections([truck], positions, 25.0)
    claim = extract_claim(report(repo, "REP-126"), repo.scene.zones)
    result = verify_at_capture(claim, meta, [truck], matches, repo.tracks)
    assert result.verdict == "CORROBORATED", result.checks
    assert result.linked_detection_ids == ["DET-1"]


def test_watch_mode_report_is_pending_until_its_frame_is_captured(
    repo: Repository, images: list[ImageMeta]
) -> None:
    claim = extract_claim(report(repo, "REP-120"), repo.scene.zones)  # 12:25, frame at 14:10
    point: LatLon = claim.location  # type: ignore[assignment]
    tracks = list(repo.tracks.values())
    before = reports_near_at_capture([claim], point, 300, 0, 13 * 60, tracks, images)
    after = reports_near_at_capture([claim], point, 300, 0, 14 * 60 + 10, tracks, images)
    assert before[0].nearest_track_id is None  # awaiting frame
    assert after[0].nearest_track_id == "T0192"
    assert after[0].nearest_track_m is not None and after[0].nearest_track_m <= 5
