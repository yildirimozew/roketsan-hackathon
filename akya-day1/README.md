# Roketsan Hackathon — Drone Görüntülerinde Araç Tespiti

Level-Up AI | Roketsan Yapay Zekâ Hackathonu, 1. aşama. Drone görüntülerinde alanı 200 px² ve üzeri olan araçları
tespit edip `car`, `van`, `truck`, `bus` olarak sınıflandırıyoruz. Metrik, dört sınıfın AP ortalaması olan
mAP@0.5.

Veride iki zorluk öne çıkıyor:

- **Küçük nesneler:** Araçların çoğu 32 px'ten küçük.
- **Sınıf dengesizliği:** Otobüsler kutuların %3'ü, kamyonlar %7'si. Buna rağmen her sınıf mAP'nin dörtte biri
  kadar ağırlık taşıyor. Car/van ayrımı da en çok karışan ikili.

## Final çözüm: dört detektörlü ensemble

Kaggle'a gönderdiğimiz modelin eğitimden submission'a kadar tamamı tek bir notebook'ta:
**[`roketsan_ensemble.ipynb`](roketsan_ensemble.ipynb)**.

| Model | Girdi | Neden var | Füzyon ağırlığı |
|---|---|---|---|
| RF-DETR Large + yatay flip TTA | 704 px karo | Transformer (DINOv2 omurga); YOLO'lardan farklı hatalar yapıyor | 1.0 |
| YOLO11m | tam görüntü, 1280 px | Güçlü tam görüntü taban modeli | 0.8 |
| YOLO11m + repeat-factor sampling | tam görüntü, 1280 px | Otobüs/kamyon içeren görüntüleri 3x/2x örnekliyor | 0.6 |
| YOLO26-S-P2 | 704 px karo | Ek P2 (stride 4) başlığıyla küçük nesneler | 0.4 |

Pipeline'ın ana adımları:

1. **Karo tabanlı eğitim:** Küçük araçları küçültmeden görmek için 704 px, %25 örtüşmeli karolar kullanılıyor.
   Nadir sınıfların etrafına ek karolar kesiliyor: %55 van (yanında car olanlar öncelikli), %30 truck, %15 bus.
   Bütün rastgele seçimler sabit anahtarların hash'inden türetildiği için karo kümesi her çalıştırmada aynı.
2. **Karo birleştirme:** Test görüntüsü aynı ızgarayla karolanıyor. Her kutuyu yalnızca merkezine sahip olan karo
   tutuyor, sonra sınıf bazlı NMS uygulanıyor. Böylece karo kenarında kesilen araçlar iki kez sayılmıyor.
3. **İki aşamalı eğitim:** Her model önce `scene_holdout_v2` train kümesinde eğitilip doğrulanıyor. Karo tabanlı
   iki model ardından bütün etiketli verilerle (6.471 görüntü) kısa bir ince ayardan geçiyor.
4. **Kutu füzyonu:** Her görüntü ve sınıf için dört modelin kutuları kümeleniyor (IoU ≥ 0.55, her kümede bir
   modelden en fazla bir kutu). Küme kutusu, skorla ağırlıklı ortalama olarak hesaplanıyor. Birden fazla model aynı
   kutuda anlaşırsa güven skoru yükseltiliyor. Ağırlıklar ve bu yükseltme oranı doğrulama tahminleri üzerinde
   seçildi.

### Doğrulama stratejisi

Rastgele bölmede aynı sahneden kareler train ve val'e dağılıyor ve skoru yapay olarak şişiriyordu. Bu yüzden
bütün model seçimleri [`splits/scene_holdout_v2`](splits/scene_holdout_v2/README.md) üzerinde yapıldı. Bu split'in
özellikleri:

