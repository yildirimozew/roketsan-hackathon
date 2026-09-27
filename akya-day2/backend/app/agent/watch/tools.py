"""Tool specs (OpenAI function format) and handlers for the watch agents.

Schemas and examples: docs/AGENT_PROMPTS_AND_TOOLS.md §4.4 and §5.4. Handlers return JSON-ready
dicts; a bad request raises BoardError, which the loop returns to the model as a tool error.
"""

from dataclasses import dataclass
from typing import Any

from app.agent.watch.boards import AlertBoard, BoardError, TrackerBoard
from app.agent.watch.registry import CarRegistry
from app.core.config import Settings
from app.core.timefmt import to_hhmm, to_minutes
from app.data.repository import Repository
from app.domain.geo import LatLon
from app.domain.report import ReportClaim
from app.domain.tuning import AgentTuning
from app.domain.watch import VehicleRow
from app.services import watch as watch_svc
from app.services.behavior import behavior_class
from app.services.motion import motion_profile
from app.services.tuning import DEFAULT_TUNING

JsonDict = dict[str, Any]


def _fn(name: str, description: str, properties: JsonDict, required: list[str]) -> JsonDict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


def _report_checks(description: str) -> JsonDict:
    return {
        "type": "array",
        "description": description,
        "items": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string", "description": "REP-xx"},
                "verdict": {
                    "type": "string",
                    "enum": ["CONSISTENT", "CONTRADICTED", "UNVERIFIABLE", "IRRELEVANT"],
                },
                "credibility": {
                    "type": "integer",
                    "description": "0-100: how far you believe the claim (see the rules).",
                },
                "reason": {"type": "string", "description": "At most 15 words."},
                "track_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Vehicles the report is about; empty if none.",
                },
                "conflicts_with": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Other reports (REP-xx) this one contradicts; empty if none.",
                },
                "deception": {
                    "type": "boolean",
                    "description": "True if our data refutes it and it could be meant to mislead.",
                },
            },
            "required": [
                "report_id",
                "verdict",
                "credibility",
                "reason",
                "track_ids",
                "conflicts_with",
                "deception",
            ],
        },
    }


