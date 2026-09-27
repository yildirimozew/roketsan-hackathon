"""Watch-run evaluation: scoring against a given ground truth (scripts/watch_eval.py)."""

from typing import Any

from scripts.watch_eval import Truth, evaluate, headline


def _tick(t: str) -> dict[str, Any]:
    return {"type": "tick_started", "tick": t}


def _high(t: str, tid: str) -> dict[str, Any]:
    return {"type": "level_changed", "tick": t, "track_id": tid, "to_level": "HIGH"}


def _alert(t: str, ids: list[str], headline: str) -> dict[str, Any]:
    return {"type": "operator_alert", "tick": t, "alert": {"track_ids": ids, "headline": headline}}


def test_scores_recall_delay_and_unbacked_decisions() -> None:
    truth = {
        "T1": Truth("pattern", 600, "orbit", {600, 605, 610}),
        "T2": Truth("pattern", 605, "loop", {605, 610}),
        "T3": Truth("approach", 610, "fast approach", {610}),
    }
    events = [
        _tick("10:00"),
        _high("10:00", "T1"),
        _tick("10:05"),
        _alert("10:05", ["T1"], "orbit"),
        _high("10:05", "T9"),  # no code rule backs it
        _tick("10:10"),
        _high("10:10", "T2"),
        _alert("10:10", ["T9"], "six cars met"),  # not backed either
    ]
    r = evaluate(events, truth)
    assert r.high_at == {"T1": 600, "T9": 605, "T2": 610}
    assert r.alert_at == {"T1": 605, "T9": 610}
    assert r.unbacked_high == [("T9", "10:05", "within 1 km of the base only")]
    assert r.unbacked_alerts == [("10:10", "six cars met")]
    lines = headline(r)
    assert lines[0].startswith(
        "Looping/orbiting vehicles within 5 km: 2/2 rated HIGH, median 2 min"
    )
    assert "1/2 named in an operator alert" in lines[0]
    assert "Fast close approaches: 0/1 rated HIGH; 0/1 named in an operator alert." in lines
    assert "Probing vehicles (approach, pull back, return): none in this run." in lines
