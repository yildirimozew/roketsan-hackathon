"""Track points and derived motion features."""

from app.domain.base import DomainModel
from app.domain.geo import LatLon


class TrackPoint(DomainModel):
    """One track sample."""

    time: str  # "HH:MM", display only
    time_min: int  # minutes since midnight
    position: LatLon


class Track(DomainModel):
    """All samples of one vehicle, sorted by time (last 2 h, 5 min steps)."""

    track_id: str
    points: list[TrackPoint]


class TrackSnapshot(DomainModel):
    """A track's interpolated position at capture time, if it falls inside the frame."""

    track_id: str
    position: LatLon
    center_px: tuple[float, float]
    matched_detection_id: str | None


class Stop(DomainModel):
    """A run of samples with speed below the stop threshold.

    `duration_min` counts 5-minute sample slots (k samples -> 5k min), matching the organizer's
    example (12:10..12:45 at one spot = "40 dk").
    """

    start: str  # "HH:MM"
    duration_min: int
    position: LatLon
    zone: str | None = None
    distance_to_base_m: float


class MotionProfile(DomainModel):
    """Motion features of one track over the window before capture (AGENT_DESIGN §3 step 5)."""

    track_id: str
    points: list[TrackPoint]
    path_km: float
    mean_speed_ms: float
    last10_speed_ms: float
    heading_deg: float | None  # clockwise from north; None if it never moved
    bearing_to_base_deg: float
    dist_now_m: float
    dist_30m_ago_m: float | None
    dist_60m_ago_m: float | None
    min_dist_m: float
    approach_rate_m_per_min: float  # positive = closing on base
    stops: list[Stop]
    zones_visited: list[str]
    eta_to_base_min: float | None


class MapTrack(Track):
    """A track for the field map, with the frame it belongs to (last point = capture time)."""

    image_id: str | None