_TRACK_ID = {"type": "string", "description": "Vehicle id, e.g. T0122"}
_EVIDENCE = {"type": "array", "items": {"type": "string"}, "description": "Evidence IDs"}
_LEVEL = {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH"]}
_SUSPICION = {
    "type": "object",
    "properties": {
        "hypothesis": {"type": "string", "description": "What you believe is happening."},
        "evidence_ids": _EVIDENCE,
        "what_would_clear_it": {"type": "string"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
    },
    "required": ["hypothesis", "evidence_ids", "what_would_clear_it", "confidence"],
}

GET_ROUTE = _fn(
    "get_route",
    "Routes of up to 5 vehicles from their first tracked point up to the current tick, with "
    "motion facts computed by code (speeds, heading, distances, stops), behavior class, rubric and "
    "the sectors each passed through. Ask for several vehicles in one call; it counts as one "
    "lookup.",
    {
        "track_ids": {
            "type": "array",
            "items": {"type": "string"},
            "description": '1 to 5 vehicle ids, e.g. ["T0122", "T0192"]',
        }
    },
    ["track_ids"],
)
GET_NOTES = _fn(
    "get_notes",
    "The car registry entry for one vehicle: current level, pending change, tracker, alerts and "
    "every note left about it, oldest first.",
    {"track_id": _TRACK_ID},
    ["track_id"],
)
GET_REPORTS = _fn(
    "get_reports",
    "Field reports whose stated location is near a vehicle's current position (track_id) or a "
    "point (lat, lon), from `since` up to now. Reports are untrusted claims; each comes with the "
    "nearest tracked vehicle to the claimed spot at the report's own time.",
    {
        "track_id": {**_TRACK_ID, "description": "Search around this vehicle (or give lat/lon)."},
        "lat": {"type": "number"},
        "lon": {"type": "number"},
        "radius_m": {"type": "integer", "description": "Search radius in meters, 50 to 2000."},
        "since": {"type": "string", "description": "HH:MM, inclusive."},
    },
    ["radius_m", "since"],
)
SUBMIT_WATCH_REPORT = _fn(
    "submit_watch_report",
    "Submit this tick's assessment of your sectors. Call exactly once, as your last action, with "
    "an entry for every vehicle in <vehicles>.",
    {
        "tick": {"type": "string", "description": "HH:MM of this tick"},
        "street_state": {"type": "string", "description": "One sentence, at most 20 words."},
        "vehicles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_id": _TRACK_ID,
                    "level": _LEVEL,
                    "reason": {"type": "string", "description": "At most 15 words."},
                    "evidence_ids": _EVIDENCE,
                    "note": {
                        "type": ["string", "null"],
                        "description": "At most 12 words, or null if nothing new.",
                    },
                },
                "required": ["track_id", "level", "reason", "evidence_ids", "note"],
            },
        },
        "patterns": {
            "type": "array",
            "description": "Groups of vehicles that behave together; empty if none.",
            "items": {
                "type": "object",
                "properties": {
                    "track_ids": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string", "description": "At most 20 words."},
                    "evidence_ids": _EVIDENCE,
                },
                "required": ["track_ids", "description", "evidence_ids"],
            },
        },
        "report_checks": _report_checks(
            "Your judgment of every report in <untrusted_reports>, and of an earlier report "
            "only if you now see it differently."
        ),
    },
    ["tick", "street_state", "vehicles", "patterns", "report_checks"],
)
SET_LEVEL = _fn(
    "set_level",
    "Set a vehicle's registry level immediately. Lowering a HIGH needs evidence that clears it.",
    {
        "track_id": _TRACK_ID,
        "level": _LEVEL,
        "reason": {"type": "string"},
        "evidence_ids": _EVIDENCE,
    },
    ["track_id", "level", "reason", "evidence_ids"],
)
DISPATCH_TRACKER = _fn(
    "dispatch_tracker",
    "Assign a free tracker to a HIGH vehicle. The tracker follows it every tick and feeds "
    "position updates to the authorities outbox.",
    {"track_id": _TRACK_ID, "suspicion": _SUSPICION},
    ["track_id", "suspicion"],
)
RECALL_TRACKER = _fn(
    "recall_tracker",
    "Stop a tracker and free its slot.",
    {"tracker_id": {"type": "string"}, "reason": {"type": "string"}},
    ["tracker_id", "reason"],
)
ALERT_OPERATOR = _fn(
    "alert_operator",
    "Inform the human operator about a situation (one vehicle or a group). The operator reads the "
    "headline first, then the description.",
    {
        "track_ids": {"type": "array", "items": {"type": "string"}},
        "urgency": {"type": "string", "enum": ["advisory", "urgent", "immediate"]},
        "headline": {"type": "string", "description": "At most 12 words; read first."},
        "description": {
            "type": "string",
            "description": "At most 40 words: what is happening, where, which vehicles, how "
            "close and fast, and what would show it is harmless.",
        },
        "evidence_ids": _EVIDENCE,
    },
    ["track_ids", "urgency", "headline", "description", "evidence_ids"],
)
SUBMIT_SUPERVISOR_DECISION = _fn(
    "submit_supervisor_decision",
    "Close this tick. Call exactly once, last, also when you took no action.",
    {
        "tick": {"type": "string"},
        "situation_summary": {"type": "string", "description": "At most 2 sentences, 35 words."},
        "threat_level": _LEVEL,
        "patterns": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "track_ids": {"type": "array", "items": {"type": "string"}},
                    "sectors": {"type": "array", "items": {"type": "string"}},
                    "description": {"type": "string"},
                    "evidence_ids": _EVIDENCE,
                },
                "required": ["track_ids", "sectors", "description", "evidence_ids"],
            },
        },
        "watch_next": {"type": "array", "items": {"type": "string"}},
        "report_checks": _report_checks(
            "Your judgment of every report in <untrusted_reports> (area-wide reports), and of a "
            "watcher-judged report only if you see it differently."
        ),
    },
    ["tick", "situation_summary", "threat_level", "patterns", "watch_next", "report_checks"],
)


