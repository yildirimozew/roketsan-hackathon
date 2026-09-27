"""One agent turn as a bounded tool-calling loop that must end with a `submit_*` call.

Shared by the watcher and the supervisor. The model may make up to `max_lookups` read-only tool
calls (`lookup_tools`); state-changing tools are bounded only by the round-trip cap. An invalid or
missing submission gets one repair message with the error; after that the caller uses its
deterministic fallback. LLM failures never raise out of here.
"""

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.agent.llm_client import ChatLLM, Message, ToolSpec
from app.agent.watch.boards import BoardError
from app.core.errors import LLMError

Handler = Callable[[dict[str, Any]], dict[str, Any]]
MAX_ROUND_TRIPS_EXTRA = 3  # round trips allowed beyond the lookup budget (submit + repair)


class SubmitError(ValueError):
    """A `submit_*` call whose content fails our checks; the message goes back to the model."""


def fill_pattern_track_ids(args: dict[str, Any]) -> dict[str, Any]:
    """GLM often leaves `track_ids` out of a pattern (or `track_id` out of a vehicle entry) but
    cites the vehicles as TRK-<id> evidence; derive the ids from the evidence instead of spending
    a repair round trip."""

    def trk(item: dict[str, Any]) -> list[str]:
        return [e[4:] for e in item.get("evidence_ids") or [] if str(e).startswith("TRK-")]

    out = dict(args)
    if isinstance(args.get("patterns"), list):
        out["patterns"] = [
            {**p, "track_ids": trk(p)} if isinstance(p, dict) and not p.get("track_ids") else p
            for p in args["patterns"]
        ]
    if isinstance(args.get("vehicles"), list):
        out["vehicles"] = [
            {**v, "track_id": trk(v)[0]}
            if isinstance(v, dict) and not v.get("track_id") and trk(v)
            else v
            for v in args["vehicles"]
        ]
    return out


@dataclass
class LoopResult[T]:
    """What one agent turn produced."""

    output: T | None
    tool_calls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    llm_calls: int = 0
    duration_ms: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)  # every LLM call and tool result


async def run_tool_loop[T](
    llm: ChatLLM,
    *,
    system: str,
    user: str,
    tools: list[ToolSpec],
    handlers: dict[str, Handler],
    submit_name: str,
    parse_submit: Callable[[dict[str, Any]], T],
    model: str | None,
    reasoning_effort: str,
    max_tokens: int,
    max_lookups: int,
    lookup_tools: frozenset[str],
) -> LoopResult[T]:
    """Run the loop; `parse_submit` raises SubmitError or ValidationError on a bad submission."""
    started = time.perf_counter()
    result: LoopResult[T] = LoopResult(output=None)
    messages: list[Message] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    lookups = repairs = 0
    for _ in range(max_lookups + MAX_ROUND_TRIPS_EXTRA):
        try:
            response = await llm.chat(
                messages,
                tools,
                model=model,
                reasoning_effort=reasoning_effort,
                max_tokens=max_tokens,
            )
        except LLMError as exc:
            result.warnings.append(f"LLM call failed: {exc}")
            break
        result.llm_calls += 1
        result.trace.append(
            {
                "step": "llm",
                "call": result.llm_calls,
                "reasoning": response.reasoning,
                "content": response.content,
                "tool_calls": [
                    {"id": c.id, "name": c.name, "arguments": _parse_or_raw(c.arguments)}
                    for c in response.tool_calls
                ],
                "finish_reason": response.finish_reason,
                "latency_ms": response.latency_ms,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "cached": response.cached,
            }
        )
        messages.append(response.assistant_message())
        if not response.tool_calls:
            if response.finish_reason == "length":
                result.warnings.append("model output was cut off (max_tokens)")
            repairs += 1
            if repairs > 1:
                break
            nudge = f"Finish now by calling {submit_name} with your answer."
            result.trace.append({"step": "repair", "message": nudge})
            messages.append({"role": "user", "content": nudge})
            continue

        for call in response.tool_calls:
            result.tool_calls.append(call.name)
            limited = call.name in lookup_tools
            over = limited and lookups >= max_lookups
            payload = _run_call(call.name, call.arguments, handlers, submit_name, over)
            if limited and "error" not in payload:
                lookups += 1
            if call.name == submit_name and "error" not in payload:
                try:
                    result.output = parse_submit(payload["args"])
                    payload = {"ok": True}
                except (SubmitError, ValidationError) as exc:
                    repairs += 1
                    payload = {"error": f"invalid {submit_name}: {_short(exc)}"}
                    result.warnings.append(payload["error"])
            result.trace.append(
                {"step": "tool", "id": call.id, "name": call.name, "result": payload}
            )
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(payload, ensure_ascii=False),
                }
            )
        if result.output is not None or repairs > 1:
            break
    result.duration_ms = round((time.perf_counter() - started) * 1000)
    return result


def _run_call(
    name: str,
    raw_args: str,
    handlers: dict[str, Handler],
    submit_name: str,
    over_limit: bool,
) -> dict[str, Any]:
    """Execute one tool call; errors come back as {"error": ...} for the model to read."""
    try:
        args = json.loads(raw_args or "{}")
    except json.JSONDecodeError:
        return {"error": "arguments are not valid JSON"}
    if not isinstance(args, dict):
        return {"error": "arguments must be a JSON object"}
    if name == submit_name:
        return {"args": args}
    handler = handlers.get(name)
    if handler is None:
        return {"error": f"unknown tool {name}"}
    if over_limit:
        return {"error": f"lookup limit reached for this tick; act or call {submit_name} now"}
    try:
        return handler(args)
    except BoardError as exc:
        return {"error": str(exc)}


def _parse_or_raw(arguments: str) -> Any:
    """Tool arguments as JSON when they parse, else the raw string (for traces)."""
    try:
        return json.loads(arguments or "{}")
    except json.JSONDecodeError:
        return arguments


def _short(exc: Exception) -> str:
    """Compact validation message for the model (first few errors only)."""
    if isinstance(exc, ValidationError):
        parts = [f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()[:5]]
        return "; ".join(parts)
    return str(exc)
