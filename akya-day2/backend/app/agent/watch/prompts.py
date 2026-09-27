"""Load versioned prompt files from app/agent/prompts/, fill {{variables}}, and check admin
overrides (spec §3.4)."""

import logging
import re
from collections.abc import Mapping
from functools import cache
from pathlib import Path

from app.domain.tuning import AgentTuning, PromptName

logger = logging.getLogger(__name__)
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
PROMPT_FILES: dict[PromptName, str] = {"watcher": "watcher_v12", "supervisor": "supervisor_v12"}
LANGUAGE_NAMES = {"tr": "Turkish", "en": "English"}
_VAR = re.compile(r"\{\{(\w+)\}\}")
_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


@cache
def file_text(name: str) -> str:
    """Raw text of prompt file `name` (e.g. "watcher_v12")."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def _vars(text: str) -> set[str]:
    return set(_VAR.findall(text))


def required_vars(name: str) -> list[str]:
    """The {{variables}} used in prompt file `name`, sorted."""
    return sorted(_vars(file_text(name)))


def _fill(name: str, text: str, values: Mapping[str, object]) -> str:
    missing = sorted(_vars(text) - values.keys())
    if missing:
        raise KeyError(f"prompt {name} needs {missing}")
    return _VAR.sub(lambda m: str(values[m.group(1)]), text)


def render(name: str, override: str | None = None, **values: object) -> str:
    """Prompt `name` (or the `override` text) with {{vars}} filled; missing var -> KeyError."""
    return _fill(name, file_text(name) if override is None else override, values)


def render_with_fallback(
    name: str, override: str | None, values: dict[str, object]
) -> tuple[str, list[str]]:
    """Render the admin override if usable, else the file; returns (text, warnings)."""
    if override is not None:
        try:
            return _fill(name, override, values), []
        except KeyError as exc:
            logger.warning("admin prompt unusable", extra={"prompt": name, "error": str(exc)})
            warning = f"admin prompt for {name} unusable ({exc}); file prompt used"
            return _fill(name, file_text(name), values), [warning]
    return _fill(name, file_text(name), values), []


def _num(x: float) -> str:
    return f"{x:g}"


def threshold_vars(tuning: AgentTuning) -> dict[str, str]:
    """Threshold numbers written into the prompts, formatted like the prompt text (2.5 km, 15)."""
    c, g, b = tuning.ceiling, tuning.groups, tuning.behavior
    return {
        "probe_range_km": _num(b.probe_range_m / 1000),
        "probe_out_km": _num(b.probe_out_m / 1000),
        "stakeout_near_km": _num(b.stakeout_near_m / 1000),
        "stakeout_min": _num(b.stakeout_min),
        "approach_high_km": _num(c.approach_high_m / 1000),
        "approach_high_eta_min": _num(c.approach_high_eta_min),
        "at_base_km": _num(c.at_base_m / 1000),
        "group_radius_m": _num(g.group_radius_m),
        "large_group_word": _WORDS.get(g.large_group, str(g.large_group)),
    }


def var_diff(prompt: PromptName, text: str) -> tuple[list[str], list[str]]:
    """(missing, unknown) variables of `text` against the prompt's file."""
    need, have = set(required_vars(PROMPT_FILES[prompt])), _vars(text)
    return sorted(need - have), sorted(have - need)


def prompt_problems(prompt: PromptName, text: str) -> list[str]:
    """Validation problems of an admin override, in the tuning_problems format."""
    missing, unknown = var_diff(prompt, text)
    problems = []
    if missing:
        problems.append(f"prompts.{prompt}: missing_vars {','.join(missing)}")
    if unknown:
        problems.append(f"prompts.{prompt}: unknown_vars {','.join(unknown)}")
    return problems
