import json
from pathlib import Path

import pytest
from app.core.errors import DetectorError
from app.data.repository import Repository
from app.domain.brief import Brief
from app.domain.geo import LatLon
from app.services import motion as motion_svc
from app.services.behavior import behavior_class
from app.services.tracks import match_detections, tracks_at

from core_upgrades.tests.conftest import located_detection
from core_upgrades.z01_detection_guard import (
    StrictPrecomputedDetector,
    detect_with_fallback,
    validate_detections_file,
)
from core_upgrades.z02_track_only import (
    explain_unmatched_detections,
    find_track_only,
    score_track_only,
)
from core_upgrades.z08_insufficient import apply_to_brief, assess_evidence


def _write(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "detections.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_missing_file_or_frame_raises_but_an_empty_frame_is_valid(tmp_path: Path) -> None:
    with pytest.raises(DetectorError):
        StrictPrecomputedDetector(tmp_path / "none.json", 0.35).detect("img_000860", None)
    det = StrictPrecomputedDetector(_write(tmp_path, {"img_000860": []}), 0.35)
    assert det.detect("img_000860", None) == []
    with pytest.raises(DetectorError):
        det.detect("img_000001", None)


def test_detect_with_fallback_never_raises(tmp_path: Path) -> None:
    missing = StrictPrecomputedDetector(tmp_path / "none.json", 0.35)
    none = detect_with_fallback(missing, missing, "img_000860", None)
    assert not none.available and none.detections == [] and none.warnings
    good = StrictPrecomputedDetector(
        _write(
            tmp_path,
            {"img_000860": [{"label": "truck", "confidence": 0.9, "bbox": [727, 284, 58, 34]}]},
        ),
        0.35,
    )
    used = detect_with_fallback(missing, good, "img_000860", None)
    assert used.available and len(used.detections) == 1 and "fallback" in used.warnings[-1]


def test_validate_detections_file_lists_problems(tmp_path: Path) -> None:
    path = _write(tmp_path, {"img_a": [{"label": "tank", "confidence": 2, "bbox": [0, 0, 0, 5]}]})
    problems = validate_detections_file(path, ["img_a", "img_b"], ["car", "van", "truck", "bus"])
    assert len(problems) == 4  # missing img_b, label, bbox, confidence


def test_undetected_looping_vehicle_still_gets_its_risk(repo: Repository, base: LatLon) -> None:
    meta = repo.get_image_meta("img_006673")
    positions = tracks_at(list(repo.tracks.values()), meta.capture_min)
    only = find_track_only(meta, positions, [])
    assert "T0043" in {v.track_id for v in only}
    v = next(v for v in only if v.track_id == "T0043")
    motion = motion_svc.motion_profile(
        repo.tracks["T0043"], meta.capture_min, base, repo.scene.zones, 1.0, 2000.0
    )
    risk = score_track_only(v, motion, base, behavior_class(motion.points, base))
    assert risk.detection_id == "TRK-T0043" and risk.level == "HIGH"
    assert risk.factors[-1].name == "not_seen_in_image"


def test_matched_tracks_are_not_track_only_and_untracked_boxes_are_explained(
    repo: Repository, base: LatLon
) -> None:
    meta = repo.get_image_meta("img_000860")
    truck = located_detection(1, "truck", (727, 284, 58, 34), meta, base)
    stray = located_detection(2, "car", (5, 5, 20, 10), meta, base).model_copy(
        update={"confidence": 0.3}
    )
    positions = tracks_at(list(repo.tracks.values()), meta.capture_min)
    matches = match_detections([truck, stray], positions, 25.0)
    assert "T0122" not in {v.track_id for v in find_track_only(meta, positions, matches)}
    notes = explain_unmatched_detections([truck, stray], matches)
    assert [(n.detection_id, n.hypothesis) for n in notes] == [("DET-2", "false_positive_likely")]


def _brief(action: str) -> Brief:
    return Brief(
        image_id="img_x",
        level="HIGH",
        headline="h",
        summary="s",
        vehicles=[],
        report_notes=[],
        uncertainties=["u"],
        recommended_action=action,
        evidence_ids=[],
        generated_by="fallback",  # type: ignore[arg-type]
    )


def test_insufficient_evidence_flags_and_raises_action_but_not_level() -> None:
    blind = assess_evidence(
        detector_available=False,
        fallback_used=False,
        in_frame_track_ids=["T1", "T2"],
        matched_track_ids=[],
        n_detections=0,
        n_track_only=2,
    )
    assert blind.insufficient_evidence and blind.reasons[0] == "no_detector"
    fine = assess_evidence(
        detector_available=True,
        fallback_used=True,
        in_frame_track_ids=["T1", "T2"],
        matched_track_ids=["T1", "T2"],
        n_detections=2,
        n_track_only=0,
    )
    assert not fine.insufficient_evidence and fine.reasons == ["fallback_detector"]
    out = apply_to_brief(_brief("MONITOR"), blind, "tr")
    assert (
        out.recommended_action == "VERIFY" and out.level == "HIGH" and len(out.uncertainties) == 2
    )
    assert apply_to_brief(_brief("ESCALATE"), blind).recommended_action == "ESCALATE"
