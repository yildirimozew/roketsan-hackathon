"""Current prompts (v12): thresholds are variables filled from the tuning; admin overrides."""

from app.agent.watch.prompts import (
    PROMPT_FILES,
    file_text,
    prompt_problems,
    render,
    render_with_fallback,
    required_vars,
    threshold_vars,
)
from app.services.tuning import DEFAULT_TUNING

WATCHER_BASE = dict(
    watcher_id="W1",
    sector_names="A, B",
    base_name="Base",
    base_lat=39.9,
    base_lon=32.8,
    max_tool_calls=3,
    output_language="Turkish",
)
SUPERVISOR_BASE = dict(
    base_name="Base",
    base_lat=39.9,
    base_lon=32.8,
    n_watchers=4,
    watcher_layout="W1: A",
    tracker_rules="3. none",
    max_tool_calls=6,
    output_language="Turkish",
)
WATCHER, SUPERVISOR = PROMPT_FILES["watcher"], PROMPT_FILES["supervisor"]


def test_defaults_read_like_the_rules() -> None:
    tv = threshold_vars(DEFAULT_TUNING)
    watcher = render(WATCHER, **WATCHER_BASE, **tv)
    assert "came within 2.5 km, pulled back at least 3 km" in watcher
    assert "within 1 km of the base for 15 minutes or more" in watcher
    assert "only a final approach within 1.5 km or 5 minutes may be HIGH" in watcher
    assert "four or more together may be MEDIUM" in watcher
    supervisor = render(SUPERVISOR, **SUPERVISOR_BASE, **tv)
    assert "(four or more)" in supervisor and "{{" not in supervisor


def test_thresholds_show_up_in_the_prompt() -> None:
    behavior = DEFAULT_TUNING.behavior.model_copy(update={"probe_range_m": 3000.0})
    groups = DEFAULT_TUNING.groups.model_copy(update={"large_group": 3})
    tuned = DEFAULT_TUNING.model_copy(update={"behavior": behavior, "groups": groups})
    text = render(WATCHER, **WATCHER_BASE, **threshold_vars(tuned))
    assert "came within 3 km, pulled back" in text
    assert "three or more together may be MEDIUM" in text


def test_required_vars_come_from_the_file() -> None:
    assert "approach_high_km" in required_vars(WATCHER)
    assert "probe_range_km" in required_vars(WATCHER)
    assert "watcher_id" in required_vars(WATCHER)
    assert "tracker_rules" in required_vars(SUPERVISOR)


def test_prompt_problems_names_missing_and_unknown_vars() -> None:
    text = file_text(WATCHER).replace("{{at_base_km}}", "{{at_base_miles}}")
    assert prompt_problems("watcher", text) == [
        "prompts.watcher: missing_vars at_base_km",
        "prompts.watcher: unknown_vars at_base_miles",
    ]
    assert prompt_problems("watcher", file_text(WATCHER)) == []


def test_broken_override_falls_back_to_the_file() -> None:
    values = {**WATCHER_BASE, **threshold_vars(DEFAULT_TUNING)}
    text, warnings = render_with_fallback(WATCHER, "Hello {{nope}}", values)
    assert text == render(WATCHER, **values)
    assert warnings and "file prompt used" in warnings[0]
    text, warnings = render_with_fallback(WATCHER, "Hi {{watcher_id}}", values)
    assert (text, warnings) == ("Hi W1", [])
