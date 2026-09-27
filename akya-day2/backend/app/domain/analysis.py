"""The full result of analyzing one frame."""

from typing import Literal

from pydantic import Field

from app.domain.base import DomainModel
from app.domain.brief import Brief
from app.domain.detection import Detection, TrackMatch
from app.domain.events import StepResult
from app.domain.image import ImageMeta
from app.domain.report import ReportAssessment, ReportClaim
from app.domain.risk import VehicleRisk
from app.domain.scene import Scene
from app.domain.track import MotionProfile, TrackSnapshot

AnalysisStatus = Literal["running", "done", "error"]


class TokenUsage(DomainModel):
    """LLM token counters for one analysis."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    calls: int = 0
    cache_hits: int = 0


class Analysis(DomainModel):
    """Everything the pipeline produced for one frame. Self-contained so it can be replayed."""

    id: str
    image_id: str
    status: AnalysisStatus
    image: ImageMeta | None = None
    scene: Scene | None = None
    steps: list[StepResult] = Field(default_factory=list)
    detections: list[Detection] = Field(default_factory=list)
    track_snapshots: list[TrackSnapshot] = Field(default_factory=list)
    matches: list[TrackMatch] = Field(default_factory=list)
    motions: list[MotionProfile] = Field(default_factory=list)
    reports: list[ReportClaim] = Field(default_factory=list)  # relevant reports only
    report_assessments: list[ReportAssessment] = Field(default_factory=list)
    risks: list[VehicleRisk] = Field(default_factory=list)
    brief: Brief | None = None
    timings_ms: dict[str, int] = Field(default_factory=dict)
    token_usage: TokenUsage = Field(default_factory=TokenUsage)


class AnalysisCreate(DomainModel):
    """Request body for `POST /api/analyses`."""

    image_id: str
    force_refresh: bool = False


class AnalysisCreated(DomainModel):
    """Response of `POST /api/analyses`."""

    analysis_id: str
