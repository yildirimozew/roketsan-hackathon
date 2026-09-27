"""Car registry level rules (docs/AGENT_PROMPTS_AND_TOOLS.md §3.2)."""

from app.agent.watch.registry import CarRegistry


def test_watcher_raise_needs_two_consecutive_ticks() -> None:
    reg = CarRegistry()
    first = reg.propose("T1", "HIGH", "14:05", "watcher:B", "closing fast")
    assert first is not None and first.pending
    assert reg.get("T1").level == "LOW" and reg.effective_level("T1") == "HIGH"
    assert reg.propose("T1", "HIGH", "14:05", "watcher:B", "same tick again") is None
    second = reg.propose("T1", "HIGH", "14:10", "watcher:A", "still closing")
    assert second is not None and not second.pending
    assert reg.get("T1").level == "HIGH" and reg.get("T1").pending is None


def test_watcher_cannot_lower_and_a_lower_proposal_drops_the_pending_raise() -> None:
    reg = CarRegistry()
    reg.set_level("T1", "MEDIUM", "supervisor", "setup")
    reg.propose("T1", "HIGH", "14:05", "watcher:B", "closing")
    assert reg.propose("T1", "LOW", "14:10", "watcher:B", "report says friendly") is None
    assert reg.get("T1").level == "MEDIUM" and reg.get("T1").pending is None


def test_supervisor_set_level_is_immediate_and_may_lower() -> None:
    reg = CarRegistry()
    reg.propose("T1", "HIGH", "14:05", "watcher:B", "closing")
    change = reg.set_level("T1", "HIGH", "supervisor", "cross-sector pattern")
    assert change is not None and not change.pending and reg.get("T1").pending is None
    lowered = reg.set_level("T1", "LOW", "supervisor", "turned away")
    assert lowered is not None and reg.get("T1").level == "LOW"


def test_note_ids_are_per_vehicle_and_sequential() -> None:
    reg = CarRegistry()
    a = reg.add_note("T1", "12:50", "watcher:A", "MEDIUM", "parked 45 min", ["TRK-T1"])
    b = reg.add_note("T1", "13:55", "watcher:A", "MEDIUM", "second stop", ["TRK-T1"])
    assert (a.id, b.id) == ("NOTE-T1-1", "NOTE-T1-2")
    assert reg.note_ids() == {"NOTE-T1-1", "NOTE-T1-2"}
