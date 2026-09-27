"""The protected base and the monitored zones."""

from app.domain.base import DomainModel
from app.domain.geo import LatLon


class Zone(DomainModel):
    """A monitored zone, identified by name (as used in reports)."""

    name: str
    center: LatLon


class Base(DomainModel):
    """The protected base."""

    name: str
    position: LatLon


class Scene(DomainModel):
    """Static geography of the day: base plus zones."""

    base: Base
    zones: list[Zone]
