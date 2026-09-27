"""Operator conversation in watch mode: dedicated watchers and announced vehicles (fake LLM)."""

import asyncio
import json
from typing import Any

import pytest

from app.agent.llm_client import ChatResult, Message, ToolCall, ToolSpec
from app.agent.watch.boards import BoardError
from app.agent.watch.runner import WatchRunner
from app.agent.watch.supervisor import SupervisorOutcome, _Effects
from app.core.config import Settings
from app.data.repository import Repository
from app.data.scenario import scenario_tracks
from app.domain.scenario import Scenario, ScenarioMessage, ScenarioPoint, ScenarioTrack
from app.services import watch as w
from tests.agent.fake_llm import FakeLLM, rubric_responder, submit
from tests.agent.test_watch_agents import make_ctx


def _scenario(repo: Repository) -> Scenario:
    """A car from the north, straight at the base, 13:55-14:05; announced at 13:56."""
    base = repo.scene.base.position
    points = [
        ScenarioPoint(time=t, lat=base.lat + d, lon=base.lon)
        for t, d in (("13:55", 0.03), ("14:00", 0.02), ("14:05", 0.01))
    ]
    return Scenario(
        name="test",
        description="test",
        operator_messages=[ScenarioMessage(time="13:56", text="create a watcher, a car is coming")],
        extra_tracks=[ScenarioTrack(track_id="T9001", description="friendly car", points=points)],
    )


def operator_responder(sector: str, watch: str) -> Any:
    """The operator turn: both tools in one response, then the reply; everything else as usual."""

    def respond(messages: list[Message], tools: list[ToolSpec]) -> ChatResult:
        if "reply_operator" not in {t["function"]["name"] for t in tools}:
            return rubric_responder(messages, tools)
        if not any(m["role"] == "tool" for m in messages):
            expected = {
                "description": "friendly car",
                "sector": sector,
                "arrive_from": "14:00",
                "arrive_to": "14:10",
                "vehicle_type": "car",
            }
            return ChatResult(
                content="",
                tool_calls=[
                    ToolCall(
                        "a", "create_watcher", json.dumps({"sector": watch, "reason": "asked"})
                    ),
                    ToolCall("b", "register_expected_vehicle", json.dumps(expected)),
                ],
                finish_reason="tool_calls",
            )
        return submit("reply_operator", {"reply": "W done; EXP-1 registered."})

    return respond


@pytest.fixture
def scenario_run(golden_repo: Repository, golden_settings: Settings) -> list[Any]:
    scn = _scenario(golden_repo)
    golden_repo.tracks.update({t.track_id: t for t in scenario_tracks(scn)})
    zones = golden_repo.scene.zones
    first = golden_repo.tracks["T9001"].points[0].position
    sector = w.sector_of(first, zones)
    watch = next(z.name for z in zones if z.name != sector)
    events: list[Any] = []
    llm = FakeLLM(responder=operator_responder(sector, watch))
    runner = WatchRunner(golden_repo, golden_settings, llm, events.append, scenario=scn)
    asyncio.run(runner.run(14 * 60, 14 * 60 + 5))
    return events


def test_operator_creates_a_dedicated_watcher(scenario_run: list[Any]) -> None:
    types = [e.type for e in scenario_run]
    assert types[0] == "tick_started" and types[1] == "scenario_loaded"
    reply = next(e for e in scenario_run if e.type == "operator_reply")
    assert reply.generated_by == "llm" and reply.reply.startswith("W done")
    assert [a.tool for a in reply.actions] == ["create_watcher", "register_expected_vehicle"]
    new = reply.actions[0].summary.split(" · ")[0]  # e.g. "W5"
    sector = reply.actions[0].summary.split(" · ")[1].split(":")[0]
    for tick in (e for e in scenario_run if e.type == "tick_started"):
        assert tick.checks[new] == sector  # every tick, from the tick it was created in
        others = [s for wid, s in tick.checks.items() if wid != new]
        assert sector not in others  # the other watchers leave it to the new one


def test_announced_vehicle_is_matched_and_kept_low(scenario_run: list[Any]) -> None:
    exp = [e.vehicle for e in scenario_run if e.type == "expected_vehicle"]
    assert exp[0].track_id is None and exp[-1].track_id == "T9001"  # registered, then matched
    rows = [r for e in scenario_run if e.type == "watcher_report" for r in e.rows]
    mine = [r for r in rows if r.track_id == "T9001" and r.expected]
    assert all(r.max_level == "LOW" for r in mine)
    raised = [e for e in scenario_run if e.type == "level_changed" and e.track_id == "T9001"]
    assert all(e.to_level == "LOW" for e in raised)


def test_supervisor_may_not_alert_about_announced_vehicles(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    tid = next(iter(ctx.rows))
    ctx.rows[tid] = ctx.rows[tid].model_copy(update={"expected": "EXP-1: announced"})
    effects = _Effects(ctx, SupervisorOutcome.__new__(SupervisorOutcome))
    args = {
        "track_ids": [tid],
        "urgency": "urgent",
        "headline": "h",
        "description": "d",
        "evidence_ids": [f"TRK-{tid}"],
    }
    with pytest.raises(BoardError, match="announced by the operator"):
        effects.alert_operator(args)


def test_a_plain_text_answer_is_the_reply(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    """The model registers the vehicle, then answers in text instead of calling reply_operator."""
    from app.agent.llm_client import ChatResult
    from app.agent.watch.operator import OperatorBoard, OperatorInput, run_operator_turn
    from app.domain.watch import ExpectedVehicle

    ctx = make_ctx(golden_repo, golden_settings)
    sector = golden_repo.scene.zones[0].name
    registered: list[ExpectedVehicle] = []

    def register(v: ExpectedVehicle) -> ExpectedVehicle:
        registered.append(v.model_copy(update={"expected_id": "EXP-1"}))
        return registered[-1]

    args = {
        "description": "van",
        "sector": sector,
        "arrive_from": "14:00",
        "arrive_to": "14:20",
        "vehicle_type": "van",
    }
    text = ChatResult(content="EXP-1 kaydedildi; LOW tutulacak.", finish_reason="stop")
    llm = FakeLLM([submit("register_expected_vehicle", args), text, text])
    inp = OperatorInput(
        tick="14:05",
        time="14:01",
        text="a van is coming",
        layout={},
        dedicated={},
        flagged=[],
        expected=[],
    )
    out = await_(run_operator_turn(llm, ctx, inp, OperatorBoard(lambda s, r: "W5", register)))
    assert out.generated_by == "llm" and out.reply == "EXP-1 kaydedildi; LOW tutulacak."
    assert [a.tool for a in out.actions] == ["register_expected_vehicle"] and registered
    assert any("reply taken from the model's text" in w for w in out.warnings)


def await_(coro: Any) -> Any:
    return asyncio.run(coro)


def test_fallback_reply_says_what_the_tools_did() -> None:
    from app.agent.fallback_templates import operator_fallback

    done = [
        {"kind": "watcher", "wid": "W5", "sector": "Dogu Yolu"},
        {
            "kind": "expected",
            "eid": "EXP-1",
            "sector": "Kuzey Yolu",
            "start": "10:45",
            "end": "11:05",
        },
    ]
    text = operator_fallback("tr", done)
    assert text.startswith("W5 oluşturuldu; Doğu Yolu bölgesini")
    assert "EXP-1 kaydedildi: Kuzey Yolu üzerinden 10:45–11:05" in text and "LOW" in text
    assert operator_fallback("tr", []).startswith("Mesajınızı aldım")
