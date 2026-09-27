"""Report handling without an LLM: rule-based claim extraction, relevance and verification.

These are the deterministic parts of AGENT_DESIGN §3 step 6 (6b) plus the fallback for 6a/6c.
The LLM (P2) may refine claims and verdicts; the trust policy below stays enforced in code.
"""

import re
from dataclasses import dataclass

from app.domain.detection import Detection, TrackMatch
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.report import (
    Activity,
    ClaimKind,
    FieldReport,
    MapReport,
    ReportCheck,
    ReportClaim,
    Verdict,
)
from app.domain.scene import Zone
from app.domain.track import Track
from app.services.geo import frame_center, haversine_m
from app.services.motion import nearest_zone
from app.services.tracks import position_at

_TR_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜâ", "cgiosuCGIOSUa")
_COORD_RE = re.compile(r"(\d{1,2}\.\d+)\s*°?\s*N[,\s]+(\d{1,3}\.\d+)\s*°?\s*E", re.IGNORECASE)
_COUNT_RE = re.compile(r"\b(\d+)\s+(?:adet\s+)?[a-z]")

# Keyword tables operate on normalized (lowercase ASCII) text.
_VEHICLE_WORDS: tuple[tuple[str, str], ...] = (
    ("agir arac", "truck"),
    ("kamyon", "truck"),
    ("tir", "truck"),
    ("otobus", "bus"),
    ("minibus", "bus"),
    ("panelvan", "van"),
    ("kamyonet", "van"),
    ("van", "van"),
    ("otomobil", "car"),
    ("binek", "car"),
    ("araba", "car"),
    ("sedan", "car"),
)
_COLORS = ("beyaz", "siyah", "kirmizi", "mavi", "gri", "yesil", "sari", "lacivert", "turuncu")
_ACTIVITY_WORDS: tuple[tuple[str, Activity], ...] = (
    ("yukleme", "loading"),
    ("yuk indir", "loading"),
    ("park", "stationary"),
    ("duruyor", "stationary"),
    ("durdugu", "stationary"),
    ("bekliyor", "stationary"),
    ("beklemede", "stationary"),
    ("hareketsiz", "stationary"),
    ("yerinden ayrilmadi", "stationary"),
    ("sabit", "stationary"),
    ("hareket halinde", "moving"),
    ("ilerliyor", "moving"),
    ("ilerleyen", "moving"),
    ("usse gelen", "moving"),
    ("yaklasiyor", "moving"),
    ("seyir halinde", "moving"),
    ("transit", "moving"),
    ("uzaklasiyor", "moving"),
    ("konvoy", "moving"),
)
# Regexes on normalized text; first match wins, so specific phrases come before generic words.
_KIND_WORDS: tuple[tuple[str, ClaimKind], ...] = (
    (r"\bdost\b", "FRIENDLY_PRESENCE"),
    (r"tatbikat", "FRIENDLY_PRESENCE"),
    (r"bize bagli", "FRIENDLY_PRESENCE"),
    (r"kimlik teyidi", "FRIENDLY_PRESENCE"),
    (r"planli ikmal", "FRIENDLY_PRESENCE"),
    (r"teyitli", "FRIENDLY_PRESENCE"),
    (r"onceden bildiril", "FRIENDLY_PRESENCE"),
    (r"endise yok", "ALL_CLEAR"),
    (r"tehdit yok", "ALL_CLEAR"),
    (r"guvenli", "ALL_CLEAR"),
    (r"temiz", "ALL_CLEAR"),
    (r"sorun yok", "ALL_CLEAR"),
    (r"durum bildirmedi", "ALL_CLEAR"),
    # Density anomaly ("beklenmedik yogunluk; olagan trafik 4 arac") must not read as normal.
    (r"beklenmedik", "OTHER"),
    (r"yogunluk", "OTHER"),
    # "olagan" but not "olagandisi" / "olagandan".
    (r"\bolagan\b", "TRAFFIC_NORMAL"),
    (r"\bnormal\b", "TRAFFIC_NORMAL"),
)
_INSTRUCTION_WORDS = (
    "talimat",
    "yok say",
    "ignore",
    "system",
    "sistem notu",
    "prompt",
    "olarak raporla",
    "olarak isaretle",
)
HEAVY = {"truck", "bus"}
_TRUST = {"official": 0.8, "third_party": 0.5}


