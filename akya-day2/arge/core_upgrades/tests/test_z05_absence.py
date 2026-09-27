from app.data.repository import Repository
from app.domain.geo import LatLon
from app.domain.image import ImageMeta

from core_fixes.tests.conftest import located_detection, report
from core_fixes.z05_absence import check_absence, extract_claim_v2, frames_for_absence


def test_negated_heavy_vehicle_is_an_absence_claim_not_a_sighting(repo: Repository) -> None:
    claim = extract_claim_v2(report(repo, "REP-92"), repo.scene.zones)
    assert claim.claim_kind == "ABSENCE"
    assert claim.absence == ["no_heavy_vehicles"] and claim.vehicle_type is None


def test_no_movement_claim_is_contradicted_by_closing_tracks(
    repo: Repository, images: list[ImageMeta], base: LatLon
) -> None:
    claim = extract_claim_v2(report(repo, "REP-42"), repo.scene.zones)
    frames = frames_for_absence(claim, images)
    assert {m.image_id for m in frames} >= {"img_001733", "img_004423"}
    verdict, checks = check_absence(claim, frames, repo.tracks, base)
    assert verdict == "CONTRADICTED"
    assert all(t in checks[0].detail for t in ("T0121", "T0125", "T0143"))


def test_no_heavy_vehicles_needs_detections_and_a_truck_contradicts_it(
    repo: Repository, images: list[ImageMeta], base: LatLon
) -> None:
    claim = extract_claim_v2(report(repo, "REP-92"), repo.scene.zones)
    frames = frames_for_absence(claim, images)
    assert frames
    assert check_absence(claim, frames, repo.tracks, base)[0] == "UNVERIFIED"
    dets = {m.image_id: [] for m in frames}
    assert check_absence(claim, frames, repo.tracks, base, dets)[0] == "CORROBORATED"
    dets[frames[0].image_id] = [located_detection(1, "truck", (100, 100, 60, 30), frames[0], base)]
    assert check_absence(claim, frames, repo.tracks, base, dets)[0] == "CONTRADICTED"


def test_usual_count_is_a_baseline_and_context_reports_carry_no_claim(repo: Repository) -> None:
    usual = [
        c
        for r in repo.reports
        if (c := extract_claim_v2(r, repo.scene.zones)).usual_count is not None
    ]
    assert usual and all(c.count != c.usual_count for c in usual)
    context = [
        c
        for r in repo.reports
        if (c := extract_claim_v2(r, repo.scene.zones)).claim_kind == "CONTEXT"
    ]
    assert context and all(c.vehicle_type is None for c in context)
