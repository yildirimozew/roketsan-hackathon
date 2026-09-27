"""Watch mode tick loop (docs/AGENT_FLOW.md §3).

Each tick: run the detector on any drone frame captured now and match its boxes to tracks (vehicle
types go into the registry), let every watcher check one sector of its area (they take turns when
there are fewer watchers than sectors; a frame's sector gets priority), apply their levels and notes
under the registry rules, run the supervisor on the whole board, and emit events. One `WatchRunner`
holds the state of one replayed day.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from typing import Any

from app.agent.llm_client import ChatLLM
from app.agent.tuning_store import with_agent_knobs
from app.agent.watch import operator as operator_mod
from app.agent.watch import supervisor as supervisor_mod
from app.agent.watch import watcher as watcher_mod
from app.agent.watch.boards import AlertBoard, BoardError, TrackerBoard
from app.agent.watch.operator import OperatorBoard, OperatorInput, run_operator_turn
from app.agent.watch.registry import CarRegistry, LevelChange, level_index
from app.agent.watch.supervisor import SupervisorInput, SupervisorOutcome, run_supervisor
from app.agent.watch.tools import WatchContext
from app.agent.watch.watcher import WatcherInput, WatcherOutcome, needs_judgment, run_watcher
from app.core.config import Settings
from app.core.errors import DetectorError, NotFoundError
from app.core.timefmt import to_hhmm, to_minutes
from app.data.repository import Repository
from app.data.scenario import scenario_tracks
from app.domain.base import DomainModel
from app.domain.image import ImageMeta
from app.domain.report import ReportClaim
from app.domain.scenario import Scenario
from app.domain.track import MapTrack
from app.domain.tuning import AgentTuning
from app.domain.watch import (
    AgentTraceEvent,
    ExpectedVehicle,
    ExpectedVehicleEvent,
    FrameAnalyzedEvent,
    LevelChangedEvent,
    OperatorAlertEvent,
    OperatorMessageEvent,
    OperatorReplyEvent,
    ReportJudgment,
    ScenarioLoadedEvent,
    SupervisorDecisionEvent,
    TickCompletedEvent,
    TickStartedEvent,
    TrackerUpdateEvent,
    VehicleRow,
    WarningEvent,
    WatcherReport,
    WatcherReportEvent,
)
from app.services import watch as watch_svc
from app.services.behavior import moving_groups
from app.services.detection import Detector
from app.services.reports import extract_claim
from app.services.tracks import tracks_at
from app.services.tuning import DEFAULT_TUNING, tuning_hash

logger = logging.getLogger(__name__)
EventSink = Callable[[Any], None]
RECENT_EVENTS_KEPT = 15
MAX_WATCHERS = 8  # one per sector at most
EARLIER_REPORTS_MIN = 120  # watchers compare new reports with their sector's reports this far back


class WatchRunner:
    """State and tick loop of one watch run."""

    def __init__(
        self,
        repo: Repository,
        settings: Settings,
        llm: ChatLLM | None,
        on_event: EventSink,
        detector: Detector | None = None,
        tuning: AgentTuning = DEFAULT_TUNING,
        scenario: Scenario | None = None,
    ) -> None:
        """`scenario`: scripted operator messages; its extra tracks must already be in `repo`."""
        settings = with_agent_knobs(settings, tuning)
        self.repo, self.settings, self.llm, self.emit = repo, settings, llm, on_event
        self.tuning = tuning
        logger.info(
            "watch run tuning",
            extra={
                "tuning_hash": tuning_hash(tuning),
                "watcher_prompt": "admin" if tuning.prompts.watcher else "file",
                "supervisor_prompt": "admin" if tuning.prompts.supervisor else "file",
            },
        )
        self.detector = detector
        self.scenario = scenario
        self._scenario_sent = False
        self._dedicated: dict[str, str] = {}  # watcher -> the one sector it checks every tick
        self.expected: list[ExpectedVehicle] = []  # vehicles the operator announced
        self._held: list[DomainModel] = []  # events made before this tick's tick_started
        self._held_changes: list[LevelChange] = []
        self._now = 0
        self.registry = CarRegistry()
        self.trackers = TrackerBoard(settings.tracker_slots)
        self.alerts = AlertBoard()
        self.claims: list[ReportClaim] = [extract_claim(r, repo.scene.zones) for r in repo.reports]
        self.groups = watch_svc.watcher_groups(
            repo.scene.zones, repo.scene.base.position, settings.watcher_count
        )
        self._next: dict[str, int] = {w: 0 for w in self.groups}
        self._last_checked: dict[str, int] = {}
        self._prev_sector: dict[str, str] = {}
        self._recent: list[dict[str, Any]] = []
        self._judgments: dict[str, dict[str, Any]] = {}  # latest judgment per report id

    async def run(self, start_min: int, end_min: int) -> None:
        """Replay every tick from start to end (inclusive)."""
        for minute in watch_svc.ticks(start_min, end_min):
            await self.tick(minute)

    # ---- one tick ----

    async def tick(self, minute: int) -> None:
        """Run one 5-minute tick end to end."""
        started = time.perf_counter()
        self._now = minute
        tick = to_hhmm(minute)
        frames = [m for m in self.repo.list_images() if m.capture_min == minute]
        # The operator's messages come first: a watcher they create already works this tick.
        await self._operator_turns(tick, minute)
        checks = self._schedule(frames)
        active = sum(1 for t in self.repo.tracks.values() if watch_svc.track_until(t, minute))
        self.emit(
            TickStartedEvent(
                tick=tick,
                active_vehicles=active,
                frames=[f.image_id for f in frames],
                checks=checks,
            )
        )
        self._release_held(tick)
        frame_events = [await self._analyze_frame(f, minute) for f in frames]
        for fe in frame_events:
            self.emit(fe)
        rows = self._rows(minute)
        self._release_held(tick)
        ctx = WatchContext(
            repo=self.repo,
            settings=self.settings,
            tick_min=minute,
            claims=self.claims,
            registry=self.registry,
            trackers=self.trackers,
            alerts=self.alerts,
            rows={r.track_id: r for r in rows},
            tuning=self.tuning,
        )
        new_claims = watch_svc.claims_between(self.claims, minute - watch_svc.TICK_MIN, minute)

        inputs = [
            self._watcher_input(w, sector, tick, minute, rows, frame_events)
            for w, sector in checks.items()
        ]
        for inp in inputs:
            if not inp.rows and not inp.reports:
                self.emit(self._empty_report_event(tick, inp))
        busy = [i for i in inputs if i.rows or i.reports]  # new reports are judged even so
        outcomes = await asyncio.gather(*(run_watcher(self.llm, ctx, i) for i in busy))
        for inp, outcome in zip(busy, outcomes, strict=True):
            self._apply_watcher(tick, inp, outcome)
        for sector in checks.values():
            self._last_checked[sector] = minute

        sup_input = SupervisorInput(
            tick=tick,
            watcher_messages=[
                self._watcher_message(i, o) for i, o in zip(busy, outcomes, strict=True)
            ],
            unchecked=self._unchecked(set(checks.values()), rows),
            frames=[self._frame_block(fe) for fe in frame_events],
            recent_events=list(self._recent),
            area_reports=[
                {"report_id": c.report_id, "time": c.time, "source": c.source, "text": c.text}
                for c in watch_svc.area_claims(new_claims)
            ],
            layout=self.groups,
        )
        sup = await run_supervisor(self.llm, ctx, sup_input)
        self._apply_supervisor(tick, sup)

        if self.settings.trackers_enabled:
            for tracker in self.trackers.update(minute, self.repo.tracks, ctx.base):
                self.emit(TrackerUpdateEvent(tick=tick, tracker=tracker))
                if tracker.state == "LOST":
                    self.registry.get(tracker.track_id).tracker_id = None

        for r in rows:
            self._prev_sector[r.track_id] = r.sector
        counts = {lvl: 0 for lvl in ("LOW", "MEDIUM", "HIGH")}
        for r in rows:
            counts[self.registry.effective_level(r.track_id)] += 1
        self.emit(
            TickCompletedEvent(
                tick=tick, duration_ms=round((time.perf_counter() - started) * 1000), levels=counts
            )
        )

    # ---- scheduling and frames ----

    def _schedule(self, frames: list[ImageMeta]) -> dict[str, str]:
        """Watcher -> sector to check: a frame's sector first, else the next in its rotation."""
        frame_sectors = [f.zone for f in frames if f.zone]
        checks: dict[str, str] = {}
        dedicated = set(self._dedicated.values())
        for wid, full_area in self.groups.items():
            # Sectors with a dedicated watcher are left to it.
            area = (
                full_area
                if wid in self._dedicated
                else [s for s in full_area if s not in dedicated] or full_area
            )
            with_frame = [s for s in frame_sectors if s in area]
            idx = area.index(with_frame[0]) if with_frame else self._next[wid] % len(area)
            checks[wid] = area[idx]
            self._next[wid] = idx + 1
        return checks

    async def _analyze_frame(self, meta: ImageMeta, minute: int) -> FrameAnalyzedEvent:
        """Detect vehicles in a frame and match them to the tracks at capture time."""
        positions = tracks_at(list(self.repo.tracks.values()), minute)
        inside = sorted(t for t, p in positions.items() if watch_svc.in_frame(meta, p))
        tick, sector = to_hhmm(minute), meta.zone or ""
        if self.detector is None:
            return FrameAnalyzedEvent(
                tick=tick,
                image_id=meta.image_id,
                sector=sector,
                status="detector_unavailable",
                detections=[],
                tracks_in_frame=inside,
                note="no detector configured",
            )
        try:
            path = self.repo.image_path(meta.image_id)
        except NotFoundError:
            path = None  # precomputed detections need no file; YOLO raises DetectorError
        try:
            raw = await asyncio.to_thread(self.detector.detect, meta.image_id, path)
        except DetectorError as exc:
            return FrameAnalyzedEvent(
                tick=tick,
                image_id=meta.image_id,
                sector=sector,
                status="detector_unavailable",
                detections=[],
                tracks_in_frame=inside,
                note=exc.detail,
            )
        dets = watch_svc.frame_detections(raw, meta, positions, self.settings.match_max_m)
        for d in dets:
            if d.track_id:
                self.registry.get(d.track_id).vehicle_type = d.label
        matched = sum(1 for d in dets if d.track_id)
        return FrameAnalyzedEvent(
            tick=tick,
            image_id=meta.image_id,
            sector=sector,
            status="ok",
            detections=dets,
            tracks_in_frame=inside,
            note=f"{len(dets)} detections, {matched} matched to tracks",
        )

    @staticmethod
    def _frame_block(fe: FrameAnalyzedEvent) -> dict[str, Any]:
        matched = {d.track_id for d in fe.detections if d.track_id}
        return {
            "image_id": fe.image_id,
            "evidence_id": f"FRAME-{fe.image_id}",
            "sector": fe.sector,
            "status": fe.status,
            "detections": [d.model_dump(mode="json", exclude={"position"}) for d in fe.detections],
            "tracked_vehicles_without_detection": [
                t for t in fe.tracks_in_frame if t not in matched
            ],
        }

    # ---- rows, inputs and messages ----

    def _rows(self, minute: int) -> list[VehicleRow]:
        zones, base = self.repo.scene.zones, self.repo.scene.base.position
        groups = moving_groups(list(self.repo.tracks.values()), minute, self.tuning.groups)
        rows: list[VehicleRow] = []
        for tid, track in self.repo.tracks.items():
            upto = watch_svc.track_until(track, minute)
            if upto is None:
                continue
            entry = self.registry.get(tid)
            rows.append(
                watch_svc.vehicle_row(
                    upto,
                    minute,
                    base,
                    zones,
                    stop_speed_ms=self.settings.stop_speed_ms,
                    zone_radius_m=self.settings.zone_radius_m,
                    prev_sector=self._prev_sector.get(tid),
                    registry_level=entry.level,
                    pending_level=entry.pending.level if entry.pending else None,
                    notes_count=len(entry.notes),
                    lang=self.settings.brief_language,
                    vehicle_type=entry.vehicle_type,
                    group=groups.get(tid),
                    tuning=self.tuning,
                )
            )
        return self._apply_expected(minute, rows)

    # ---- the operator: messages to the supervisor, dedicated watchers, announced vehicles ----

    def _apply_expected(self, minute: int, rows: list[VehicleRow]) -> list[VehicleRow]:
        """Match announcements to tracks, then keep announced vehicles LOW (the operator is
        trusted; the user's rule: always LOW once announced)."""
        zones, tick = self.repo.scene.zones, to_hhmm(minute)
        taken = {e.track_id for e in self.expected if e.track_id}
        for exp in self.expected:
            if exp.track_id is None:
                tid = watch_svc.match_expected(exp, rows, self.repo.tracks, zones, taken)
                if tid is not None:
                    exp.track_id = tid
                    taken.add(tid)
                    self._held.append(ExpectedVehicleEvent(tick=tick, vehicle=exp.model_copy()))
                    self._remember(tick, "expected_vehicle_seen", tid, exp.expected_id)
        by_track = {e.track_id: e for e in self.expected if e.track_id}
        out = []
        for row in rows:
            announced = by_track.get(row.track_id)
            if announced is not None:
                row = watch_svc.mark_expected(row, announced)
                if self.registry.effective_level(row.track_id) != "LOW":
                    reason = f"{announced.expected_id}: announced by the operator"
                    change = self.registry.set_level(row.track_id, "LOW", "operator", reason)
                    if change:
                        self._held_changes.append(change)
            out.append(row)
        return out

    def _release_held(self, tick: str) -> None:
        """Emit events made before this tick's tick_started (or while building rows)."""
        if self.scenario is not None and not self._scenario_sent:
            self._scenario_sent = True
            self.emit(
                ScenarioLoadedEvent(
                    tick=tick,
                    name=self.scenario.name,
                    description=self.scenario.description,
                    extra_tracks=[
                        MapTrack(track_id=t.track_id, points=t.points, image_id=None)
                        for t in scenario_tracks(self.scenario)
                    ],
                )
            )
        held, self._held = self._held, []
        for event in held:
            self.emit(event)
        changes, self._held_changes = self._held_changes, []
        for change in changes:
            self._emit_change(tick, change)

    async def _operator_turns(self, tick: str, minute: int) -> None:
        """The supervisor answers every operator message written in this tick's window."""
        if self.scenario is None:
            return
        due = [
            m
            for m in self.scenario.operator_messages
            if minute - watch_svc.TICK_MIN <= to_minutes(m.time) < minute
        ]
        if not due:
            return
        rows = self._rows(minute)
        ctx = WatchContext(
            repo=self.repo,
            settings=self.settings,
            tick_min=minute,
            claims=self.claims,
            registry=self.registry,
            trackers=self.trackers,
            alerts=self.alerts,
            rows={r.track_id: r for r in rows},
        )
        board = OperatorBoard(self._create_watcher, self._register_expected)
        for msg in due:
            self._held.append(OperatorMessageEvent(tick=tick, time=msg.time, text=msg.text))
            self._remember(tick, "operator_message", "", msg.text)
            inp = OperatorInput(
                tick=tick,
                time=msg.time,
                text=msg.text,
                layout={w: list(s) for w, s in self.groups.items()},
                dedicated=dict(self._dedicated),
                flagged=self._suspicious(rows, {}),
                expected=[e.model_copy() for e in self.expected],
            )
            out = await run_operator_turn(self.llm, ctx, inp, board)
            self._held.append(
                OperatorReplyEvent(
                    tick=tick,
                    time=msg.time,
                    generated_by=out.generated_by,
                    duration_ms=out.duration_ms,
                    reply=out.reply,
                    actions=out.actions,
                    tool_calls=out.tool_calls,
                    warnings=out.warnings,
                )
            )
            if out.system:
                self._held.append(
                    AgentTraceEvent(
                        tick=tick,
                        agent="supervisor:operator",
                        prompt_file=operator_mod.PROMPT,
                        system_prompt=out.system,
                        user_message=out.user,
                        steps=out.trace,
                        output={"reply": out.reply},
                        generated_by=out.generated_by,
                        duration_ms=out.duration_ms,
                    )
                )

    def _create_watcher(self, sector: str, reason: str) -> str:
        """A new watcher that checks `sector` every tick (the operator asked for it)."""
        for wid, s in self._dedicated.items():
            if s == sector:
                raise BoardError(f"{wid} already watches {sector} every tick")
        if len(self.groups) >= MAX_WATCHERS:
            raise BoardError(f"at most {MAX_WATCHERS} watchers")
        wid = f"W{len(self.groups) + 1}"
        self.groups[wid] = [sector]
        self._next[wid] = 0
        self._dedicated[wid] = sector
        self._remember(to_hhmm(self._now), "watcher_created", "", f"{wid} for {sector}: {reason}")
        return wid

    def _register_expected(self, vehicle: ExpectedVehicle) -> ExpectedVehicle:
        """Record an announced vehicle; it is matched to a track when one appears."""
        registered = vehicle.model_copy(update={"expected_id": f"EXP-{len(self.expected) + 1}"})
        self.expected.append(registered)
        tick = to_hhmm(self._now)
        self._held.append(ExpectedVehicleEvent(tick=tick, vehicle=registered.model_copy()))
        self._remember(
            tick, "expected_vehicle", "", f"{registered.expected_id}: {registered.description}"
        )
        return registered

    def _sector_at(self, track_id: str, minute: int) -> str | None:
        point = next((p for p in self.repo.tracks[track_id].points if p.time_min == minute), None)
        return watch_svc.sector_of(point.position, self.repo.scene.zones) if point else None

    def _watcher_input(
        self,
        wid: str,
        sector: str,
        tick: str,
        minute: int,
        rows: list[VehicleRow],
        frame_events: list[FrameAnalyzedEvent],
    ) -> WatcherInput:
        mine = [r for r in rows if r.sector == sector]
        last = self._last_checked.get(sector)
        ref = last if last is not None else minute - watch_svc.TICK_MIN
        arrivals = []
        for r in mine:
            before = self._sector_at(r.track_id, ref)
            if before == sector:
                continue
            pts = [p for p in self.repo.tracks[r.track_id].points if p.time_min <= minute]
            arrivals.append(
                {
                    "track_id": r.track_id,
                    "came_from": before,
                    "route_so_far": [
                        [p.time, round(p.position.lat, 6), round(p.position.lon, 6)] for p in pts
                    ],
                }
            )
        quiet = [r.track_id for r in mine if not needs_judgment(r, self.tuning)]
        rng = random.Random(f"{tick}|{sector}")  # seeded: the same run samples the same vehicles
        spot = sorted(rng.sample(quiet, min(self.settings.watcher_spot_checks, len(quiet))))
        return WatcherInput(
            spot_checks=spot,
            tuning=self.tuning,
            watcher_id=wid,
            area=self.groups[wid],
            sectors=[sector],
            last_checked=to_hhmm(last) if last is not None else None,
            tick=tick,
            rows=mine,
            new_arrivals=arrivals,
            notes=[n for r in mine for n in self.registry.get(r.track_id).notes],
            frames=[self._frame_block(fe) for fe in frame_events if fe.sector == sector],
            # every report filed since the sector was last checked, and the ones before for
            # comparison (report-vs-report contradictions)
            reports=self._sector_claims(sector, ref, minute),
            earlier_reports=self._sector_claims(sector, minute - EARLIER_REPORTS_MIN, ref),
            judgments=dict(self._judgments),
        )

    def _sector_claims(self, sector: str, start_min: int, end_min: int) -> list[ReportClaim]:
        claims = watch_svc.claims_between(self.claims, start_min, end_min)
        return watch_svc.claims_for_sectors(claims, [sector], self.repo.scene.zones)

    def _remember_judgments(self, tick: str, by: str, checks: list[ReportJudgment]) -> None:
        for c in checks:
            self._judgments[c.report_id] = {
                "tick": tick,
                "by": by,
                "verdict": c.verdict,
                "credibility": c.credibility,
                "reason": c.reason,
                "conflicts_with": c.conflicts_with,
            }

    @staticmethod
    def _empty_report_event(tick: str, inp: WatcherInput) -> WatcherReportEvent:
        report = WatcherReport(tick=tick, street_state="No vehicles.", vehicles=[], patterns=[])
        return WatcherReportEvent(
            tick=tick,
            watcher=inp.watcher_id,
            sectors=inp.sectors,
            generated_by="fallback",
            duration_ms=0,
            rows=[],
            report=report,
            tool_calls=[],
            warnings=[],
        )

    def _apply_watcher(self, tick: str, inp: WatcherInput, outcome: WatcherOutcome) -> None:
        by = f"watcher:{inp.watcher_id}"
        self._remember_judgments(inp.tick, by, outcome.report.report_checks)
        for v in outcome.report.vehicles:
            # enforce_rules only lets a verdict go below the registry down to the vehicle's
            # ceiling, so a lower verdict here is an allowed de-escalation.
            if level_index(v.level) < level_index(self.registry.get(v.track_id).level):
                change = self.registry.lower(v.track_id, v.level, by, v.reason)
            else:
                change = self.registry.propose(v.track_id, v.level, tick, by, v.reason)
            if change:
                self._emit_change(tick, change)
            if v.note:
                self.registry.add_note(v.track_id, tick, by, v.level, v.note, v.evidence_ids)
        for w in outcome.warnings:
            self.emit(WarningEvent(tick=tick, scope=by, message=w))
        if outcome.system:
            self.emit(
                AgentTraceEvent(
                    tick=tick,
                    agent=by,
                    prompt_file=watcher_mod.PROMPT,
                    system_prompt=outcome.system,
                    user_message=outcome.user,
                    steps=outcome.trace,
                    output=outcome.report.model_dump(mode="json"),
                    generated_by=outcome.generated_by,
                    duration_ms=outcome.duration_ms,
                )
            )
        self.emit(
            WatcherReportEvent(
                tick=tick,
                watcher=inp.watcher_id,
                sectors=inp.sectors,
                generated_by=outcome.generated_by,
                duration_ms=outcome.duration_ms,
                rows=inp.rows,
                report=outcome.report,
                tool_calls=outcome.tool_calls,
                warnings=outcome.warnings,
                reports=watcher_mod.judged_reports(self.repo.reports, outcome.report.report_checks),
            )
        )
        for a in inp.new_arrivals:
            if self.registry.effective_level(a["track_id"]) != "LOW":
                detail = f"from {a['came_from']} into {inp.sectors[0]}"
                self._remember(tick, "handoff", a["track_id"], detail)

    def _suspicious(self, rows: list[VehicleRow], verdicts: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            level = self.registry.effective_level(row.track_id)
            if level == "LOW":
                continue
            entry = self.registry.get(row.track_id)
            v = verdicts.get(row.track_id)
            out.append(
                {
                    "track_id": row.track_id,
                    "vehicle_type": row.vehicle_type,
                    "level": level,
                    "pending": entry.pending is not None,
                    "dist_to_base_m": row.dist_to_base_m,
                    "closing_last5_m_per_min": row.closing_last5_m_per_min,
                    "eta_to_base_min": row.eta_to_base_min,
                    "alerted": bool(entry.alert_ids),
                    "reason": v.reason if v else "(level from an earlier check)",
                    "evidence_ids": v.evidence_ids if v else [f"TRK-{row.track_id}"],
                }
            )
        out.sort(key=lambda s: (-level_index(s["level"]), s["dist_to_base_m"]))
        return out

    def _watcher_message(self, inp: WatcherInput, outcome: WatcherOutcome) -> dict[str, Any]:
        verdicts = {v.track_id: v for v in outcome.report.vehicles}
        return {
            "watcher": inp.watcher_id,
            "sector": inp.sectors[0],
            "generated_by": outcome.generated_by,
            "street_state": outcome.report.street_state,
            "suspicious": self._suspicious(inp.rows, verdicts),
            "patterns": [p.model_dump(mode="json") for p in outcome.report.patterns],
            "reports": self._passed_reports(outcome),
        }

    def _passed_reports(self, outcome: WatcherOutcome) -> list[dict[str, Any]]:
        """The watcher's report judgments with the report text (untrusted); irrelevant ones are
        left out."""
        claims = {c.report_id: c for c in self.claims}
        return [
            watcher_mod.report_json(claims[c.report_id])
            | c.model_dump(mode="json", exclude={"report_id"})
            for c in outcome.report.report_checks
            if c.verdict != "IRRELEVANT"
        ]

    def _unchecked(self, checked: set[str], rows: list[VehicleRow]) -> list[dict[str, Any]]:
        out = []
        for area in self.groups.values():
            for sector in area:
                if sector in checked:
                    continue
                last = self._last_checked.get(sector)
                out.append(
                    {
                        "sector": sector,
                        "last_checked": to_hhmm(last) if last is not None else None,
                        "vehicles": self._suspicious([r for r in rows if r.sector == sector], {}),
                    }
                )
        return out

    def _apply_supervisor(self, tick: str, sup: SupervisorOutcome) -> None:
        for change in sup.level_changes:
            self._emit_change(tick, change)
        for tracker in sup.trackers:
            self.emit(TrackerUpdateEvent(tick=tick, tracker=tracker))
        for alert in sup.alerts:
            self.emit(OperatorAlertEvent(tick=tick, alert=alert))
            detail = f"{alert.alert_id}: {alert.headline}"
            self._remember(tick, "operator_alert", ",".join(alert.track_ids), detail)
        for w in sup.warnings:
            self.emit(WarningEvent(tick=tick, scope="supervisor", message=w))
        if sup.system:
            self.emit(
                AgentTraceEvent(
                    tick=tick,
                    agent="supervisor",
                    prompt_file=supervisor_mod.PROMPT,
                    system_prompt=sup.system,
                    user_message=sup.user,
                    steps=sup.trace,
                    output=sup.decision.model_dump(mode="json"),
                    generated_by=sup.generated_by,
                    duration_ms=sup.duration_ms,
                )
            )
        self.emit(
            SupervisorDecisionEvent(
                tick=tick,
                generated_by=sup.generated_by,
                duration_ms=sup.duration_ms,
                decision=sup.decision,
                actions=sup.actions,
                tool_calls=sup.tool_calls,
                warnings=sup.warnings,
                reports=watcher_mod.judged_reports(self.repo.reports, sup.decision.report_checks),
            )
        )
        self._remember_judgments(tick, "supervisor", sup.decision.report_checks)

    def _emit_change(self, tick: str, change: LevelChange) -> None:
        self.emit(
            LevelChangedEvent(
                tick=tick,
                track_id=change.track_id,
                from_level=change.from_level,
                to_level=change.to_level,
                by=change.by,
                pending=change.pending,
                reason=change.reason,
            )
        )
        if not change.pending:
            detail = f"{change.from_level} -> {change.to_level} by {change.by}"
            self._remember(tick, "level_changed", change.track_id, detail)

    def _remember(self, tick: str, kind: str, track_id: str, detail: str) -> None:
        self._recent.append({"tick": tick, "event": kind, "track_id": track_id, "detail": detail})
        del self._recent[:-RECENT_EVENTS_KEPT]
