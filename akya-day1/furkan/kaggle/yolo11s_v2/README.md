# YOLO11s · scene_holdout_v2 · Tasarım Notları

**Sahibi:** furkan · **Tarih:** 25–26 Eylül 2026 · **Durum:** Kaggle'da eğitildi (2× T4), sonuçlar aşağıda doldurulacak

Bu belge, `roketsan_yolo11s_v2.ipynb` notebook'undaki her kararın **neden** alındığını açıklar.
Kararların çoğu iki EDA'ya dayanır: `hakan/notebooks/01_eda.ipynb` ve `furkan/notebooks/01b_eda_addendum.ipynb`.
Genel ilke: **ölçüme dayanan ayarlar değiştirildi, doğrulanmamış varsayımlar için Ultralytics varsayılanları korundu.**

---

## 1. Dosyalar

| Dosya | Açıklama |
|---|---|
| `roketsan_yolo11s_v2.ipynb` | **Kullanılacak dosya.** Bölümlere ayrılmış, "Run All" ile uçtan uca çalışan Kaggle notebook'u |
| `train.py` | Aynı mantığın tek dosyalık script sürümü (ilk sürüm) |
| `yolo11s_v2_kaggle.ipynb` | `train.py`'yi saran ara sürüm; yerini `roketsan_yolo11s_v2.ipynb` aldı |

Kardeş koşu: `furkan/kaggle/yolo11m_v2/roketsan_yolo11m_v2.ipynb` (aynı tarif, YOLO11m + tahmin deneyleri).

---

## 2. Veri ve doğrulama

- **Split:** `splits/scene_holdout_v2` → 5.176 train / 1.295 val.
  - v1'in sahne grupları korunur (cosine ≥ 0,90 olan görüntüler aynı tarafta; split'ler arası sızma yok).
  - Val, testin **çözünürlük × aydınlatma** dağılımına göre katmanlanmıştır ve her katmanın içinde havuzun sınıf karışımı korunur.
  - v1'de 1400×788 val'inde bus payı %7,3'e düşmüştü (havuz %10,6); v2'de %10,5.
- **Kaggle dataset'i:** `roketsan-yolo-v2` (özel). `furkan/outputs/kaggle_upload/*.zip` parçalarından oluşur; `furkan/src/prepare_yolo.py` ile üretildi.
  - Görseller + YOLO etiketleri (`cls cx cy w h`, normalize), sınıf sırası `car=0, van=1, truck=2, bus=3` (Ardahan'ın `to_yolo.py`'si ile aynı).
  - Arka plan görüntüleri boş etiket dosyasıyla tutulur (290 adet).
- **Test ağırlıklı doğrulama:** Etiketli veride yalnızca 224 karanlık 1400×788 görüntü olduğu için val testi tam taklit edemez.
  Her val görüntüsüne `w = p_test(katman) / p_val(katman)` ağırlığı verilir (katman = çözünürlük × karanlık/aydınlık, karanlık = 64×64 gri ortalama < 55).
  **Model seçimi test ağırlıklı mAP'e göre yapılır.**

---

## 3. Kararlar ve dayanakları

| Karar | Değer | Dayanak |
|---|---|---|
| Model | YOLO11s, COCO ön-eğitimli | 6 GB yerel GPU'ya da sığan hızlı baseline; n (0,656) ve m (0,751) ölçümleri arasında eksik nokta |
| Giriş çözünürlüğü | `imgsz=1280` | EDA: kısa kenarı 16 px'in altına düşen kutular 960'ta %38, 1280'de %20 |
| Dikey çevirme | `flipud=0` | Eğik çekim perspektifi: nesne boyutu görüntünün üstünden altına 2,4 kat artıyor (Spearman ρ = 0,38). Dikey çevirme gerçekte olmayan bir geometri üretir. **Ekibin diğer koşuları `flipud=0.5` kullanıyor.** |
| Yatay çevirme | `fliplr=0.5` | Sol-sağ simetri korunuyor |
| Sınıf dengesizliği | **Repeat Factor Sampling** (t = 0,5) | Kutu payları car %75 · van %14 · truck %7 · bus %3; mAP'te her sınıf %25. Ayrıntı: Bölüm 4 |
| Veri artırımı takvimi | **LR ile azalan**, son 10 epoch mosaic kapalı | Eğitim sonunda gerçek görüntü dağılımına yaklaşmak. Ayrıntı: Bölüm 5 |
| Eğitim süresi | `time=2.5` saat (Ultralytics epoch sayısını ve LR takvimini süreye göre ayarlar) | 03:00'ten önce sonuç almak için |
| LR takvimi | `cos_lr=True`, optimizer `auto` (MuSGD, lr 0,01) | Varsayılan; azalan veri artırımı bu takvime bağlı |
| Early stopping | Kapalı (`patience=1000`) | Süre bütçeli cosine takvimin düşük LR evresi kesilmesin. Aşırı öğrenmeye karşı `last.pt` ve `best.pt` sonda yarışma metriğiyle karşılaştırılır |
| Batch | 16 (GPU başına 8) | T4'lerde GPU başına ~9–11 GB kullanıldı |
| Tahmin | `conf=0.001`, `max_det=1000` | Yarışma kuralı: düşük güvenli kutular cezalandırılmaz; görüntü başına en fazla 218 kutu |

