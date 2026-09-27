"""Shared FastAPI dependencies (singletons built once per process)."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.agent.llm_client import ChatLLM, build_llm
from app.agent.store import AnalysisStore
from app.agent.tuning_store import TuningStore
from app.agent.watch.store import WatchRunStore
from app.core.config import get_settings
from app.data.repository import Repository
from app.domain.tuning import AgentTuning
from app.services.detection import Detector, build_detector, build_fallback_detector


@lru_cache
def get_detector() -> Detector:
    """Detector singleton; model weights load once."""
    return build_detector(get_settings())


@lru_cache
def get_fallback_detector() -> Detector:
    """Precomputed detections used when the live detector fails mid-analysis."""
    return build_fallback_detector(get_settings())


@lru_cache
def get_repository() -> Repository:
    """Data pool loaded once; raises DataUnavailableError (503) while files are missing."""
    return Repository(get_settings().data_dir)


@lru_cache
def get_store() -> AnalysisStore:
    """In-memory analysis store."""
    return AnalysisStore()


@lru_cache
def get_llm() -> ChatLLM | None:
    """GLM client singleton, or None without an API key (agents then use their fallbacks)."""
    return build_llm(get_settings())


@lru_cache
def get_watch_store() -> WatchRunStore:
    """In-memory watch runs."""
    return WatchRunStore()


@lru_cache
def get_tuning_store() -> TuningStore:
    """Admin override file under the cache dir."""
    return TuningStore(get_settings().cache_dir / "admin_overrides.json")


def get_tuning(store: Annotated[TuningStore, Depends(get_tuning_store)]) -> AgentTuning:
    """Tuning snapshot for one request (defaults if the file is unusable)."""
    return store.load()[0]