def normalize(text: str) -> str:
    """Lowercase ASCII-folded text for keyword matching."""
    return text.translate(_TR_ASCII).lower()


def parse_coordinates(text: str) -> LatLon | None:
    """Parse the first "39.9374N 32.8483E" style coordinate in `text`."""
    m = _COORD_RE.search(text)
    return LatLon(lat=float(m.group(1)), lon=float(m.group(2))) if m else None


def has_instructions(text: str) -> bool:
    """True when the report text reads like instructions to the system (prompt injection)."""
    norm = normalize(text)
    return any(w in norm for w in _INSTRUCTION_WORDS)


def extract_claim(report: FieldReport, zones: list[Zone]) -> ReportClaim:
    """Rule-based claim extraction (fallback for the LLM extractor, AGENT_DESIGN §3 6a)."""
    norm = normalize(report.text)
    vehicle = next((v for word, v in _VEHICLE_WORDS if re.search(rf"\b{word}", norm)), None)
    kind: ClaimKind = next((k for pat, k in _KIND_WORDS if re.search(pat, norm)), "OTHER")
    location = parse_coordinates(report.text)
    if kind == "OTHER" and (vehicle or location):
        kind = "SIGHTING"
    count_match = _COUNT_RE.search(_COORD_RE.sub(" ", norm))
    return ReportClaim(
        report_id=report.report_id,
        time=report.time,
        time_min=report.time_min,
        source=report.source,
        text=report.text,
        location=location,
        zone=next((z.name for z in zones if normalize(z.name) in norm), None),
        vehicle_type=vehicle,
        count=int(count_match.group(1)) if count_match else None,
        color=next((c for c in _COLORS if c in norm), None),
        activity=next((a for word, a in _ACTIVITY_WORDS if word in norm), "unknown"),
        claim_kind=kind,
        extracted_by="rules",
    )


def is_relevant(
    claim: ReportClaim,
    meta: ImageMeta,
    detections: list[Detection],
    radius_m: float,
    window_min: int = 120,
) -> bool:
    """Report time inside the window before capture AND location near this frame or zone named."""
    if not (meta.capture_min - window_min <= claim.time_min <= meta.capture_min):
        return False
    if claim.zone is not None and claim.zone == meta.zone:
        return True
    if claim.location is None:
        return False
    anchors = [frame_center(meta)] + [d.position for d in detections if d.position]
    return any(haversine_m(claim.location, a) <= radius_m for a in anchors)


@dataclass(frozen=True)
class VerificationResult:
    """Code-side verdict before any LLM refinement."""

    verdict: Verdict
    checks: list[ReportCheck]
    linked_detection_ids: list[str]
    trust_weight: float
    lowers_threat: bool
    instructions: bool


def _same_kind(claimed: str, label: str) -> bool:
    return claimed == label or (claimed in HEAVY and label in HEAVY)


def _moving_at(track: Track, minute: int, stop_speed_ms: float) -> bool | None:
    a, b = position_at(track, minute - 5), position_at(track, minute)
    if a is None or b is None:
        return None
    return haversine_m(a, b) / 300 >= stop_speed_ms


