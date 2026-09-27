"""Analysis endpoints.

The pipeline is deterministic and fast (no LLM yet), so POST runs it synchronously.
TODO(P2): run as a background task and stream GET /analyses/{id}/events over SSE.
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.agent.pipeline import run_analysis
from app.agent.store import AnalysisStore
from app.api.deps import (
    get_detector,
    get_fallback_detector,
    get_repository,
    get_store,
    get_tuning,
)
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.data.repository import Repository
from app.domain.analysis import Analysis, AnalysisCreate, AnalysisCreated
from app.domain.tuning import AgentTuning
from app.services.detection import Detector
from app.services.tuning import tuning_hash

router = APIRouter(tags=["analyses"])


@router.post("/analyses", response_model=AnalysisCreated)
def create_analysis(
    body: AnalysisCreate,
    repo: Annotated[Repository, Depends(get_repository)],
    detector: Annotated[Detector, Depends(get_detector)],
    fallback: Annotated[Detector, Depends(get_fallback_detector)],
    store: Annotated[AnalysisStore, Depends(get_store)],
    settings: Annotated[Settings, Depends(get_settings)],
    tuning: Annotated[AgentTuning, Depends(get_tuning)],
) -> AnalysisCreated:
    """Analyze one frame (reuses the latest result unless `force_refresh`)."""
    key = tuning_hash(tuning)
    cached = None if body.force_refresh else store.latest_for(body.image_id, key)
    if cached is not None:
        return AnalysisCreated(analysis_id=cached.id)
    analysis = run_analysis(
        store.new_id(),
        body.image_id,
        repo,
        detector,
        settings,
        fallback_detector=fallback,
        tuning=tuning,
    )
    store.put(analysis, key)
    return AnalysisCreated(analysis_id=analysis.id)


@router.get("/analyses/{analysis_id}", response_model=Analysis)
def get_analysis(analysis_id: str, store: Annotated[AnalysisStore, Depends(get_store)]) -> Analysis:
    """Return a finished analysis."""
    analysis = store.get(analysis_id)
    if analysis is None:
        raise NotFoundError(f"analysis {analysis_id} not found")
    return analysis
