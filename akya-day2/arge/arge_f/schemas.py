"""
Aşama 2 · Araç sözleşmeleri (tool I/O şemaları)
================================================
Tek doğruluk kaynağı: araçların girdi/çıktı yapıları, kanıt kaydı, final karar,
koruma (guard) ve kırmızı takım çıktıları, arayüz olayları.

Kurallar
- Alan adları İngilizce, açıklamalar Türkçe (LLM'e giden tool tanımı `description`'lardan üretilir).
- Her araç çıktısı `ToolResult`'tan türer: status + evidence_ids + notes.
- Her sayısal değer blackboard'da bir kanıt ID'siyle (E\\d+) saklanır; brief'teki her sayı buna dayanmalı.
- LLM'e giden çıktı: `model_dump(exclude_none=True)` (kısa JSON).
- ID biçimleri: görüntü img_000860 · tespit D1 · track T0122 · rapor R017 (dosya sırası, 1'den) · kanıt E12.

Çalıştır:  python schemas.py   → tüm tool JSON şemalarını tools_schema.json'a yazar.
"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Ortak tipler
# ---------------------------------------------------------------------------
EvidenceId = str      # "E12"
DetId = str           # "D3"
TrackId = str         # "T0122"
ReportId = str        # "R017"
HHMM = str            # "14:10"


class Status(str, Enum):
    ok = "ok"
    low_confidence = "low_confidence"   # sonuç var ama güven düşük
    unknown = "unknown"                 # "bilmiyorum": karar verecek kanıt yok
    failed = "failed"                   # araç çalışmadı → yedek davranış


class LatLon(BaseModel):
    lat: float
    lon: float


class BBoxPx(BaseModel):
    x: float = Field(description="Sol üst köşe x (px)")
    y: float = Field(description="Sol üst köşe y (px)")
    w: float
    h: float


class SuperClass(str, Enum):
    light = "light"       # car + van
    heavy = "heavy"       # truck + bus
    unknown = "unknown"   # hiçbir sınıfa yeterince yakın değil (open-set)


class Level(str, Enum):
    DUSUK = "DUSUK"
    IZLE = "IZLE"
    DIKKAT = "DIKKAT"
    KRITIK = "KRITIK"
    BELIRSIZ = "BELIRSIZ"   # kanıt karar için yetersiz (çekimser)


class ToolResult(BaseModel):
    status: Status = Status.ok
    evidence_ids: list[EvidenceId] = Field(default_factory=list,
                                           description="Bu çağrının blackboard'a yazdığı kanıtlar")
    notes: list[str] = Field(default_factory=list, description="Kısa uyarılar, bozulma nedenleri")


class Evidence(BaseModel):
    """Blackboard kaydı. Yalnızca eklenir; değişiklik = yeni sürüm (supersedes)."""
    id: EvidenceId
    image_id: str
    tool: str
    kind: str = Field(description="ör. detection, geo, track_match, motion, report, advice")
    subject: Optional[str] = Field(None, description="D3 / T0122 / R017 ...")
    value: dict
    confidence: Optional[float] = None
    supersedes: Optional[EvidenceId] = None
    created_at: str


# ---------------------------------------------------------------------------
# 1 · open_image
# ---------------------------------------------------------------------------
class OpenImageIn(BaseModel):
    image_id: str


class Corners(BaseModel):
    top_left: LatLon
    top_right: LatLon
    bottom_left: LatLon
    bottom_right: LatLon


class Stratum(BaseModel):
    resolution: str = Field(description="ör. 1360x765")
    mean_brightness: float = Field(description="0-255 ortalama parlaklık")
    is_dark: bool


class DetectorReportCard(BaseModel):
    """Aşama 1 val sonuçlarından bu katmanda dedektörün karnesi."""
    stratum_key: str
    map50: float
    ap50_per_class: dict[Literal["car", "van", "truck", "bus"], float]
    n_val: int = Field(description="Katmandaki val görüntü sayısı")
    shrunk: bool = Field(description="Az örnek → genel ortalamaya çekildi mi (empirical Bayes)")
    shrink_k: Optional[float] = Field(None, description="AP = (n·AP_katman + k·AP_genel)/(n+k)")
    source: str = "scene_holdout_v2 val_strata"


class TrackBundle(BaseModel):
    """Çekim saatinde biten track'ler: bu karenin iş dosyası (kare başına 3-10)."""
    track_ids: list[TrackId]
    inside_frame_ids: list[TrackId] = Field(description="Çekim anında kare sınırı içinde olanlar")
    n_total: int
    n_inside: int = Field(description="Beklenen hareketli araç sayısı (tespit kontrolü için)")


