"""Field map: every track and report of the day, plus motion of one track at a chosen time."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_repository
from app.core.config import Settings, get_settings
from app.core.errors import NotFoundError
from app.core.timefmt import to_minutes
from app.data.repository import Repository
from app.domain.report import MapReport
from app.domain.track import MapTrack, MotionProfile
from app.services.motion import motion_profile
from app.services.reports import locate_report
from app.services.tracks import map_tracks

router = APIRouter(tags=["field"])


@router.get("/tracks", response_model=list[MapTrack])
def list_tracks(repo: Annotated[Repository, Depends(get_repository)]) -> list[MapTrack]:
    """All tracks of the day with the frame each one belongs to."""
    return map_tracks(list(repo.tracks.values()), repo.list_images())


@router.get("/reports", response_model=list[MapReport])
def list_reports(
    repo: Annotated[Repository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[MapReport]:
    """All field reports sorted by time, with parsed coordinates and zone."""
    reports = sorted(repo.reports, key=lambda r: (r.time_min, r.report_id))
    return [locate_report(r, repo.scene.zones, settings.zone_radius_m) for r in reports]


@router.get("/tracks/{track_id}/motion", response_model=MotionProfile)
def get_track_motion(
    track_id: str,
    repo: Annotated[Repository, Depends(get_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
    at: Annotated[str, Query(pattern=r"^\d{1,2}:\d{2}$", description='"HH:MM"')],
) -> MotionProfile:
    """Motion of one track up to `at`, clamped to the track's time span."""
    track = repo.tracks.get(track_id)
    if track is None or not track.points:
        raise NotFoundError(f"track {track_id} not found")
    minute = min(max(to_minutes(at), track.points[0].time_min), track.points[-1].time_min)
    return motion_profile(
        track,
        minute,
        repo.scene.base.position,
        repo.scene.zones,
        settings.stop_speed_ms,
        settings.zone_radius_m,
    )
