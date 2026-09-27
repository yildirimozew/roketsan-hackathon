"""Z8 - "insufficient evidence": the system says "I am not sure" instead of a confident LOW.

Decided 2026-09-26: a flag, not a fifth level. The level stays; the brief gets an uncertainty line
and at least `VERIFY`.

Integration: compute `assess_evidence` at the end of pipeline step 7 (inputs come from Z1 / Z2),
store it on `Analysis` (contracts.EvidenceStatus), and call `apply_to_brief` in step 8. The UI
shows a badge next to the level. The template strings go to `agent/fallback_templates.py`.
"""

from app.domain.brief import Brief, RecommendedAction

from .contracts import EvidenceStatus

MIN_TRACK_COVERAGE = 0.5  # share of in-frame tracks that a detection must cover
MAX_TRACK_ONLY_SHARE = 0.5  # more vehicles known only from tracks than this: vision is weak

# Move to agent/fallback_templates.py (the only place Turkish template text may live).
UNCERTAINTY = {
    "en": "Insufficient evidence for this frame ({why}); treat the level as provisional and "
    "request another look.",
    "tr": "Bu kare için kanıt yetersiz ({why}); seviyeyi geçici kabul edin ve yeniden bakılmasını "
    "isteyin.",
}
REASON_TEXT = {
    "no_detector": {"en": "no detector output", "tr": "tespit çıktısı yok"},
    "fallback_detector": {"en": "fallback detector used", "tr": "yedek dedektör kullanıldı"},
    "low_track_coverage": {
        "en": "detections cover few of the tracked vehicles",
        "tr": "tespitler izlenen araçların azını karşılıyor",
    },
    "mostly_track_only": {
        "en": "most vehicles known only from tracks",
        "tr": "araçların çoğu yalnızca iz verisinden biliniyor",
    },
}
_ACTION_ORDER: tuple[RecommendedAction, ...] = ("MONITOR", "VERIFY", "ESCALATE")


def assess_evidence(
    *,
    detector_available: bool,
    fallback_used: bool,
    in_frame_track_ids: list[str],
    matched_track_ids: list[str],
    n_detections: int,
    n_track_only: int,
) -> EvidenceStatus:
    """Flag the frame when vision is missing, degraded or disagrees with the tracks."""
    reasons: list[str] = []
    if not detector_available:
        reasons.append("no_detector")
    elif fallback_used:
        reasons.append("fallback_detector")
    if detector_available and in_frame_track_ids:
        covered = len(set(matched_track_ids) & set(in_frame_track_ids)) / len(in_frame_track_ids)
        if covered < MIN_TRACK_COVERAGE:
            reasons.append("low_track_coverage")
    vehicles = n_detections + n_track_only
    if vehicles and n_track_only / vehicles > MAX_TRACK_ONLY_SHARE:
        reasons.append("mostly_track_only")
    # A fallback detector alone is worth reporting but is not "insufficient" by itself.
    insufficient = any(r != "fallback_detector" for r in reasons)
    return EvidenceStatus(insufficient_evidence=insufficient, reasons=reasons)


def apply_to_brief(brief: Brief, status: EvidenceStatus, lang: str = "en") -> Brief:
    """Add the uncertainty line and raise the action to at least VERIFY; the level is unchanged."""
    if not status.insufficient_evidence:
        return brief
    lang = lang if lang in UNCERTAINTY else "en"
    why = ", ".join(REASON_TEXT[r][lang] for r in status.reasons if r in REASON_TEXT)
    action = max(brief.recommended_action, "VERIFY", key=_ACTION_ORDER.index)
    return brief.model_copy(
        update={
            "uncertainties": [UNCERTAINTY[lang].format(why=why), *brief.uncertainties],
            "recommended_action": action,
        }
    )
