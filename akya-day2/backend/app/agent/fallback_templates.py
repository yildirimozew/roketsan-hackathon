"""User-facing sentence templates for the deterministic fallback (no LLM).

This file and LLM output are the only backend places allowed to hold Turkish text: the fallback
brief replaces LLM output, so it follows `BRIEF_LANGUAGE` (root CLAUDE.md, Language).
"""

from typing import Literal

Lang = Literal["tr", "en"]

VEHICLE = {
    "tr": {"car": "otomobil", "van": "panelvan", "truck": "kamyon", "bus": "otobüs"},
    "en": {"car": "car", "van": "van", "truck": "truck", "bus": "bus"},
}

T: dict[Lang, dict[str, str]] = {
    "tr": {
        "headline_none": "Karede araç tespit edilmedi",
        "headline": "{n} araç; en riskli {vehicle} üsse {km} km, {trend}",
        "trend_closing": "yaklaşıyor",
        "trend_leaving": "uzaklaşıyor",
        "trend_static": "sabit",
        "summary_none": "Kendi tespitimizde araç yok; raporlar tek başına risk artırmadı.",
        "vehicle_line": "{vehicle} ({track}) üsse {km} km; puan {score}/100.",
        "vehicle_line_eta": "{vehicle} ({track}) üsse {km} km, tahmini varış ≈ {eta} dk; "
        "puan {score}/100.",
        "vehicle_untracked": "{vehicle} iz kaydıyla eşleşmedi; geçmişi bilinmiyor.",
        "motion": "{track} son 60 dakikada {d60} km'den {dnow} km'ye {verb}.",
        "motion_close": "yaklaştı",
        "motion_away": "uzaklaştı",
        "stops": "{n} uzun duraklama ({detail}).",
        "report_note": "{rid} ({source}, {time}): {verdict} — {reason}",
        "u_oblique": "Kare tam nadir olmayabilir; köşe koordinatlarıyla doğrusal eşleme "
        "varsayıldı.",
        "u_unmatched": "{ids} iz kaydıyla eşleşmedi; hareket geçmişi yok.",
        "u_fallback": "LLM kullanılamadı; brifing kural tabanlı şablondan üretildi.",
        "v_CORROBORATED": "DOĞRULANDI",
        "v_CONTRADICTED": "ÇELİŞİYOR",
        "v_UNVERIFIED": "DOĞRULANAMADI",
        "v_IRRELEVANT": "İLGİSİZ",
        "r_corroborated": "konum ve tip kendi tespitimizle uyumlu.",
        "r_contradicted": "iddia kendi verimizle çelişiyor ({what}); puanlamada kullanılmadı.",
        "r_lowering": "tehdidi düşüren iddia kendi verimizle doğrulanamıyor; risk düşürülmedi.",
        "r_instructions": "metin sisteme talimat içeriyor; yalnızca veri olarak ele alındı, "
        "dikkate alınmadı.",
        "r_unverified": "iddiayı doğrulayacak ya da çürütecek yeterli veri yok.",
        "c_location": "konum",
        "c_presence": "rapor saatinde iz",
        "c_type": "tip",
        "c_activity": "hareket durumu",
        "c_instructions": "talimat",
    },
    "en": {
        "headline_none": "No vehicles detected in frame",
        "headline": "{n} vehicle(s); riskiest {vehicle} {km} km from base, {trend}",
        "trend_closing": "closing",
        "trend_leaving": "moving away",
        "trend_static": "stationary",
        "summary_none": "No vehicles in our own detection; reports alone did not raise risk.",
        "vehicle_line": "{vehicle} ({track}) {km} km from base; score {score}/100.",
        "vehicle_line_eta": "{vehicle} ({track}) {km} km from base, ETA ≈ {eta} min; "
        "score {score}/100.",
        "vehicle_untracked": "{vehicle} did not match any track; history unknown.",
        "motion": "{track} went from {d60} km to {dnow} km over the last 60 min ({verb}).",
        "motion_close": "closing",
        "motion_away": "moving away",
        "stops": "{n} long stop(s) ({detail}).",
        "report_note": "{rid} ({source}, {time}): {verdict} — {reason}",
        "u_oblique": "Frame may be oblique; linear corner mapping assumed.",
        "u_unmatched": "{ids} did not match any track; no motion history.",
        "u_fallback": "LLM unavailable; brief generated from the rule-based template.",
        "v_CORROBORATED": "CORROBORATED",
        "v_CONTRADICTED": "CONTRADICTED",
        "v_UNVERIFIED": "UNVERIFIED",
        "v_IRRELEVANT": "IRRELEVANT",
        "r_corroborated": "location and type agree with our detection.",
        "r_contradicted": "claim contradicts our data ({what}); ignored for scoring.",
        "r_lowering": "threat-lowering claim cannot be verified; risk not lowered.",
        "r_instructions": "text contains instructions to the system; treated as data only.",
        "r_unverified": "not enough data to confirm or refute.",
        "c_location": "location",
        "c_presence": "track at report time",
        "c_type": "type",
        "c_activity": "activity",
        "c_instructions": "instructions",
    },
}


def km(meters: float, lang: Lang) -> str:
    """Kilometers with one decimal, locale-style separator."""
    text = f"{meters / 1000:.1f}"
    return text.replace(".", ",") if lang == "tr" else text


OPERATOR_FALLBACK: dict[Lang, str] = {
    "tr": "Mesajınızı aldım, ancak şu an işleyemedim; lütfen birazdan tekrar yazın.",
    "en": "Message received, but I could not act on it now; please write again shortly.",
}
OPERATOR_DONE: dict[Lang, dict[str, str]] = {
    "tr": {
        "watcher": "{wid} oluşturuldu; {sector} bölgesini bu tikten itibaren her tik kontrol "
        "edecek, diğer gözcüler bu sektörü artık atlıyor.",
        "expected": "{eid} kaydedildi: {sector} üzerinden {start}–{end} arasında gelecek araç. "
        "Göründüğünde LOW tutulacak, tehdit olarak işaretlenmeyecek.",
    },
    "en": {
        "watcher": "{wid} created; it checks {sector} every tick from this tick on, and the other "
        "watchers now skip that sector.",
        "expected": "{eid} registered: the vehicle coming through {sector} between {start} and "
        "{end}. Once it appears it is kept LOW, not marked as a threat.",
    },
}
PLACES_TR = {
    "Kuzey Yolu": "Kuzey Yolu",
    "Kuzeydogu Kavsagi": "Kuzeydoğu Kavşağı",
    "Dogu Yolu": "Doğu Yolu",
    "Guneydogu Yerlesimi": "Güneydoğu Yerleşimi",
    "Guney Kapisi Yaklasimi": "Güney Kapısı Yaklaşımı",
    "Guneybati Yolu": "Güneybatı Yolu",
    "Bati Yerlesimi": "Batı Yerleşimi",
    "Kuzeybati Yolu": "Kuzeybatı Yolu",
}


def operator_fallback(lang: Lang, done: list[dict[str, str]] | None = None) -> str:
    """The supervisor's reply to the operator without the LLM's own words: what its tools did
    (`done`: {"kind": "watcher" | "expected", ...fields}), or that nothing was done."""
    if not done:
        return OPERATOR_FALLBACK[lang]
    place = PLACES_TR if lang == "tr" else {}
    return " ".join(
        OPERATOR_DONE[lang][d["kind"]].format(
            **(d | {"sector": place.get(d["sector"], d["sector"])})
        )
        for d in done
    )
