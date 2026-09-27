"""Watch mode: per-tick vehicle facts, car registry, agent outputs and events.

See docs/AGENT_FLOW.md (roles) and docs/AGENT_PROMPTS_AND_TOOLS.md (prompts, tools, examples).
"""

from typing import Annotated, Any, Literal

from pydantic import Field

from app.domain.base import DomainModel
from app.domain.geo import LatLon
from app.domain.report import FieldReport, ReportClaim
from app.domain.risk import RiskFactor, RiskLevel
from app.domain.track import MapTrack

WatchLevel = Literal["LOW", "MEDIUM", "HIGH"]
WATCH_LEVELS: tuple[WatchLevel, ...] = ("LOW", "MEDIUM", "HIGH")
BehaviorClass = Literal[
    "steady_approach",
    "loops_around_base",
    "fixed_range_orbit",
    "probing_return",
    "perimeter_stakeout",
    "mixed_transit",
    "leaving_base",
    "parked",
    "unknown",
]
VehicleStatus = Literal["new_in_sector", "staying", "new_track"]
GeneratedBy = Literal["llm", "fallback"]


class Rubric(DomainModel):
    """Track-only rubric at a tick (no vehicle type or report points)."""

    score: int
    level: RiskLevel
    factors: list[RiskFactor]


class VehicleRow(DomainModel):
    """One vehicle in a sector at a tick; every number is computed by code."""

    track_id: str
    vehicle_type: str | None  # from a drone frame detection matched to this track, else None
    status: VehicleStatus
    position: LatLon
    sector: str
    dist_to_base_m: int
    bearing_from_base_deg: int
    moving: bool
    speed_last10_ms: float
    heading_deg: float | None
    heading_vs_base_deg: int | None  # 0 = straight at the base, 180 = straight away
    approach_rate_60m_m_per_min: float  # + = closing
    closing_last5_m_per_min: int  # + = closing, last tick only
    eta_to_base_min: float | None
    current_stop_min: int
    long_stops_within_6km: int
    behavior_class: BehaviorClass
    rubric: Rubric
    # Highest level this vehicle may get, computed by code (services/risk.level_ceiling).
    max_level: WatchLevel = "HIGH"
    # Other vehicles moving together with this one (services/behavior.moving_groups).
    group_ids: list[str] = Field(default_factory=list)
    # Set when the operator announced this vehicle (ExpectedVehicle): code keeps it LOW.
    expected: str | None = None
    registry_level: WatchLevel
    pending_level: WatchLevel | None
    notes_count: int
    one_liner: str


class ReportLookup(DomainModel):
    """A report near a point, with a code-side check against our tracks at the report's time."""

    claim: ReportClaim
    distance_to_query_m: int | None
    nearest_track_id: str | None  # nearest tracked vehicle to the claimed spot at report time
    nearest_track_m: int | None


class Note(DomainModel):
    """A remark about one vehicle, left in the registry by a watcher or the supervisor."""

    id: str  # NOTE-<track_id>-<n>
    tick: str
    author: str  # "watcher:<id>" or "supervisor"
    level: WatchLevel
    text: str
    evidence_ids: list[str]


class PendingLevel(DomainModel):
    """A watcher's level change waiting for its second consecutive tick."""

    level: WatchLevel
    since: str
    by: str


class RegistryEntry(DomainModel):
    """Shared memory about one vehicle."""

    track_id: str
    level: WatchLevel = "LOW"
    pending: PendingLevel | None = None
    notes: list[Note] = Field(default_factory=list)
    vehicle_type: str | None = None  # from the latest frame detection matched to this track
    tracker_id: str | None = None
    alert_ids: list[str] = Field(default_factory=list)


# ---- agent outputs (the `submit_*` tool arguments, validated with these models) ----


class VehicleVerdict(DomainModel):
    """A watcher's level and reason for one vehicle."""

    track_id: str
    level: WatchLevel
    reason: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    note: str | None = None


ReportVerdict = Literal["CONSISTENT", "CONTRADICTED", "UNVERIFIABLE", "IRRELEVANT"]


class ExpectedVehicle(DomainModel):
    """A vehicle the human operator announced to the supervisor (trusted, unlike field reports).
    Code matches it to a track when one appears and keeps that vehicle LOW."""

    expected_id: str  # EXP-<n>
    announced_at: str  # HH:MM of the operator's message
    description: str
    sector: str
    arrive_from: str  # HH:MM
    arrive_to: str  # HH:MM
    vehicle_type: str | None = None
    track_id: str | None = None  # the matched track, once seen


