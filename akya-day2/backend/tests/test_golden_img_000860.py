"""Golden example from the case brief (AGENT_DESIGN §9). Must always pass.

Uses the committed fixture (tests/fixtures/golden) and a fixed detection; never the model.
When the real data arrives, refresh the fixture from it and these numbers must still hold.
"""

import pytest

from app.agent.pipeline import run_analysis
from app.core.config import Settings
from app.data.repository import Repository
from app.domain.analysis import Analysis
from app.services.detection import PrecomputedDetector


@pytest.fixture
def analysis(
    golden_repo: Repository, golden_detector: PrecomputedDetector, golden_settings: Settings
) -> Analysis:
    return run_analysis("golden", "img_000860", golden_repo, golden_detector, golden_settings)


def test_detection_fixture(analysis: Analysis) -> None:
    (det,) = analysis.detections
    assert det.label == "truck"
    assert det.bbox == (727, 284, 58, 34)
    assert det.center_px == (756.0, 301.0)


def test_georeference(analysis: Analysis) -> None:
    pos = analysis.detections[0].position
    assert pos is not None
    assert pos.lat == pytest.approx(39.92531, abs=1e-5)
    assert pos.lon == pytest.approx(32.87183, abs=1e-5)


def test_distance_to_base(analysis: Analysis) -> None:
    assert 1550 <= (analysis.detections[0].distance_to_base_m or 0) <= 1700


def test_track_match(analysis: Analysis) -> None:
    (match,) = analysis.matches
    assert match.track_id == "T0122"
    assert match.distance_m is not None and match.distance_m < 1
    assert match.second_best_m == pytest.approx(41, abs=2)
    assert match.second_best_track_id == "T0032"
    assert match.confidence == "high"


def test_motion(analysis: Analysis) -> None:
    (motion,) = analysis.motions
    at_1315 = next(p for p in motion.points if p.time == "13:15")
    assert at_1315 is not None
    assert motion.dist_now_m == pytest.approx(1600, abs=100)
    assert motion.approach_rate_m_per_min > 50
    assert motion.path_km == pytest.approx(10.5, abs=0.2)
    assert motion.last10_speed_ms == pytest.approx(6, abs=0.5)
    long_stops = sorted(s.duration_min for s in motion.stops if s.duration_min >= 30)
    assert long_stops == [40, 45]


def test_report_corroborated(analysis: Analysis) -> None:
    by_time = {c.time: c for c in analysis.reports}
    claim = by_time["12:35"]
    assert claim.source == "official" and claim.vehicle_type == "truck"
    verdict = next(a for a in analysis.report_assessments if a.report_id == claim.report_id)
    assert verdict.verdict == "CORROBORATED"
    checks = {c.name: c.status for c in verdict.checks}
    assert checks["location"] == "match" and checks["type"] == "match"


def test_level_and_brief(analysis: Analysis) -> None:
    assert analysis.brief is not None
    # A very fast, close approach: HIGH. CRITICAL needs more than a steady approach since the
    # rubric was recalibrated (loops/orbits are the main danger patterns, AGENT_DESIGN §3 step 7).
    assert analysis.brief.level == "HIGH"
    assert analysis.brief.recommended_action == "VERIFY"
    assert set(analysis.brief.evidence_ids) >= {"DET-1", "TRK-T0122"}
