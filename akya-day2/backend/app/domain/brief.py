"""The final, evidence-cited risk brief."""

from typing import Literal

from app.domain.base import DomainModel
from app.domain.risk import RiskLevel

RecommendedAction = Literal["MONITOR", "VERIFY", "ESCALATE"]
BriefSource = Literal["llm", "fallback"]


class VehicleBriefLine(DomainModel):
    """One sentence about one vehicle, with its evidence IDs."""

    detection_id: str
    track_id: str | None
    level: RiskLevel
    text: str
    evidence_ids: list[str]


class Brief(DomainModel):
    """Operator-facing risk brief for one frame."""

    image_id: str
    level: RiskLevel
    headline: str
    summary: str
    vehicles: list[VehicleBriefLine]
    report_notes: list[str]
    uncertainties: list[str]
    recommended_action: RecommendedAction
    evidence_ids: list[str]
    generated_by: BriefSource