- Görsel olarak benzer sahneler aynı tarafta tutuluyor, sahne grubu ya da birebir kopya sızıntısı yok.
- Val kümesi, test setinin çözünürlük × parlaklık dağılımına göre seçildi (MILP ile).
- Skorlar hem düz mAP@0.5 hem de test dağılımına göre yeniden ağırlıklandırılmış mAP ile raporlanıyor
  (`val_strata.csv`).

Bütün skorlar yarışmanın metriğini birebir uygulayan [`ardahan/evaluate.py`](ardahan/evaluate.py) ile hesaplandı:
pycocotools, eşleşmeyen 200 px² altı tahminler yok sayılıyor, `maxDets 1000`. Ultralytics'in kendi val skoru bu
metriğe göre yaklaşık 3 puan yüksek çıkıyor.

## Kurulum

Bu klasör `roketsan-hackathon` reposunun `akya-day1/` alt klasörü. Aşağıdaki komutlar ve bütün göreli yollar
(`data/`, `splits/`, `work/`, klasör README'leri ve script docstring'lerindeki "repo kökü") `akya-day1/` klasörüne
göre yazıldı.

```bash
cd akya-day1
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install torch==2.10.0 torchvision==0.25.0 --index-url https://download.pytorch.org/whl/cu128
pip install -r requirements.txt
```

Kaggle verisini aşağıdaki yapıyla `akya-day1/data/` klasörüne koyun. Veri Git'e dahil değil.

```text
data/
├── train/
│   ├── annotations.csv        # image_id,x,y,w,h,label
│   └── images/*.jpg
├── test/images/*.jpg
└── sample_submission.csv
```

## Çalıştırma

- **Final submission:** `roketsan_ensemble.ipynb` dosyasını `akya-day1/` klasöründen çalıştırın. Çıktı
  `akya-day1/work/submission.csv` olarak yazılır.
  - Eğitim bölümleri (3–7) birbirinden bağımsız, farklı makinelerde çalıştırılabilir.
  - Tahmin ve füzyon bölümleri (8–9) dört ağırlık dosyasının hepsine ihtiyaç duyar.
- **Bir tahmin dosyasını skorlamak:**

  ```bash
  python ardahan/evaluate.py preds.csv --images splits/scene_holdout_v2/val.txt \
      --weights splits/scene_holdout_v2/val_strata.csv
  ```

- **Submission formatını doğrulamak:**

  ```bash
  python ardahan/check_submission.py work/submission.csv
  ```

## Repo yapısı

| Yol | İçerik |
|---|---|
| `roketsan_ensemble.ipynb` | Final model: dört detektörün eğitimi, test tahmini, füzyon ve submission |
| `splits/` | Ortak train/val manifest'leri: rastgele split, 5 fold, `scene_holdout_v1` ve final `scene_holdout_v2` |
| `ardahan/` | Yarışma metriği ve submission kontrolü; Kaggle YOLO11 koşuları; TTA/WBF, crop sınıflandırıcı, sızıntı analizi |
| `furkan/` | EDA eki (çözünürlük × aydınlık katmanları); `scene_holdout_v2` split'i; test ağırlıklı mAP; YOLO11m/11s Kaggle koşuları ve takım modelleri karşılaştırması |
| `hakan/` | EDA ve uçtan uca Kaggle notebook'u (ensemble'daki YOLO11m) |
| `mustafa/` | Son işleme deneyleri: sınıf hedging, sınıf bazlı eşikler, alan/oran filtreleri, submission formatlayıcı ve testleri |
| `yildirim/` | A100 kümesinde Slurm pipeline'ları: RF-DETR, karo tabanlı YOLO26-S-P2, D-FINE, Cascade R-CNN, ConvNeXt yeniden skorlama |
| `collective_summary.txt` | Takımın deney günlüğü: denenen her şey ve sonucu |

Her takım üyesi kendi klasöründe çalıştı. Klasörlerin README'leri ilgili deneylerin ayrıntılarını içeriyor.
Model ağırlıkları, tahminler ve veri Git'e dahil değil.