class IntegrityCheck(BaseModel):
    name: Literal["file_exists", "size_matches_meta", "corners_axis_aligned",
                  "square_pixels", "time_format"]
    passed: bool
    value: Optional[str] = Field(None, description="ör. gsd_x/gsd_y=0.994")


class OODFlag(BaseModel):
    """Aynı çözünürlükteki Aşama 1 dağılımına göre sapma."""
    reference: str = Field(description="ör. '1920x1080, n=67'")
    z_brightness: float
    z_contrast: float
    blur_laplacian_var: Optional[float] = None
    overexposed_ratio: Optional[float] = Field(None, description="≥250 piksel oranı")
    flag: bool = Field(description="|z| > 2 veya kalite eşiği aşıldı")
    reason: Optional[str] = None


class OpenImageOut(ToolResult):
    image_id: str
    width_px: int
    height_px: int
    capture_time: HHMM
    corners: Corners
    stratum: Stratum
    integrity_checks: list[IntegrityCheck]
    track_bundle: TrackBundle
    reports_in_window: int = Field(description="Zaman penceresindeki rapor sayısı (konumdan bağımsız)")
    ood: Optional[OODFlag] = Field(None, description="Piksel istatistiği; görüntü modeli kullanılmaz")


# ---------------------------------------------------------------------------
# 2 · place_on_map
# ---------------------------------------------------------------------------
class PlaceOnMapIn(BaseModel):
    image_id: str


class ZoneRef(BaseModel):
    name: str
    distance_to_center_km: float


class Sector(BaseModel):
    """Üsse göre yön dilimi. 8 bölge = 8 pusula yönü (45°, ±22.5°)."""
    name: str = Field(description="zones.json adı, ör. 'Dogu Yolu'")
    index: int = Field(description="0=Kuzey … 7=Kuzeybati, saat yönü")
    bearing_from_base_deg: float = Field(description="Üsten kareye yön, 0=kuzey")


class Ring(BaseModel):
    """Üsse uzaklık halkası; veride 5 halka (~1.7/2.6/3.5/4.4/5.3 km)."""
    index: int = Field(description="1=en iç … 5=en dış")
    distance_km: float


class SectorSibling(BaseModel):
    image_id: str
    capture_time: HHMM
    ring: int


class PlaceOnMapOut(ToolResult):
    center: LatLon
    footprint_m: tuple[float, float] = Field(description="(genişlik, yükseklik) metre")
    footprint_polygon: list[LatLon] = Field(description="Kapsama alanı köşeleri (TL, TR, BR, BL)")
    gsd_m_per_px: tuple[float, float] = Field(description="(x, y) piksel başına metre")
    sector: Sector
    ring: Ring
    nearest_zone_center: ZoneRef = Field(description="Yalnız rapor eşleme için; bölge kararı sector'dan")
    base_distance_km: float
    base_bearing_deg: float = Field(description="Kareden üsse yön, 0=kuzey")
    base_facing_edge: Literal["top", "right", "bottom", "left", "top_right", "bottom_right",
                              "bottom_left", "top_left"]
    min_detectable_area_m2: float = Field(description="200 px² eşiğinin yerdeki karşılığı (kör nokta)")
    sector_siblings: list[SectorSibling] = Field(default_factory=list,
                                                 description="Aynı yöndeki diğer kareler (gün katmanı)")


# ---------------------------------------------------------------------------
# 3 · detect
# ---------------------------------------------------------------------------
class DetectIn(BaseModel):
    """Görüntü modeli YALNIZCA bu araçta çalışır. Diğer adımlar çıktısını kanıt olarak okur."""
    image_id: str
    min_confidence: float = Field(0.05, description="Aday kutular için alt eşik")
    region_center: Optional[LatLon] = Field(
        None, description="Verilirse bölgesel yeniden tespit (3. adıma dönüş): o nokta çevresinde düşük eşik + SAHI")
    region_radius_m: float = Field(30.0, description="Bölgesel modda yarıçap")
    reason: Optional[str] = Field(None, description="Bölgesel modda zorunlu: ör. 'R042 3 kamyon diyor, tespit 1'")


