# ============================================================
# AR-GE ID     : R6.10
# Başlık       : NATO Admiralty kodu (A–F kaynak, 1–6 bilgi) her rapor için
# Akış adımı   : 6 – assess_reports (rapor değerlendirme)
# Durum        : test edildi
# Amaç         : Kaynak güvenilirliği ile bilginin doğruluğunu ayrı eksenlerde puanlamak; kaynağı etiketine
#                göre değil, günün geri kalanındaki doğrulanma oranına göre derecelendirmek.
# Kanıt        : Kontrol edilebilen raporlarda official 45/50, third_party 22/23 doğrulandı → üçüncü taraf
#                kaynaklar resmî kaynaklar kadar tuttu.
# Çalıştırma   : arge/ klasöründen: python -m arge_m.run  (Admiralty kodu her raporun satırında)
# Entegrasyon  : backend/app/services/reports.py:_TRUST (sabit 0.8 / 0.5 güven) yerine;
#                ReportAssessment'a admiralty_code alanı.
# Sınırlar     : 'A' otomatik verilmez. İki kaynak türünün ikisi de şu an B çıkıyor; ayrım bilgi
#                notundan geliyor. Kaynak türü başına tek not (kişi/birim bilgisi veride yok).
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""NATO Admiralty code (AJP-2.1 inspired) for every field report: source reliability A-F and
information credibility 1-6, rated on two separate axes.

- Source (A-F): seeded from the `source` field (official -> B, third_party -> C), then re-rated from
  how often that source's *other* checkable reports held up today (leave-one-out, so a report never
  grades its own source). "A" is never assigned automatically: one day of data is not a track record.
- Information (1-6): from the claim check in `claims.py`, never from the source label.
- Context reports (weather, radio outage, plans, last night's tips) get no code: "read, not relevant".
"""

from dataclasses import dataclass

from .claims import CheckedReport

SOURCE_SEED = {"official": "B", "third_party": "C"}
MIN_CHECKABLE = 5  # fewer checkable reports than this -> keep the seed grade
# (minimum Beta-mean, grade), best first. Beta(1 + consistent, 1 + contradicted) mean.
GRADE_STEPS = ((0.8, "B"), (0.6, "C"), (0.4, "D"), (0.0, "E"))
SOURCE_LABEL = {
    "A": "completely reliable", "B": "usually reliable", "C": "fairly reliable",
    "D": "not usually reliable", "E": "unreliable", "F": "reliability cannot be judged",
}
INFO_LABEL = {
    1: "confirmed by other sources", 2: "probably true", 3: "possibly true",
    4: "doubtful", 5: "improbable", 6: "truth cannot be judged",
}


@dataclass(frozen=True)
class AdmiraltyRating:
    report_id: str
    source_grade: str | None  # None for context reports
    info_grade: int | None
    reason: str

    @property
    def code(self) -> str:
        """'B5', or '-' for a report that was read but is not relevant."""
        if self.source_grade is None or self.info_grade is None:
            return "-"
        return f"{self.source_grade}{self.info_grade}"


@dataclass(frozen=True)
class SourceStats:
    source: str
    reports: int
    consistent: int
    contradicted: int
    unverifiable: int
    not_assessed: int

    @property
    def checkable(self) -> int:
        return self.consistent + self.contradicted


def source_grade(source: str, checked: list[CheckedReport], exclude_id: str | None = None) -> tuple[str, str]:
    """Grade a source from its other checkable reports. Returns (grade, basis sentence)."""
    seed = SOURCE_SEED.get(source)
    if seed is None:
        return "F", f"unknown source type '{source}'"
    own = [c for c in checked if c.report.source == source and c.report.report_id != exclude_id]
    ok = sum(c.status == "CONSISTENT" for c in own)
    bad = sum(c.status == "CONTRADICTED" for c in own)
    if ok + bad < MIN_CHECKABLE:
        return seed, f"{source}: default grade, only {ok + bad} other checkable report(s)"
    mean = (1 + ok) / (2 + ok + bad)
    grade = next(g for threshold, g in GRADE_STEPS if mean >= threshold)
    return grade, f"{source}: {ok}/{ok + bad} other checkable reports held up today"


def _corroborated(cr: CheckedReport, checked: list[CheckedReport]) -> list[str]:
    """Other consistent reports about the same vehicle (same matched track)."""
    tracks = set(cr.subject_track_ids)
    if not tracks:
        return []
    return [
        o.report.report_id
        for o in checked
        if o is not cr and o.status == "CONSISTENT" and tracks & set(o.subject_track_ids)
    ]


def info_grade(cr: CheckedReport, checked: list[CheckedReport]) -> tuple[int | None, str]:
    """Credibility of the information itself, from our own sensors."""
    assertions = cr.parsed.assertions
    supported = [a for a in assertions if a.status == "supported"]
    contradicted = [a for a in assertions if a.status == "contradicted"]
    open_parts = [a for a in assertions if a.status == "unverifiable" and a.type != "color"]

    if cr.status == "NOT_ASSESSED":
        grade, why = None, "read; context only, not relevant to a vehicle"
    elif cr.status == "CONTRADICTED":
        grade = 4 if supported else 5
        why = f"{contradicted[0].type} contradicted: {contradicted[0].how}"
    elif cr.status == "CONSISTENT":
        others = _corroborated(cr, checked)
        if others:
            grade, why = 1, f"matches our data and {', '.join(others[:3])}"
        elif not open_parts:
            grade, why = 2, f"{supported[0].type} supported: {supported[0].how}"
        else:
            grade = 3
            why = f"{supported[0].type} supported; {open_parts[0].type} cannot be checked"
    else:
        grade = 6
        why = f"{open_parts[0].type}: {open_parts[0].how}" if open_parts else "nothing checkable"

    if grade is not None and grade < 3 and "IDENTITY" in cr.parsed.categories:
        grade = 3  # the report's key claim (who the vehicle is) can never be checked
        why = f"{why}; identity itself cannot be checked"
    if cr.parsed.instruction_like:
        grade = 6 if grade in (None, 6) else max(grade, 4)
        why = f"instruction-like text treated as data; {why}"
    if cr.deception_indicator:
        why = f"identity claim with a contradicted checkable part (possible deception); {why}"
    return grade, why


def rate_all(checked: list[CheckedReport]) -> list[AdmiraltyRating]:
    ratings: list[AdmiraltyRating] = []
    for cr in checked:
        info, info_why = info_grade(cr, checked)
        if info is None:
            ratings.append(AdmiraltyRating(cr.report.report_id, None, None, info_why))
            continue
        grade, grade_why = source_grade(cr.report.source, checked, exclude_id=cr.report.report_id)
        ratings.append(AdmiraltyRating(cr.report.report_id, grade, info, f"{grade_why}. {info_why}"))
    return ratings


def day_summary(checked: list[CheckedReport]) -> list[SourceStats]:
    """Per-source totals for the end-of-day slide: 'X of official reports held up'."""
    out = []
    for source in sorted({c.report.source for c in checked}):
        own = [c for c in checked if c.report.source == source]
        out.append(
            SourceStats(
                source=source,
                reports=len(own),
                consistent=sum(c.status == "CONSISTENT" for c in own),
                contradicted=sum(c.status == "CONTRADICTED" for c in own),
                unverifiable=sum(c.status == "UNVERIFIABLE" for c in own),
                not_assessed=sum(c.status == "NOT_ASSESSED" for c in own),
            )
        )
    return out