class ReportJudgment(DomainModel):
    """An agent's own judgment of one field report: does it fit our tracks, frames and the other
    reports? The verdict and the 0-100 credibility score are the model's; code only checks ids."""

    report_id: str
    verdict: ReportVerdict
    credibility: int = Field(ge=0, le=100)
    reason: str = Field(min_length=1)
    track_ids: list[str] = Field(default_factory=list)  # vehicles the report is about
    conflicts_with: list[str] = Field(default_factory=list)  # reports it contradicts
    deception: bool = False  # a refuted claim that could be meant to mislead


class GroupPattern(DomainModel):
    """Vehicles in one watcher's area that behave together."""

    track_ids: list[str] = Field(min_length=1)
    description: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class WatcherReport(DomainModel):
    """`submit_watch_report` arguments."""

    tick: str
    street_state: str = Field(min_length=1)
    vehicles: list[VehicleVerdict]
    patterns: list[GroupPattern] = Field(default_factory=list)
    report_checks: list[ReportJudgment] = Field(default_factory=list)


class Suspicion(DomainModel):
    """Why the supervisor dispatches a tracker or alerts the authorities."""

    hypothesis: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    what_would_clear_it: str = Field(min_length=1)
    confidence: Literal["low", "medium", "high"]


class SupervisorPattern(DomainModel):
    """A pattern across vehicles, possibly across sectors."""

    track_ids: list[str] = Field(min_length=1)
    sectors: list[str]
    description: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)


class SupervisorDecision(DomainModel):
    """`submit_supervisor_decision` arguments."""

    tick: str
    situation_summary: str = Field(min_length=1)
    threat_level: WatchLevel
    patterns: list[SupervisorPattern] = Field(default_factory=list)
    watch_next: list[str] = Field(default_factory=list)
    report_checks: list[ReportJudgment] = Field(default_factory=list)  # area-wide reports


class SupervisorAction(DomainModel):
    """One side-effecting tool call the supervisor made this tick."""

    tool: str
    ok: bool
    summary: str
    track_ids: list[str] = Field(default_factory=list)


TrackerStateName = Literal["FOLLOWING", "LOST", "RECALLED"]


class TrackerState(DomainModel):
    """A tracker assigned to one vehicle."""

    tracker_id: str
    track_id: str
    state: TrackerStateName
    source: Literal["REAL", "SIMULATED"]
    position: LatLon
    dist_to_base_m: int
    speed_ms: float
    heading_deg: float | None
    eta_to_base_min: float | None
    uncertainty_m: int
    since: str
    last_tick: str
    suspicion: Suspicion


class OperatorAlert(DomainModel):
    """The supervisor informing the human operator about a situation."""

    alert_id: str
    tick: str
    urgency: Literal["advisory", "urgent", "immediate"]
    track_ids: list[str]
    headline: str
    description: str
    evidence_ids: list[str]


class FrameDetection(DomainModel):
    """One detector box in a drone frame, georeferenced and matched to a track."""

    detection_id: str
    label: str
    confidence: float
    position: LatLon | None
    track_id: str | None
    match_m: float | None


# ---- events (SSE contract proposal, docs/AGENT_PROMPTS_AND_TOOLS.md §8) ----


class TickStartedEvent(DomainModel):
    type: Literal["tick_started"] = "tick_started"
    tick: str
    active_vehicles: int
    frames: list[str]
    checks: dict[str, str]  # watcher id -> sector it checks this tick


class FrameAnalyzedEvent(DomainModel):
    type: Literal["frame_analyzed"] = "frame_analyzed"
    tick: str
    image_id: str
    sector: str
    status: Literal["ok", "detector_unavailable"]
    detections: list[FrameDetection]
    tracks_in_frame: list[str]
    note: str


class WatcherReportEvent(DomainModel):
    type: Literal["watcher_report"] = "watcher_report"
    tick: str
    watcher: str
    sectors: list[str]
    generated_by: GeneratedBy
    duration_ms: int
    rows: list[VehicleRow]
    report: WatcherReport
    tool_calls: list[str]
    warnings: list[str]
    # The field reports judged in `report.report_checks` (untrusted text), so a client can show
    # them without another request.
    reports: list[FieldReport] = Field(default_factory=list)


