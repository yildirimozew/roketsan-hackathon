"""The frontend mocks must stay valid against the backend contract."""

import pytest

from app.core.config import REPO_DIR
from app.domain import Analysis

MOCKS = sorted((REPO_DIR / "frontend" / "src" / "mocks").glob("*.analysis.json"))


def test_mocks_exist() -> None:
    assert {p.name.split(".")[0] for p in MOCKS} >= {"img_000860"}


@pytest.mark.parametrize("path", MOCKS, ids=lambda p: p.name)
def test_mock_analysis_matches_domain_model(path: object) -> None:
    analysis = Analysis.model_validate_json(path.read_bytes())  # type: ignore[attr-defined]
    assert len(analysis.steps) == 8
    assert analysis.brief is not None and analysis.scene is not None
