"""Pipeline step names, step results and SSE events (AGENT_DESIGN §5)."""

from typing import Annotated, Any, Literal

from pydantic import Field

from app.domain.base import DomainModel
from app.domain.brief import Brief

StepName = Literal[
    "load_frame",
    "detect",
    "georeference",
    "match_tracks",
    "analyze_motion",
    "assess_reports",
    "score_risk",
    "write_brief",
]
STEP_NAMES: tuple[StepName, ...] = (
    "load_frame",
    "detect",
    "georeference",
    "match_tracks",
    "analyze_motion",
    "assess_reports",
    "score_risk",
    "write_brief",
)
StepStatus = Literal["pending", "running", "done", "warning", "error"]


class StepResult(DomainModel):
    """Final state of one pipeline step, stored in the analysis."""

    step: StepName
    index: int  # 1-based
    status: StepStatus
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int | None = None


class StepStartedEvent(DomainModel):
    type: Literal["step_started"] = "step_started"
    step: StepName
    index: int
    total: int
    ts: str


class StepCompletedEvent(DomainModel):
    type: Literal["step_completed"] = "step_completed"
    step: StepName
    index: int
    summary: str
    data: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int


class StepWarningEvent(DomainModel):
    type: Literal["step_warning"] = "step_warning"
    step: StepName
    message: str


class BriefEvent(DomainModel):
    type: Literal["brief"] = "brief"
    brief: Brief


class DoneEvent(DomainModel):
    type: Literal["done"] = "done"
    analysis_id: str


class ErrorEvent(DomainModel):
    type: Literal["error"] = "error"
    message: str
    recoverable: bool


AnalysisEvent = Annotated[
    StepStartedEvent | StepCompletedEvent | StepWarningEvent | BriefEvent | DoneEvent | ErrorEvent,
    Field(discriminator="type"),
]
