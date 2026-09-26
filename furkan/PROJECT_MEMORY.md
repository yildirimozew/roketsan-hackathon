# Furkan · Proje Hafızası (ROKETSAN LEVEL-UP AI Hackathon)

> Yeni bir Claude oturumu açıldığında **önce bu dosyayı okut.** Son güncelleme: 26 Eylül 2026 sabahı.
> Ayrıntılar: `furkan/kaggle/yolo11s_v2/README.md`, `furkan/kaggle/yolo11m_v2/README.md`, `collective_summary.txt`.

---

## 1. Görev

**Hackathon:** LEVEL-UP AI | ROKETSAN, 25–27 Eylül 2026.

### Aşama 1: Kaggle yarışması
- Drone görüntülerinde **≥200 px²** araçları tespit etmek. Sınıflar: `car`, `van`, `truck`, `bus`.
- Metrik: **mAP@0.5**. Public LB %40, Private LB %60.
- Submission formatı: `image_id,PredictionString`. Her kutu `label conf x y w h` (x,y sol üst köşe). Boş görüntü için `none`.
- Limit: **günde 5, toplam 10 submission**. Kaggle **Cumartesi öğlen** kapanıyor.
- **Submission yalnızca takım hesabından yapılır.** Kural tek takım hesabı; takım dışı bir hesapla yarışmaya katılma.

### Aşama 2: LLM ajanı
Akış: tespit → köşe koordinatlarıyla piksel→GPS dönüşümü → `tracks.csv` ile hareket analizi → `field_reports` doğrulaması → risk brifingi. GLM için $15 kredi var.

---

## 2. Çalışma kuralları (kullanıcı tercihleri + repo)

- **Doğrulanmamış veya varsayıma dayalı değişiklik yapma.** Etkisinden emin olmadığımız şeyi eklemiyoruz.
- **Karar verilmeden kod/script yazma.** Önce planı konuş, onay al, sonra yaz.
- W&B kullanılmıyor. WBF bizim koşularımızda istenmedi.
- Notebook'lar ROKETSAN ekibi için **okunabilir, profesyonel ve bölümlü** olmalı, Run-All ile baştan sona çalışmalı. `%%writefile` ile tek parça script istenmiyor.
- Kısa ve net Türkçe iletişim.
- Repo kuralları:
  - Herkes yalnızca kendi klasöründe çalışır (`furkan/`).
  - Her iş sonrası `collective_summary.txt`'e kısa bir not eklenir.
  - Veri, ağırlık, tahmin ve secret commit edilmez.
  - Branch + PR. Commit'ler Windows'tan (git bash) atılır.
- **VisDrone ile pretrain edilmiş ağırlıklar kullanılmıyor** (test sızıntısı riski). Sadece COCO init.
- Git notu: satır sonu kaynaklı sahte "modified" dosyalar çıkabiliyor. Kontrol ederken `GIT_OPTIONAL_LOCKS=0` ve `core.autocrlf=true` kullan; kalan `index.lock` dosyasını sil.

---

## 3. Takım

Diğer arkadaşların klasörleri: `ardahan/`, `hakan/`, `mustafa/`, `sude/`, `yildirim/`.

- **Hakan:** Ana EDA.
- **Ardahan:**
  - `ardahan/evaluate.py`: yarışma usulü skorlama (pycocotools, eşleşmeyen <200 px² tahminler yok sayılır, maxDets 1000).
  - `ardahan/check_submission.py`: kenarda kırpılıp yüksekliği sıfıra inen kutuları yakalar; bunlar atılmalı.
  - Kaggle YOLO11n 0.656, YOLO11m 0.751 (fold 1).
- **Yıldırım:** RF-DETR Large (tile 704, fixed-split ~0.804), YOLO26 sliced pilotlar, Cascade R-CNN ConvNeXt-T, D-FINE.
  - 3 model WBF ensemble: fold 1'de 0.815.
  - ConvNeXt car/van füzyonu denendi, −0.026 verdiği için reddedildi.

---

## 4. Veri kararları

### EDA ek analizi
Dosyalar: `furkan/notebooks/01b_eda_addendum.ipynb` ve `furkan/val_test_weights.csv`.

- Test setinin **%44'ü 1400×788**, bunların **%45'i karanlık** (64×64 gri ortalaması <55). 1360×765 testin %26'sı.
- 1400×788'de bus oranı %10.6. Testteki bus payı train'in yaklaşık 1.5 katı bekleniyor.
- Perspektif etkisi var: araç boyu görüntünün üstünden altına ×2.4 büyüyor. Bu yüzden **flipud=0**.
- Ultralytics val skoru yarışma metriğinden **~3 puan yüksek** okuyor.

### `splits/scene_holdout_v2`
- v1'in ResNet-18 sahne grupları (cos ≥ 0.90) kullanıldı.
- Her çözünürlük × dark tabakası için testle eşleşecek şekilde MILP ile bölündü. Hiçbir tabakanın %50'sinden fazlası val'e gitmiyor.
- **Val 1295 / train 5176.**
- `val_strata.csv` ağırlıklarıyla (w = p_test/p_val, ESS ~1167) **test ağırlıklı val mAP** hesaplanıyor. Tüm model karşılaştırmaları bu metrikle yapılıyor.

