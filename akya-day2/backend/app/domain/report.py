"""Field reports: raw entries, extracted claims and per-frame assessments."""

from typing import Literal

from app.domain.base import DomainModel
from app.domain.geo import LatLon

Activity = Literal["moving", "stationary", "loading", "unknown"]
ClaimKind = Literal["SIGHTING", "ALL_CLEAR", "FRIENDLY_PRESENCE", "TRAFFIC_NORMAL", "OTHER"]
Verdict = Literal["CORROBORATED", "CONTRADICTED", "UNVERIFIED", "IRRELEVANT"]
CheckName = Literal["location", "presence", "type", "activity", "instructions"]
CheckStatus = Literal["match", "mismatch", "unknown"]
ClaimSource = Literal["llm", "rules"]


class FieldReport(DomainModel):
    """One raw report from field_reports.json. `text` is untrusted."""

    report_id: str  # "REP-07", assigned by file order
    time: str  # "HH:MM"
    time_min: int
    source: str
    text: str


class ReportClaim(DomainModel):
    """Structured claim extracted from one free-text report. The text is untrusted."""

    report_id: str
    time: str
    time_min: int
    source: str
    text: str
    location: LatLon | None = None
    zone: str | None = None
    vehicle_type: str | None = None
    count: int | None = None
    color: str | None = None
    activity: Activity = "unknown"
    claim_kind: ClaimKind = "OTHER"
    extracted_by: ClaimSource = "rules"


class ReportCheck(DomainModel):
    """One code-side comparison of a claim against our own data."""

    name: CheckName
    status: CheckStatus
    detail: str  # short English/data detail for the raw view; UI builds its own label


class ReportAssessment(DomainModel):
    """Verdict on one report relative to one frame's own sensor data."""

    report_id: str
    verdict: Verdict
    reason: str
    checks: list[ReportCheck]
    linked_detection_ids: list[str]
    trust_weight: float


class MapReport(FieldReport):
    """A raw report placed on the field map: parsed coordinates and its zone.

    `zone` is the zone the text names; otherwise the zone nearest its coordinates
    (`zone_named` tells which).
    """

    location: LatLon | None = None
    zone: str | None = None
    zone_named: bool = False
