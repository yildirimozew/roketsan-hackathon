"""Run watch mode over a few ticks of the real day and print what the agents do.

    uv run python -m scripts.watch_demo --data-dir ../data --start 10:10 --end 10:30 \
        --watchers 4 --weights ../models/yolo26s_p2_full_v2.pt

Every event is also written as JSON lines to backend/.cache/watch_runs/<start>-<end>.jsonl (the
format the UI will receive over SSE). LLM responses are cached on disk, so a rerun with the same
inputs costs nothing and replays the same decisions.
"""

import argparse
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from app.agent.llm_client import GLMClient, build_llm
from app.agent.tuning_store import TuningStore
from app.agent.watch.runner import WatchRunner
from app.core.config import get_settings
from app.core.timefmt import to_minutes
from app.data.repository import Repository
from app.data.scenario import load_scenario, scenario_tracks
from app.domain.watch import (
    ExpectedVehicleEvent,
    FrameAnalyzedEvent,
    LevelChangedEvent,
    OperatorAlertEvent,
    OperatorMessageEvent,
    OperatorReplyEvent,
    SupervisorDecisionEvent,
    TickCompletedEvent,
    TickStartedEvent,
    TrackerUpdateEvent,
    WarningEvent,
    WatcherReportEvent,
    event_payload,
)
from app.services.detection import build_detector
from app.services.tuning import tuning_hash


