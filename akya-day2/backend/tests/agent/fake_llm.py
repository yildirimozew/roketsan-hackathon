"""Deterministic stand-ins for the GLM client (tests never call the real LLM)."""

import json
import re
from collections.abc import Callable
from typing import Any

from app.agent.llm_client import ChatResult, Message, ToolCall, ToolSpec
from app.core.errors import LLMError

Responder = Callable[[list[Message], list[ToolSpec]], ChatResult]


def submit(name: str, args: dict[str, Any], call_id: str = "c1") -> ChatResult:
    """A response that calls one tool."""
    return ChatResult(
        content="",
        tool_calls=[ToolCall(id=call_id, name=name, arguments=json.dumps(args))],
        finish_reason="tool_calls",
    )


class FakeLLM:
    """Returns scripted results in order, or asks a responder function."""

    model = "fake"

    def __init__(
        self, script: list[ChatResult | Exception] | None = None, responder: Responder | None = None
    ) -> None:
        self.script = list(script or [])
        self.responder = responder
        self.requests: list[list[Message]] = []

    async def chat(
        self,
        messages: list[Message],
        tools: list[ToolSpec],
        *,
        model: str | None = None,
        reasoning_effort: str = "low",
        max_tokens: int = 8000,
    ) -> ChatResult:
        self.requests.append([dict(m) for m in messages])
        if self.script:
            item = self.script.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        if self.responder is not None:
            return self.responder(messages, tools)
        raise LLMError("script exhausted")


def _block(text: str, tag: str) -> Any:
    match = re.search(rf"<{tag}>\n(.*?)\n</{tag}>", text, re.S)
    return json.loads(match.group(1)) if match else None


def _unverifiable(user: str) -> list[dict[str, Any]]:
    return [
        {
            "report_id": r["report_id"],
            "verdict": "UNVERIFIABLE",
            "credibility": 40,
            "reason": "fake report check",
            "track_ids": [],
            "conflicts_with": [],
            "deception": False,
        }
        for r in _block(user, "untrusted_reports") or []
    ]


def rubric_responder(messages: list[Message], tools: list[ToolSpec]) -> ChatResult:
    """Watchers: every listed vehicle at its rubric level (CRITICAL -> HIGH).
    Supervisor: a plain decision without actions. Both judge every new report UNVERIFIABLE."""
    user = messages[1]["content"]
    tick = re.match(r"Tick (\d\d:\d\d)", user)
    assert tick is not None
    names = {t["function"]["name"] for t in tools}
    if "submit_watch_report" in names:
        vehicles = _block(user, "vehicles") or []
        return submit(
            "submit_watch_report",
            {
                "tick": tick.group(1),
                "street_state": "fake street state",
                "vehicles": [
                    {
                        "track_id": v["track_id"],
                        "level": {"CRITICAL": "HIGH"}.get(
                            v["rubric"]["level"], v["rubric"]["level"]
                        ),
                        "reason": "fake reason",
                        "evidence_ids": [f"TRK-{v['track_id']}"],
                        "note": None,
                    }
                    for v in vehicles
                ],
                "patterns": [],
                "report_checks": _unverifiable(user),
            },
        )
    return submit(
        "submit_supervisor_decision",
        {
            "tick": tick.group(1),
            "situation_summary": "fake summary",
            "threat_level": "LOW",
            "patterns": [],
            "watch_next": [],
            "report_checks": _unverifiable(user),
        },
    )
