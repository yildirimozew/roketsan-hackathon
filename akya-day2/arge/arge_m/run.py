# ============================================================
# AR-GE ID     : R6 (çalıştırıcı)
# Başlık       : 137 raporun tamamını kontrol edip tablo ve özet yazdırma
# Akış adımı   : 6 – assess_reports (rapor değerlendirme)
# Durum        : test edildi
# Amaç         : Her rapor için kategori, iddia kontrolleri ve Admiralty kodunu tek komutla göstermek.
# Kanıt        : 137 raporun hepsi bir kategoriye atanıyor; 6 rapor çelişiyor.
# Çalıştırma   : arge/ klasöründen: python -m arge_m.run [--quiet] [--detections dosya.json] [--json cikti.json]
# Entegrasyon  : Ana koda taşınmaz; UI'daki rapor inceleme ekranı (R10.1) için örnek veri üretir.
# Sınırlar     : Python ≥ 3.10 gerekir (sistemdeki python 3.9).
# NOT          : Bu dosya bir AR-GE önerisidir; ana koda doğrudan eklenmemiştir.
# ============================================================
"""Print every report with its categories, assertion checks and Admiralty code.

    python -m arge_m.run                         # from arge/
    python -m arge_m.run --detections path.json  # backend PrecomputedDetector format
    python -m arge_m.run --json out.json
"""

import argparse
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .rapor_degerlendirme.admiralty import day_summary, rate_all
from .rapor_degerlendirme.claims import check_all
from .ortak.data import DEFAULT_DATA_DIR, load_dataset


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=DEFAULT_DATA_DIR)
    ap.add_argument("--detections", type=Path, default=None)
    ap.add_argument("--json", type=Path, default=None, help="write the full result as JSON")
    ap.add_argument("--quiet", action="store_true", help="summary only")
    args = ap.parse_args()

    ds = load_dataset(args.data, args.detections)
    checked = check_all(ds)
    ratings = rate_all(checked)

    if not args.quiet:
        for cr, r in zip(checked, ratings):
            p = cr.parsed
            print(f"{r.report_id} {p.report.time} {p.report.source:11} {r.code:3} {cr.status:13} "
                  f"{'/'.join(p.categories):28} {p.report.text}")
            for a in p.assertions:
                print(f"      {a.status:13} {a.type:20} {a.how}")
            print(f"      -> {r.reason}")

    print("\nCategories (primary):", dict(Counter(c.parsed.primary for c in checked)))
    print("Admiralty codes:", dict(sorted(Counter(r.code for r in ratings).items())))
    for s in day_summary(checked):
        rate = f"{s.consistent}/{s.checkable}" if s.checkable else "n/a"
        print(f"{s.source:11} {s.reports:3} reports: held up {rate} of checkable, "
              f"contradicted {s.contradicted}, unverifiable {s.unverifiable}, context {s.not_assessed}")
    deceptive = [cr.report.report_id for cr in checked if cr.deception_indicator]
    print("Identity claims with a contradicted checkable part:", deceptive or "none")

    if args.json:
        payload = [
            {"report": asdict(cr.report), "categories": cr.parsed.categories, "status": cr.status,
             "frames": cr.frame_ids, "deception_indicator": cr.deception_indicator,
             "assertions": [asdict(a) for a in cr.parsed.assertions],
             "admiralty": {"code": r.code, "reason": r.reason}}
            for cr, r in zip(checked, ratings)
        ]
        args.json.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