### Bilerek eklenmeyenler

| Fikir | Neden eklenmedi |
|---|---|
| Kayıp fonksiyonunda class weight | Ultralytics'te hazır parametre yok; özel kayıp kodu gözetimsiz gece koşusu için riskli. Ayrıca en zayıf sınıflar van/truck, en nadir sınıf bus değil; frekansın tersiyle ağırlıklandırma yanlış sınıfı güçlendirir |
| "Bazı batch'lerde FPN" | YOLO11'de FPN + PAN her ileri geçişte zaten var; açıp kapatmak train/test uyumsuzluğu yaratır |
| 1400×788 oversampling, `hsv_v` artırımı | Yönleri EDA'dan geliyor ama büyüklükleri tahmin; doğrulanmadan eklenmedi |
| VisDrone ön-eğitimli ağırlıklar | Test verisi büyük ihtimalle VisDrone'dan; test sızması riski |
| P2 head, 1536 eğitim | Bellek/süre riski; Yıldırım A100'de P2 deniyor |
| Copy-paste | Ultralytics'te yalnızca segmentasyon maskeleriyle çalışıyor |

---

## 4. Repeat Factor Sampling (RFS)

Kaynak: Gupta ve ark., *LVIS: A Dataset for Large Vocabulary Instance Segmentation*, CVPR 2019.

```
r_c       = max(1, sqrt(t / f_c))          f_c: sınıfı içeren train görüntülerinin oranı, t = 0.5
r_görüntü = max(r_c, görüntüdeki sınıflar üzerinden)
```

- Kesirli tekrar stokastik yuvarlanır (seed 42). Sonuç: **+492 görüntü tekrarı (+%9,5)** → eğitim listesi 5.668 görüntü.
- Tekrarlar farklı adlı hardlink'lerle (`<id>__rfs1.jpg`) oluşturulur, çünkü Ultralytics aynı dosya yolunu tekilleştirir.
- Kayıp fonksiyonuna dokunmaz, yalnızca eğitim listesini değiştirir (düşük hata riski).
- Bonus: nadir sınıflı görüntüler çoğunlukla testin %44'ünü oluşturan 1400×788 grubundan geldiği için eğitim dağılımını teste de yaklaştırır.

---

## 5. LR'ye bağlı azalan veri artırımı

Ultralytics yalnızca son `close_mosaic` epoch'ta mosaic'i kapatır. Burada fikir sürekli hâle getirildi:

```
faktör(e) = F + (1 − F) · (lf(e) − lrf) / (1 − lrf)        F = 0.3,  lf: cosine LR çarpanı
```

- Etkilenen ayarlar: mosaic olasılığı, `scale`, `translate`, `hsv_h`, `hsv_s`, `hsv_v` (`fliplr` sabit).
- Son 10 epoch mosaic tamamen kapalı.
- Uygulama: `aug_decay.py` içinde `AugDecayTrainer` (DetectionTrainer alt sınıfı). Her epoch başında dataloader'ın transform'ları yeniden kurulur ve `train_loader.reset()` ile worker'lara iletilir (Ultralytics'in `close_mosaic` mekanizmasıyla aynı).
- **DDP notu:** 2× T4'te Ultralytics her GPU için ayrı süreç başlatır ve trainer'ı cloudpickle ile aktarır. Kapanış epoch sayısı `AUG_CLOSE_N` ortam değişkeniyle geçirilir; aksi hâlde alt süreçler sıfırlanmış `close_mosaic` değerini alıp mosaic'i hiç kapatmıyordu (testte yakalanıp düzeltildi).
- Her epoch'un değerleri `runs/y11s_v2/aug_log.jsonl` dosyasına yazılır.

---

## 6. Değerlendirme