class Detection(BaseModel):
    det_id: DetId
    evidence_id: EvidenceId
    bbox_px: BBoxPx
    center_px: tuple[float, float]
    area_px: float
    class_probs: dict[Literal["car", "van", "truck", "bus"], float]
    top_class: Literal["car", "van", "truck", "bus"]
    super_class: SuperClass
    class_decision: Literal["fine", "super", "unknown"] = Field(
        description="fine: alt sınıf güvenilir · super: yalnız hafif/ağır · unknown: open-set")
    confidence_raw: float
    confidence_calibrated: float
    ensemble_agreement: Optional[float] = Field(None, description="0-1; modeller arası uyum (IoU×sınıf)")
    state: Literal["candidate", "fact"] = Field(
        description="candidate: düşük güven, doğrulama bekliyor · fact: güvenli veya track ile doğrulandı")
    near_track_id: Optional[TrackId] = Field(None, description="Çekim anındaki en yakın track noktası (kapı içinde)")
    near_blind_threshold: bool = Field(False, description="Alan 200 px² eşiğine yakın → sınıf güvenilmez")
    open_set_score: Optional[float] = Field(None, description="Prototiplere en yüksek kosinüs benzerliği; düşük = sınıf dışı")
    from_local_redetect: bool = Field(False, description="Track noktası çevresinde düşük eşikle bulundu")
    dominant_color: Optional[str] = Field(None, description="Crop'un baskın rengi (rapor renk iddiaları için)")


class DetectOut(ToolResult):
    mode: Literal["full", "region"] = "full"
    region_px: Optional[BBoxPx] = None
    region_conclusion: Optional[Literal["found", "not_found", "unsure"]] = Field(
        None, description="Bölgesel modda: aranan araç bulundu mu")
    report_card: Optional[DetectorReportCard] = Field(
        None, description="Bu kare katmanında dedektörün Aşama 1 karnesi; güvenin ne kadar olduğunu söyler")
    detections: list[Detection]
    counts: dict[str, int] = Field(description="ör. {'fact': 4, 'candidate': 3, 'heavy': 1}")
    expected_from_tracks: int = Field(description="Çekim anında kare içindeki track sayısı")
    prior_hits: int = Field(description="Bir tespitle karşılanan track noktası sayısı")
    local_redetect_ids: list[TrackId] = Field(default_factory=list,
                                              description="Tespitsiz kalıp çevresinde yerel tespit yapılan track'ler")
    track_recall: Optional[float] = Field(None, description="prior_hits / expected_from_tracks")
    model: str = Field(description="ör. yolo11m_ens@1536_tta")


# ---------------------------------------------------------------------------
# 4 · pixel_to_geo
# ---------------------------------------------------------------------------
class PixelToGeoIn(BaseModel):
    image_id: str
    det_ids: Optional[list[DetId]] = Field(None, description="Boşsa tüm tespitler")


class GeoPoint(BaseModel):
    det_id: DetId
    evidence_id: EvidenceId
    position: LatLon
    error_radius_m: float = Field(description="Kutu belirsizliğinin metre karşılığı")
    base_distance_km: float
    method: Literal["linear_corners"] = Field(
        "linear_corners", description="Veri sözleşmesi: kutu merkezi + köşelerden doğrusal oran (track'ler de böyle üretilmiş)")


class PixelToGeoOut(ToolResult):
    points: list[GeoPoint]


# ---------------------------------------------------------------------------
# 5 · find_tracks
# ---------------------------------------------------------------------------
class FindTracksIn(BaseModel):
    image_id: str
    gate_m: float = Field(15.0, description="Eşleşme için en büyük mesafe")


class TrackCandidate(BaseModel):
    track_id: TrackId
    distance_m: float


class TrackMatch(BaseModel):
    det_id: DetId
    evidence_id: EvidenceId
    best: Optional[TrackCandidate] = None
    second: Optional[TrackCandidate] = None
    ratio: Optional[float] = Field(None, description="best/second (Lowe oran testi); küçük = güvenilir")
    status: Literal["matched", "ambiguous", "no_match"]
    promoted_to_fact: bool = Field(False, description="Aday kutu track ile doğrulanıp olguya yükseldi mi")
    pass_no: Literal[1, 2] = Field(1, description="1: olgu kutular · 2: aday kutular (ByteTrack tarzı)")
    gate_m: float = Field(description="Bu eşleşmede kullanılan kapı")
    alternatives: list[TrackCandidate] = Field(default_factory=list,
                                               description="Belirsiz eşleşmede diğer aday track'ler")


