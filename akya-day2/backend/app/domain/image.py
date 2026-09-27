"""Frame metadata."""

from app.domain.base import DomainModel
from app.domain.geo import CornerName, LatLon


class ImageMeta(DomainModel):
    """One drone frame: size in pixels, capture time and ground corners."""

    image_id: str
    width_px: int
    height_px: int
    capture_time: str  # "HH:MM", display only
    capture_min: int  # minutes since midnight
    corners: dict[CornerName, LatLon]
    zone: str | None = None
