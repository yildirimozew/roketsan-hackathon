"""Z9 - the "control computer": deterministic checks on every LLM text before an operator sees it.

Today the per-frame brief has no validator (`agent/pipeline.py`: "TODO(P2): LLM brief + validator")
and watch mode checks evidence ids only (`agent/watch/tools.py:unknown_evidence`), not the numbers
in the text. The principle "every number comes from a deterministic tool" (AGENT_FLOW §9) has no
code enforcing it.

Checks: schema (required text present), evidence (every id exists), numbers (every number with a
unit matches a computed fact of the same kind), level (within one step of the rubric), policy
(no report lowered the level; every deception indicator is mentioned).

Integration: pipeline step 8 calls `guard_brief` on the LLM brief (one repair with
`verdict.feedback`, then the template brief, marked unverified); watch mode calls `check_text` on
watcher reasons / notes and supervisor alerts with `facts_from_rows`. The template brief must
always pass (tested), so the fallback can never be rejected.
"""

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Literal

from app.domain.analysis import Analysis
from app.domain.base import DomainModel
from app.domain.brief import Brief
from app.domain.risk import RISK_LEVELS, RiskLevel
from app.domain.watch import VehicleRow

UnitClass = Literal[
    "distance_m", "speed_ms", "rate_m_per_min", "duration_min", "count", "angle_deg"
]

REL_TOL = 0.05  # numbers may be rounded: 5 % or half the last shown digit, whichever is larger
COUNT_TOL = 1.0
WINDOW_MINUTES = (5, 10, 15, 20, 30, 60, 120)  # rubric / template windows ("son 60 dakikada")
_SUFFIX = r"[a-zçğıöşü']*"  # Turkish case endings: "dakikada", "km'den"
# (regex, class, factor to base unit, allows a word suffix). Order matters: longest first.
_UNITS: tuple[tuple[str, UnitClass, float, bool], ...] = (
    (r"km", "distance_m", 1000.0, False),
    (r"m/s", "speed_ms", 1.0, False),
    (r"m/dk|m/min", "rate_m_per_min", 1.0, False),
    (r"metre|meters?", "distance_m", 1.0, True),
    (r"m", "distance_m", 1.0, False),
    (r"dakika|minutes?", "duration_min", 1.0, True),
    (r"dk|min", "duration_min", 1.0, False),
    (r"°|derece|deg", "angle_deg", 1.0, True),
    (
        r"araç|arac|vehicles?|adet|otomobil|kamyon|panelvan|otobüs|cars?|trucks?|vans?|bus(?:es)?",
        "count",
        1.0,
        True,
    ),
)
_NUMBER = r"(?<![\w.,:/-])(\d+(?:[.,]\d+)?)\s*"
_ID_RE = re.compile(r"\b(?:DET-\d+|TRK-T\d{4}|REP-\d+|T\d{4})\b")


@dataclass(frozen=True)
class NumberMention:
    """A number with a unit found in text, converted to the unit class's base unit."""

    text: str
    value: float
    unit: UnitClass
    step: float  # value of one unit in the last shown digit, in base units