def verify_claim(
    claim: ReportClaim,
    meta: ImageMeta,
    detections: list[Detection],
    matches: list[TrackMatch],
    tracks: dict[str, Track],
    radius_m: float,
    stop_speed_ms: float,
) -> VerificationResult:
    """Compare a relevant claim with detections now and tracks at the report's own time."""
    checks: list[ReportCheck] = []
    if claim.location is not None:
        near = [
            (d, haversine_m(claim.location, d.position))
            for d in detections
            if d.position and haversine_m(claim.location, d.position) <= radius_m
        ]
    else:
        near = [(d, 0.0) for d in detections]  # zone-level claim: every vehicle in frame
    near.sort(key=lambda item: item[1])
    if claim.vehicle_type:  # link only vehicles of the claimed kind when any exist nearby
        near = [(d, m) for d, m in near if _same_kind(claim.vehicle_type, d.label)] or near
    if claim.location is not None:
        # A pinpointed claim is about `count` vehicles (default 1), not every vehicle in 300 m:
        # frames are only 100-370 m wide, so the radius alone would link the whole frame.
        near = near[: max(1, claim.count or 1)]
    linked = [d for d, _ in near]

    if claim.location is not None:
        checks.append(
            ReportCheck(
                name="location",
                status="match" if near else "mismatch",
                detail=f"{near[0][0].id} at {near[0][1]:.0f} m" if near else "no detection nearby",
            )
        )
        at_time = [
            tid
            for tid, t in tracks.items()
            if (p := position_at(t, claim.time_min)) and haversine_m(p, claim.location) <= radius_m
        ]
        checks.append(
            ReportCheck(
                name="presence",
                status="match" if at_time else "mismatch",
                detail=(
                    f"tracks near at {claim.time}: {', '.join(at_time[:3])}"
                    if at_time
                    else f"no track near at {claim.time}"
                ),
            )
        )
    elif claim.zone is not None:
        checks.append(ReportCheck(name="location", status="match", detail=f"zone {claim.zone}"))

    if claim.vehicle_type and linked:
        labels = {d.label for d in linked}
        ok = any(_same_kind(claim.vehicle_type, label) for label in labels)
        checks.append(
            ReportCheck(
                name="type",
                status="match" if ok else "mismatch",
                detail=f"claimed {claim.vehicle_type}, detected {', '.join(sorted(labels))}",
            )
        )

    if claim.activity in ("moving", "stationary") and linked:
        by_det = {m.detection_id: m.track_id for m in matches}
        states = [
            s
            for d in linked
            if (tid := by_det.get(d.id))
            and (s := _moving_at(tracks[tid], claim.time_min, stop_speed_ms)) is not None
        ]
        if states:
            ok = any(states) if claim.activity == "moving" else not all(states)
            checks.append(
                ReportCheck(
                    name="activity",
                    status="match" if ok else "mismatch",
                    detail=f"claimed {claim.activity} at {claim.time}",
                )
            )

    instructions = has_instructions(claim.text)
    if instructions:
        checks.append(
            ReportCheck(
                name="instructions",
                status="mismatch",
                detail="instruction-like text treated as data",
            )
        )

    lowers = claim.claim_kind in ("ALL_CLEAR", "FRIENDLY_PRESENCE")
    status = {c.name: c.status for c in checks}
    contradicted = (
        status.get("type") == "mismatch"
        or status.get("activity") == "mismatch"
        or (status.get("location") == "mismatch" and status.get("presence") == "mismatch")
    )
    verdict: Verdict
    if instructions:
        verdict = "UNVERIFIED"
    elif contradicted:
        verdict = "CONTRADICTED"
    elif lowers:
        verdict = "UNVERIFIED"  # threat-lowering claims we cannot verify never lower the score
    elif (claim.location is not None and status.get("location") == "match") or status.get(
        "type"
    ) == "match":
        # A zone-name match alone is not evidence: it needs a pinpointed location or a type match.
        verdict = "CORROBORATED"
    else:
        verdict = "UNVERIFIED"

    trust = _TRUST.get(claim.source, 0.4)
    if verdict == "CONTRADICTED" or instructions:
        trust = 0.0
    return VerificationResult(
        verdict=verdict,
        checks=checks,
        linked_detection_ids=[d.id for d in linked],
        trust_weight=trust,
        lowers_threat=lowers,
        instructions=instructions,
    )


def locate_report(report: FieldReport, zones: list[Zone], zone_radius_m: float) -> MapReport:
    """Place a raw report on the map: its coordinates, and the zone it names or else lies in."""
    norm = normalize(report.text)
    location = parse_coordinates(report.text)
    named = next((z.name for z in zones if normalize(z.name) in norm), None)
    return MapReport(
        **report.model_dump(),
        location=location,
        zone=named or (nearest_zone(location, zones, zone_radius_m) if location else None),
        zone_named=named is not None,
    )