class ScenarioLoadedEvent(DomainModel):
    """A scripted demo scenario runs: its synthetic vehicles, so a client can draw them."""

    type: Literal["scenario_loaded"] = "scenario_loaded"
    tick: str
    name: str
    description: str
    extra_tracks: list[MapTrack]


class OperatorMessageEvent(DomainModel):
    """The human operator wrote to the supervisor."""

    type: Literal["operator_message"] = "operator_message"
    tick: str
    time: str
    text: str


class OperatorReplyEvent(DomainModel):
    """The supervisor's answer to the operator, with what its tools did."""

    type: Literal["operator_reply"] = "operator_reply"
    tick: str
    time: str  # of the operator message it answers
    generated_by: GeneratedBy
    duration_ms: int
    reply: str
    actions: list[SupervisorAction]
    tool_calls: list[str]
    warnings: list[str]


class ExpectedVehicleEvent(DomainModel):
    """An announced vehicle was registered, or matched to a track."""

    type: Literal["expected_vehicle"] = "expected_vehicle"
    tick: str
    vehicle: ExpectedVehicle


class AgentTraceEvent(DomainModel):
    """Everything one agent turn saw and did: prompts, each LLM call (with the model's reasoning),
    each tool call and result, and the final output."""

    type: Literal["agent_trace"] = "agent_trace"
    tick: str
    agent: str  # "watcher:W1" or "supervisor"
    prompt_file: str  # e.g. "watcher_v3"
    system_prompt: str
    user_message: str
    steps: list[dict[str, Any]]
    output: dict[str, Any] | None
    generated_by: GeneratedBy
    duration_ms: int


class LevelChangedEvent(DomainModel):
    type: Literal["level_changed"] = "level_changed"
    tick: str
    track_id: str
    from_level: WatchLevel
    to_level: WatchLevel
    by: str
    pending: bool
    reason: str


class SupervisorDecisionEvent(DomainModel):
    type: Literal["supervisor_decision"] = "supervisor_decision"
    tick: str
    generated_by: GeneratedBy
    duration_ms: int
    decision: SupervisorDecision
    actions: list[SupervisorAction]
    tool_calls: list[str]
    warnings: list[str]
    reports: list[FieldReport] = Field(default_factory=list)  # judged in decision.report_checks


class TrackerUpdateEvent(DomainModel):
    type: Literal["tracker_update"] = "tracker_update"
    tick: str
    tracker: TrackerState


class OperatorAlertEvent(DomainModel):
    type: Literal["operator_alert"] = "operator_alert"
    tick: str
    alert: OperatorAlert


class WarningEvent(DomainModel):
    type: Literal["warning"] = "warning"
    tick: str
    scope: str
    message: str


class TickCompletedEvent(DomainModel):
    type: Literal["tick_completed"] = "tick_completed"
    tick: str
    duration_ms: int
    levels: dict[str, int]


WatchEvent = Annotated[
    TickStartedEvent
    | FrameAnalyzedEvent
    | AgentTraceEvent
    | ScenarioLoadedEvent
    | OperatorMessageEvent
    | OperatorReplyEvent
    | ExpectedVehicleEvent
    | WatcherReportEvent
    | LevelChangedEvent
    | SupervisorDecisionEvent
    | TrackerUpdateEvent
    | OperatorAlertEvent
    | WarningEvent
    | TickCompletedEvent,
    Field(discriminator="type"),
]


class WatchRunCreate(DomainModel):
    """Request body for `POST /api/watch/runs` (times as HH:MM, both ticks included)."""

    start: str = "13:50"
    end: str = "14:15"
    watchers: int | None = Field(default=None, ge=1, le=8)


class WatchRunCreated(DomainModel):
    """Response of `POST /api/watch/runs`."""

    run_id: str


class WatchRunStatus(DomainModel):
    """State of one watch run."""

    run_id: str
    status: Literal["running", "done", "failed"]
    start: str
    end: str
    watchers: int
    events: int
    alerts: list[OperatorAlert]
    trackers: list[TrackerState]


class WatchRecording(DomainModel):
    """A recorded watch run available for demo replay."""

    recording_id: str
    ticks: list[str]
    watchers: list[str]
    events: int
    llm_turns: int
    alerts: int


def event_payload(event: DomainModel) -> dict[str, Any]:
    """JSON-ready dict of an event (for SSE lines and JSONL logs)."""
    return event.model_dump(mode="json")