class OrphanTrack(BaseModel):
    """Çekim anında hiçbir tespitle eşleşmeyen track."""
    track_id: TrackId
    evidence_id: EvidenceId
    position: LatLon
    position_px: tuple[float, float]
    inside_frame: bool
    edge_distance_m: float = Field(0.0, description="Kare dışındaysa kenara uzaklık")
    hypothesis: Literal["missed", "blind_spot", "outside_near_edge"] = Field(
        description="missed → bölgesel detect önerilir · blind_spot → kör nokta alanı · outside_near_edge → görüş alanı dışı")


class UnmatchedDetection(BaseModel):
    """Track'i olmayan tespit."""
    det_id: DetId
    evidence_id: EvidenceId
    hypothesis: Literal["parked_likely", "false_positive_likely", "unknown"]
    reason: str


class FindTracksOut(ToolResult):
    capture_time: HHMM
    tracks_at_time: int = Field(description="time == çekim saati olan track sayısı (kare içi+dışı)")
    matches: list[TrackMatch]
    orphan_tracks: list[OrphanTrack]
    unmatched_detections: list[UnmatchedDetection] = Field(default_factory=list)
    method: Literal["hungarian_two_pass"] = "hungarian_two_pass"


# ---------------------------------------------------------------------------
# 6 · analyze_motion
# ---------------------------------------------------------------------------
class AnalyzeMotionIn(BaseModel):
    track_ids: list[TrackId]


class Dwell(BaseModel):
    start: HHMM
    end: HHMM
    duration_min: int
    position: LatLon


class Anomaly(BaseModel):
    time: HHMM
    type: Literal["impossible_speed", "position_jump", "reverse_jump"]
    value: float


class Motion(BaseModel):
    track_id: TrackId
    evidence_id: EvidenceId
    window: tuple[HHMM, HHMM]
    n_points: int
    path_length_km: float
    net_displacement_km: float
    speed_mean_mps: float
    speed_last_10min_mps: float
    speed_max_mps: float
    heading_deg: Optional[float] = Field(None, description="Son yarım saatteki genel yön; duruyorsa None")
    base_distance_km: dict[Literal["start", "min", "end"], float]
    base_distance_series: list[tuple[HHMM, float]] = Field(description="Arayüz grafiği için")
    trend: Literal["approaching", "receding", "stable", "circling"]
    approach_rate_mps: float = Field(description="Pozitif = üsse yaklaşıyor (radyal hız)")
    noise_floor_m: float = Field(5.0, description="Bu değerin altındaki 5 dk adımlar durak sayılır")
    moving_share: float = Field(description="Hareketli adımların oranı (0-1)")
    sweep_deg: float = Field(description="Üs etrafında toplam açısal tarama (derece)")
    closest_ever_km: float = Field(description="2 saat içinde üsse en yakın mesafe")
    closest_ever_time: HHMM
    population_percentiles: dict[str, float] = Field(
        description="226 track'e göre yüzdelik: approach_rate, closest_ever, sweep, dwell_near_base, moving_share")
    eta_min_if_moving: Optional[tuple[float, float]] = Field(
        None, description="Son hareketli segment hızıyla üsse varış süresi aralığı (dk)")
    state_now: Literal["moving", "stopped", "parked"] = Field(description="Ortak hareket sözlüğü (raporlarla aynı)")
    dwells: list[Dwell]
    anomalies: list[Anomaly]
    behavior_tags: list[Literal["approaching", "loitering", "circling", "waiting", "stop_and_go",
                                "transit", "leaving"]]


class AnalyzeMotionOut(ToolResult):
    motions: list[Motion]


# ---------------------------------------------------------------------------
# 7 · search_reports
# ---------------------------------------------------------------------------
class SearchReportsIn(BaseModel):
    image_id: str
    time_window_min: int = Field(150, description="Çekim saatinden geriye bakılacak süre")
    radius_m: float = Field(500.0, description="Kare çevresinde arama yarıçapı")
    include_general: bool = Field(True, description="Konumsuz genel raporlar (tatbikat, hava...) dahil mi")


