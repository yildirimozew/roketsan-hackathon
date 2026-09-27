import asyncio
from pathlib import Path

import httpx
from app.agent.pipeline import run_analysis
from app.core.config import Settings
from app.data.repository import Repository
from app.domain.analysis import Analysis
from app.services.detection import PrecomputedDetector
from app.services.risk import frame_level

from core_fixes.tests.conftest import REPO_DIR
from core_fixes.z09_guard import FactTable, check_text, extract_numbers, guard_brief
from core_fixes.z10_budget_mode import (
    BudgetMonitor,
    BudgetStatus,
    budget_url,
    fetch_budget,
    parse_budget,
    resolve_mode,
)

GOLDEN = REPO_DIR / "backend" / "tests" / "fixtures" / "golden"


def _golden_analysis(repo: Repository, lang: str) -> Analysis:
    settings = Settings(_env_file=None, data_dir=REPO_DIR / "data", brief_language=lang)  # type: ignore[arg-type]
    detector = PrecomputedDetector(GOLDEN / "detections.json", settings.detect_conf_min)
    return run_analysis("t", "img_000860", repo, detector, settings)


def test_numbers_are_read_with_units_and_turkish_decimals() -> None:
    found = {
        (n.unit, n.value)
        for n in extract_numbers(
            "Kamyon üsse 1,6 km'den geldi; son 60 dakikada 65 m/dk, ETA ≈ 3 dk, 2 araç. "
            "T0122 at 14:10."
        )
    }
    assert found == {
        ("distance_m", 1600.0),
        ("duration_min", 60.0),
        ("rate_m_per_min", 65.0),
        ("duration_min", 3.0),
        ("count", 2.0),
    }


def test_template_brief_always_passes_the_guard(repo: Repository) -> None:
    for lang in ("tr", "en"):
        analysis = _golden_analysis(repo, lang)
        assert analysis.brief is not None
        verdict = guard_brief(analysis.brief, analysis, frame_level(analysis.risks))
        assert verdict.ok, (lang, verdict.feedback)


def test_guard_rejects_invented_numbers_ids_level_jumps_and_hidden_deception(
    repo: Repository,
) -> None:
    analysis = _golden_analysis(repo, "en")
    brief = analysis.brief
    assert brief is not None
    rubric = frame_level(analysis.risks)
    fake_km = brief.model_copy(update={"summary": brief.summary + " It is 9.9 km from base."})
    assert [c.name for c in guard_brief(fake_km, analysis, rubric).checks if not c.passed] == [
        "numbers"
    ]
    fake_id = brief.model_copy(update={"evidence_ids": [*brief.evidence_ids, "REP-999"]})
    assert not guard_brief(fake_id, analysis, rubric).ok
    jump = (
        brief.model_copy(update={"level": "LOW"})
        if rubric in ("HIGH", "CRITICAL")
        else brief.model_copy(update={"level": "CRITICAL"})
    )
    assert not guard_brief(jump, analysis, "CRITICAL" if jump.level == "LOW" else "LOW").ok
    hidden = guard_brief(brief, analysis, rubric, deception_report_ids=["REP-61"])
    assert [c.name for c in hidden.checks if not c.passed] == ["policy"]


def test_check_text_for_watch_messages() -> None:
    facts = FactTable(ids={"TRK-T0122", "T0122"})
    facts.add("distance_m", 1650)
    facts.add("rate_m_per_min", 250)
    ok = check_text("T0122 is 1.6 km out, closing ~250 m/min.", ["TRK-T0122"], facts)
    assert all(c.passed for c in ok)
    bad = check_text("T0999 is 1.2 km out.", [], facts)
    assert [c.passed for c in bad] == [False, False]


def test_budget_parsing_and_url() -> None:
    assert budget_url("https://gw.example/v1/") == "https://gw.example/key/info"
    assert parse_budget({"spend": 0.08, "max_budget": 15}).ok
    low = parse_budget({"info": {"spend": 14.5, "max_budget": 15}})
    assert not low.ok and low.remaining_usd == 0.5
    assert not parse_budget({"foo": 1}).ok


def test_fetch_budget_and_monitor() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer k"
        return httpx.Response(200, json={"info": {"spend": 14.6, "max_budget": 15.0}})

    status = asyncio.run(
        fetch_budget("https://gw/key/info", "k", transport=httpx.MockTransport(handler))
    )
    assert not status.ok and status.remaining_usd == 0.4
    broken = asyncio.run(
        fetch_budget(
            "https://gw/key/info", "k", transport=httpx.MockTransport(lambda r: httpx.Response(500))
        )
    )
    assert not broken.ok and "failed" in broken.detail

    calls = []

    async def fake() -> BudgetStatus:
        calls.append(1)
        return BudgetStatus(ok=len(calls) < 2, detail="")

    monitor = BudgetMonitor(fake, check_every=3)
    results = [asyncio.run(monitor.allow_live()) for _ in range(4)]
    assert results == [True, True, True, False] and len(calls) == 2


def test_resolve_mode() -> None:
    common = {
        "replay": False,
        "llm_enabled": True,
        "budget_ok": True,
        "detector_available": True,
        "fallback_detector": False,
    }
    assert resolve_mode(**common) == "full"
    assert resolve_mode(**{**common, "budget_ok": False}) == "llm_off"
    assert resolve_mode(**{**common, "detector_available": False}) == "tracks_only"
    assert resolve_mode(**{**common, "replay": True}) == "replay"


def test_golden_fixture_exists() -> None:
    assert (GOLDEN / "detections.json").is_file(), Path(GOLDEN)
