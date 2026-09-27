# ============================================================
# AR-GE ID     : R6.11
# Başlık       : arge_m iddia/karar sonuçlarını SENTINEL backend modellerine çeviren adaptör
# Akış adımı   : 6 – assess_reports (rapor değerlendirme)
# Durum        : test edildi
# Amaç         : arge_m'nin CheckedReport sonucunu backend'in ReportClaim / ReportAssessment
#                modellerine dönüştürmek; böylece öneriler ana koda şema değiştirmeden denenebilir.
# Kanıt        : 137 raporun hepsi geçerli backend modeline dönüşüyor (tests/test_compat.py).
# Çalıştırma   : arge/ klasöründen: python -m pytest arge_m/tests/test_compat.py -q
# Entegrasyon  : backend/app/services/reports.py:extract_claim / verify_claim çıktısının yerine;
#                app.domain.report.ReportClaim, ReportCheck, ReportAssessment (salt okunur kullanılır).
# Sınırlar     : Backend şemasında karşılığı olmayanlar yalnızca `reason` metnine yazılır:
#                kimlik (identity), yokluk (no_heavy_vehicles, no_notable_movement), yoğunluk
#                (above_usual_density), renk, yük, "bölgeden uzaklaşıyor", üsse yönelme (toward_base
#                "activity" kontrolüne katlanır), aldatma göstergesi ve Admiralty kodu.
#                Backend'in pydantic ortamı gerekir (Python 3.12); arge_m'in kendisi gerektirmez.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Adapter: arge_m CheckedReport -> backend ReportClaim / ReportAssessment (backend used read-only)."""

import sys
from typing import Any

from .ortak.data import REPO_DIR
from .rapor_degerlendirme.admiralty import AdmiraltyRating
from .rapor_degerlendirme.claims import CheckedReport, ParsedReport

BACKEND_DIR = REPO_DIR / "backend"

# Same values as backend services/reports.py:_TRUST (private there, so mirrored here).
_TRUST = {"official": 0.8, "third_party": 0.5}
# arge_m report status -> backend Verdict.
_VERDICT = {
    "CONSISTENT": "CORROBORATED",
    "CONTRADICTED": "CONTRADICTED",
    "UNVERIFIABLE": "UNVERIFIED",
    "NOT_ASSESSED": "IRRELEVANT",
}
# arge_m assertion -> backend ReportCheck name. Types missing here have no backend equivalent.
_CHECK_NAME = {
    "existence": "location",
    "count": "presence",
    "type": "type",
    "stationary": "activity",
    "moving": "activity",
    "toward_base": "activity",
}
_CHECK_STATUS = {"supported": "match", "contradicted": "mismatch", "unverifiable": "unknown"}


def _backend() -> Any:
    """Import backend models lazily so arge_m itself keeps working without pydantic."""
    if str(BACKEND_DIR) not in sys.path:
        sys.path.append(str(BACKEND_DIR))  # append, never prepend: backend must not shadow arge_m
    from app.domain import geo, report

    return geo, report


def claim_kind(p: ParsedReport) -> str:
    """Closest backend ClaimKind for an arge_m report."""
    types = {a.type for a in p.assertions}
    if "IDENTITY" in p.categories:
        return "FRIENDLY_PRESENCE"
    if "ABSENCE" in p.categories:
        return "TRAFFIC_NORMAL" if types == {"traffic_normal"} else "ALL_CLEAR"
    if p.location is not None and p.categories != ["CONTEXT"]:
        return "SIGHTING"  # sighting, stationary, movement and density reports with a location
    return "OTHER"


def _vehicle(p: ParsedReport) -> str | None:
    # Backend has no "heavy" class; its own rules map "agir arac" to truck.
    return {"heavy": "truck", "any": None}.get(p.vehicle or "any", p.vehicle)


def _activity(p: ParsedReport) -> str:
    types = {a.type for a in p.assertions}
    if "stationary" in types:
        return "stationary"
    return "moving" if types & {"moving", "toward_base"} else "unknown"


def to_backend_claim(p: ParsedReport) -> Any:
    geo, report = _backend()
    r = p.report
    return report.ReportClaim(
        report_id=r.report_id, time=r.time, time_min=r.time_min, source=r.source, text=r.text,
        location=geo.LatLon(lat=p.location.lat, lon=p.location.lon) if p.location else None,
        zone=p.zone, vehicle_type=_vehicle(p), count=p.count, color=p.color,
        activity=_activity(p), claim_kind=claim_kind(p), extracted_by="rules",
    )


def verdict(c: CheckedReport) -> str:
    """Backend Verdict. An identity report whose movement holds up stays UNVERIFIED, never
    CORROBORATED: the backend's trust policy says threat-lowering claims we cannot confirm
    must not look confirmed."""
    if "IDENTITY" in c.parsed.categories and c.status == "CONSISTENT":
        return "UNVERIFIED"
    return _VERDICT[c.status]


def to_backend_assessment(c: CheckedReport, rating: AdmiraltyRating | None = None) -> Any:
    _, report = _backend()
    checks = [
        report.ReportCheck(name=_CHECK_NAME[a.type], status=_CHECK_STATUS[a.status], detail=f"{a.type}: {a.how}")
        for a in c.parsed.assertions
        if a.type in _CHECK_NAME
    ]
    if c.parsed.instruction_like:
        checks.append(report.ReportCheck(name="instructions", status="mismatch",
                                         detail="instruction-like text treated as data"))
    extra = [f"{a.type}={a.status}" for a in c.parsed.assertions if a.type not in _CHECK_NAME]
    reason = "; ".join(
        part for part in (
            f"Admiralty {rating.code}: {rating.reason}" if rating else "",
            f"not in backend schema: {', '.join(extra)}" if extra else "",
            "possible deception" if c.deception_indicator else "",
        ) if part
    ) or c.status
    contradicted = c.status == "CONTRADICTED" or c.parsed.instruction_like
    return report.ReportAssessment(
        report_id=c.report.report_id,
        verdict=verdict(c),
        reason=reason,
        checks=checks,
        linked_detection_ids=sorted({e for a in c.parsed.assertions for e in a.evidence if e.startswith("DET-")}),
        trust_weight=0.0 if contradicted else _TRUST.get(c.report.source, 0.4),
    )
