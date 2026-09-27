"""TuningStore: diff-only persistence, reset, safe loading, validation (spec §3.2, §5)."""

import json
from pathlib import Path

import pytest

from app.agent.tuning_store import TuningStore, preview_prompt, tuning_view
from app.agent.watch.prompts import PROMPT_FILES, file_text
from app.core.config import Settings
from app.core.errors import TuningValidationError
from app.domain.tuning import PromptPreviewRequest
from app.services.tuning import DEFAULT_TUNING


@pytest.fixture
def store(tmp_path: Path) -> TuningStore:
    return TuningStore(tmp_path / "admin_overrides.json")


def _at_base(m: float):  # type: ignore[no-untyped-def]
    return DEFAULT_TUNING.model_copy(
        update={"ceiling": DEFAULT_TUNING.ceiling.model_copy(update={"at_base_m": m})}
    )


def test_missing_file_gives_defaults(store: TuningStore) -> None:
    assert store.load() == (DEFAULT_TUNING, None)


def test_save_writes_only_the_diff(store: TuningStore) -> None:
    store.save(_at_base(1500.0))
    assert json.loads(store.path.read_text(encoding="utf-8")) == {"ceiling": {"at_base_m": 1500.0}}
    assert store.load() == (_at_base(1500.0), None)


def test_saving_defaults_removes_the_file(store: TuningStore) -> None:
    store.save(_at_base(1500.0))
    store.save(DEFAULT_TUNING)
    assert not store.path.exists()


def test_reset(store: TuningStore) -> None:
    store.save(_at_base(1500.0))
    store.reset()
    assert store.load() == (DEFAULT_TUNING, None)
    store.reset()  # idempotent


def test_corrupt_file_falls_back_with_warning(store: TuningStore) -> None:
    store.path.write_text("{not json", encoding="utf-8")
    tuning, warning = store.load()
    assert tuning == DEFAULT_TUNING and warning is not None


def test_stale_key_falls_back_with_warning(store: TuningStore) -> None:
    store.path.write_text(json.dumps({"ceiling": {"renamed_field": 1}}), encoding="utf-8")
    tuning, warning = store.load()
    assert tuning == DEFAULT_TUNING and warning is not None


def test_invalid_values_are_rejected_and_not_written(store: TuningStore) -> None:
    with pytest.raises(TuningValidationError) as err:
        store.save(_at_base(-5.0))
    assert "ceiling.at_base_m: positive" in err.value.detail
    assert not store.path.exists()


def test_prompt_override_needs_every_variable(store: TuningStore) -> None:
    text = file_text(PROMPT_FILES["watcher"]).replace("{{at_base_km}}", "1")
    bad = DEFAULT_TUNING.model_copy(
        update={"prompts": DEFAULT_TUNING.prompts.model_copy(update={"watcher": text})}
    )
    with pytest.raises(TuningValidationError) as err:
        store.save(bad)
    assert err.value.detail == "prompts.watcher: missing_vars at_base_km"


def test_prompt_override_round_trips_unicode(store: TuningStore) -> None:
    text = file_text(PROMPT_FILES["watcher"]) + "\nNot: şüpheli İzmir ğ"
    t = DEFAULT_TUNING.model_copy(
        update={"prompts": DEFAULT_TUNING.prompts.model_copy(update={"watcher": text})}
    )
    store.save(t)
    assert store.load()[0].prompts.watcher == text


def test_view_reports_overrides_and_env_knobs(store: TuningStore, settings: Settings) -> None:
    store.save(_at_base(1500.0))
    view = tuning_view(store, settings)
    assert view.overridden == ["ceiling.at_base_m"]
    assert view.defaults == DEFAULT_TUNING
    assert view.env_knobs.watcher_max_tool_calls == settings.watcher_max_tool_calls
    assert "at_base_km" in view.prompt_variables.watcher
    assert view.prompt_defaults.watcher == file_text(PROMPT_FILES["watcher"])
    assert view.load_warning is None and len(view.hash) == 8


def test_preview_renders_or_lists_problems(settings: Settings) -> None:
    ok = preview_prompt(
        PromptPreviewRequest(
            name="watcher", text=file_text(PROMPT_FILES["watcher"]), tuning=_at_base(2000.0)
        ),
        settings,
    )
    assert ok.rendered is not None and "within 2 km of the base" in ok.rendered
    bad = preview_prompt(
        PromptPreviewRequest(name="watcher", text="Hi {{nope}}", tuning=DEFAULT_TUNING), settings
    )
    assert bad.rendered is None and "nope" in bad.unknown and "watcher_id" in bad.missing


def test_out_of_range_file_falls_back_with_warning(store: TuningStore) -> None:
    store.path.write_text(json.dumps({"rubric": {"level_step": 0}}), encoding="utf-8")
    tuning, warning = store.load()
    assert tuning == DEFAULT_TUNING and warning is not None
