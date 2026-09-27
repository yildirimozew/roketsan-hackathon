"""Vehicle detections and their track matches."""

from typing import Literal

from app.domain.base import DomainModel
from app.domain.geo import LatLon

MatchConfidence = Literal["high", "medium", "low", "none"]


class Detection(DomainModel):
    """One detected vehicle. Geo fields are filled by the georeference step."""

    id: str  # "DET-1"
    label: str
    confidence: float
    bbox: tuple[int, int, int, int]  # x, y, w, h in pixels (top-left origin)
    center_px: tuple[float, float]
    position: LatLon | None = None
    distance_to_base_m: float | None = None
    bearing_from_base_deg: float | None = None


class TrackMatch(DomainModel):
    """Assignment of a detection to a track at capture time."""

    detection_id: str
    track_id: str | None
    distance_m: float | None
    second_best_m: float | None
    second_best_track_id: str | None = None
    confidence: MatchConfidence
