"""Watch agents with a fake LLM: tool loop, repair, fallbacks, supervisor effects, runner."""

from typing import Any

import pytest

from app.agent.llm_client import ChatResult
from app.agent.tuning_store import with_agent_knobs
from app.agent.watch import tools as t
from app.agent.watch.boards import AlertBoard, BoardError, TrackerBoard
from app.agent.watch.registry import CarRegistry
from app.agent.watch.runner import WatchRunner
from app.agent.watch.supervisor import SupervisorInput, run_supervisor
from app.agent.watch.tools import WatchContext
from app.agent.watch.watcher import (
    WatcherInput,
    build_user_message,
    judged_rows,
    needs_judgment,
    run_watcher,
)
from app.core.config import Settings
from app.core.errors import LLMError
from app.data.repository import Repository
from app.services import watch as w
from app.services.reports import extract_claim
from app.services.tuning import DEFAULT_TUNING
from tests.agent.fake_llm import FakeLLM, rubric_responder, submit

TICK = 14 * 60 + 5


def allow_high(ctx: WatchContext, tid: str) -> None:
    """Let a vehicle reach HIGH (its ceiling) for tests that need a HIGH."""
    ctx.rows[tid] = ctx.rows[tid].model_copy(update={"max_level": "HIGH"})


def make_ctx(repo: Repository, settings: Settings) -> WatchContext:
    base, zones = repo.scene.base.position, repo.scene.zones
    rows = {}
    for tid, track in repo.tracks.items():
        upto = w.track_until(track, TICK)
        if upto is not None:
            rows[tid] = w.vehicle_row(
                upto,
                TICK,
                base,
                zones,
                stop_speed_ms=1.0,
                zone_radius_m=2000,
                prev_sector=None,
                registry_level="LOW",
                pending_level=None,
                notes_count=0,
                lang="en",
            )
    return WatchContext(
        repo=repo,
        settings=settings,
        tick_min=TICK,
        claims=[extract_claim(r, zones) for r in repo.reports],
        registry=CarRegistry(),
        trackers=TrackerBoard(2),
        alerts=AlertBoard(),
        rows=rows,
    )


def watcher_input(ctx: WatchContext) -> WatcherInput:
    rows = list(ctx.rows.values())
    sectors = sorted({r.sector for r in rows})
    return WatcherInput(
        watcher_id="W1",
        area=sectors,
        sectors=sectors,
        last_checked=None,
        tick="14:05",
        rows=rows,
        new_arrivals=[],
        notes=[],
        frames=[],
        reports=[],
    )


def good_report(ctx: WatchContext, level: str = "HIGH") -> dict[str, Any]:
    return {
        "tick": "14:05",
        "street_state": "ok",
        "vehicles": [
            {
                "track_id": tid,
                "level": level,
                "reason": "r",
                "evidence_ids": [f"TRK-{tid}"],
                "note": None,
            }
            for tid, row in ctx.rows.items()
        ],
        "patterns": [],
    }


async def test_watcher_valid_submission(golden_repo: Repository, golden_settings: Settings) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    llm = FakeLLM([submit("submit_watch_report", good_report(ctx, "MEDIUM"))])
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    assert out.generated_by == "llm"
    assert {v.track_id for v in out.report.vehicles} == set(ctx.rows)


