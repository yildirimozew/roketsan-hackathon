"""Z7 - a deception indicator raises the linked vehicle's level by one step.

Decided 2026-09-26. Requires Z4 + Z6: with report-time matching the rule would punish the wrong
vehicles (REP-06 / REP-78 / REP-120 are consistent at capture time).

Policy choice to confirm before merging: the +1 may exceed the motion ceiling
(`services/risk.py:level_ceiling`) by one step, because deception is evidence independent of the
motion patterns the ceiling is built from. Set `exceed_ceiling=False` to keep the ceiling.

Integration: pipeline step 7, after `score_vehicle` (all vehicles, incl. Z2 track-only ones);
watch mode: `raise_watch_level` when a watcher's report check has `deception=True`.
Docs: AGENT_DESIGN §3 step 6 ("contradicted ... ignored for scoring") and step 7, §12.
"""

from app.domain.risk import RISK_LEVELS, RiskFactor, RiskLevel, VehicleRisk
from app.domain.watch import WATCH_LEVELS, WatchLevel

from .contracts import ReportAssessmentV2

DECEPTION_FACTOR = "deception_indicator"


def _step_up(level: RiskLevel) -> RiskLevel:
    return RISK_LEVELS[min(len(RISK_LEVELS) - 1, RISK_LEVELS.index(level) + 1)]


def apply_deception(
    risks: list[VehicleRisk],
    assessments: list[ReportAssessmentV2],
    exceed_ceiling: bool = True,
) -> list[VehicleRisk]:
    """+1 level for every vehicle linked to a deceptive report (by detection id or track id).

    A vehicle is raised once, however many deceptive reports point at it. With
    `exceed_ceiling=False` a vehicle already capped by the ceiling is left unchanged.
    """
    deceptive = [a for a in assessments if a.deception_indicator]
    out: list[VehicleRisk] = []
    for r in risks:
        hits = [
            a.report_id
            for a in deceptive
            if r.detection_id in a.linked_detection_ids
            or (r.track_id is not None and r.track_id in a.deception_track_ids)
        ]
        capped = any(f.name == "ceiling" for f in r.factors)
        if not hits or (capped and not exceed_ceiling):
            out.append(r)
            continue
        out.append(
            r.model_copy(
                update={
                    "level": _step_up(r.level),
                    "factors": [
                        *r.factors,
                        RiskFactor(
                            name=DECEPTION_FACTOR, points=0, detail=f"+1 level: {', '.join(hits)}"
                        ),
                    ],
                }
            )
        )
    return out


def raise_watch_level(level: WatchLevel) -> WatchLevel:
    """Watch-mode counterpart: one step up, at most HIGH."""
    return WATCH_LEVELS[min(len(WATCH_LEVELS) - 1, WATCH_LEVELS.index(level) + 1)]