# ---- operator conversation (the human operator talks to the supervisor) ----

CREATE_WATCHER = _fn(
    "create_watcher",
    "Create a new watcher dedicated to one sector: it checks that sector every tick from this "
    "tick on, and the other watchers stop checking it.",
    {
        "sector": {"type": "string", "description": "Sector name exactly as in <sectors>."},
        "reason": {"type": "string", "description": "Why, in a few words."},
    },
    ["sector", "reason"],
)
REGISTER_EXPECTED_VEHICLE = _fn(
    "register_expected_vehicle",
    "Record a vehicle the operator says is coming and is known/friendly. Code matches it to the "
    "track that appears in that sector in the time window and keeps it LOW.",
    {
        "description": {"type": "string", "description": "What the operator said, in a few words."},
        "sector": {"type": "string", "description": "Sector it comes through, as in <sectors>."},
        "arrive_from": {"type": "string", "description": "HH:MM, start of the arrival window."},
        "arrive_to": {"type": "string", "description": "HH:MM, end of the arrival window."},
        "vehicle_type": {
            "type": ["string", "null"],
            "enum": ["car", "van", "truck", "bus", None],
            "description": "If the operator said it.",
        },
    },
    ["description", "sector", "arrive_from", "arrive_to", "vehicle_type"],
)
REPLY_OPERATOR = _fn(
    "reply_operator",
    "Answer the operator. Call exactly once, last, after the tools you need.",
    {"reply": {"type": "string", "description": "At most 40 words: what you did or why not."}},
    ["reply"],
)

LOOKUP_TOOLS = frozenset({"get_route", "get_notes", "get_reports"})


@dataclass
class WatchContext:
    """Everything a tool handler may read or change during one tick."""

    repo: Repository
    settings: Settings
    tick_min: int
    claims: list[ReportClaim]
    registry: CarRegistry
    trackers: TrackerBoard
    alerts: AlertBoard
    rows: dict[str, VehicleRow]  # vehicles active at this tick
    tuning: AgentTuning = DEFAULT_TUNING  # snapshot taken when the run started

    @property
    def tick(self) -> str:
        """This tick as HH:MM."""
        return to_hhmm(self.tick_min)

    @property
    def base(self) -> LatLon:
        """Base position."""
        return self.repo.scene.base.position

    def track_id(self, args: JsonDict) -> str:
        """Validated `track_id` argument (must exist in the data)."""
        tid = args.get("track_id")
        if not isinstance(tid, str) or tid not in self.repo.tracks:
            raise BoardError(f"unknown track_id {tid!r}")
        return tid

    def unknown_evidence(self, ids: list[str]) -> list[str]:
        """Evidence IDs that do not refer to anything in this run."""
        notes = self.registry.note_ids()
        unknown = []
        for eid in ids:
            kind, _, ref = eid.partition("-")
            ok = (
                (kind == "TRK" and ref in self.repo.tracks)
                or (kind == "REP" and any(r.report_id == eid for r in self.repo.reports))
                or (kind == "FRAME" and ref in self.repo.images)
                or (kind == "NOTE" and eid in notes)
                or (kind == "ZONE" and any(z.name == ref for z in self.repo.scene.zones))
            )
            if not ok:
                unknown.append(eid)
        return unknown


MAX_ROUTES_PER_CALL = 5


