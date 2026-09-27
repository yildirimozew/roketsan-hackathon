from pathlib import Path

import pytest

from app.agent.pipeline import run_analysis
from app.core.config import Settings
from app.core.errors import DetectorError
from app.data.repository import Repository
from app.domain.detection import Detection
from app.services.detection import PrecomputedDetector


class BrokenDetector:
    """Stands in for a model that fails at inference time (CUDA error, missing file...)."""

    name = "ultralytics"

    def is_ready(self) -> tuple[bool, str]:
        return True, "pretends to be fine"

    def detect(self, image_id: str, image_path: Path | None) -> list[Detection]:
        raise DetectorError("CUDA out of memory")


def test_detector_failure_falls_back_with_warning(
    golden_repo: Repository, golden_detector: PrecomputedDetector, golden_settings: Settings
) -> None:
    analysis = run_analysis(
        "fb",
        "img_000860",
        golden_repo,
        BrokenDetector(),
        golden_settings,
        fallback_detector=golden_detector,
    )
    detect = next(s for s in analysis.steps if s.step == "detect")
    assert detect.status == "warning"
    assert "CUDA out of memory" in detect.warnings[0]
    assert detect.data["detector"] == "precomputed"
    assert analysis.brief is not None and analysis.brief.level == "HIGH"


def test_detector_failure_without_fallback_raises(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    with pytest.raises(DetectorError):
        run_analysis("fb", "img_000860", golden_repo, BrokenDetector(), golden_settings)
