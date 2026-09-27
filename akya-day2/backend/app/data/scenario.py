"""Loads a demo scenario file (`backend/scenarios/*.json`) and turns its tracks into `Track`s."""

import json
from pathlib import Path

from app.core.timefmt import to_minutes
from app.domain.geo import LatLon
from app.domain.scenario import Scenario
from app.domain.track import Track, TrackPoint


def load_scenario(path: Path) -> Scenario:
    """Parse and validate a scenario file."""
    return Scenario.model_validate(json.loads(path.read_text(encoding="utf-8")))


def scenario_tracks(scenario: Scenario) -> list[Track]:
    """The scenario's extra vehicles as tracks (sorted samples, minutes since midnight)."""
    return [
        Track(
            track_id=t.track_id,
            points=sorted(
                (
                    TrackPoint(
                        time=p.time,
                        time_min=to_minutes(p.time),
                        position=LatLon(lat=p.lat, lon=p.lon),
                    )
                    for p in t.points
                ),
                key=lambda p: p.time_min,
            ),
        )
        for t in scenario.extra_tracks
    ]