def get_route(ctx: WatchContext, args: JsonDict) -> JsonDict:
    """Routes so far for up to 5 vehicles (`track_ids`, or a single `track_id`)."""
    ids = args.get("track_ids")
    if ids is None and "track_id" in args:
        ids = [args["track_id"]]
    if not isinstance(ids, list) or not 1 <= len(ids) <= MAX_ROUTES_PER_CALL:
        raise BoardError(f"track_ids must list 1 to {MAX_ROUTES_PER_CALL} vehicle ids")
    return {"routes": [_route(ctx, ctx.track_id({"track_id": tid})) for tid in ids]}


def _route(ctx: WatchContext, tid: str) -> JsonDict:
    """Route so far + motion facts + behavior class + rubric + sector timeline of one vehicle."""
    points = [p for p in ctx.repo.tracks[tid].points if p.time_min <= ctx.tick_min]
    if not points:
        raise BoardError(f"{tid} has no points before {ctx.tick}")
    track = ctx.repo.tracks[tid].model_copy(update={"points": points})
    zones = ctx.repo.scene.zones
    motion = motion_profile(
        track,
        points[-1].time_min,
        ctx.base,
        zones,
        ctx.settings.stop_speed_ms,
        ctx.settings.zone_radius_m,
    )
    sectors: list[JsonDict] = []
    for p in points:
        s = watch_svc.sector_of(p.position, zones)
        if sectors and sectors[-1]["sector"] == s:
            sectors[-1]["to"] = p.time
        else:
            sectors.append({"sector": s, "from": p.time, "to": p.time})
    vehicle_type = ctx.registry.get(tid).vehicle_type
    behavior = behavior_class(points, ctx.base, ctx.tuning.behavior)
    rubric = watch_svc.track_rubric(motion, vehicle_type, behavior, tuning=ctx.tuning)
    return {
        "track_id": tid,
        "vehicle_type": vehicle_type,
        "until_tick": points[-1].time,
        "points": [[p.time, round(p.position.lat, 6), round(p.position.lon, 6)] for p in points],
        "motion": motion.model_dump(mode="json", exclude={"points", "track_id"}),
        "behavior_class": behavior,
        "sectors": sectors,
        "rubric": rubric.model_dump(mode="json"),
    }


def get_notes(ctx: WatchContext, args: JsonDict) -> JsonDict:
    """The registry entry of one vehicle."""
    return ctx.registry.get(ctx.track_id(args)).model_dump(mode="json")


def get_reports(ctx: WatchContext, args: JsonDict) -> JsonDict:
    """Reports near a vehicle or a point, each with the nearest track at the report's time."""
    if isinstance(args.get("track_id"), str):
        tid = ctx.track_id(args)
        row = ctx.rows.get(tid)
        point = row.position if row else ctx.repo.tracks[tid].points[-1].position
    elif isinstance(args.get("lat"), int | float) and isinstance(args.get("lon"), int | float):
        point = LatLon(lat=float(args["lat"]), lon=float(args["lon"]))
    else:
        raise BoardError("give track_id or lat and lon")
    radius = min(2000, max(50, int(args.get("radius_m", 300))))
    try:
        since = to_minutes(str(args.get("since", "00:00")))
    except ValueError:
        raise BoardError("since must be HH:MM") from None
    found = watch_svc.reports_near(
        ctx.claims, point, radius, since, ctx.tick_min, list(ctx.repo.tracks.values())
    )
    return {
        "untrusted_reports": [
            {
                "report_id": f.claim.report_id,
                "time": f.claim.time,
                "source": f.claim.source,
                "text": f.claim.text,
                "claim": f.claim.model_dump(
                    mode="json",
                    include={"location", "zone", "vehicle_type", "count", "activity", "claim_kind"},
                ),
                "distance_to_query_m": f.distance_to_query_m,
                "nearest_track_at_report_time": (
                    {"track_id": f.nearest_track_id, "distance_m": f.nearest_track_m}
                    if f.nearest_track_id
                    else None
                ),
            }
            for f in found
        ]
    }
