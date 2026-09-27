# ============================================================
# AR-GE ID     : R6.1–R6.9
# Başlık       : Genişletilmiş SALUTE: rapor iddialarını ayrıştırma ve kendi verimizle kontrol
# Akış adımı   : 6 – assess_reports (rapor değerlendirme)
# Durum        : test edildi
# Amaç         : Her raporu atomik iddialara bölmek (varlık, sayı, tip, duruş, hareket, üsse yönelme,
#                yoğunluk, yokluk, kimlik, renk, yük) ve her birini desteklendi / çelişiyor / doğrulanamaz diye işaretlemek.
# Kanıt        : 72 koordinatlı raporun 62'si bir izin SON noktasına (çekim anı) 15 m'den yakın, rapor
#                saatindeki konuma yakın olan yalnızca 17. Kimlik raporlarından REP-61 (T0075 üsten uzaklaşıyor)
#                ve REP-113 (T0124 yaklaşmıyor) çelişiyor.
# Çalıştırma   : arge/ klasöründen: python -m arge_m.run
# Entegrasyon  : backend/app/services/reports.py:extract_claim ve verify_claim; ayrıca
#                services/watch.py:reports_near (şu an rapor saatindeki en yakın izi kullanıyor).
# Sınırlar     : Tespit olmadan tip, 'ağır araç yok' ve eksik araç iddiaları doğrulanamaz kalır.
#                Renk ve yük hiç kontrol edilmez. Yoğunluk tüm kareyi sayar.
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Extended SALUTE claims: parse a free-text field report into atomic assertions and check each
one against our own sensors (tracks, and detections when available).

Two extensions to classic SALUTE, because the organizer's reports need them:
- absence claims ("agir arac hareketi yok", "kayda deger hareketlilik bulunmuyor") are negative
  assertions: a heavy vehicle in the area contradicts them instead of confirming a sighting;
- identity claims ("planli ikmal araci", "bize bagli unsur") can never be sensed, so they are always
  unverifiable and must never lower risk on their own; the movement part of the same report is
  checked separately.

