"""Shared fixtures: the live backend on sys.path and the organizer data in data/.

Run from the repo root with the backend environment:
    uv --directory backend run pytest ../arge/core_fixes/tests -q
"""

import sys
from pathlib import Path

import pytest

REPO_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_DIR / "backend"))
sys.path.insert(0, str(REPO_DIR / "arge"))

from app.data.repository import Repository  # noqa: E402
from app.domain.detection import Detection  # noqa: E402
from app.domain.geo import LatLon  # noqa: E402
from app.domain.image import ImageMeta  # noqa: E402
from app.domain.report import FieldReport  # noqa: E402
from app.services.detection.base import make_detection  # noqa: E402
from app.services.geo import bearing_deg, haversine_m, pixel_to_latlon  # noqa: E402


@pytest.fixture(scope="session")
def repo() -> Repository:
    return Repository(REPO_DIR / "data")


@pytest.fixture(scope="session")
def images(repo: Repository) -> list[ImageMeta]:
    return repo.list_images()


@pytest.fixture(scope="session")
def base(repo: Repository) -> LatLon:
    return repo.scene.base.position


def report(repo: Repository, report_id: str) -> FieldReport:
    """One raw report by id."""
    return next(r for r in repo.reports if r.report_id == report_id)


def located_detection(
    index: int, label: str, bbox: tuple[int, int, int, int], meta: ImageMeta, base: LatLon
) -> Detection:
    """A detection georeferenced the way pipeline step 3 does it."""
    d = make_detection(index, label, 0.9, bbox)
    pos = pixel_to_latlon(d.center_px[0], d.center_px[1], meta)
    return d.model_copy(
        update={
            "position": pos,
            "distance_to_base_m": round(haversine_m(base, pos)),
            "bearing_from_base_deg": round(bearing_deg(base, pos), 1),
        }
    )
