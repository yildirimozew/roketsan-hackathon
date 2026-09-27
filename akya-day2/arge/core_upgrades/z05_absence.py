"""Z5 - read negative reports correctly ("agir arac hareketi yok") and check absence claims.

Today `services/reports.py:extract_claim` reads "agir arac hareketi yok, yalnizca binek araclar"
as a heavy-vehicle SIGHTING, so a truck in the area would *corroborate* a report that says there
is none (e.g. REP-92). 22 reports are absence claims.

Integration:
- `services/reports.py`: run `absence_kinds` / `is_context` before the vehicle keywords
  (`extract_claim_v2` shows the order); add "ABSENCE" / "CONTEXT" to `ClaimKind` (contracts.py).
- pipeline step 6: absence claims go to `check_absence` instead of `verify_claim`.
- An absence claim never lowers a level: a supported one is only "consistent" (no points).
"""

import re

from app.domain.detection import Detection
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.report import FieldReport, Verdict
from app.domain.scene import Zone
from app.domain.track import Track
from app.services.reports import HEAVY, extract_claim, normalize

from .contracts import AbsenceKind, ReportCheckV2, ReportClaimV2
from .z03_stationary import closing_m
from .z04_capture_time import frame_for

ZONE_WINDOW_MIN = 120  # a zone report is checked against that zone's frames up to 2 h later
NOTABLE_CLOSING_M = 1000.0  # closing this much on the base in 30 min is "notable movement"

# Tried before any vehicle keyword: the first match decides the meaning of the sentence.
ABSENCE_PATTERNS: tuple[tuple[str, AbsenceKind], ...] = (
    (r"agir (?:bir )?arac (?:hareketi )?(?:yok|bulunmuyor|gorulmedi)", "no_heavy_vehicles"),
    (r"kayda deger (?:bir )?hareketlilik (?:yok|bulunmuyor|gorulmedi)", "no_notable_movement"),
    (r"olagandisi bir durum bildirmedi|sorun yok|tehdit yok|endise yok", "no_anomaly"),
    (r"trafik akisi normal", "traffic_normal"),
)
# Statements that carry no checkable claim about a vehicle now (weather, radio, last night, plans).
CONTEXT_PATTERNS = (
    r"telsiz baglantisi",
    r"ihbar incelendi",
    r"\bdun gece\b",
    r"\bhava (?:acik|kapali|yagisli)|gorus mesafesi",
    r"planlanan saatte yola cikacak",
)
_HEAVY_WORDS = r"agir (?:bir )?arac|kamyon/otobus"
_USUAL_RE = re.compile(r"(?:genellikle|olagan trafik) (\d+) arac")


def absence_kinds(text: str) -> list[AbsenceKind]:
    """Absence claims stated in the text (empty when the report asserts presence)."""
    norm = normalize(text)
    return [kind for pat, kind in ABSENCE_PATTERNS if re.search(pat, norm)]


def is_context(text: str) -> bool:
    """True for context-only statements (weather, radio loss, last night, a future plan)."""
    norm = normalize(text)
    return any(re.search(p, norm) for p in CONTEXT_PATTERNS)


def extract_claim_v2(report: FieldReport, zones: list[Zone]) -> ReportClaimV2:
    """`services.reports.extract_claim` with negation, context, "agir bir arac" and usual counts."""
    base = extract_claim(report, zones)
    norm = normalize(report.text)
    update: dict[str, object] = {}
    usual = _USUAL_RE.search(norm)
    if usual:
        update["usual_count"] = int(usual.group(1))
        if base.count == int(usual.group(1)):
            update["count"] = None  # "genellikle 4 arac" is a baseline, not the claimed count
    if absence := absence_kinds(report.text):
        # The vehicle word inside a negation is what is *absent*: drop it.
        update |= {
            "claim_kind": "ABSENCE",
            "absence": absence,
            "vehicle_type": None,
            "activity": "unknown",
        }
    elif is_context(report.text) and base.location is None:
        update |= {"claim_kind": "CONTEXT", "vehicle_type": None, "activity": "unknown"}
    elif base.vehicle_type is None and re.search(_HEAVY_WORDS, norm):
        update["vehicle_type"] = "truck"  # "agir bir aracin": heavy family (truck ~ bus)
    return ReportClaimV2(**{**base.model_dump(), **update})


def frames_for_absence(claim: ReportClaimV2, images: list[ImageMeta]) -> list[ImageMeta]:
    """Frames an absence claim covers: its coordinate's frame, else its zone's frames <= 2 h on."""
    if claim.location is not None:
        frame = frame_for(claim.location, images)
        return [frame] if frame is not None else []
    if claim.zone is None:
        return []
    t = claim.time_min
    return [m for m in images if m.zone == claim.zone and t <= m.capture_min <= t + ZONE_WINDOW_MIN]


def _tracks_ending_at(tracks: dict[str, Track], minute: int) -> list[Track]:
    return [t for t in tracks.values() if t.points and t.points[-1].time_min == minute]


def check_absence(
    claim: ReportClaimV2,
    frames: list[ImageMeta],
    tracks: dict[str, Track],
    base: LatLon,
    detections_by_frame: dict[str, list[Detection]] | None = None,
) -> tuple[Verdict, list[ReportCheckV2]]:
    """Verdict and one `area` check per absence kind. Never lowers a level (caller's rule)."""
    names = ", ".join(m.image_id for m in frames) or "none"
    if not frames:
        return "UNVERIFIED", [
            ReportCheckV2(
                name="area", status="unknown", detail=f"no frame covers {claim.zone or 'the claim'}"
            )
        ]
    dets = detections_by_frame or {}
    checks: list[ReportCheckV2] = []
    for kind in claim.absence:
        if kind == "no_heavy_vehicles":
            seen = [m for m in frames if m.image_id in dets]
            heavy = [
                f"{m.image_id}:{d.id} {d.label}"
                for m in seen
                for d in dets[m.image_id]
                if d.label in HEAVY
            ]
            if heavy:
                checks.append(
                    ReportCheckV2(
                        name="area", status="mismatch", detail="heavy seen: " + ", ".join(heavy)
                    )
                )
            elif len(seen) == len(frames):
                checks.append(
                    ReportCheckV2(name="area", status="match", detail=f"no truck or bus in {names}")
                )
            else:
                checks.append(
                    ReportCheckV2(
                        name="area", status="unknown", detail=f"needs detections for {names}"
                    )
                )
        elif kind == "no_notable_movement":
            closing = [
                (t.track_id, c)
                for m in frames
                for t in _tracks_ending_at(tracks, m.capture_min)
                if (c := closing_m(t, m.capture_min, base)) is not None and c >= NOTABLE_CLOSING_M
            ]
            detail = (
                "; ".join(
                    f"{tid} closed {c / 1000:.1f} km on the base in 30 min" for tid, c in closing
                )
                if closing
                else f"no track closed >= {NOTABLE_CLOSING_M / 1000:.0f} km in 30 min in {names}"
            )
            checks.append(
                ReportCheckV2(name="area", status="mismatch" if closing else "match", detail=detail)
            )
        else:  # no_anomaly, traffic_normal: too vague to check, and they may never lower a level
            checks.append(
                ReportCheckV2(name="area", status="unknown", detail=f"{kind}: vague area statement")
            )
    statuses = {c.status for c in checks}
    verdict: Verdict = (
        "CONTRADICTED"
        if "mismatch" in statuses
        else "CORROBORATED"
        if "match" in statuses
        else "UNVERIFIED"
    )
    return verdict, checks
