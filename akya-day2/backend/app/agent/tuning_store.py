"""Admin tuning: override file I/O and how a snapshot is applied to a run (spec §3.2).

The file holds only the admin's differences from DEFAULT_TUNING. Loading never raises: a missing
file means defaults; an unreadable or stale one means defaults plus a warning for the UI.
"""

import json
import logging
import os
from pathlib import Path

from pydantic import ValidationError

from app.agent.watch.prompts import (
    LANGUAGE_NAMES,
    PROMPT_FILES,
    file_text,
    prompt_problems,
    render,
    required_vars,
    threshold_vars,
    var_diff,
)
from app.core.config import Settings
from app.core.errors import TuningStoreError, TuningValidationError
from app.domain.tuning import (
    AgentTuning,
    EnvKnobs,
    PromptPreview,
    PromptPreviewRequest,
    PromptTexts,
    PromptVariables,
    TuningView,
)
from app.services.tuning import (
    DEFAULT_TUNING,
    apply_overrides,
    overridden_paths,
    overrides_of,
    tuning_hash,
    tuning_problems,
)

logger = logging.getLogger(__name__)


def with_agent_knobs(settings: Settings, tuning: AgentTuning) -> Settings:
    """`settings` with every non-None agent knob of `tuning` applied (names match Settings)."""
    update = {k: v for k, v in tuning.agents.model_dump().items() if v is not None}
    return settings.model_copy(update=update) if update else settings


class TuningStore:
    """The admin override file (JSON, UTF-8)."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> tuple[AgentTuning, str | None]:
        """Current tuning and a warning when the file could not be used."""
        if not self.path.exists():
            return DEFAULT_TUNING, None
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                raise ValueError("override file is not a JSON object")
            tuning = apply_overrides(raw)
        except (OSError, ValueError, ValidationError) as exc:
            logger.warning(
                "admin overrides ignored", extra={"path": str(self.path), "error": str(exc)}
            )
            return DEFAULT_TUNING, f"{self.path.name} ignored: {type(exc).__name__}"
        # Values saved under older rules can load but still break a run (e.g. level_step 0).
        if problems := tuning_problems(tuning):
            logger.warning(
                "admin overrides ignored", extra={"path": str(self.path), "problems": problems}
            )
            return DEFAULT_TUNING, f"{self.path.name} ignored: invalid values ({problems[0]})"
        return tuning, None

    def save(self, tuning: AgentTuning) -> None:
        """Validate and persist the diff from the defaults; the defaults remove the file."""
        problems = tuning_problems(tuning)
        for name in PROMPT_FILES:
            text = getattr(tuning.prompts, name)
            if text is not None:
                problems += prompt_problems(name, text)
        if problems:
            raise TuningValidationError("; ".join(problems))
        diff = overrides_of(tuning)
        if not diff:
            self.reset()
            return
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            raise TuningStoreError(f"could not write {self.path.name}: {exc}") from exc

    def reset(self) -> None:
        """Back to the defaults (delete the file if present)."""
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            raise TuningStoreError(f"could not delete {self.path.name}: {exc}") from exc


def tuning_view(store: TuningStore, settings: Settings) -> TuningView:
    """Everything the admin page needs in one response."""
    current, warning = store.load()
    return TuningView(
        defaults=DEFAULT_TUNING,
        current=current,
        overridden=overridden_paths(current),
        env_knobs=EnvKnobs.model_validate(settings.model_dump(include=set(EnvKnobs.model_fields))),
        prompt_defaults=PromptTexts(
            watcher=file_text(PROMPT_FILES["watcher"]),
            supervisor=file_text(PROMPT_FILES["supervisor"]),
        ),
        prompt_variables=PromptVariables(
            watcher=required_vars(PROMPT_FILES["watcher"]),
            supervisor=required_vars(PROMPT_FILES["supervisor"]),
        ),
        hash=tuning_hash(current),
        load_warning=warning,
    )


# Scene values in previews are placeholders: the preview is about wording and thresholds.
_SAMPLE_SCENE: dict[str, object] = {
    "base_name": "<base>",
    "base_lat": "<lat>",
    "base_lon": "<lon>",
    "watcher_id": "W1",
    "sector_names": "<sector A>, <sector B>",
    "n_watchers": 4,
    "watcher_layout": "watcher W1: <sector A>, <sector B>; ...",
    "tracker_rules": "3. <tracker rules>",
}


def preview_prompt(req: PromptPreviewRequest, settings: Settings) -> PromptPreview:
    """`req.text` rendered with sample scene values and `req.tuning`, or its variable problems."""
    missing, unknown = var_diff(req.name, req.text)
    if missing or unknown:
        return PromptPreview(rendered=None, missing=missing, unknown=unknown)
    s = with_agent_knobs(settings, req.tuning)
    max_calls = s.watcher_max_tool_calls if req.name == "watcher" else s.supervisor_max_tool_calls
    values = {
        **_SAMPLE_SCENE,
        "max_tool_calls": max_calls,
        "output_language": LANGUAGE_NAMES[s.brief_language],
        **threshold_vars(req.tuning),
    }
    rendered = render(PROMPT_FILES[req.name], req.text, **values)
    return PromptPreview(rendered=rendered, missing=[], unknown=[])
