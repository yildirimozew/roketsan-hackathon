"""Operator conversation: the human operator writes to the supervisor during a watch run, and the
supervisor answers in one LLM turn with tools that change the watch (AGENT_DESIGN §12, operator).

The operator is trusted, unlike field reports. Tools: `create_watcher` (a new watcher dedicated to
one sector) and `register_expected_vehicle` (a vehicle the operator announces; code matches it to a
track and keeps it LOW), plus read-only lookups. The turn ends with `reply_operator`.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from app.agent.fallback_templates import operator_fallback
from app.agent.llm_client import ChatLLM
from app.agent.watch import tools as t
from app.agent.watch.boards import BoardError
from app.agent.watch.loop import run_tool_loop
from app.agent.watch.prompts import LANGUAGE_NAMES, render
from app.domain.watch import ExpectedVehicle, GeneratedBy, SupervisorAction
from app.services.watch import resolve_sector

PROMPT = "operator_chat_v2"
MAX_TOKENS = 6000
_HHMM = re.compile(r"^\d{2}:\d{2}$")


class OperatorReply(BaseModel):
    """`reply_operator` arguments."""

    reply: str = Field(min_length=1)


@dataclass
class OperatorInput:
    """One operator message and the state the supervisor answers it in."""

    tick: str
    time: str  # HH:MM the operator wrote it
    text: str
    layout: dict[str, list[str]]  # watcher -> sectors
    dedicated: dict[str, str]  # watcher -> the one sector it checks every tick
    flagged: list[dict[str, Any]]  # MEDIUM/HIGH vehicles now
    expected: list[ExpectedVehicle]


@dataclass
class OperatorOutcome:
    """The supervisor's answer and what its tools did."""

    reply: str
    generated_by: GeneratedBy
    duration_ms: int = 0
    actions: list[SupervisorAction] = field(default_factory=list)
    tool_calls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    system: str = ""
    user: str = ""
    trace: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class OperatorBoard:
    """What the operator's tools may change, provided by the runner."""

    create_watcher: Callable[[str, str], str]  # (sector, reason) -> watcher id
    register_expected: Callable[[ExpectedVehicle], ExpectedVehicle]  # assigns the id


class _Effects:
    """Side-effecting tool handlers for one operator turn; records what they did."""

    def __init__(self, ctx: t.WatchContext, inp: OperatorInput, board: OperatorBoard) -> None:
        self.ctx, self.inp, self.board = ctx, inp, board
        self.actions: list[SupervisorAction] = []
        self.done: list[dict[str, str]] = []  # for a templated reply if the model writes none

    def _sector(self, raw: Any) -> str:
        sector = resolve_sector(str(raw or ""), self.ctx.repo.scene.zones)
        if sector is None:
            names = [z.name for z in self.ctx.repo.scene.zones]
            raise BoardError(f"unknown sector {raw!r}; use one of {names}")
        return sector

    def create_watcher(self, args: dict[str, Any]) -> dict[str, Any]:
        sector = self._sector(args.get("sector"))
        reason = str(args.get("reason") or "").strip() or "operator request"
        wid = self.board.create_watcher(sector, reason)
        self.done.append({"kind": "watcher", "wid": wid, "sector": sector})
        self.actions.append(
            SupervisorAction(tool="create_watcher", ok=True, summary=f"{wid} · {sector}: {reason}")
        )
        return {"watcher_id": wid, "sector": sector, "checks": "every tick, starting this tick"}

    def register_expected_vehicle(self, args: dict[str, Any]) -> dict[str, Any]:
        sector = self._sector(args.get("sector"))
        start, end = str(args.get("arrive_from") or ""), str(args.get("arrive_to") or "")
        if not (_HHMM.match(start) and _HHMM.match(end)) or start > end:
            raise BoardError(
                "arrive_from and arrive_to must be HH:MM with arrive_from <= arrive_to"
            )
        description = str(args.get("description") or "").strip()
        if not description:
            raise BoardError("description is required")
        kind = args.get("vehicle_type")
        vehicle = self.board.register_expected(
            ExpectedVehicle(
                expected_id="",
                announced_at=self.inp.time,
                description=description,
                sector=sector,
                arrive_from=start,
                arrive_to=end,
                vehicle_type=kind if kind in ("car", "van", "truck", "bus") else None,
            )
        )
        self.done.append(
            {
                "kind": "expected",
                "eid": vehicle.expected_id,
                "sector": sector,
                "start": start,
                "end": end,
            }
        )
        self.actions.append(
            SupervisorAction(
                tool="register_expected_vehicle",
                ok=True,
                summary=f"{vehicle.expected_id} · {sector} {start}-{end}: {description}",
            )
        )
        return {
            "expected_id": vehicle.expected_id,
            "effect": "matched to its track when it appears in that sector and window; kept LOW",
        }


