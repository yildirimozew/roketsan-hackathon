"""Run the real pipeline on the mock dataset and write frontend mock fixtures.

Writes frontend/src/mocks/<image_id>.analysis.json for the demo frames and copies their images to
frontend/public/mock-images/ (gitignored), so VITE_USE_MOCKS=true shows real pipeline output.

Usage: uv run python -m scripts.build_mock_fixture [--data data/stage2_mock]
"""

import argparse
import shutil
from pathlib import Path

from app.agent.pipeline import run_analysis
from app.core.config import REPO_DIR, Settings
from app.data.repository import Repository
from app.services.detection import PrecomputedDetector

DEMO_FRAMES = ("img_000860", "img_001204", "img_000517", "img_000412")
MOCKS = REPO_DIR / "frontend" / "src" / "mocks"
MOCK_IMAGES = REPO_DIR / "frontend" / "public" / "mock-images"


def main() -> None:
    """Analyze each demo frame and write its fixture."""
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=REPO_DIR / "data" / "stage2_mock")
    args = ap.parse_args()

    settings = Settings(
        _env_file=None,
        data_dir=args.data,
        detections_file=args.data / "detections.json",
    )
    repo = Repository(settings.data_dir)
    detector = PrecomputedDetector(settings.detections_file, settings.detect_conf_min)
    MOCKS.mkdir(parents=True, exist_ok=True)
    MOCK_IMAGES.mkdir(parents=True, exist_ok=True)
    for old in MOCKS.glob("*.analysis.json"):
        old.unlink()

    for image_id in DEMO_FRAMES:
        analysis = run_analysis(f"mock-{image_id}", image_id, repo, detector, settings)
        (MOCKS / f"{image_id}.analysis.json").write_text(
            analysis.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        shutil.copy(repo.image_path(image_id), MOCK_IMAGES / f"{image_id}.jpg")
        brief = analysis.brief
        print(f"{image_id}: {brief.level if brief else '-'} · {brief.headline if brief else ''}")


if __name__ == "__main__":
    main()
