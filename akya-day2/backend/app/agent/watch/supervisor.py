"""Head supervisor: one tool loop per tick over the whole board.

Prompt, tools and examples: docs/AGENT_PROMPTS_AND_TOOLS.md §5.

The supervisor keeps the human operator informed. Side-effecting tools (set_level, alert_operator,
and dispatch_tracker / recall_tracker when trackers are enabled) change the run state immediately
and are recorded as actions. If the model does not finish with a valid `submit_supervisor_decision`,
a deterministic fallback alerts the operator about confirmed HIGH vehicles that were not alerted
yet and writes a templated summary.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.agent.llm_client import ChatLLM
from app.agent.watch import tools as t
from app.agent.watch.boards import BoardError
from app.agent.watch.loop import SubmitError, fill_pattern_track_ids, run_tool_loop
from app.agent.watch.prompts import (
    LANGUAGE_NAMES,
    PROMPT_FILES,
    render_with_fallback,
    threshold_vars,
)
from app.agent.watch.registry import LevelChange, level_index
from app.agent.watch.watcher import report_problems
from app.domain.watch import (
    WATCH_LEVELS,
    GeneratedBy,
    OperatorAlert,
    SupervisorAction,
    SupervisorDecision,
    Suspicion,
    TrackerState,
    WatchLevel,
)

PROMPT = PROMPT_FILES["supervisor"]
MAX_TOKENS = 16000
NO_TRACKERS = (
    "3. No trackers or field units are available in this exercise: you cannot send anyone. "
    "Your output is information for the operator."
)
TRACKER_RULES = (
    "3. You have {slots} tracker slots. dispatch_tracker (HIGH vehicles only) puts a tracker on a "
    "vehicle until you recall it or it loses the vehicle; prefer vehicles closest to the base in "
    "time, heavy vehicles and vehicles in a coordinated pattern, and state a suspicion."
)


@dataclass
class SupervisorInput:
    """The board at one tick."""

    tick: str
    watcher_messages: list[dict[str, Any]]
    unchecked: list[dict[str, Any]]
    frames: list[dict[str, Any]]
    recent_events: list[dict[str, Any]]
    area_reports: list[dict[str, Any]]
    layout: dict[str, list[str]]


@dataclass
class SupervisorOutcome:
    """Decision plus every state change the supervisor made this tick."""

    decision: SupervisorDecision
    generated_by: GeneratedBy
    actions: list[SupervisorAction] = field(default_factory=list)
    level_changes: list[LevelChange] = field(default_factory=list)
    trackers: list[TrackerState] = field(default_factory=list)
    alerts: list[OperatorAlert] = field(default_factory=list)
    duration_ms: int = 0
    tool_calls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    system: str = ""
    user: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)


class _Effects:
    """Side-effecting tool handlers bound to one tick; records what they did."""

    def __init__(self, ctx: t.WatchContext, out: SupervisorOutcome) -> None:
        self.ctx, self.out = ctx, out

    def _evidence(self, raw: Any) -> list[str]:
        ids = [str(e) for e in raw] if isinstance(raw, list) else []
        if not ids:
            raise BoardError("evidence_ids must be a non-empty list")
        if bad := self.ctx.unknown_evidence(ids):
            raise BoardError(f"unknown evidence ids {bad}")
        return ids

    def set_level(self, args: dict[str, Any]) -> dict[str, Any]:
        tid = self.ctx.track_id(args)
        level = args.get("level")
        if level not in WATCH_LEVELS:
            raise BoardError(f"level must be one of {list(WATCH_LEVELS)}")
        row = self.ctx.rows.get(tid)
        if row is not None and WATCH_LEVELS.index(level) > WATCH_LEVELS.index(row.max_level):
            raise BoardError(
                f"{tid} may be at most {row.max_level}: HIGH is for vehicles looping around or "
                "orbiting the base, probing it from within 1 km, or driving right up to it (a "
                "final approach within 1.5 km or 5 min, or within 1 km after driving in); MEDIUM "
                "for probing, a stakeout or a large group moving together; normal-speed "
                "approaches and the base's own traffic are LOW"
            )
        reason = str(args.get("reason") or "").strip()
        if not reason:
            raise BoardError("reason is required")
        self._evidence(args.get("evidence_ids"))
        change = self.ctx.registry.set_level(tid, level, "supervisor", reason)
        if change:
            self.out.level_changes.append(change)
        self.out.actions.append(
            SupervisorAction(
                tool="set_level", ok=True, summary=f"{tid} -> {level}: {reason}", track_ids=[tid]
            )
        )
        return {"track_id": tid, "level": level, "applied_at": self.ctx.tick}

    def alert_operator(self, args: dict[str, Any]) -> dict[str, Any]:
        ids = args.get("track_ids")
        if not isinstance(ids, list) or not ids:
            raise BoardError("track_ids must be a non-empty list")
        track_ids = [self.ctx.track_id({"track_id": i}) for i in ids]
        announced = [i for i in track_ids if (r := self.ctx.rows.get(i)) and r.expected]
        if announced and len(announced) == len(track_ids):
            raise BoardError(f"{announced} were announced by the operator; do not alert about them")
        rows = [self.ctx.rows[i] for i in track_ids if i in self.ctx.rows]
        if rows and all(r.max_level == "LOW" for r in rows):
            raise BoardError(
                "no code rule backs an alert about these vehicles (all may be at most LOW: "
                "normal-speed approaches, the base's own traffic, or vehicles that only meet "
                "inside a drone frame); alert only about circling, probing, a stakeout, a very "
                "close approach or a large group moving together"
            )
        headline = str(args.get("headline") or "").strip()
        description = str(args.get("description") or "").strip()
        if not headline or not description:
            raise BoardError("headline and description are required")
        alert = self.ctx.alerts.notify(
            self.ctx.tick,
            track_ids,
            str(args.get("urgency")),
            headline,
            description,
            self._evidence(args.get("evidence_ids")),
        )
        for tid in track_ids:
            self.ctx.registry.get(tid).alert_ids.append(alert.alert_id)
        self.out.alerts.append(alert)
        self.out.actions.append(
            SupervisorAction(
                tool="alert_operator",
                ok=True,
                summary=f"{alert.alert_id} [{alert.urgency}]: {headline}",
                track_ids=track_ids,
            )
        )
        return {"alert_id": alert.alert_id, "delivered": True}

    def dispatch_tracker(self, args: dict[str, Any]) -> dict[str, Any]:
        tid = self.ctx.track_id(args)
        if self.ctx.registry.effective_level(tid) != "HIGH":
            raise BoardError(f"{tid} is not HIGH; use set_level first if the evidence supports it")
        try:
            suspicion = Suspicion.model_validate(args.get("suspicion"))
        except ValidationError as exc:
            raise BoardError(f"invalid suspicion: {exc.errors()[0]['msg']}") from None
        self._evidence(suspicion.evidence_ids)
        tracker = self.ctx.trackers.dispatch(
            self.ctx.repo.tracks[tid], self.ctx.tick_min, self.ctx.base, suspicion
        )
        self.ctx.registry.get(tid).tracker_id = tracker.tracker_id
        self.out.trackers.append(tracker)
        self.out.actions.append(
            SupervisorAction(
                tool="dispatch_tracker",
                ok=True,
                summary=f"{tracker.tracker_id} on {tid}",
                track_ids=[tid],
            )
        )
        return {"tracker_id": tracker.tracker_id, "slots_free": self.ctx.trackers.free_slots()}

    def recall_tracker(self, args: dict[str, Any]) -> dict[str, Any]:
        tracker = self.ctx.trackers.recall(str(args.get("tracker_id")))
        self.ctx.registry.get(tracker.track_id).tracker_id = None
        self.out.trackers.append(tracker)
        self.out.actions.append(
            SupervisorAction(
                tool="recall_tracker",
                ok=True,
                summary=f"{tracker.tracker_id} recalled: {args.get('reason', '')}",
                track_ids=[tracker.track_id],
            )
        )
        return {"tracker_id": tracker.tracker_id, "slots_free": self.ctx.trackers.free_slots()}


def build_user_message(ctx: t.WatchContext, inp: SupervisorInput) -> str:
    """The per-tick user turn: board, unchecked sectors, frames, recent events, area reports."""

    def block(tag: str, value: object) -> str:
        return f"<{tag}>\n{json.dumps(value, ensure_ascii=False)}\n</{tag}>"

    parts = [
        f"Tick {inp.tick}.",
        block("watcher_messages", inp.watcher_messages),
        block("unchecked_sectors", inp.unchecked),
        block("frames", inp.frames),
        block("recent_events", inp.recent_events),
    ]
    if ctx.settings.trackers_enabled:
        active = [tr.model_dump(mode="json", exclude={"suspicion"}) for tr in ctx.trackers.active()]
        parts[0] += f" Tracker slots free: {ctx.trackers.free_slots()} of {ctx.trackers.slots}."
        parts.append(block("trackers", active))
    parts.append(block("untrusted_reports", inp.area_reports))
    return "\n\n".join(parts)


def system_prompt(ctx: t.WatchContext, layout: dict[str, list[str]]) -> tuple[str, list[str]]:
    """The supervisor's fixed system prompt and any warnings."""
    base = ctx.repo.scene.base
    layout_text = "; ".join(f"watcher {w}: {', '.join(s)}" for w, s in layout.items())
    tracker_rules = (
        TRACKER_RULES.format(slots=ctx.settings.tracker_slots)
        if ctx.settings.trackers_enabled
        else NO_TRACKERS
    )
    values: dict[str, object] = {
        "base_name": base.name,
        "base_lat": base.position.lat,
        "base_lon": base.position.lon,
        "n_watchers": len(layout),
        "watcher_layout": layout_text,
        "tracker_rules": tracker_rules,
        "max_tool_calls": ctx.settings.supervisor_max_tool_calls,
        "output_language": LANGUAGE_NAMES[ctx.settings.brief_language],
        **threshold_vars(ctx.tuning),
    }
    return render_with_fallback(PROMPT, ctx.tuning.prompts.supervisor, values)


