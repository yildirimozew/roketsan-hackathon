from app.data.repository import Repository
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.risk import RiskFactor, VehicleRisk
from app.services.reports import extract_claim

from core_upgrades.contracts import ReportAssessmentV2
from core_upgrades.z04_capture_time import frame_for, verify_at_capture
from core_upgrades.z06_deception import annotate, assess
from core_upgrades.z07_deception_level import apply_deception, raise_watch_level


def _assess_friendly(
    repo: Repository, images: list[ImageMeta], base: LatLon
) -> dict[str, ReportAssessmentV2]:
    out = {}
    for r in repo.reports:
        claim = annotate(extract_claim(r, repo.scene.zones))
        if not (claim.identity_claim and claim.toward_base and claim.location):
            continue
        meta = frame_for(claim.location, images)
        assert meta is not None
        result = verify_at_capture(claim, meta, [], [], repo.tracks, detector_available=False)
        out[r.report_id] = assess(claim, result, meta, repo.tracks, [], base, reason="-")
    return out


def test_only_rep61_and_rep113_are_deceptive(
    repo: Repository, images: list[ImageMeta], base: LatLon
) -> None:
    found = _assess_friendly(repo, images, base)
    assert len(found) == 15
    deceptive = {rid: a for rid, a in found.items() if a.deception_indicator}
    assert set(deceptive) == {"REP-61", "REP-113"}
    assert deceptive["REP-61"].deception_track_ids == ["T0075"]
    assert deceptive["REP-113"].deception_track_ids == ["T0124"]
    assert deceptive["REP-61"].checked_frame_id == "img_006444"
    assert all(a.trust_weight == 0 for a in deceptive.values())


def _risk(det: str, track: str, level: str, capped: bool = False) -> VehicleRisk:
    factors = [RiskFactor(name="ceiling", points=0, detail="capped")] if capped else []
    return VehicleRisk(detection_id=det, track_id=track, score=30, level=level, factors=factors)  # type: ignore[arg-type]


def test_deception_raises_the_linked_vehicle_once_and_respects_the_ceiling_switch() -> None:
    a = ReportAssessmentV2(
        report_id="REP-61",
        verdict="CONTRADICTED",
        reason="-",
        checks=[],
        linked_detection_ids=[],
        trust_weight=0.0,
        deception_indicator=True,
        deception_track_ids=["T0075"],
    )
    twice = [a, a.model_copy(update={"report_id": "REP-99"})]
    risks = [_risk("DET-1", "T0075", "MEDIUM"), _risk("DET-2", "T0001", "MEDIUM")]
    raised = apply_deception(risks, twice)
    assert [r.level for r in raised] == ["HIGH", "MEDIUM"]
    assert raised[0].factors[-1].name == "deception_indicator"
    capped = [_risk("DET-1", "T0075", "LOW", capped=True)]
    assert apply_deception(capped, [a])[0].level == "MEDIUM"
    assert apply_deception(capped, [a], exceed_ceiling=False)[0].level == "LOW"
    assert raise_watch_level("HIGH") == "HIGH" and raise_watch_level("LOW") == "MEDIUM"
