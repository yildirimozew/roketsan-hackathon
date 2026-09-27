"""Admin endpoints: agent tuning and prompt preview (spec §3.5).

Unprotected by design for the local demo: auth is a frontend-only mock (frontend/CLAUDE.md).
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.agent.tuning_store import TuningStore, preview_prompt, tuning_view
from app.api.deps import get_tuning_store
from app.core.config import Settings, get_settings
from app.domain.tuning import AgentTuning, PromptPreview, PromptPreviewRequest, TuningView

router = APIRouter(tags=["admin"])
Store = Annotated[TuningStore, Depends(get_tuning_store)]
Config = Annotated[Settings, Depends(get_settings)]


@router.get("/admin/tuning", response_model=TuningView)
def get_tuning_view(store: Store, settings: Config) -> TuningView:
    """Defaults, current values, overridden paths and prompt texts."""
    return tuning_view(store, settings)


@router.put("/admin/tuning", response_model=TuningView)
def put_tuning(body: AgentTuning, store: Store, settings: Config) -> TuningView:
    """Validate and save; applies to the next analysis and the next watch run."""
    store.save(body)
    return tuning_view(store, settings)


@router.delete("/admin/tuning", response_model=TuningView)
def reset_tuning(store: Store, settings: Config) -> TuningView:
    """Back to the defaults."""
    store.reset()
    return tuning_view(store, settings)


@router.post("/admin/prompts/preview", response_model=PromptPreview)
def post_prompt_preview(body: PromptPreviewRequest, settings: Config) -> PromptPreview:
    """Render a prompt text with sample scene values and the given tuning."""
    return preview_prompt(body, settings)