def _print(event: Any) -> None:
    """Human-readable console line(s) for one event."""
    if isinstance(event, TickStartedEvent):
        frames = f", frames: {', '.join(event.frames)}" if event.frames else ""
        checks = ", ".join(f"{w}→{s}" for w, s in event.checks.items())
        print(f"\n=== {event.tick} · {event.active_vehicles} active vehicles{frames}")
        print(f"  checks: {checks}")
    elif isinstance(event, FrameAnalyzedEvent):
        print(f"  [frame {event.image_id} · {event.sector}] {event.status}: {event.note}")
        for det in event.detections:
            match = f"→ {det.track_id} ({det.match_m} m)" if det.track_id else "→ no track"
            print(f"    {det.detection_id} {det.label} {det.confidence:.2f} {match}")
    elif isinstance(event, WatcherReportEvent):
        r = event.report
        tools = f" · tools: {', '.join(event.tool_calls)}" if event.tool_calls else ""
        print(
            f"\n  [watcher {event.watcher}] {event.generated_by}, {event.duration_ms / 1000:.1f}s"
            f"{tools}"
        )
        print(f"    {r.street_state}")
        for v in r.vehicles:
            if v.level != "LOW":
                print(f"    {v.level:<6} {v.track_id}: {v.reason}")
        for p in r.patterns:
            print(f"    group {', '.join(p.track_ids)}: {p.description}")
    elif isinstance(event, LevelChangedEvent):
        state = "pending" if event.pending else "confirmed"
        print(f"  > {event.track_id} {event.from_level} -> {event.to_level} ({state}, {event.by})")
    elif isinstance(event, SupervisorDecisionEvent):
        d = event.decision
        print(
            f"\n  [supervisor] {event.generated_by}, {event.duration_ms / 1000:.1f}s · "
            f"threat {d.threat_level} · tools: {', '.join(event.tool_calls) or '-'}"
        )
        print(f"    {d.situation_summary}")
        for sp in d.patterns:
            print(
                f"    pattern {', '.join(sp.track_ids)} ({', '.join(sp.sectors)}): {sp.description}"
            )
        for act in event.actions:
            print(f"    action {act.tool}: {act.summary}")
    elif isinstance(event, TrackerUpdateEvent):
        t = event.tracker
        eta = f", ETA {t.eta_to_base_min} min" if t.eta_to_base_min is not None else ""
        print(
            f"  ~ {t.tracker_id} {t.state} {t.track_id} ({t.source}): {t.dist_to_base_m} m "
            f"from base, {t.speed_ms} m/s{eta}"
        )
    elif isinstance(event, OperatorAlertEvent):
        al = event.alert
        print(f"  ! {al.alert_id} [{al.urgency}] {', '.join(al.track_ids)}: {al.headline}")
        print(f"    {al.description}")
    elif isinstance(event, WarningEvent):
        print(f"  (warning {event.scope}: {event.message})")
    elif isinstance(event, OperatorMessageEvent):
        print(f"\n  [operator {event.time}] {event.text}")
    elif isinstance(event, OperatorReplyEvent):
        print(f"  [supervisor → operator] {event.generated_by}: {event.reply}")
        for act in event.actions:
            print(f"    action {act.tool}: {act.summary}")
    elif isinstance(event, ExpectedVehicleEvent):
        v = event.vehicle
        print(f"  = {v.expected_id} {v.sector} {v.arrive_from}-{v.arrive_to} track={v.track_id}")
    elif isinstance(event, TickCompletedEvent):
        print(f"  --- tick done in {event.duration_ms / 1000:.1f}s · levels {event.levels}")


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--data-dir", type=Path, default=None)
    parser.add_argument("--start", default="10:10")
    parser.add_argument("--end", default="10:30")
    parser.add_argument("--watchers", type=int, default=None, help="watcher count (1-8)")
    parser.add_argument("--weights", type=Path, default=None, help="YOLO .pt for frame detection")
    parser.add_argument("--no-detector", action="store_true", help="skip frame detection")
    parser.add_argument("--no-llm", action="store_true", help="deterministic fallbacks only")
    parser.add_argument(
        "--save-as", default=None, help="also save as a demo recording (backend/recordings/<name>)"
    )
    parser.add_argument(
        "--scenario", type=Path, default=None, help="scripted operator messages + extra tracks"
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)
    overrides: dict[str, Any] = {}
    if args.data_dir:
        overrides["data_dir"] = args.data_dir.resolve()
    if args.watchers:
        overrides["watcher_count"] = args.watchers
    if args.weights:
        overrides |= {"detector_kind": "ultralytics", "detector_weights": args.weights.resolve()}
    settings = get_settings().model_copy(update=overrides)
    tuning, tuning_warning = TuningStore(settings.cache_dir / "admin_overrides.json").load()
    if tuning_warning:
        print(f"admin tuning ignored: {tuning_warning}")
    repo = Repository(settings.data_dir)
    scenario = load_scenario(args.scenario) if args.scenario else None
    if scenario is not None:  # its synthetic vehicles join this run only
        repo.tracks.update({t.track_id: t for t in scenario_tracks(scenario)})
    llm = None if args.no_llm else build_llm(settings)
    detector = None if args.no_detector else build_detector(settings)
    detector_state = "off" if detector is None else detector.is_ready()[1]
    print(
        f"LLM: {'off (fallbacks)' if llm is None else settings.llm_model} · "
        f"watchers: {settings.watcher_count} · detector: {detector_state} · "
        f"ticks {args.start}-{args.end} · tuning {tuning_hash(tuning)}"
    )

    out_dir = settings.cache_dir / "watch_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.start.replace(':', '')}-{args.end.replace(':', '')}.jsonl"
    with out_path.open("w", encoding="utf-8") as log:

        def on_event(event: Any) -> None:
            _print(event)
            log.write(json.dumps(event_payload(event), ensure_ascii=False) + "\n")
            log.flush()

        runner = WatchRunner(repo, settings, llm, on_event, detector, tuning, scenario=scenario)
        await runner.run(to_minutes(args.start), to_minutes(args.end))

    if isinstance(llm, GLMClient):
        print(
            f"\nLLM calls: {llm.calls} (uncached) · tokens in {llm.prompt_tokens}, "
            f"out {llm.completion_tokens}"
        )
    print(f"events: {out_path}")
    if args.save_as:
        settings.recordings_dir.mkdir(parents=True, exist_ok=True)
        saved = settings.recordings_dir / f"{args.save_as}.jsonl"
        saved.write_text(out_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"recording: {saved} (UI: /watch?recording={args.save_as})")


if __name__ == "__main__":
    asyncio.run(main())
