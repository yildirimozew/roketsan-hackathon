"""In-memory store of finished analyses, keyed by analysis id.

TODO(P2): back with the disk cache keyed by (image_id, config_key) and per-analysis event buffers.
"""

import uuid

from app.domain.analysis import Analysis


class AnalysisStore:
    """Holds analyses for the process lifetime; latest per (image, config) for quick reuse."""

    def __init__(self) -> None:
        self._by_id: dict[str, Analysis] = {}
        self._latest: dict[tuple[str, str], str] = {}

    @staticmethod
    def new_id() -> str:
        """Short random analysis id."""
        return uuid.uuid4().hex[:12]

    def put(self, analysis: Analysis, config_key: str = "") -> None:
        """Store an analysis and mark it as the latest for its image under `config_key`."""
        self._by_id[analysis.id] = analysis
        self._latest[(analysis.image_id, config_key)] = analysis.id

    def get(self, analysis_id: str) -> Analysis | None:
        """Analysis by id, if present."""
        return self._by_id.get(analysis_id)

    def latest_for(self, image_id: str, config_key: str = "") -> Analysis | None:
        """Most recent analysis of `image_id` made with `config_key`, if any."""
        aid = self._latest.get((image_id, config_key))
        return self._by_id.get(aid) if aid else None