- **Yarışma metriği** (notebook'ta `evaluate`): sınıf bazında güvene göre sıralama, IoU ≥ 0,5 açgözlü eşleştirme, eşleşmemiş 200 px² altı tahminler yok sayılır, all-point AP, dört sınıfın ortalaması. Görüntü ağırlıklarını destekler.
- Raporlanan skorlar (`last.pt` ve `best.pt` için): ağırlıksız val, **test ağırlıklı val**, sınıf AP'leri, alt kümeler (`val_1400x788`, `val_dark`, `val_1400x788_dark`).
- Ultralytics'in eğitim sırasındaki mAP50'si yarışma metriğinden ~3 puan yüksek okur (Ardahan'ın ölçümü) ve `best.pt`'yi ağırlıklı olarak mAP50-95'e göre seçer. Bu yüzden karar sondaki yarışma metriğiyle verilir.
- Ardahan'ın `ardahan/evaluate.py`'si (pycocotools) bağımsız doğrulama için kullanılabilir: `python ardahan/evaluate.py preds_val_last.csv --images splits/scene_holdout_v2/val.txt`

---

## 7. Eğitim gidişatı (Ultralytics val, ağırlıksız)

| Epoch | mAP50 | mAP50-95 | Precision | Recall | Not |
|---|---|---|---|---|---|
| 1 | 0,604 | 0,418 | 0,649 | 0,557 | Isınma (LR artıyor) |
| 2–4 | 0,553–0,560 | ~0,38 | | | Isınmada LR yükselince geçici düşüş (beklenen) |
| 7 | 0,646 | 0,446 | 0,675 | 0,609 | Toparlanma, recall artıyor |
| 21 | 0,756 | 0,541 | 0,764 | 0,686 | Orta evrede plato |
| 36 | **0,769** | **0,555** | 0,792 | 0,699 | Tepe noktası |
| 40 | 0,761 | 0,550 | 0,796 | 0,700 | Mosaic kapandı |

Gözlemler:
- Epoch süresi ~3 dk (2× T4); `time=2.5` ile toplam **49 epoch**.
- ~21. epoch'tan sonra kazanç yavaşladı; 36. epoch'tan sonra val düz/hafif aşağı, train kaybı düşmeye devam ediyor → doygunluk, olası hafif aşırı öğrenme (fark gürültü düzeyinde).
- **Precision yükseliyor, recall ~0,70'te takılı:** kaçırılanlar büyük ihtimalle çok küçük araçlar. YOLO11m notebook'undaki 1536 / TTA / SAHI tahmin deneyleri bunu hedefliyor.

---

## 8. Sonuçlar (yarışma metriği)

- 49 epoch (5 saatlik bütçe), Ultralytics val best mAP50 **0.772**.
- Yarışma metriği, best.pt, test ağırlıklı val mAP@0.5: **0.7313** (last.pt daha düşük).
- Zayıf noktalar: dark alt kümesi, van→car karışıklığı. Val cls loss ~30. epoch'tan sonra yükseliyor (sınıflandırma overfit'i).
- **Kaggle public LB: 0.64**, val'den ≈9 puan düşük. Nedeni henüz bilinmiyor (bkz. `furkan/PROJECT_MEMORY.md` → "Val–LB farkı").

Sınıf bazlı değerler notebook çıktısındaki `scores.json` içinde.

---

## 9. Çıktılar (`/kaggle/working`)

| Dosya | İçerik |
|---|---|
| `submission.csv` | Test ağırlıklı val mAP'i yüksek olan ağırlıktan |
| `submission_last.csv`, `submission_best.csv` | İki ağırlığın submission'ları |
| `scores.json` | Yarışma metriğiyle tüm skorlar, RFS parametreleri |
| `history.csv` | Epoch bazında metrikler + epoch süresi + veri artırımı değerleri |
| `preds_val_*.csv`, `preds_test_*.csv` | Ham tahminler (`image_id,label,conf,x,y,w,h`) |
| `runs/y11s_v2/` | `last.pt`, `best.pt`, 5 epoch'luk checkpoint'ler, grafikler, `aug_log.jsonl` |

---

## 10. Çalıştırma

1. Kaggle → Code → New Notebook → **File → Import Notebook** → `roketsan_yolo11s_v2.ipynb`
2. Settings: **Accelerator = GPU T4 ×2**, **Internet = On**; **Add Input** → `roketsan-yolo-v2`
3. **Save Version → Save & Run All (Commit)** (tarayıcı kapansa da çalışır)
4. Süre `TIME_H` ile ayarlanır (Bölüm 1). Kurulum ~3 dk, tahmin ve skorlama ~15 dk eklenir.

Bilinen zararsız uyarılar:
- `ray/train ... get_trial_id ... Returning None`: Kaggle ortamındaki Ray kütüphanesinin Ultralytics callback'i; etkisi yok.
- Tahminde `'half' is deprecated`: bu Ultralytics sürümünde `half` yerine `quantize=16` kullanılıyor; YOLO11m notebook'unda düzeltildi.

Karşılaşılıp düzeltilen sorun: Kaggle dataset'leri `/kaggle/input` altına symlink olarak bağlayabiliyor ve `Path.rglob` symlink'lerin içine girmiyor ("0 dosya birleştirildi" hatası). Veri birleştirme `os.walk(followlinks=True)` kullanacak şekilde düzeltildi.

---

## 11. Sonraki adımlar

- **YOLO11m** (aynı tarif, `TIME_H=5.0`) + tahminde A · 1280 / B · 1536 / C · TTA@1536 / D · SAHI karşılaştırması → `furkan/kaggle/yolo11m_v2/`
- car ↔ van karışıklığı için ikinci aşama kırpıntı sınıflandırıcı (Kaggle sonrası)
- Aşama 2: embedding tabanlı open-set ("bilmiyorum") ve görünüm eşleştirme