async def test_watcher_repairs_once_after_invalid_submission(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    bad = good_report(ctx)
    bad["vehicles"][0]["evidence_ids"] = ["TRK-NOPE"]
    llm = FakeLLM(
        [submit("submit_watch_report", bad), submit("submit_watch_report", good_report(ctx))]
    )
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    assert out.generated_by == "llm"
    assert any("unknown evidence" in m for m in out.warnings)
    assert "unknown evidence ids" in llm.requests[1][-1]["content"]  # error went back to the model


async def test_watcher_falls_back_on_llm_error(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    out = await run_watcher(FakeLLM([LLMError("timeout")]), ctx, watcher_input(ctx))
    assert out.generated_by == "fallback"
    assert all(v.reason.startswith("Rubric") for v in out.report.vehicles)


async def test_watcher_levels_are_clamped_to_one_step_from_rubric(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    tid, row = next(iter(ctx.rows.items()))
    ctx.rows[tid] = row.model_copy(
        update={
            "rubric": row.rubric.model_copy(update={"level": "HIGH", "score": 60}),
            "max_level": "HIGH",
        }
    )
    llm = FakeLLM([submit("submit_watch_report", good_report(ctx, "LOW"))])
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    levels = {v.track_id: v.level for v in out.report.vehicles}
    assert levels[tid] == "MEDIUM"  # rubric HIGH: at most one step below
    assert any(m.startswith(f"{tid}: level LOW clamped") for m in out.warnings)


async def test_lookup_budget_is_enforced(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings.model_copy(update={"watcher_max_tool_calls": 1}))
    lookups = [submit("get_route", {"track_id": "T0122"}, f"l{i}") for i in range(2)]
    llm = FakeLLM([*lookups, submit("submit_watch_report", good_report(ctx))])
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    assert out.generated_by == "llm"
    assert "lookup limit" in llm.requests[2][-1]["content"]


def supervisor_input() -> SupervisorInput:
    return SupervisorInput(
        tick="14:05",
        watcher_messages=[],
        unchecked=[],
        frames=[],
        recent_events=[],
        area_reports=[],
        layout={"W1": []},
    )


def decision() -> ChatResult:
    return submit(
        "submit_supervisor_decision",
        {
            "tick": "14:05",
            "situation_summary": "s",
            "threat_level": "HIGH",
            "patterns": [],
            "watch_next": ["T0122"],
        },
    )


async def test_supervisor_informs_operator_and_has_no_trackers_by_default(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    allow_high(ctx, "T0122")
    llm = FakeLLM(
        [
            submit("dispatch_tracker", {"track_id": "T0122"}),
            submit(
                "set_level",
                {
                    "track_id": "T0122",
                    "level": "HIGH",
                    "reason": "pattern",
                    "evidence_ids": ["TRK-T0122"],
                },
            ),
            submit(
                "alert_operator",
                {
                    "track_ids": ["T0122"],
                    "urgency": "urgent",
                    "headline": "truck closing",
                    "description": "T0122 is 1.6 km east and closing.",
                    "evidence_ids": ["TRK-T0122"],
                },
            ),
            decision(),
        ]
    )
    out = await run_supervisor(llm, ctx, supervisor_input())
    assert "unknown tool dispatch_tracker" in llm.requests[1][-1]["content"]
    assert out.generated_by == "llm"
    assert [a.tool for a in out.actions] == ["set_level", "alert_operator"]
    assert out.alerts[0].description.startswith("T0122")
    assert ctx.registry.get("T0122").alert_ids == ["ALR-1"]
    assert not ctx.trackers.all()


async def test_tracker_dispatch_requires_high_when_trackers_are_enabled(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings.model_copy(update={"trackers_enabled": True}))
    allow_high(ctx, "T0122")
    suspicion = {
        "hypothesis": "h",
        "evidence_ids": ["TRK-T0122"],
        "what_would_clear_it": "c",
        "confidence": "medium",
    }
    set_high = {
        "track_id": "T0122",
        "level": "HIGH",
        "reason": "pattern",
        "evidence_ids": ["TRK-T0122"],
    }
    llm = FakeLLM(
        [
            submit("dispatch_tracker", {"track_id": "T0122", "suspicion": suspicion}),
            submit("set_level", set_high),
            submit("dispatch_tracker", {"track_id": "T0122", "suspicion": suspicion}),
            decision(),
        ]
    )
    out = await run_supervisor(llm, ctx, supervisor_input())
    assert "is not HIGH" in llm.requests[1][-1]["content"]
    assert [a.tool for a in out.actions] == ["set_level", "dispatch_tracker"]
    assert ctx.trackers.for_track("T0122") is not None


@pytest.mark.parametrize("use_llm", [True, False])
async def test_runner_emits_a_full_tick(
    golden_repo: Repository, golden_settings: Settings, use_llm: bool
) -> None:
    events: list[Any] = []
    llm = FakeLLM(responder=rubric_responder) if use_llm else None
    runner = WatchRunner(golden_repo, golden_settings, llm, events.append)
    await runner.run(14 * 60, TICK)
    types = [e.type for e in events]
    assert types[0] == "tick_started" and types[-1] == "tick_completed"
    assert types.count("tick_started") == 2 and "supervisor_decision" in types
    assert "tracker_update" not in types  # trackers are off by default
    reports = [e for e in events if e.type == "watcher_report" and e.rows]
    assert reports and all(r.generated_by == ("llm" if use_llm else "fallback") for r in reports)
    # a raise proposed at one check and repeated at a later check is confirmed
    confirmed = [e for e in events if e.type == "level_changed" and not e.pending]
    pending = [e for e in events if e.type == "level_changed" and e.pending]
    assert {e.track_id for e in confirmed} <= {e.track_id for e in pending}


async def test_watchers_take_turns_and_a_frame_gets_priority(
    golden_repo: Repository, golden_settings: Settings, golden_detector: Any
) -> None:
    events: list[Any] = []
    settings = golden_settings.model_copy(update={"watcher_count": 4})
    runner = WatchRunner(golden_repo, settings, None, events.append, golden_detector)
    assert runner.groups["W2"] == ["Dogu Yolu", "Guneydogu Sanayi"]  # fixture zone names
    await runner.run(14 * 60 + 5, 14 * 60 + 10)
    checks = [e.checks for e in events if e.type == "tick_started"]
    assert [c["W1"] for c in checks] == ["Kuzey Yolu", "Kuzeydogu Tepesi"]  # taking turns
    # at 14:10 it is Guneydogu's turn, but frame img_000860 in Dogu Yolu takes priority
    assert [c["W2"] for c in checks] == ["Dogu Yolu", "Dogu Yolu"]
    (frame,) = [e for e in events if e.type == "frame_analyzed"]
    assert frame.status == "ok" and frame.sector == "Dogu Yolu"
    truck = next(d for d in frame.detections if d.track_id == "T0122")
    assert truck.label == "truck"
    assert runner.registry.get("T0122").vehicle_type == "truck"
    report = next(
        e for e in events if e.type == "watcher_report" and e.tick == "14:10" and e.watcher == "W2"
    )
    row = next(r for r in report.rows if r.track_id == "T0122")
    assert row.vehicle_type == "truck" and "vehicle_type" in [f.name for f in row.rubric.factors]


async def test_pattern_track_ids_are_derived_from_evidence(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    report = good_report(ctx)
    report["patterns"] = [{"description": "together", "evidence_ids": ["TRK-T0122", "TRK-T0032"]}]
    llm = FakeLLM([submit("submit_watch_report", report)])
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    assert out.generated_by == "llm" and len(llm.requests) == 1  # no repair round trip
    assert out.report.patterns[0].track_ids == ["T0122", "T0032"]


async def test_vehicle_track_id_is_derived_from_evidence(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    report = good_report(ctx)
    del report["vehicles"][0]["track_id"]
    llm = FakeLLM([submit("submit_watch_report", report)])
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    assert out.generated_by == "llm" and len(llm.requests) == 1
    assert {v.track_id for v in out.report.vehicles} == set(ctx.rows)


def test_get_route_takes_several_vehicles_in_one_call(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    out = t.get_route(ctx, {"track_ids": ["T0122", "T0032"]})
    assert [r["track_id"] for r in out["routes"]] == ["T0122", "T0032"]
    with pytest.raises(BoardError):
        t.get_route(ctx, {"track_ids": ["T0122"] * 6})


async def test_spot_checked_vehicle_must_be_judged(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    inp = watcher_input(ctx)
    tid, row = next(iter(ctx.rows.items()))
    quiet = row.model_copy(
        update={
            "rubric": row.rubric.model_copy(update={"level": "LOW", "score": 0}),
            "closing_last5_m_per_min": 0,
            "status": "staying",
        }
    )
    inp.rows = [quiet if r.track_id == tid else r for r in inp.rows]
    assert tid not in {r.track_id for r in judged_rows(inp)}
    inp.spot_checks = [tid]
    assert tid in {r.track_id for r in judged_rows(inp)}
    assert '"spot_check": true' in build_user_message(inp)
    report = good_report(ctx)
    report["vehicles"] = [v for v in report["vehicles"] if v["track_id"] != tid]
    llm = FakeLLM(
        [submit("submit_watch_report", report), submit("submit_watch_report", good_report(ctx))]
    )
    out = await run_watcher(llm, ctx, inp)
    assert f"missing vehicles from <vehicles>: ['{tid}']" in out.warnings[0]


async def test_runner_emits_agent_traces_with_every_step(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    events: list[Any] = []
    runner = WatchRunner(
        golden_repo, golden_settings, FakeLLM(responder=rubric_responder), events.append
    )
    await runner.run(TICK, TICK)
    traces = [e for e in events if e.type == "agent_trace"]
    assert {tr.agent.split(":")[0] for tr in traces} == {"watcher", "supervisor"}
    for tr in traces:
        assert tr.system_prompt.startswith("# Role") and tr.user_message.startswith("Tick 14:05")
        kinds = [s["step"] for s in tr.steps]
        assert kinds[0] == "llm" and "tool" in kinds and tr.output is not None
        assert "reasoning" in tr.steps[0]


async def test_levels_never_exceed_the_vehicle_ceiling(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    # 3.5 km out, closing at 6 m/s, ETA 8.4 min: normal driving toward the base, capped at LOW
    assert ctx.rows["T0122"].max_level == "LOW"
    llm = FakeLLM([submit("submit_watch_report", good_report(ctx, "HIGH"))])
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    order = ["LOW", "MEDIUM", "HIGH"]
    for v in out.report.vehicles:
        assert order.index(v.level) <= order.index(ctx.rows[v.track_id].max_level)


async def test_supervisor_cannot_set_a_level_above_the_ceiling(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    set_high = {"track_id": "T0122", "level": "HIGH", "reason": "r", "evidence_ids": ["TRK-T0122"]}
    llm = FakeLLM([submit("set_level", set_high), decision()])
    out = await run_supervisor(llm, ctx, supervisor_input())
    assert "may be at most LOW" in llm.requests[1][-1]["content"]
    assert ctx.registry.get("T0122").level == "LOW" and not out.level_changes


async def test_level_drops_to_the_ceiling_when_no_longer_justified(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    tid = "T0122"
    ctx.rows[tid] = ctx.rows[tid].model_copy(update={"registry_level": "HIGH"})
    llm = FakeLLM([submit("submit_watch_report", good_report(ctx, "MEDIUM"))])
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    assert {v.track_id: v.level for v in out.report.vehicles}[tid] == ctx.rows[tid].max_level


def judgment(report_id: str, **kw: Any) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "verdict": "CONTRADICTED",
        "credibility": 10,
        "reason": "Tracks show no truck there.",
        "track_ids": [],
        "conflicts_with": [],
        "deception": False,
    } | kw


async def test_watcher_must_judge_every_new_report(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    inp = watcher_input(ctx)
    inp.reports = [c for c in ctx.claims if c.report_id == "REP-01"]
    judged = good_report(ctx, "MEDIUM") | {
        "report_checks": [judgment("REP-01", conflicts_with=["REP-03"], deception=True)]
    }
    llm = FakeLLM(
        [
            submit("submit_watch_report", good_report(ctx, "MEDIUM")),
            submit("submit_watch_report", judged),
        ]
    )
    out = await run_watcher(llm, ctx, inp)
    assert "missing report_checks for ['REP-01']" in llm.requests[1][-1]["content"]
    check = out.report.report_checks[0]
    assert (check.verdict, check.credibility, check.conflicts_with) == (
        "CONTRADICTED",
        10,
        ["REP-03"],
    )
    assert check.deception  # the model's own judgment; code does not overrule it


async def test_report_judgments_must_name_real_reports(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    bad = good_report(ctx, "MEDIUM") | {
        "report_checks": [judgment("REP-01", conflicts_with=["REP-99"])]
    }
    llm = FakeLLM(
        [submit("submit_watch_report", bad), submit("submit_watch_report", good_report(ctx))]
    )
    out = await run_watcher(llm, ctx, watcher_input(ctx))
    assert out.generated_by == "llm" and out.report.report_checks == []
    assert "unknown report ids" in llm.requests[1][-1]["content"]


async def test_supervisor_must_judge_area_reports(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    area = [{"report_id": "REP-02", "time": "11:55", "source": "third_party", "text": "..."}]
    inp = SupervisorInput(
        tick="14:05",
        watcher_messages=[],
        unchecked=[],
        frames=[],
        recent_events=[],
        area_reports=area,
        layout={},
    )
    plain = {
        "tick": "14:05",
        "situation_summary": "s",
        "threat_level": "LOW",
        "patterns": [],
        "watch_next": [],
    }
    judged = plain | {"report_checks": [judgment("REP-02", verdict="UNVERIFIABLE", credibility=40)]}
    llm = FakeLLM(
        [submit("submit_supervisor_decision", plain), submit("submit_supervisor_decision", judged)]
    )
    out = await run_supervisor(llm, ctx, inp)
    assert "missing report_checks for ['REP-02']" in llm.requests[1][-1]["content"]
    assert [c.report_id for c in out.decision.report_checks] == ["REP-02"]


async def test_runner_passes_report_judgments_on(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    events: list[Any] = []
    runner = WatchRunner(
        golden_repo, golden_settings, FakeLLM(responder=rubric_responder), events.append
    )
    await runner.run(13 * 60, 13 * 60 + 15)
    judged = [
        e
        for e in events
        if e.type == "watcher_report"
        and any(c.report_id == "REP-01" for c in e.report.report_checks)
    ]
    assert len(judged) == 1  # judged once, at the first check of its sector after 13:05
    event = judged[0]
    assert [r.report_id for r in event.reports] == ["REP-01"]  # text for the UI
    trace = next(
        e
        for e in events
        if e.type == "agent_trace" and e.agent == "supervisor" and e.tick == event.tick
    )
    assert (
        '"report_id": "REP-01"' in trace.user_message and '"credibility": 40' in trace.user_message
    )


def test_with_agent_knobs_only_overrides_set_values(golden_settings: Settings) -> None:
    knobs = DEFAULT_TUNING.agents.model_copy(update={"watcher_max_tool_calls": 1})
    s = with_agent_knobs(golden_settings, DEFAULT_TUNING.model_copy(update={"agents": knobs}))
    assert s.watcher_max_tool_calls == 1
    assert s.supervisor_max_tool_calls == golden_settings.supervisor_max_tool_calls
    assert with_agent_knobs(golden_settings, DEFAULT_TUNING) is golden_settings


def test_closing_threshold_decides_full_rows(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    ctx = make_ctx(golden_repo, golden_settings)
    row = next(r for r in ctx.rows.values() if r.rubric.level == "LOW").model_copy(
        update={
            "closing_last5_m_per_min": 60,
            "registry_level": "LOW",
            "pending_level": None,
            "notes_count": 0,
            "status": "staying",
            "max_level": "LOW",
        }
    )
    assert not needs_judgment(row)
    judgment = DEFAULT_TUNING.judgment.model_copy(update={"closing_min_m_per_min": 50})
    assert needs_judgment(row, DEFAULT_TUNING.model_copy(update={"judgment": judgment}))


def test_runner_keeps_its_start_snapshot(
    golden_repo: Repository, golden_settings: Settings
) -> None:
    groups = DEFAULT_TUNING.groups.model_copy(update={"large_group": 3})
    tuned = DEFAULT_TUNING.model_copy(update={"groups": groups})
    runner = WatchRunner(golden_repo, golden_settings, None, lambda e: None, None, tuned)
    assert runner.tuning is tuned
