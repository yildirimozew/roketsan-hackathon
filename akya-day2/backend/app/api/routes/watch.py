"""Watch mode endpoints (docs/AGENT_PROMPTS_AND_TOOLS.md §8)."""

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.agent.llm_client import ChatLLM
from app.agent.watch.recordings import list_recordings, load_recording
from app.agent.watch.store import WatchRun, WatchRunStore
from app.api.deps import get_detector, get_llm, get_repository, get_tuning, get_watch_store
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.core.timefmt import to_minutes
from app.data.repository import Repository
from app.domain.tuning import AgentTuning
from app.domain.watch import (
    WatchEvent,
    WatchRecording,
    WatchRunCreate,
    WatchRunCreated,
    WatchRunStatus,
    event_payload,
)
from app.services.detection import Detector

router = APIRouter(tags=["watch"])


def _run(store: WatchRunStore, run_id: str) -> WatchRun:
    run = store.get(run_id)
    if run is None:
        raise NotFoundError(f"watch run {run_id} not found")
    return run


@router.post("/watch/runs", response_model=WatchRunCreated)
async def create_run(
    body: WatchRunCreate,
    repo: Annotated[Repository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    llm: Annotated[ChatLLM | None, Depends(get_llm)],
    detector: Annotated[Detector, Depends(get_detector)],
    store: Annotated[WatchRunStore, Depends(get_watch_store)],
    tuning: Annotated[AgentTuning, Depends(get_tuning)],
) -> WatchRunCreated:
    """Start replaying ticks `start`..`end` in the background."""
    if body.watchers:
        settings = settings.model_copy(update={"watcher_count": body.watchers})
    run = store.start(
        repo, settings, llm, detector, to_minutes(body.start), to_minutes(body.end), tuning
    )
    return WatchRunCreated(run_id=run.run_id)


@router.get("/watch/runs/{run_id}", response_model=WatchRunStatus)
def get_run(
    run_id: str, store: Annotated[WatchRunStore, Depends(get_watch_store)]
) -> WatchRunStatus:
    """Status, alerts and trackers of a run."""
    return _run(store, run_id).status_view()


@router.get("/watch/runs/{run_id}/log", response_model=list[WatchEvent])
def get_log(
    run_id: str, store: Annotated[WatchRunStore, Depends(get_watch_store)]
) -> list[WatchEvent]:
    """Every event so far (same objects as the SSE stream; also gives the UI typed events)."""
    return list(_run(store, run_id).events)


@router.get("/watch/runs/{run_id}/events")
async def stream_events(
    run_id: str, store: Annotated[WatchRunStore, Depends(get_watch_store)]
) -> StreamingResponse:
    """SSE: replay buffered events, then follow live until the run ends (heartbeat every 15 s)."""
    run = _run(store, run_id)

    async def lines() -> AsyncIterator[str]:
        async for event in run.follow():
            if event is None:
                yield ": heartbeat\n\n"
            else:
                yield f"data: {json.dumps(event_payload(event), ensure_ascii=False)}\n\n"

    return StreamingResponse(lines(), media_type="text/event-stream")


@router.get("/watch/recordings", response_model=list[WatchRecording])
def get_recordings(settings: Annotated[Settings, Depends(get_settings)]) -> list[WatchRecording]:
    """Recorded runs available for demo replay (no LLM calls)."""
    return list_recordings(settings.recordings_dir)


@router.get("/watch/recordings/{recording_id}", response_model=list[WatchEvent])
def get_recording(
    recording_id: str, settings: Annotated[Settings, Depends(get_settings)]
) -> list[WatchEvent]:
    """Every event of one recording, in order."""
    return load_recording(settings.recordings_dir, recording_id)
