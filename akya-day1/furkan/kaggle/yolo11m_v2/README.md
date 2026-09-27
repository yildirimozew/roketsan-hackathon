# YOLO11m · scene_holdout_v2 · Tasarım ve Sonuç Notları

> Temel tarif (veri, RFS, azalan augmentation, evaluator) YOLO11s ile aynı: `../yolo11s_v2/README.md`.
> Bu dosya sadece farkları ve sonuçları anlatıyor. Genel proje bağlamı: `furkan/PROJECT_MEMORY.md`.

## 1. 11s'e göre değişenler

| Ayar | 11s | 11m | Neden |
|---|---|---|---|
| Model | yolo11s.pt | **yolo11m.pt** | Ardahan'ın fold 1 sonucu: 11m, 11n'den +9.5 puan; kapasite asıl darboğaz |
| Batch | – | 8 | 2×T4 bellek sınırı |
| `TIME_H` | 5.0 | 5.0 | 51 epoch sığdı (~353 s/epoch) |
| `AUG_FLOOR` | – | 0.6 | 11s'te ~30. epoch'tan sonra cls overfit görüldü; augmentation daha az azalıyor |
| `hsv_v` | azalan | **sabit 0.5** | Karanlık sahneler zayıf; parlaklık çeşitliliği hiç kısılmıyor |
| Tahmin | 1280 | A/B/C/D + NMS taraması | Aşağıda |
| fp16 tahmin | `half` (deprecated) | `quantize=16` | Uyarı spam'i giderildi, fp16 doğrulandı |

## 2. Tahmin yöntemleri

- **A:** 1280, düz tahmin.
- **B:** 1536, düz tahmin.
- **C:** TTA@1536. Ultralytics TTA ölçekleri küçülterek çalışıyor (1.0 / 0.83 / 0.67), bu yüzden 1536'dan başlatılıyor.
- **D:** SAHI. 800 px tile'lar 1280'de tahmin ediliyor, tam görüntü tahminiyle birleştiriliyor. Owner filter + batched NMS 0.6.
- **Post-hoc NMS taraması:** 0.50–0.70.

Tüm tahminler: conf=0.001, max_det=1000.

## 3. Sonuçlar

Yarışma metriği, `scene_holdout_v2` val, test ağırlıklı mAP@0.5.

| Ağırlık · yöntem | TW mAP | dark |
|---|---|---|
| last.pt · A | 0.7447 | |
| best.pt · A | 0.7566 | 0.640 |
| best.pt · B | 0.7722 | |
| best.pt · C | 0.7874 | **0.702** |
| best.pt · D | 0.7882 | 0.677 |
| **best.pt · C · NMS 0.6** | **0.7894** | |

Ek değerler:
- Ultralytics best: mAP50 0.800 (car .909, van .713, truck .740, bus .838), mAP50-95 0.584.
- best.pt · A için ağırlıksız mAP 0.7652; 1400×788 alt kümesi 0.783, 1400×788_dark 0.639.
- C ile sınıf bazında: van 0.673, truck 0.743, bus 0.824.
- Confusion matrix: van→car %26, truck→background %19, bus→background %11.

## 4. Yorum

- **Model kapasitesi:** 11s'e göre düz tahminde +2.5, en iyi yöntemle +5.8 puan.
- **TTA:** en büyük kazancı en zayıf yerlerde sağladı, dark alt kümesinde +6.3, van'da +5.5.
- **C ile D:** aradaki 0.001'lik fark gürültü düzeyinde. C seçildi, çünkü dark'ta belirgin şekilde önde (test setinin %45'i karanlık) ve daha basit.
- **NMS 0.6:** +0.2 puan, o da gürültü sınırında. Zararı yok.
- **Overfit:** best ile last arasında −1.2 puan fark var ve val cls loss ~35. epoch'tan sonra hafif yükseliyor. 11s'e göre daha hafif. best.pt kullanılıyor.
- **Kalan puanlar:** van↔car ayrımı, kaçırılan truck/bus'lar ve dark sahneler.

## 5. Çıktılar

| Dosya | İçerik |
|---|---|
| `submission.csv` | best.pt · C · NMS 0.6, 405,582 kutu, 1 `none` |
| `submission_<ağırlık>_<yöntem>_nms<eşik>.csv` | Tüm varyantlar. Yedek: A @ 0.7 (324,965 kutu) |
| `preds_val_*.csv`, `preds_test_*.csv` | Ham tahminler |
| `scores.json` | `method_scores`, `nms_sweep`, `aug_floor`, `hsv_v` |

## 6. Kaggle

- Public LB: _gönderince buraya yaz_
- Beklenti: 11s'teki val→LB farkı (−9) sürerse ~0.70. Teşhis planı için `PROJECT_MEMORY.md` Bölüm 7'ye bak.
