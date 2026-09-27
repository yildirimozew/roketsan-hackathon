"""Recorded watch runs: JSONL event logs written by `scripts.watch_demo`, replayed by the UI.

A recording is validated against `WatchEvent` when read, so a stale log with old event types is
reported instead of reaching the UI.
"""

import json
from functools import lru_cache
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.core.errors import NotFoundError
from app.domain.watch import WatchEvent, WatchRecording

_EVENTS = TypeAdapter(list[WatchEvent])


def _path(recordings_dir: Path, recording_id: str) -> Path:
    path = recordings_dir / f"{recording_id}.jsonl"
    if path.parent != recordings_dir or not path.is_file():
        raise NotFoundError(f"recording {recording_id} not found")
    return path


@lru_cache(maxsize=8)
def _load(path: Path, mtime: float) -> list[WatchEvent]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return _EVENTS.validate_python([json.loads(line) for line in lines if line.strip()])


def load_recording(recordings_dir: Path, recording_id: str) -> list[WatchEvent]:
    """All events of one recording, in order; raises NotFoundError."""
    path = _path(recordings_dir, recording_id)
    return _load(path, path.stat().st_mtime)


def list_recordings(recordings_dir: Path) -> list[WatchRecording]:
    """Summaries of every valid recording in the directory (invalid ones are skipped)."""
    out: list[WatchRecording] = []
    for path in sorted(recordings_dir.glob("*.jsonl")) if recordings_dir.is_dir() else []:
        try:
            events = load_recording(recordings_dir, path.stem)
        except (ValidationError, json.JSONDecodeError):
            continue
        starts = [e for e in events if e.type == "tick_started"]
        out.append(
            WatchRecording(
                recording_id=path.stem,
                ticks=[e.tick for e in starts],
                watchers=sorted(starts[0].checks) if starts else [],
                events=len(events),
                llm_turns=sum(
                    1 for e in events if e.type == "agent_trace" and e.generated_by == "llm"
                ),
                alerts=sum(1 for e in events if e.type == "operator_alert"),
            )
        )
    return out
