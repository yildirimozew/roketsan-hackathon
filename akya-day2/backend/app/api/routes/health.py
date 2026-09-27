"""Liveness and dependency status."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app import __version__
from app.agent.llm_client import llm_status
from app.api.deps import get_detector
from app.core.config import Settings, get_settings
from app.data.repository import data_status
from app.domain.health import ComponentStatus, Health
from app.services.detection import Detector

router = APIRouter(tags=["health"])


@router.get("/health", response_model=Health)
def get_health(
    settings: Annotated[Settings, Depends(get_settings)],
    detector: Annotated[Detector, Depends(get_detector)],
) -> Health:
    """Report API liveness and LLM / detector / data availability."""
    llm_ok, llm_detail = llm_status(settings)
    det_ok, det_detail = detector.is_ready()
    data_ok, data_detail = data_status(settings.data_dir)
    return Health(
        version=__version__,
        llm=ComponentStatus(available=llm_ok, detail=llm_detail),
        detector=ComponentStatus(available=det_ok, detail=f"{detector.name}: {det_detail}"),
        data=ComponentStatus(available=data_ok, detail=data_detail),
    )
