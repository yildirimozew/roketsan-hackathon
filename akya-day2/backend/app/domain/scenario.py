"""A scripted demo scenario for watch mode: operator messages to the supervisor at clock times and
extra tracks (a synthetic vehicle) added for that run only. Loaded by `app/data/scenario.py`."""

from pydantic import Field

from app.domain.base import DomainModel


class ScenarioMessage(DomainModel):
    """What the human operator writes to the supervisor, and when (HH:MM)."""

    time: str
    text: str = Field(min_length=1)


class ScenarioPoint(DomainModel):
    """One sample of a scenario track (5-minute steps, like tracks.csv)."""

    time: str
    lat: float
    lon: float


class ScenarioTrack(DomainModel):
    """A synthetic vehicle added to the run (never written to the organizer data)."""

    track_id: str
    description: str
    points: list[ScenarioPoint] = Field(min_length=2)


class Scenario(DomainModel):
    """`backend/scenarios/<name>.json`."""

    name: str
    description: str
    operator_messages: list[ScenarioMessage] = Field(default_factory=list)
    extra_tracks: list[ScenarioTrack] = Field(default_factory=list)