def _board(inp: SupervisorInput) -> list[dict[str, Any]]:
    """Every MEDIUM/HIGH vehicle on the board (checked and unchecked sectors)."""
    rows = [s for m in inp.watcher_messages for s in m.get("suspicious", [])]
    return rows + [v for u in inp.unchecked for v in u.get("vehicles", [])]


def _checker(ctx: t.WatchContext, inp: SupervisorInput) -> Any:
    def parse(args: dict[str, Any]) -> SupervisorDecision:
        decision = SupervisorDecision.model_validate(
            {**fill_pattern_track_ids(args), "tick": inp.tick}
        )
        ids = [i for p in decision.patterns for i in p.track_ids] + decision.watch_next
        problems = []
        if unknown := sorted({i for i in ids if i not in ctx.repo.tracks}):
            problems.append(f"unknown track ids: {unknown}")
        if bad := ctx.unknown_evidence([e for p in decision.patterns for e in p.evidence_ids]):
            problems.append(f"unknown evidence ids: {sorted(set(bad))}")
        problems += report_problems(
            ctx, decision.report_checks, inp.tick, {r["report_id"] for r in inp.area_reports}
        )
        if problems:
            raise SubmitError("; ".join(problems))
        return decision

    return parse


def fallback_decision(ctx: t.WatchContext, inp: SupervisorInput, out: SupervisorOutcome) -> None:
    """Alert the operator once about confirmed HIGH vehicles; templated summary."""
    board = _board(inp)
    new_high = sorted(
        {
            v["track_id"]
            for v in board
            if ctx.registry.get(v["track_id"]).level == "HIGH"
            and not ctx.registry.get(v["track_id"]).alert_ids
        }
    )
    if new_high:
        try:
            _Effects(ctx, out).alert_operator(
                {
                    "track_ids": new_high,
                    "urgency": "urgent",
                    "headline": f"{len(new_high)} vehicle(s) confirmed HIGH by the watchers",
                    "description": "Confirmed HIGH by the sector watchers: "
                    + ", ".join(new_high)
                    + ". Automatic alert (supervisor model unavailable); check their routes.",
                    "evidence_ids": [f"TRK-{tid}" for tid in new_high],
                }
            )
        except BoardError as exc:
            out.warnings.append(f"fallback alert: {exc}")
    top: WatchLevel = max((v["level"] for v in board), key=level_index, default="LOW")
    high = sorted({v["track_id"] for v in board if v["level"] == "HIGH"})
    out.decision = SupervisorDecision(
        tick=inp.tick,
        situation_summary=(
            f"{len(board)} vehicles on watch lists; HIGH: {', '.join(high) or 'none'}."
        ),
        threat_level=top,
        patterns=[],
        watch_next=high,
    )