class ParsedClaim(BaseModel):
    kind: Literal["sighting", "friendly_claim", "all_clear", "unverified_tip", "irrelevant", "unknown"]
    location_type: Literal["coord", "zone", "none"]
    position: Optional[LatLon] = None
    zone_name: Optional[str] = None
    zone_edit_distance: Optional[int] = Field(None, description="Bölge adı fuzzy eşleme mesafesi")
    vehicle_text: Optional[str] = Field(None, description="Metindeki ifade: 'kamyon', 'agir arac'...")
    super_class: Optional[SuperClass] = None
    count: Optional[int] = None
    color: Optional[str] = None
    motion: Optional[Literal["moving", "stopped", "parked", "approaching", "leaving", "transit", "normal"]] = None
    direction: Optional[Literal["toward_base", "away", "none"]] = None
    identity_claim: Optional[Literal["friendly", "supply", "patrol"]] = Field(
        None, description="Kimlik beyanı; sensörle doğrulanamaz, riski tek başına düşüremez")
    template_id: Optional[str] = Field(None, description="Kalıp kimliği (regex eşleşmesi)")
    parse_method: Literal["regex", "llm"]


class ReportCheck(BaseModel):
    """Aracın otomatik ön kontrolü. Nihai hüküm agent'ın; bu yalnızca kanıt."""
    coverage: Literal["in_frame", "near_frame", "out_of_coverage", "no_location"]
    distance_to_frame_m: Optional[float] = None
    time_delta_min: int = Field(description="Çekim saati − rapor saati")
    matched_det_ids: list[DetId] = Field(default_factory=list)
    matched_track_ids: list[TrackId] = Field(default_factory=list)
    auto_status: Literal["consistent", "contradicts", "unverifiable"]
    mismatches: list[str] = Field(default_factory=list, description="ör. 'sayı: rapor 3, tespit 1'")


class AtomicClaim(BaseModel):
    """Raporun tek bir doğrulanabilir parçası."""
    type: Literal["existence", "count", "class", "motion", "direction", "identity", "color",
                  "area_status", "context"]
    value: str
    status: Literal["supported", "contradicted", "unverifiable"]
    how: str = Field(description="ör. 'T0182 rapor saatinde 1 m, son 30 dk hareketsiz'")
    evidence: list[EvidenceId] = Field(default_factory=list)


class TrackAtReportTime(BaseModel):
    track_id: TrackId
    distance_m: float
    state_at_report: Literal["moving", "stopped"]
    radial_at_report: Literal["toward_base", "away", "none"]


class Report(BaseModel):
    report_id: ReportId
    evidence_id: EvidenceId
    time: HHMM
    source: Literal["official", "third_party"]
    text: str
    parsed: ParsedClaim
    check: ReportCheck
    linked_image_id: Optional[str] = Field(None, description="Konumu kapsama alanına düşen kare")
    track_at_report_time: Optional[TrackAtReportTime] = None
    claims: list[AtomicClaim] = Field(default_factory=list)
    deception_indicator: bool = Field(False, description="Kimlik beyanının doğrulanabilir kısmı veriyle çelişiyor")


class SourceReliability(BaseModel):
    """Gün boyu doğrulanabilir iddialardan öğrenilen güvenilirlik (Beta-Bernoulli)."""
    source: Literal["official", "third_party"]
    claim_kind: str = Field(description="ör. sighting_stopped, friendly_approaching")
    alpha: float = Field(description="1 + desteklenen")
    beta: float = Field(description="1 + çelişen")
    mean: float


