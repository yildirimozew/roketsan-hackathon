"""Risk levels and per-vehicle risk scoring output."""

from typing import Literal

from app.domain.base import DomainModel

RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
RISK_LEVELS: tuple[RiskLevel, ...] = ("LOW", "MEDIUM", "HIGH", "CRITICAL")


class RiskFactor(DomainModel):
    """One rubric line contributing points to a vehicle score."""

    name: str
    points: int
    detail: str


class VehicleRisk(DomainModel):
    """Rubric score (0-100) for one detected vehicle."""

    detection_id: str
    track_id: str | None
    score: int
    level: RiskLevel
    factors: list[RiskFactor]