async def run_supervisor(
    llm: ChatLLM | None, ctx: t.WatchContext, inp: SupervisorInput
) -> SupervisorOutcome:
    """One supervisor turn; never raises for LLM problems."""
    placeholder = SupervisorDecision(
        tick=inp.tick, situation_summary="-", threat_level="LOW", patterns=[], watch_next=[]
    )
    out = SupervisorOutcome(decision=placeholder, generated_by="llm")
    if llm is None:
        out.generated_by = "fallback"
        out.warnings.append("LLM disabled")
        fallback_decision(ctx, inp, out)
        return out
    effects = _Effects(ctx, out)
    handlers = {
        "get_route": lambda a: t.get_route(ctx, a),
        "get_notes": lambda a: t.get_notes(ctx, a),
        "get_reports": lambda a: t.get_reports(ctx, a),
        "set_level": effects.set_level,
        "alert_operator": effects.alert_operator,
    }
    tools = [t.GET_ROUTE, t.GET_NOTES, t.GET_REPORTS, t.SET_LEVEL, t.ALERT_OPERATOR]
    if ctx.settings.trackers_enabled:
        handlers |= {
            "dispatch_tracker": effects.dispatch_tracker,
            "recall_tracker": effects.recall_tracker,
        }
        tools += [t.DISPATCH_TRACKER, t.RECALL_TRACKER]
    out.system, prompt_warnings = system_prompt(ctx, inp.layout)
    out.user = build_user_message(ctx, inp)
    out.warnings.extend(prompt_warnings)
    loop = await run_tool_loop(
        llm,
        system=out.system,
        user=out.user,
        tools=[*tools, t.SUBMIT_SUPERVISOR_DECISION],
        handlers=handlers,
        submit_name="submit_supervisor_decision",
        parse_submit=_checker(ctx, inp),
        model=ctx.settings.supervisor_model,
        reasoning_effort=ctx.settings.supervisor_reasoning_effort,
        max_tokens=MAX_TOKENS,
        max_lookups=ctx.settings.supervisor_max_tool_calls,
        lookup_tools=t.LOOKUP_TOOLS,
    )
    out.duration_ms, out.tool_calls, out.trace = loop.duration_ms, loop.tool_calls, loop.trace
    out.warnings.extend(loop.warnings)
    if loop.output is None:
        out.generated_by = "fallback"
        out.warnings.append("fallback decision used")
        fallback_decision(ctx, inp, out)
    else:
        out.decision = loop.output
    return out