class SearchReportsOut(ToolResult):
    reports: list[Report]
    reliability: list[SourceReliability] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 8 · risk_advisor  (bulanık + DS danışman; karar agent'ta)
# ---------------------------------------------------------------------------
class RiskAdvisorIn(BaseModel):
    image_id: str


class FiredRule(BaseModel):
    rule_id: str
    text: str = Field(description="ör. 'YAKIN ve HIZLI_YAKLAŞIYOR ve AĞIR ise YÜKSEK'")
    strength: float


class DSMass(BaseModel):
    threat: float
    benign: float
    unknown: float = Field(description="Dağıtılamayan kütle: bilinmezlik")
    conflict_k: float = Field(description="Kaynaklar arası çatışma (0-1)")


class VehicleAdvice(BaseModel):
    subject: str = Field(description="D3 veya T0122")
    evidence_id: EvidenceId
    level: Level
    score: float
    fired_rules: list[FiredRule]
    ds: DSMass
    inputs: dict[str, float | str] = Field(description="Kullanılan girdiler: uzaklık, yaklaşma hızı, tcpa, sınıf...")


class Counterfactual(BaseModel):
    """Tek girdi değişince danışman seviyesi (danışman deterministik → ucuz)."""
    subject: str
    change: str = Field(description="ör. 'sweep_deg 441 → 0' veya 'R006 doğru kabul edilirse'")
    level_before: Level
    level_after: Level


class RiskAdvisorOut(ToolResult):
    policy_version: str = Field(description="LEVEL_POLICY sürümü")
    overall_level: Level
    vehicles: list[VehicleAdvice]
    counterfactuals: list[Counterfactual] = Field(default_factory=list)
    robustness: Literal["robust", "sensitive"] = Field(
        description="Belirsiz eşleşme/sınıf alternatiflerinde seviye değişiyor mu")


# ---------------------------------------------------------------------------
# 9 · submit_assessment  (agent'ın final kararı: girdi şeması)
# ---------------------------------------------------------------------------
class VehicleFinding(BaseModel):
    det_id: Optional[DetId] = None
    track_id: Optional[TrackId] = None
    super_class: SuperClass
    fine_class: Optional[Literal["car", "van", "truck", "bus"]] = None
    base_distance_km: Optional[float] = None
    trend: Optional[str] = None
    level: Level
    evidence: list[EvidenceId]


class ReportVerdict(BaseModel):
    report_id: ReportId
    verdict: Literal["supported", "contradicted", "unverifiable", "irrelevant"]
    reason: str
    evidence: list[EvidenceId]


class AdvisorAgreement(BaseModel):
    advisor_level: Level
    agrees: bool
    deviation_reason: Optional[str] = Field(None, description="Uyuşmuyorsa zorunlu, kanıt ID'si içermeli")


class Assessment(BaseModel):
    image_id: str
    level: Level
    vehicles: list[VehicleFinding]
    reports: list[ReportVerdict]
    advisor: AdvisorAgreement
    uncertainties: list[str]
    robustness: Literal["robust", "sensitive"]
    counterfactuals: list[str] = Field(default_factory=list, description="Danışmandan alınan 1-2 karşı-olgusal cümle")
    recommended_action: str = Field(description="Operatör için tek somut eylem; seviyeyle uyumlu (LEVEL_POLICY)")
    brief: str = Field(description="Durum / Gerekçe / Raporlar / Belirsizlik+Eylem; her cümlede [E..]/[R..]/[T..] atfı")


# ---------------------------------------------------------------------------
# Seviye politikası (ekipçe dondurulacak taslak; eşikler popülasyon yüzdeliği)
# ---------------------------------------------------------------------------
LEVEL_POLICY = {
    "version": "v0-taslak",
    "KRITIK": {"action": "Hemen teyit ve müdahale",
               "rule": "(sweep_deg>180 veya closest_ever_km<1) VE ring==1 VE son 30 dk içeri hareket; "
                       "veya ağır araç + iç halkaya yaklaşma + aldatma göstergesi"},
    "DIKKAT": {"action": "Operatöre bildir, sonraki drone geçişinde kontrol",
               "rule": "İki güçlü sinyal (popülasyon üst %10) veya karede aldatma göstergesi"},
    "IZLE":   {"action": "Rutin takip",
               "rule": "Tek sıra dışı sinyal"},
    "DUSUK":  {"action": "İşlem gerekmez", "rule": "Sinyal yok"},
    "BELIRSIZ": {"action": "Ek veri iste (yeniden geçiş / teyit)", "rule": "Kanıt karar için yetersiz"},
    "modifiers": ["Aldatma göstergesi: +1 kademe",
                  "Kimlik beyanı tek başına seviyeyi düşüremez",
                  "Sağlamlık 'sensitive' ise ihtiyatlı (yüksek) seviye"],
}


# ---------------------------------------------------------------------------
# Koruma katmanı ve kırmızı takım
# ---------------------------------------------------------------------------
class GuardCheck(BaseModel):
    name: Literal["schema", "checklist", "grounding", "policy_asymmetric_trust",
                  "advisor_deviation", "budget", "loop"]
    passed: bool
    message: Optional[str] = None


class GuardVerdict(BaseModel):
    ok: bool
    checks: list[GuardCheck]
    feedback: Optional[str] = Field(None, description="Başarısızsa agent'a dönecek düzeltme talimatı")


class Challenge(BaseModel):
    type: Literal["deceptive_report_relied", "ambiguous_match_as_certain",
                  "in_coverage_report_ignored", "unsupported_number", "level_inconsistent", "other"]
    severity: Literal["blocking", "advisory"]
    targets: list[str] = Field(description="İlgili ID'ler")
    text: str


class CriticReview(BaseModel):
    ok: bool = Field(description="Engelleyici itiraz yoksa True")
    challenges: list[Challenge]


# ---------------------------------------------------------------------------
# Sonuç, olay akışı, gün tablosu
# ---------------------------------------------------------------------------
class RunResult(BaseModel):
    assessment: Assessment
    guard: GuardVerdict
    critic: Optional[CriticReview] = None
    mode: Literal["full", "llm_off", "degraded"]
    revisions: int
    llm_calls: int
    cost_usd: float


class UIEvent(BaseModel):
    """Arayüzdeki adım oynatıcısı için; her araç çağrısında bir olay."""
    image_id: str
    seq: int
    step: int = Field(description="1-8 resmi adım; 0 = kontrol (guard/critic)")
    tool: str
    title: str = Field(description="ör. 'Hareket kaydını bul'")
    detail: str = Field(description="ör. 'T0122 · <1 m (ikinci: T0032 · 41 m)'")
    evidence_ids: list[EvidenceId]
    overlay: Optional[dict] = Field(None, description="Çizim: kutular, noktalar, rota")


class DayItem(BaseModel):
    rank: int
    image_id: str
    capture_time: HHMM
    zone: str
    level: Level
    headline: str
    tcpa_min: Optional[float] = None
    cross_checks: list[str] = Field(default_factory=list, description="Başka karelerle çapraz doğrulama notları")


class DaySummary(BaseModel):
    items: list[DayItem]
    shift_brief: str
    stats: dict[str, int]


# ---------------------------------------------------------------------------
# Tool kaydı → LLM tool tanımları
# ---------------------------------------------------------------------------
TOOLS: dict[str, tuple[type[BaseModel], type[BaseModel], str]] = {
    "open_image":        (OpenImageIn, OpenImageOut, "Adım 1 · Görüntü boyutu, çekim saati, köşeler, katman ve dedektör karnesi."),
    "place_on_map":      (PlaceOnMapIn, PlaceOnMapOut, "Adım 2 · Karenin yerdeki alanı, bölgesi, üsse uzaklığı, kör nokta eşiği."),
    "detect":            (DetectIn, DetectOut, "Adım 3 · Araç tespiti (görüntü modelinin tek kullanıldığı yer); hiyerarşik sınıf, "
                                               "kalibre güven, aday/olgu, karne. region_center ile bölgesel yeniden tespit (kare başına en fazla 2)."),
    "pixel_to_geo":      (PixelToGeoIn, PixelToGeoOut, "Adım 4 · Kutu merkezlerini WGS84 koordinata çevirir."),
    "find_tracks":       (FindTracksIn, FindTracksOut, "Adım 5 · Tespitleri çekim anındaki track noktalarıyla eşler; öksüz track'leri verir."),
    "analyze_motion":    (AnalyzeMotionIn, AnalyzeMotionOut, "Adım 6 · 2 saatlik kayıttan hız, yön, duraklama, üsse yaklaşma, CPA/TCPA."),
    "search_reports":    (SearchReportsIn, SearchReportsOut, "Adım 7 · Zaman/konum penceresindeki raporlar, ayrıştırılmış iddialar ve ön kontrol."),
    "risk_advisor":      (RiskAdvisorIn, RiskAdvisorOut, "Adım 8 · Kural tabanlı danışman önerisi (bulanık + DS). Karar sende."),
    "submit_assessment": (Assessment, GuardVerdict, "Final · Değerlendirmeyi gönderir; koruma ve kırmızı takım kontrolünden geçer."),
}


def openai_tools() -> list[dict]:
    return [{"type": "function",
             "function": {"name": n, "description": d, "parameters": i.model_json_schema()}}
            for n, (i, _o, d) in TOOLS.items()]


if __name__ == "__main__":
    import json
    out = {n: {"input": i.model_json_schema(), "output": o.model_json_schema(), "description": d}
           for n, (i, o, d) in TOOLS.items()}
    with open("tools_schema.json", "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"{len(out)} araç şeması yazıldı → tools_schema.json")
