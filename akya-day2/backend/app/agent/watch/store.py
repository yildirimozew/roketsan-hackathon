"""Watch runs executing as background asyncio tasks, with buffered events.

Every event is kept, so a client that connects late (or reconnects) replays the run from the start
and then follows it live (backend/CLAUDE.md, API rules).
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Any

from app.agent.llm_client import ChatLLM
from app.agent.watch.runner import WatchRunner
from app.core.config import Settings
from app.core.timefmt import to_hhmm
from app.data.repository import Repository
from app.domain.tuning import AgentTuning
from app.domain.watch import WarningEvent, WatchRunStatus
from app.services.detection import Detector
from app.services.tuning import DEFAULT_TUNING

logger = logging.getLogger(__name__)
HEARTBEAT_S = 15.0


class WatchRun:
    """One replay of part of the day."""

    def __init__(
        self,
        run_id: str,
        repo: Repository,
        settings: Settings,
        llm: ChatLLM | None,
        detector: Detector | None,
        start_min: int,
        end_min: int,
        tuning: AgentTuning = DEFAULT_TUNING,
    ) -> None:
        self.run_id, self.start_min, self.end_min = run_id, start_min, end_min
        self.watchers = settings.watcher_count
        self.events: list[Any] = []
        self.status = "running"
        self._changed = asyncio.Event()
        self.runner = WatchRunner(repo, settings, llm, self.add, detector, tuning)
        self.task: asyncio.Task[None] | None = None

    def add(self, event: Any) -> None:
        """Buffer an event and wake every follower."""
        self.events.append(event)
        self._changed.set()
        self._changed = asyncio.Event()

    async def execute(self) -> None:
        """Run all ticks; a crash marks the run failed instead of killing the server."""
        try:
            await self.runner.run(self.start_min, self.end_min)
            self.status = "done"
        except Exception as exc:  # background-task boundary: report, never propagate
            logger.exception("watch run failed", extra={"run_id": self.run_id})
            self.status = "failed"
            self.add(WarningEvent(tick=to_hhmm(self.end_min), scope="run", message=repr(exc)))
        self._changed.set()

    async def follow(self, from_index: int = 0) -> AsyncIterator[Any | None]:
        """Buffered events, then live ones until the run ends; None means heartbeat."""
        index = from_index
        while True:
            while index < len(self.events):
                yield self.events[index]
                index += 1
            if self.status != "running":
                return
            waiter = self._changed
            try:
                await asyncio.wait_for(waiter.wait(), HEARTBEAT_S)
            except TimeoutError:
                yield None

    def status_view(self) -> WatchRunStatus:
        """Snapshot for `GET /api/watch/runs/{run_id}`."""
        return WatchRunStatus.model_validate(
            {
                "run_id": self.run_id,
                "status": self.status,
                "start": to_hhmm(self.start_min),
                "end": to_hhmm(self.end_min),
                "watchers": self.watchers,
                "events": len(self.events),
                "alerts": self.runner.alerts.all(),
                "trackers": self.runner.trackers.all(),
            }
        )


class WatchRunStore:
    """Runs for the process lifetime."""

    def __init__(self) -> None:
        self._runs: dict[str, WatchRun] = {}

    def start(
        self,
        repo: Repository,
        settings: Settings,
        llm: ChatLLM | None,
        detector: Detector | None,
        start_min: int,
        end_min: int,
        tuning: AgentTuning = DEFAULT_TUNING,
    ) -> WatchRun:
        """Create a run and start it as a background task on the running loop."""
        run = WatchRun(
            uuid.uuid4().hex[:12], repo, settings, llm, detector, start_min, end_min, tuning
        )
        run.task = asyncio.create_task(run.execute())
        self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> WatchRun | None:
        """Run by id, if present."""
        return self._runs.get(run_id)