def extract_numbers(text: str) -> list[NumberMention]:
    """Numbers followed by a known unit (decimal point or comma); bare numbers are ignored."""
    found: list[NumberMention] = []
    taken: list[tuple[int, int]] = []
    for pat, unit, factor, suffix in _UNITS:
        tail = _SUFFIX if suffix else r"(?![a-zçğıöşü/])"
        for m in re.finditer(_NUMBER + rf"(?:{pat}){tail}", text, flags=re.IGNORECASE):
            if any(a < m.end() and m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            raw = m.group(1).replace(",", ".")
            decimals = len(raw.split(".")[1]) if "." in raw else 0
            found.append(
                NumberMention(m.group(0).strip(), float(raw) * factor, unit, 10**-decimals * factor)
            )
    return found


@dataclass
class FactTable:
    """Every number the pipeline computed, by unit class, plus every valid evidence id."""

    values: dict[UnitClass, set[float]] = field(default_factory=dict)
    ids: set[str] = field(default_factory=set)

    def add(self, unit: UnitClass, *values: float | None) -> None:
        bucket = self.values.setdefault(unit, set())
        bucket.update(abs(float(v)) for v in values if v is not None)

    def supports(self, n: NumberMention) -> bool:
        tol_abs = COUNT_TOL if n.unit == "count" else n.step / 2
        return any(
            abs(n.value - f) <= max(tol_abs, REL_TOL * f) for f in self.values.get(n.unit, ())
        )


def facts_from_analysis(analysis: Analysis) -> FactTable:
    """Facts and valid ids of one per-frame analysis (track-only rows from Z2 included)."""
    facts = FactTable()
    facts.add("duration_min", *WINDOW_MINUTES)
    for d in analysis.detections:
        facts.add("distance_m", d.distance_to_base_m)
        facts.add("angle_deg", d.bearing_from_base_deg)
        facts.ids.add(d.id)
    labels = [d.label for d in analysis.detections]
    facts.add("count", len(labels), *(labels.count(lab) for lab in set(labels)))
    facts.add(
        "count", len(analysis.track_snapshots), sum(1 for m in analysis.matches if m.track_id)
    )
    for m in analysis.matches:
        facts.add("distance_m", m.distance_m, m.second_best_m)
        if m.track_id:
            facts.ids.update({f"TRK-{m.track_id}", m.track_id})
    for s in analysis.track_snapshots:
        facts.ids.update({f"TRK-{s.track_id}", s.track_id})
    for p in analysis.motions:
        facts.add(
            "distance_m",
            p.dist_now_m,
            p.dist_30m_ago_m,
            p.dist_60m_ago_m,
            p.min_dist_m,
            p.path_km * 1000,
        )
        facts.add("speed_ms", p.mean_speed_ms, p.last10_speed_ms)
        facts.add("rate_m_per_min", p.approach_rate_m_per_min)
        facts.add("duration_min", p.eta_to_base_min, *(s.duration_min for s in p.stops))
        facts.add("distance_m", *(s.distance_to_base_m for s in p.stops))
        facts.add("angle_deg", p.heading_deg, p.bearing_to_base_deg)
        facts.add("count", len(p.stops))
    for r in analysis.risks:
        facts.ids.add(r.detection_id)  # includes TRK-<id> stand-ins of Z2
        if r.track_id:
            facts.ids.update({f"TRK-{r.track_id}", r.track_id})
    for c in analysis.reports:
        facts.ids.add(c.report_id)
        facts.add("count", c.count)  # a quoted claim ("7 kamyon") is a legitimate number
    if analysis.image and analysis.image.zone:
        facts.ids.add(f"ZONE-{analysis.image.zone}")
    return facts


def facts_from_rows(rows: Iterable[VehicleRow]) -> FactTable:
    """Watch mode: the numbers a watcher or the supervisor was shown for its vehicles."""
    facts = FactTable()
    facts.add("duration_min", *WINDOW_MINUTES)
    rows = list(rows)
    facts.add("count", len(rows))
    for r in rows:
        facts.ids.update({f"TRK-{r.track_id}", r.track_id})
        facts.add("distance_m", r.dist_to_base_m)
        facts.add("speed_ms", r.speed_last10_ms)
        facts.add("rate_m_per_min", r.approach_rate_60m_m_per_min, r.closing_last5_m_per_min)
        facts.add("duration_min", r.eta_to_base_min, r.current_stop_min)
        facts.add("angle_deg", r.heading_deg, r.heading_vs_base_deg, r.bearing_from_base_deg)
        facts.add("count", r.long_stops_within_6km)
    return facts


class GuardCheck(DomainModel):
    """One control-computer check."""

    name: Literal["schema", "evidence", "numbers", "level", "policy"]
    passed: bool
    message: str = ""


class GuardVerdict(DomainModel):
    """All checks; `feedback` is the repair instruction sent back to the LLM once."""

    ok: bool
    checks: list[GuardCheck]
    feedback: str = ""


def _verdict(checks: list[GuardCheck]) -> GuardVerdict:
    failed = [c for c in checks if not c.passed]
    feedback = "Fix these and answer again: " + " | ".join(f"{c.name}: {c.message}" for c in failed)
    return GuardVerdict(ok=not failed, checks=checks, feedback=feedback if failed else "")


def check_text(text: str, evidence_ids: Iterable[str], facts: FactTable) -> list[GuardCheck]:
    """Evidence and number checks for any agent text (brief, watcher reason, supervisor alert)."""
    ids = set(evidence_ids) | set(_ID_RE.findall(text))
    unknown = sorted(i for i in ids if i not in facts.ids)
    bad = [n.text for n in extract_numbers(text) if not facts.supports(n)]
    return [
        GuardCheck(
            name="evidence",
            passed=not unknown,
            message=f"unknown ids: {', '.join(unknown)}" if unknown else "",
        ),
        GuardCheck(
            name="numbers",
            passed=not bad,
            message=f"not in computed facts: {', '.join(bad)}" if bad else "",
        ),
    ]


def _brief_text(brief: Brief) -> str:
    return " ".join(
        [
            brief.headline,
            brief.summary,
            *(v.text for v in brief.vehicles),
            *brief.report_notes,
            *brief.uncertainties,
        ]
    )


def guard_brief(
    brief: Brief,
    analysis: Analysis,
    rubric_level: RiskLevel,
    deception_report_ids: Iterable[str] = (),
    lowering_report_ids: Iterable[str] = (),
) -> GuardVerdict:
    """All control-computer checks on one brief against its own analysis."""
    text = _brief_text(brief)
    ids = [*brief.evidence_ids, *(i for v in brief.vehicles for i in v.evidence_ids)]
    checks = [
        GuardCheck(
            name="schema",
            passed=bool(brief.headline.strip() and brief.summary.strip()),
            message="headline and summary must not be empty",
        )
    ]
    checks += check_text(text, ids, facts_from_analysis(analysis))
    gap = RISK_LEVELS.index(brief.level) - RISK_LEVELS.index(rubric_level)
    checks.append(
        GuardCheck(
            name="level",
            passed=abs(gap) <= 1,
            message=f"level {brief.level} is {abs(gap)} steps from the rubric's {rubric_level}"
            if abs(gap) > 1
            else "",
        )
    )
    problems: list[str] = []
    lowering = list(lowering_report_ids)
    if gap < 0 and lowering:
        problems.append(
            f"level below the rubric while threat-lowering reports exist ({', '.join(lowering)})"
        )
    mentioned = set(ids) | set(_ID_RE.findall(text))
    missing = [r for r in deception_report_ids if r not in mentioned]
    if missing:
        problems.append(f"deception indicator not mentioned: {', '.join(missing)}")
    checks.append(GuardCheck(name="policy", passed=not problems, message="; ".join(problems)))
    for c in checks:
        if c.passed:
            c.message = ""
    return _verdict(checks)
