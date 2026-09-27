"""Z6 - check "toward the base" and flag deception (identity claim whose checkable part fails).

Evidence (real data, capture-time matching from Z4): of 15 located "friendly vehicle coming to
the base" reports, 13 fit; REP-61 (T0075 leaves, 4.1 -> 5.3 km, img_006444) and REP-113 (T0124
does not close, 3.4 -> 3.5 km, img_000733) do not. Identity itself can never be sensed.

Integration:
- `services/reports.py:extract_claim`: set `toward_base` / `identity_claim` (`annotate`).
- pipeline step 6: after `verify_at_capture` (Z4), build the assessment with `assess`; the
  `deception_indicator` feeds Z7. The reason strings go to `agent/fallback_templates.py`.
"""

import re

from app.domain.detection import TrackMatch
from app.domain.geo import LatLon
from app.domain.image import ImageMeta
from app.domain.report import ReportClaim, Verdict
from app.domain.track import Track
from app.services.reports import VerificationResult, normalize

from .contracts import ReportAssessmentV2, ReportCheckV2, ReportClaimV2
from .z03_stationary import closing_m
from .z04_capture_time import MATCH_M, tracks_near

CLOSING_MIN_M = 200.0  # distance-to-base drop over the last 30 min to count as "toward the base"
TOWARD_BASE_PATTERNS = (r"usse dogru", r"usse gelen")
IDENTITY_PATTERNS = (
    r"planli ikmal",
    r"bize bagli",
    r"\bdost\b",
    r"kimlik teyidi",
    r"\bteyitli",
    r"onceden bildiril",
    r"tatbikat",
    r"devriye unsuru",
)
# Move to agent/fallback_templates.py (the only place Turkish template text may live).
DECEPTION_REASON = {
    "en": "Identity claim cannot be verified and its checkable part contradicts our data: {what}. "
    "Treated as a deception indicator.",
    "tr": "Kimlik beyanı doğrulanamaz ve doğrulanabilir kısmı verimizle çelişiyor: {what}. "
    "Aldatma göstergesi olarak değerlendirildi.",
}


def annotate(claim: ReportClaim) -> ReportClaimV2:
    """Add the `toward_base` and `identity_claim` flags read from the text."""
    norm = normalize(claim.text)
    fields = claim.model_dump()
    fields["toward_base"] = any(re.search(p, norm) for p in TOWARD_BASE_PATTERNS)
    fields["identity_claim"] = claim.claim_kind == "FRIENDLY_PRESENCE" or any(
        re.search(p, norm) for p in IDENTITY_PATTERNS
    )
    return ReportClaimV2(**fields)


def subject_track_ids(
    claim: ReportClaim,
    result: VerificationResult,
    meta: ImageMeta,
    tracks: dict[str, Track],
    matches: list[TrackMatch],
) -> list[str]:
    """The vehicle(s) the report is about at capture time: a track on the coordinate, else the
    tracks of the linked detections."""
    if claim.location is not None:
        near = tracks_near(claim.location, tracks, meta.capture_min, MATCH_M)
        if near:
            return [near[0].track_id]
    by_det = {m.detection_id: m.track_id for m in matches if m.track_id}
    return [tid for d in result.linked_detection_ids if (tid := by_det.get(d))]


def direction_check(
    claim: ReportClaimV2,
    subjects: list[str],
    meta: ImageMeta,
    tracks: dict[str, Track],
    base: LatLon,
) -> ReportCheckV2 | None:
    """`toward_base` claim vs the subject's distance to the base over the 30 min before capture."""
    if not claim.toward_base or not subjects:
        return None
    tid = subjects[0]
    closing = closing_m(tracks[tid], meta.capture_min, base)
    if closing is None:
        return None
    return ReportCheckV2(
        name="direction",
        status="match" if closing >= CLOSING_MIN_M else "mismatch",
        detail=f"{tid} {'closed' if closing >= 0 else 'opened'} {abs(closing):.0f} m on the base "
        f"in the 30 min before {meta.capture_time}",
    )


def assess(
    claim: ReportClaimV2,
    result: VerificationResult,
    meta: ImageMeta,
    tracks: dict[str, Track],
    matches: list[TrackMatch],
    base: LatLon,
    reason: str,
    lang: str = "en",
) -> ReportAssessmentV2:
    """Assessment with the direction and identity checks and the deception indicator."""
    checks = list(result.checks)
    subjects = subject_track_ids(claim, result, meta, tracks, matches)
    if (direction := direction_check(claim, subjects, meta, tracks, base)) is not None:
        checks.append(direction)
    if claim.identity_claim:
        checks.append(
            ReportCheckV2(
                name="identity",
                status="unknown",
                detail="identity cannot be sensed; never lowers a level",
            )
        )
    failed = [
        c for c in checks if c.status == "mismatch" and c.name not in ("instructions", "identity")
    ]
    verdict: Verdict = "CONTRADICTED" if failed and not result.instructions else result.verdict
    deception = claim.identity_claim and verdict == "CONTRADICTED"
    if deception:
        reason = DECEPTION_REASON.get(lang, DECEPTION_REASON["en"]).format(
            what="; ".join(c.detail for c in failed)
        )
    return ReportAssessmentV2(
        report_id=claim.report_id,
        verdict=verdict,
        reason=reason,
        checks=checks,
        linked_detection_ids=result.linked_detection_ids,
        trust_weight=0.0 if verdict == "CONTRADICTED" else result.trust_weight,
        deception_indicator=deception,
        deception_track_ids=subjects if deception else [],
        checked_frame_id=meta.image_id,
    )
