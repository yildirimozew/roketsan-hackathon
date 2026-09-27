"""Public-contract changes needed by Z2, Z5, Z6, Z8 and Z10, staged as extended models.

On integration, fold these fields into the backend models named in each docstring, then run
`make gen-types`. Until then the extended models are drop-in subclasses: a list typed with the
backend model accepts them, so the staged code runs against the unchanged backend.
"""

from typing import Literal

from app.domain.base import DomainModel
from app.domain.report import ReportAssessment, ReportCheck, ReportClaim
from pydantic import Field

# -> app/domain/report.py: CheckName (+ "direction", "identity", "area", "count")
CheckNameV2 = Literal[
    "location",
    "presence",
    "type",
    "activity",
    "instructions",
    "direction",
    "identity",
    "area",
    "count",
]
# -> app/domain/report.py: ClaimKind (+ "ABSENCE", "CONTEXT")
ClaimKindV2 = Literal[
    "SIGHTING",
    "ALL_CLEAR",
    "FRIENDLY_PRESENCE",
    "TRAFFIC_NORMAL",
    "OTHER",
    "ABSENCE",
    "CONTEXT",
]
AbsenceKind = Literal["no_heavy_vehicles", "no_notable_movement", "no_anomaly", "traffic_normal"]


class ReportCheckV2(ReportCheck):
    """-> app/domain/report.py: ReportCheck with the extended `name`."""

    name: CheckNameV2  # type: ignore[assignment]


class ReportClaimV2(ReportClaim):
    """-> app/domain/report.py: ReportClaim + absence / direction / identity fields (Z5, Z6)."""

    claim_kind: ClaimKindV2 = "OTHER"  # type: ignore[assignment]
    absence: list[AbsenceKind] = Field(default_factory=list)
    toward_base: bool = False  # the text claims movement toward the base
    identity_claim: bool = False  # friendly / supply / own unit: can never be sensed
    usual_count: int | None = None  # "olagan trafik 4 arac": a baseline, not a count


class ReportAssessmentV2(ReportAssessment):
    """-> app/domain/report.py: ReportAssessment + deception fields (Z6), frame checked (Z4)."""

    deception_indicator: bool = False
    deception_track_ids: list[str] = Field(default_factory=list)
    checked_frame_id: str | None = None


RunMode = Literal["full", "llm_off", "detector_degraded", "tracks_only", "replay"]


class EvidenceStatus(DomainModel):
    """-> app/domain/analysis.py: Analysis.evidence (Z8) and Analysis.mode (Z10)."""

    insufficient_evidence: bool
    reasons: list[str] = Field(default_factory=list)
    mode: RunMode = "full"