### Eğitim verisi hazırlığı
- Hazırlık: `furkan/src/prepare_yolo.py` → `furkan/outputs/yolo_v2/` (gitignored).
- Kaggle'a private dataset olarak yüklendi: **`roketsan-yolo-v2`** (7 zip parçası, 1.85 GB).

---

## 5. Eğitim tarifi (11s ve 11m ortak)

- Ultralytics 8.4.163, COCO init, Kaggle 2×T4 DDP, imgsz 1280.
- `time` bütçesi kullanılıyor: epoch sayısı ve scheduler bütçeye göre yeniden hesaplanıyor. Optimizer auto → MuSGD, lr 0.01.
- **Repeat Factor Sampling** (LVIS): r_c = max(1, √(0.5/f_c)), stokastik yuvarlama. Tekrarlanan görüntüler hardlink ile `<id>__rfsN` olarak ekleniyor (+492 görüntü).
- **LR'ye bağlı azalan augmentation**, özel `AugDecayTrainer` ile:
  - Her epoch başında transform'lar yeniden kuruluyor.
  - Son 10 epoch'ta mosaic kapatılıyor.
  - DDP subprocess'lerinde ayarlar `AUG_CLOSE_N` ve `AUG_FLOOR` ortam değişkenleriyle aktarılıyor.
- Değerlendirme:
  - Yarışma usulü evaluator: sınıf bazında güven sıralaması, greedy IoU ≥ 0.5, eşleşmeyen <200 px² tahminler yok sayılır, all-point AP.
  - Test ağırlıklı skor ve alt kümeler (1400×788, dark, 1400×788_dark) raporlanıyor.
- Kaggle tuzağı: `/kaggle/input` symlink'li olabiliyor ve `Path.rglob` symlink'lere girmiyor. Dosya taraması için `os.walk(followlinks=True)` kullan.

---

## 6. Sonuçlar

| Model / yöntem | Test ağırlıklı val mAP@0.5 | Kaggle public LB |
|---|---|---|
| YOLO11s best.pt, 1280 | 0.7313 | **0.64** |
| YOLO11m best.pt, A · 1280 | 0.7566 | – |
| YOLO11m B · 1536 | 0.7722 | – |
| YOLO11m C · TTA@1536 | 0.7874 | – |
| YOLO11m D · SAHI (800 tile@1280 + tam görüntü) | 0.7882 | – |
| **YOLO11m C · TTA@1536 · NMS 0.6** | **0.7894** | _gönderilecek / girilecek_ |

YOLO11m ayrıntıları:
- 51 epoch, 5.0 saat. Ultralytics best mAP50 0.800 (car .909, van .713, truck .740, bus .838).
- Yarışma metriğinde last.pt 0.7447, best.pt 0.7566.
- TTA ile dark alt kümesi 0.640'tan **0.702**'ye çıktı. SAHI'de dark 0.677.
- Hatalar: van→car %26, truck→background %19, bus→background %11.
- `submission.csv` = best.pt · C · NMS 0.6, 405,582 kutu.
- Yedek submission: A @ NMS 0.7.

---

## 7. Açık sorun: Val–LB farkı (en önemli belirsizlik)

YOLO11s'te val 0.731 iken LB 0.64 geldi (≈ −9 puan). Aynı fark sürerse 11m TTA için LB beklentisi **~0.70**.

Olası nedenler:
1. Test setinin val'den gerçekten zor olması.
2. Kaggle metriğinin farklı çalışması: maxDets=100 veya küçük kutuların farklı sayılması.
3. Submission hatası (daha az olası).

Teşhis planı:
- 11m submission sonucunu 0.64 ile karşılaştır.
  - ~0.70 gelirse fark sistematik.
  - 0.75+ gelirse 11s submission'ında bir hata vardı.
- Takım arkadaşlarının kendi val ile LB farklarını sor.
- Görüntü başına en fazla 100 kutu (`max_det=100`) içeren bir varyant göndererek maxDets varsayımını test et.
- `ardahan/check_submission.py` ile submission formatını doğrula.

---

## 8. Sıradaki adımlar

1. 11m `submission.csv`'yi **takım hesabından** gönder ve LB sonucunu bu dosyaya yaz.
2. Val–LB farkını teşhis et (Bölüm 7).
3. Kalan submission haklarını değerlendir. Seçenekler:
   - C + D birleşimi
   - Yıldırım'ın RF-DETR / WBF ensemble'ı
4. `collective_summary.txt`'e 11m notunu ekle, branch/PR aç.
5. Aşama 2 (LLM ajanı) hazırlığı. Fikirler: embedding tabanlı open-set ("bilmiyorum"), görünüm eşleştirme.

---

## 9. Dosya haritası (`furkan/`)

| Yol | İçerik |
|---|---|
| `notebooks/01b_eda_addendum.ipynb` | EDA ek analizi |
| `val_test_weights.csv` | Tabaka önem ağırlıkları |
| `src/make_scene_holdout_v2.py`, `src/prepare_yolo.py`, `src/weighted_map.py` | Split üretimi, YOLO veri hazırlığı, ağırlıklı mAP |
| `kaggle/yolo11s_v2/` | 11s notebook'u (`roketsan_yolo11s_v2.ipynb`), `train.py`, tasarım README'si |
| `kaggle/yolo11m_v2/` | 11m notebook'u (`roketsan_yolo11m_v2.ipynb`) + README |
| `outputs/` | Gitignored. yolo_v2 verisi, kaggle_upload zip'leri |