def build_user_message(inp: OperatorInput) -> str:
    """The operator's message with the current layout and board."""

    def block(tag: str, value: object) -> str:
        return f"<{tag}>\n{json.dumps(value, ensure_ascii=False)}\n</{tag}>"

    layout = [
        {"watcher": w, "sectors": s, "dedicated": w in inp.dedicated} for w, s in inp.layout.items()
    ]
    return "\n\n".join(
        [
            f"Tick {inp.tick}. The operator wrote at {inp.time}:",
            block("operator_message", inp.text),
            block("layout", layout),
            block("sectors", sorted({s for secs in inp.layout.values() for s in secs})),
            block("flagged_vehicles", inp.flagged),
            block("expected_vehicles", [e.model_dump(mode="json") for e in inp.expected]),
        ]
    )


def system_prompt(ctx: t.WatchContext) -> str:
    """The operator-conversation system prompt."""
    base = ctx.repo.scene.base
    return render(
        PROMPT,
        base_name=base.name,
        output_language=LANGUAGE_NAMES[ctx.settings.brief_language],
    )


def plain_text_reply(trace: list[dict[str, Any]]) -> str | None:
    """The model's last plain-text answer, when it answered without calling reply_operator
    (the reply is free text, so a written answer is still the answer)."""
    for step in reversed(trace):
        text = str(step.get("content") or "").strip() if step.get("step") == "llm" else ""
        if text:
            return text
    return None


def _parse(args: dict[str, Any]) -> OperatorReply:
    return OperatorReply.model_validate(args)


async def run_operator_turn(
    llm: ChatLLM | None, ctx: t.WatchContext, inp: OperatorInput, board: OperatorBoard
) -> OperatorOutcome:
    """One supervisor answer to the operator; never raises for LLM problems."""
    lang = ctx.settings.brief_language
    if llm is None:
        return OperatorOutcome(operator_fallback(lang), "fallback", warnings=["LLM disabled"])
    effects = _Effects(ctx, inp, board)
    handlers = {
        "get_route": lambda a: t.get_route(ctx, a),
        "get_notes": lambda a: t.get_notes(ctx, a),
        "create_watcher": effects.create_watcher,
        "register_expected_vehicle": effects.register_expected_vehicle,
    }
    system, user = system_prompt(ctx), build_user_message(inp)
    loop = await run_tool_loop(
        llm,
        system=system,
        user=user,
        tools=[
            t.GET_ROUTE,
            t.GET_NOTES,
            t.CREATE_WATCHER,
            t.REGISTER_EXPECTED_VEHICLE,
            t.REPLY_OPERATOR,
        ],
        handlers=handlers,
        submit_name="reply_operator",
        parse_submit=_parse,
        model=ctx.settings.supervisor_model,
        reasoning_effort=ctx.settings.supervisor_reasoning_effort,
        max_tokens=MAX_TOKENS,
        max_lookups=ctx.settings.supervisor_max_tool_calls,
        lookup_tools=t.LOOKUP_TOOLS,
    )
    warnings = list(loop.warnings)
    reply = loop.output.reply if loop.output is not None else plain_text_reply(loop.trace)
    if loop.output is None and reply is not None:
        warnings.append("reply taken from the model's text (reply_operator not called)")
    return OperatorOutcome(
        reply=reply if reply is not None else operator_fallback(lang, effects.done),
        generated_by="llm" if reply is not None else "fallback",
        duration_ms=loop.duration_ms,
        actions=effects.actions,
        tool_calls=loop.tool_calls,
        warnings=warnings,
        system=system,
        user=user,
        trace=loop.trace,
    )
