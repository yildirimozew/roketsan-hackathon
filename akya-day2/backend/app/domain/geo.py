"""Geographic primitives."""

from typing import Literal

from pydantic import ConfigDict

from app.domain.base import DomainModel

CornerName = Literal["tl", "tr", "br", "bl"]


class LatLon(DomainModel):
    """WGS84 position in decimal degrees."""

    model_config = ConfigDict(frozen=True)  # merged with DomainModel config

    lat: float
    lon: float