Data finding that drives the matching (measured on the organizer's files, see ARGE_M.md R6.5):
every coordinate report lies inside exactly one frame, 5-120 min before its capture, and 62 of 72
sit within 15 m of a track's END point (the vehicle at capture time) but only 17 at the report's own
timestamp. So a report describes the vehicle as seen in its frame; the report timestamp is soft.
"""

import re
from dataclasses import dataclass, field
from typing import Literal

from ..ortak.data import Dataset, Detection, Frame, Point, Report, Track

Category = Literal["SIGHTING", "STATIONARY", "MOVEMENT", "DENSITY", "ABSENCE", "IDENTITY", "CONTEXT"]
AssertionType = Literal[
    "existence",
    "count",
    "type",
    "stationary",
    "moving",
    "toward_base",
    "leaving_area",
    "above_usual_density",
    "no_heavy_vehicles",
    "no_notable_movement",
    "no_anomaly",
    "traffic_normal",
    "identity",
    "color",
    "cargo",
]
Status = Literal["supported", "contradicted", "unverifiable"]
ReportStatus = Literal["CONSISTENT", "CONTRADICTED", "UNVERIFIABLE", "NOT_ASSESSED"]
Vehicle = Literal["car", "van", "truck", "bus", "heavy", "any"]

# Tunables (metres / minutes). Chosen from the data, see README.
FRAME_MARGIN_M = 60.0  # a coordinate report belongs to the frame whose footprint (+margin) holds it
MATCH_M = 25.0  # report coordinate -> vehicle at capture time
GROUP_M = 80.0  # multi-vehicle claims spread up to ~76 m around the stated coordinate
# Max drift from the final position that still counts as "not moving". Measured: parked tracks
# drift at most 39 m over 60 min, every other track moves >= 400 m, so 100 m sits in the gap.
STATIONARY_MAX_M = 100.0
MOVING_MIN_M = 100.0  # path over the last 30 min to count as "moving"
CLOSING_MIN_M = 200.0  # distance-to-base drop over the last 30 min to count as "toward the base"
NOTABLE_CLOSING_M = 1000.0  # closing this much in 30 min is "notable movement" in an area
ZONE_WINDOW_MIN = 120  # zone reports are checked against that zone's frames up to 2 h later

HEAVY: frozenset[str] = frozenset({"truck", "bus"})
_TR_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜâ", "cgiosuCGIOSUa")
_COORD_RE = re.compile(r"(\d{1,2}\.\d+)\s*°?\s*N[,\s]+(\d{1,3}\.\d+)\s*°?\s*E", re.IGNORECASE)

# Order matters: the first match wins, so specific phrases come before generic words.
_VEHICLE_WORDS: tuple[tuple[str, Vehicle], ...] = (
    (r"agir (?:bir )?arac", "heavy"),
    (r"kamyon/otobus", "heavy"),
    (r"kamyonet", "van"),
    (r"kamyon", "truck"),
    (r"otobus|minibus", "bus"),
    (r"panelvan", "van"),
    (r"otomobil|binek|sedan", "car"),
    (r"\barac", "any"),
)
_COUNT_WORDS = r"(?:araclik|agir (?:bir )?arac|kamyon|otobus|panelvan|otomobil|arac)"
_COLORS = ("beyaz", "siyah", "kirmizi", "mavi", "gri", "yesil", "sari", "lacivert", "turuncu")

_CONTEXT_PATTERNS = (
    r"telsiz baglantisi",
    r"ihbar incelendi",
    r"\bdun gece\b",
    r"\bhava (?:acik|kapali|yagisli)|gorus mesafesi",
    r"planlanan saatte yola cikacak",  # a plan, not an observation
)
_IDENTITY_PATTERNS = (
    r"planli ikmal",
    r"bize bagli",
    r"\bdost\b",
    r"kimlik teyidi",
    r"\bteyitli",
    r"onceden bildiril",
    r"tatbikat",
)
_ABSENCE_PATTERNS: tuple[tuple[str, AssertionType], ...] = (
    (r"agir arac (?:hareketi )?(?:yok|bulunmuyor|gorulmedi)", "no_heavy_vehicles"),
    (r"kayda deger (?:bir )?hareketlilik (?:yok|bulunmuyor)", "no_notable_movement"),
    (r"olagandisi bir durum bildirmedi|sorun yok|tehdit yok|endise yok", "no_anomaly"),
    (r"trafik akisi normal", "traffic_normal"),
)
_STATIONARY_PATTERNS = (
    r"hareketsiz",
    r"yerinden ayrilmadi",
    r"durdugu",
    r"duruyor",
    r"bekliyor",
    r"beklemede",
    r"park halinde",
)
_LONG_STOP_PATTERNS = (r"uzun suredir", r"bir saatten uzun")
_MOVING_PATTERNS = (r"ilerliyor", r"ilerleyen", r"usse gelen", r"transit", r"uzaklasiyor", r"konvoy")
_TOWARD_BASE_PATTERNS = (r"usse dogru", r"usse gelen")
_HEARSAY_PATTERNS = (r"bir ihbara gore", r"bir kaynak", r"ihbar alindi", r"bildirildi", r"iletti")
_CARGO_PATTERNS = (r"\byuklu\b", r"uzeri ortulu")
_INSTRUCTION_PATTERNS = (
    r"talimat",
    r"yok say",
    r"ignore",
    r"system",
    r"sistem notu",
    r"prompt",
    r"olarak raporla",
    r"olarak isaretle",
    r"risk(?:i)? (?:seviyesini )?(?:dusuk|low)",
)


def normalize(text: str) -> str:
    """Lowercase ASCII-folded text for pattern matching."""
    return text.translate(_TR_ASCII).lower()


def _any(patterns: tuple[str, ...], norm: str) -> bool:
    return any(re.search(p, norm) for p in patterns)


@dataclass
class Assertion:
    """One checkable (or explicitly uncheckable) part of a report."""

    type: AssertionType
    value: str
    status: Status = "unverifiable"
    how: str = ""
    evidence: list[str] = field(default_factory=list)


@dataclass
class ParsedReport:
    report: Report
    categories: list[Category]
    location: Point | None
    zone: str | None
    vehicle: Vehicle | None
    count: int | None
    usual_count: int | None
    color: str | None
    hearsay: bool
    instruction_like: bool
    assertions: list[Assertion]
    unparsed: bool  # nothing recognised; filed as CONTEXT so every report still gets a category

    @property
    def primary(self) -> Category:
        order: tuple[Category, ...] = (
            "IDENTITY", "ABSENCE", "DENSITY", "MOVEMENT", "STATIONARY", "SIGHTING", "CONTEXT",
        )
        return next(c for c in order if c in self.categories)


@dataclass
class CheckedReport:
    parsed: ParsedReport
    frame_ids: list[str]  # frames the report was checked against
    status: ReportStatus
    deception_indicator: bool  # identity claim whose checkable part contradicts our data

    @property
    def report(self) -> Report:
        return self.parsed.report

    @property
    def linked_track_ids(self) -> list[str]:
        return sorted({e[4:] for a in self.parsed.assertions for e in a.evidence if e.startswith("TRK-")})

    @property
    def subject_track_ids(self) -> list[str]:
        """The vehicle(s) the report is about: evidence of existence/motion, not of area counts."""
        subject_types = ("existence", "stationary", "moving", "toward_base")
        return sorted(
            {e[4:] for a in self.parsed.assertions if a.type in subject_types and a.status == "supported"
             for e in a.evidence if e.startswith("TRK-")}
        )


def parse_report(report: Report, zone_names: list[str]) -> ParsedReport:
    """Rule-based parse into SALUTE-style assertions. Nothing is checked here."""
    norm = normalize(report.text)
    m = _COORD_RE.search(report.text)
    location = Point(float(m.group(1)), float(m.group(2))) if m else None
    zone = next((z for z in zone_names if normalize(z) in norm), None)
    instruction_like = _any(_INSTRUCTION_PATTERNS, norm)
    hearsay = _any(_HEARSAY_PATTERNS, norm)
    base = dict(report=report, location=location, zone=zone, hearsay=hearsay, instruction_like=instruction_like)

    if _any(_CONTEXT_PATTERNS, norm) and location is None:
        return ParsedReport(
            **base, categories=["CONTEXT"], vehicle=None, count=None, usual_count=None, color=None,
            assertions=[], unparsed=False,
        )

    text_wo_coord = _COORD_RE.sub(" ", norm)
    vehicle = next((v for pat, v in _VEHICLE_WORDS if re.search(pat, text_wo_coord)), None)
    usual = re.search(r"(?:genellikle|olagan trafik) (\d+) arac", text_wo_coord)
    usual_count = int(usual.group(1)) if usual else None
    count_text = text_wo_coord[: usual.start()] if usual else text_wo_coord
    cm = re.search(rf"\b(\d+|bir) {_COUNT_WORDS}", count_text)
    count = None if cm is None else (1 if cm.group(1) == "bir" else int(cm.group(1)))
    color = next((c for c in _COLORS if re.search(rf"\b{c}\b", norm)), None)

    assertions: list[Assertion] = []
    absence = [(p, t) for p, t in _ABSENCE_PATTERNS if re.search(p, norm)]
    for _, atype in absence:
        assertions.append(Assertion(atype, "area"))
    if usual_count is not None or re.search(r"yogun", norm):
        assertions.append(Assertion("above_usual_density", f"more than usual ({usual_count or '?'})"))
    if location is not None and not absence:
        assertions.append(Assertion("existence", vehicle or "any"))
        if count is not None and usual_count is None:
            assertions.append(Assertion("count", str(count)))
        if vehicle not in (None, "any"):
            assertions.append(Assertion("type", vehicle))
    if _any(_STATIONARY_PATTERNS, norm):
        window = 60 if _any(_LONG_STOP_PATTERNS, norm) else 30
        assertions.append(Assertion("stationary", f"{window} min"))
    elif _any(_MOVING_PATTERNS, norm):
        assertions.append(Assertion("moving", "last 30 min"))
        if _any(_TOWARD_BASE_PATTERNS, norm):
            assertions.append(Assertion("toward_base", "last 30 min"))
        elif re.search(r"bolgeden uzaklasiyor", norm):
            assertions.append(Assertion("leaving_area", "area"))
    if _any(_IDENTITY_PATTERNS, norm):
        assertions.append(Assertion("identity", "friendly/supply"))
    if color and location is not None:
        assertions.append(Assertion("color", color))
    if _any(_CARGO_PATTERNS, norm):
        assertions.append(Assertion("cargo", "loaded/covered"))

    categories = _categories(assertions)
    return ParsedReport(
        **base, categories=categories or ["CONTEXT"], vehicle=vehicle, count=count,
        usual_count=usual_count, color=color, assertions=assertions, unparsed=not categories,
    )


def _categories(assertions: list[Assertion]) -> list[Category]:
    by_type: dict[AssertionType, Category] = {
        "existence": "SIGHTING", "count": "SIGHTING", "type": "SIGHTING", "color": "SIGHTING",
        "cargo": "SIGHTING", "stationary": "STATIONARY", "moving": "MOVEMENT",
        "toward_base": "MOVEMENT", "leaving_area": "MOVEMENT", "above_usual_density": "DENSITY",
        "no_heavy_vehicles": "ABSENCE", "no_notable_movement": "ABSENCE", "no_anomaly": "ABSENCE",
        "traffic_normal": "ABSENCE", "identity": "IDENTITY",
    }
    out: list[Category] = []
    for a in assertions:
        c = by_type[a.type]
        if c not in out:
            out.append(c)
    return out


# --- checking against our own data -------------------------------------------------------------


def _same_type(claimed: Vehicle, label: str) -> bool:
    """Tolerant type match: heavy = truck|bus; car <-> van are easily confused from above."""
    if claimed == "any":
        return True
    if claimed == "heavy" or claimed in HEAVY:
        return label in HEAVY
    return label in ("car", "van")


def _window(track: Track, start: int, end: int) -> list[Point]:
    return [p.pos for p in track.points if start <= p.minute <= end]


def _path_m(points: list[Point]) -> float:
    return sum(a.dist_m(b) for a, b in zip(points, points[1:]))


def _frame_for(loc: Point, ds: Dataset) -> Frame | None:
    inside = [f for f in ds.frames.values() if f.contains(loc, FRAME_MARGIN_M)]
    return min(inside, key=lambda f: f.center.dist_m(loc), default=None)


def _det_id(d: Detection, ds: Dataset) -> str:
    return f"DET-{d.image_id}-{ds.detections[d.image_id].index(d) + 1}"


def check_report(parsed: ParsedReport, ds: Dataset) -> CheckedReport:
    """Mark each assertion supported / contradicted / unverifiable, then derive the report status."""
    frames: list[Frame] = []
    if "CONTEXT" in parsed.categories and len(parsed.categories) == 1:
        return CheckedReport(parsed, [], "NOT_ASSESSED", False)
    if parsed.location is not None:
        frame = _frame_for(parsed.location, ds)
        if frame is not None:
            frames = [frame]
            _check_point_claims(parsed, frame, ds)
        else:
            for a in parsed.assertions:
                a.how = a.how or "outside drone coverage"
    elif parsed.zone is not None:
        t = parsed.report.time_min
        frames = [
            f for f in ds.frames_in_zone(parsed.zone) if t <= f.capture_min <= t + ZONE_WINDOW_MIN
        ]
        _check_area_claims(parsed, frames, ds)

    for a in parsed.assertions:
        if a.type == "identity":
            a.how = "identity cannot be sensed from imagery or tracks; never lowers risk"
        elif a.type in ("color", "cargo") and not a.how:
            a.how = "no colour/cargo classifier"
        elif a.type in ("no_anomaly", "traffic_normal") and not a.how:
            a.how = "vague area statement; cannot lower risk"
        elif not a.how:
            a.how = "no frame covers this claim"

    statuses = {a.status for a in parsed.assertions}
    status: ReportStatus = (
        "CONTRADICTED" if "contradicted" in statuses
        else "CONSISTENT" if "supported" in statuses
        else "UNVERIFIABLE"
    )
    deception = "IDENTITY" in parsed.categories and status == "CONTRADICTED"
    return CheckedReport(parsed, [f.image_id for f in frames], status, deception)


def _check_point_claims(parsed: ParsedReport, frame: Frame, ds: Dataset) -> None:
    loc, cap = parsed.location, frame.capture_min
    assert loc is not None
    tracks = sorted(ds.tracks_ending_at(cap), key=lambda t: t.end.pos.dist_m(loc))
    dets = ds.detections.get(frame.image_id)  # None = detector not run for this frame
    near_tracks = [t for t in tracks if t.end.pos.dist_m(loc) <= MATCH_M]
    group_tracks = [t for t in tracks if t.end.pos.dist_m(loc) <= GROUP_M]
    near_dets = sorted(
        (d for d in dets or [] if d.pos.dist_m(loc) <= MATCH_M), key=lambda d: d.pos.dist_m(loc)
    )
    n_claimed = parsed.count or 1
    where = f"{frame.image_id} at {frame.capture_time}"

    for a in parsed.assertions:
        if a.type == "existence":
            if near_tracks:
                t = near_tracks[0]
                a.status, a.evidence = "supported", [f"TRK-{t.track_id}"]
                a.how = f"{t.track_id} is {t.end.pos.dist_m(loc):.0f} m from the stated point in {where}"
            elif near_dets:
                a.status, a.evidence = "supported", [_det_id(near_dets[0], ds)]
                a.how = f"detected {near_dets[0].label} {near_dets[0].pos.dist_m(loc):.0f} m away in {where}"
            elif dets is not None:
                a.status, a.how = "contradicted", f"no track or detection within {MATCH_M:.0f} m in {where}"
            else:
                a.how = f"no track within {MATCH_M:.0f} m in {where}; parked vehicles may have no track (run the detector)"
        elif a.type == "count":
            claimed = int(a.value)
            if dets is not None:
                same = [d for d in dets if d.pos.dist_m(loc) <= GROUP_M and _same_type(parsed.vehicle or "any", d.label)]
                ok = abs(len(same) - claimed) <= 1
                a.status = "supported" if ok else "contradicted"
                a.evidence = [_det_id(d, ds) for d in same]
                a.how = f"claimed {claimed}, detected {len(same)} matching vehicle(s) within {GROUP_M:.0f} m"
            elif len(group_tracks) >= claimed - 1 and group_tracks:
                a.status, a.evidence = "supported", [f"TRK-{t.track_id}" for t in group_tracks]
                a.how = f"claimed {claimed}, {len(group_tracks)} track(s) within {GROUP_M:.0f} m (type unknown)"
            else:
                a.how = f"claimed {claimed}, {len(group_tracks)} track(s) within {GROUP_M:.0f} m; parked vehicles may lack tracks"
        elif a.type == "type":
            if near_dets:
                d = near_dets[0]
                a.status = "supported" if _same_type(a.value, d.label) else "contradicted"  # type: ignore[arg-type]
                a.evidence = [_det_id(d, ds)]
                a.how = f"claimed {a.value}, detected {d.label}"
            else:
                a.how = "tracks carry no vehicle type; needs a detection"
        elif a.type in ("stationary", "moving", "toward_base"):
            if n_claimed > 1 and group_tracks:
                _check_group_motion(a, group_tracks, n_claimed, cap, ds)
            elif near_tracks:
                ok, detail = _motion_ok(a, near_tracks[0], cap, ds)
                a.status = "supported" if ok else "contradicted"
                a.evidence, a.how = [f"TRK-{near_tracks[0].track_id}"], detail
            else:
                a.how = "no matched track to read motion from"
        elif a.type == "leaving_area":
            a.how = "'leaving the area' has no reference point to measure against"
        elif a.type == "above_usual_density":
            _check_density(a, parsed, frame, tracks, dets, ds)


def _motion_ok(a: Assertion, t: Track, cap: int, ds: Dataset) -> tuple[bool, str]:
    """Does one track behave as the assertion claims? Returns (ok, detail)."""
    if a.type == "stationary":
        window = int(a.value.split()[0])
        drift = max(p.dist_m(t.end.pos) for p in _window(t, cap - window, cap))
        return drift <= STATIONARY_MAX_M, f"{t.track_id} drifted {drift:.0f} m in the last {window} min"
    if a.type == "moving":
        path = _path_m(_window(t, cap - 30, cap))
        return path >= MOVING_MIN_M, f"{t.track_id} moved {path:.0f} m in the last 30 min"
    before = t.position_at(cap - 30) or t.points[0].pos  # toward_base
    closing = before.dist_m(ds.base) - t.end.pos.dist_m(ds.base)
    return closing >= CLOSING_MIN_M, (
        f"{t.track_id} distance to base {before.dist_m(ds.base) / 1000:.1f} -> "
        f"{t.end.pos.dist_m(ds.base) / 1000:.1f} km in the last 30 min"
    )


def _check_group_motion(a: Assertion, group: list[Track], n_claimed: int, cap: int, ds: Dataset) -> None:
    """A claim about N vehicles ("5 kamyonun durdugu", "3 araclik konvoy").

    Tracks carry no type and frames are dense (median nearest-neighbour 17 m), so we cannot tell
    which N of the nearby tracks the report means. Instead: supported when at least N-1 of the
    tracks within GROUP_M behave as claimed (+-1 tolerance, as for counts); contradicted when none
    do. In between, a stationary claim stays unverifiable (parked vehicles may have no track), while
    a moving claim is contradicted (moving vehicles always leave a track).
    """
    results = [(t, *_motion_ok(a, t, cap, ds)) for t in group]
    ok = [(t, d) for t, good, d in results if good]
    need = max(1, n_claimed - 1)
    summary = f"{len(ok)} of {len(group)} track(s) within {GROUP_M:.0f} m fit, claim is {n_claimed}"
    if len(ok) >= need:
        a.status = "supported"
        a.evidence = [f"TRK-{t.track_id}" for t, _ in ok]
        a.how = f"{summary}: " + "; ".join(d for _, d in ok)
    elif not ok or a.type != "stationary":
        a.status = "contradicted"
        a.evidence = [f"TRK-{t.track_id}" for t, _, _ in results]
        a.how = f"{summary}: " + "; ".join(d for _, _, d in results)
    else:
        a.evidence = [f"TRK-{t.track_id}" for t, _ in ok]
        a.how = f"{summary}; the rest may be parked vehicles without a track"


def _check_density(
    a: Assertion, parsed: ParsedReport, frame: Frame, tracks: list[Track],
    dets: list[Detection] | None, ds: Dataset,
) -> None:
    if parsed.usual_count is None:
        a.how = "no usual count stated"
        return
    in_frame = [t for t in tracks if frame.contains(t.end.pos, 30)]
    observed = max(len(in_frame), len(dets or []))
    a.status = "supported" if observed > parsed.usual_count else "contradicted"
    a.evidence = [f"TRK-{t.track_id}" for t in in_frame]
    a.how = f"usual {parsed.usual_count}, observed {observed} vehicle(s) in {frame.image_id}"


def _check_area_claims(parsed: ParsedReport, frames: list[Frame], ds: Dataset) -> None:
    if not frames:
        for a in parsed.assertions:
            a.how = f"no frame of {parsed.zone} within {ZONE_WINDOW_MIN} min after the report"
        return
    names = ", ".join(f.image_id for f in frames)
    for a in parsed.assertions:
        if a.type == "no_heavy_vehicles":
            if any(f.image_id not in ds.detections for f in frames):
                a.how = f"needs detections for {names}"
                continue
            heavy = [d for f in frames for d in ds.detections[f.image_id] if d.label in HEAVY]
            a.status = "contradicted" if heavy else "supported"
            a.evidence = [_det_id(d, ds) for d in heavy]
            a.how = (
                f"{len(heavy)} heavy vehicle(s) detected in {names}" if heavy
                else f"no truck or bus detected in {names}"
            )
        elif a.type == "no_notable_movement":
            closing: list[tuple[str, float]] = []
            for f in frames:
                for t in ds.tracks_ending_at(f.capture_min):
                    before = t.position_at(f.capture_min - 30) or t.points[0].pos
                    c = before.dist_m(ds.base) - t.end.pos.dist_m(ds.base)
                    if c >= NOTABLE_CLOSING_M:
                        closing.append((t.track_id, c))
            a.status = "contradicted" if closing else "supported"
            a.evidence = [f"TRK-{tid}" for tid, _ in closing]
            a.how = (
                "; ".join(f"{tid} closed {c / 1000:.1f} km on the base in 30 min" for tid, c in closing)
                if closing
                else f"no track closed >= {NOTABLE_CLOSING_M / 1000:.0f} km on the base in {names}"
            )


def check_all(ds: Dataset) -> list[CheckedReport]:
    zone_names = [z.name for z in ds.zones]
    return [check_report(parse_report(r, zone_names), ds) for r in ds.reports]
