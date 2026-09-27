"""Trackers and the operator alert outbox for one watch run.

Trackers are code, not agents: each tick a following tracker reads the vehicle's next real track
point. When the track ends the tracker is LOST. They are off by default
(`SENTINEL_TRACKERS_ENABLED`); mock track extension is backlog (PLAN.md §10).
"""

from app.core.timefmt import to_hhmm
from app.domain.geo import LatLon
from app.domain.track import Track
from app.domain.watch import OperatorAlert, Suspicion, TrackerState
from app.services.geo import angle_diff_deg, bearing_deg, haversine_m


class BoardError(Exception):
    """A tool request that cannot be carried out (returned to the model as a tool error)."""


def _tracker_fix(track: Track, minute: int, base: LatLon) -> dict[str, object] | None:
    """Position, speed (m/s), heading (deg), distance (m) and ETA (min) at `minute`."""
    idx = next((i for i, p in enumerate(track.points) if p.time_min == minute), None)
    if idx is None:
        return None
    here = track.points[idx].position
    dist = haversine_m(here, base)
    speed, heading, eta = 0.0, None, None
    if idx > 0:
        prev = track.points[idx - 1]
        step = haversine_m(prev.position, here)
        speed = step / max(1, (minute - prev.time_min) * 60)
        if step > 1:
            heading = round(bearing_deg(prev.position, here), 1)
            closing = angle_diff_deg(heading, bearing_deg(here, base)) < 90
            if closing and speed >= 0.5:
                eta = round(dist / speed / 60, 1)
    return {
        "position": LatLon(lat=round(here.lat, 6), lon=round(here.lon, 6)),
        "dist_to_base_m": round(dist),
        "speed_ms": round(speed, 2),
        "heading_deg": heading,
        "eta_to_base_min": eta,
    }


class TrackerBoard:
    """A fixed number of tracker slots."""

    def __init__(self, slots: int) -> None:
        self.slots = slots
        self._trackers: dict[str, TrackerState] = {}

    def all(self) -> list[TrackerState]:
        """Every tracker ever dispatched in this run."""
        return list(self._trackers.values())

    def active(self) -> list[TrackerState]:
        """Trackers currently following a vehicle."""
        return [t for t in self._trackers.values() if t.state == "FOLLOWING"]

    def free_slots(self) -> int:
        """Slots not taken by a following tracker."""
        return self.slots - len(self.active())

    def for_track(self, track_id: str) -> TrackerState | None:
        """The following tracker on a vehicle, if any."""
        return next((t for t in self.active() if t.track_id == track_id), None)

    def dispatch(
        self, track: Track, minute: int, base: LatLon, suspicion: Suspicion
    ) -> TrackerState:
        """Assign a free tracker to a vehicle that is tracked at `minute`."""
        if self.for_track(track.track_id) is not None:
            raise BoardError(f"{track.track_id} already has a tracker")
        if self.free_slots() <= 0:
            raise BoardError(f"no free tracker slot ({self.slots} in use)")
        fix = _tracker_fix(track, minute, base)
        if fix is None:
            raise BoardError(f"{track.track_id} has no position at {to_hhmm(minute)}")
        tracker = TrackerState(
            tracker_id=f"TRK-{len(self._trackers) + 1}",
            track_id=track.track_id,
            state="FOLLOWING",
            source="REAL",
            uncertainty_m=0,
            since=to_hhmm(minute),
            last_tick=to_hhmm(minute),
            suspicion=suspicion,
            **fix,
        )
        self._trackers[tracker.tracker_id] = tracker
        return tracker

    def recall(self, tracker_id: str) -> TrackerState:
        """Stop a following tracker and free its slot."""
        tracker = self._trackers.get(tracker_id)
        if tracker is None or tracker.state != "FOLLOWING":
            raise BoardError(f"no following tracker {tracker_id}")
        tracker = tracker.model_copy(update={"state": "RECALLED"})
        self._trackers[tracker_id] = tracker
        return tracker

    def update(self, minute: int, tracks: dict[str, Track], base: LatLon) -> list[TrackerState]:
        """Advance every following tracker to `minute`; returns the changed trackers."""
        changed: list[TrackerState] = []
        for tracker in self.active():
            if tracker.last_tick == to_hhmm(minute):
                continue
            fix = _tracker_fix(tracks[tracker.track_id], minute, base)
            update: dict[str, object] = {"last_tick": to_hhmm(minute)}
            update.update(fix if fix is not None else {"state": "LOST"})
            new = tracker.model_copy(update=update)
            self._trackers[tracker.tracker_id] = new
            changed.append(new)
        return changed


class AlertBoard:
    """Alerts the supervisor sends to the human operator."""

    def __init__(self) -> None:
        self._alerts: list[OperatorAlert] = []

    def all(self) -> list[OperatorAlert]:
        """Every alert in this run, oldest first."""
        return list(self._alerts)

    def notify(
        self,
        tick: str,
        track_ids: list[str],
        urgency: str,
        headline: str,
        description: str,
        evidence_ids: list[str],
    ) -> OperatorAlert:
        """Record and return an alert to the operator."""
        if urgency not in ("advisory", "urgent", "immediate"):
            raise BoardError(f"unknown urgency {urgency!r}")
        alert = OperatorAlert.model_validate(
            {
                "alert_id": f"ALR-{len(self._alerts) + 1}",
                "tick": tick,
                "urgency": urgency,
                "track_ids": track_ids,
                "headline": headline,
                "description": description,
                "evidence_ids": evidence_ids,
            }
        )
        self._alerts.append(alert)
        return alert
