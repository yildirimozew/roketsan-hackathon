# ARGE_M — Mustafa'nın AR-GE bulguları ve önerileri (SENTINEL, Aşama 2)

## 1. Özet

`arge/arge_m/`, SENTINEL ajanı için AR-GE çalışma alanıdır: bulgular, öneriler ve çalışan prototipler.
Kod **`backend/app`'ten bağımsızdır** (yalnızca Python standart kütüphanesi; ana kodu içe aktarmaz,
değiştirmez) ve organizatörün gerçek verisi (`data/`: 40 kare, 226 iz, 137 rapor) üzerinde çalışır.
Ana bulgular:

- **Raporlar aracı karenin çekim anındaki yeriyle anlatıyor, rapor saatiyle değil.** 72 koordinatlı
  raporun 60'ı bir izin son noktasına (çekim anı) 15 m'den yakın; rapor saatindeki konuma yakın olan 17.
  SENTINEL'in rapor kontrolü ve izleme modundaki `get_reports` aracı rapor saatini kullanıyor (R6.5).
- **Resmî "dost araç" raporlarından ikisi hareketle çelişiyor:** REP-61 (T0075 üsten uzaklaşıyor,
  4.1 → 5.3 km) ve REP-113 (T0124 yaklaşmıyor, 3.4 → 3.5 km). Diğer 13 "üsse doğru" iddiası tutuyor (R6.7).
- **Üçüncü taraf raporlar resmî raporlar kadar tuttu:** kontrol edilebilenlerde official 45/50,
  third_party 22/23 (R6.10).
- **Risk puanında ayırt etmeyen faktörler var:** "üs yakınında duraklama" 226 izin 206'sında puan veriyor,
  "< 1 km" kademesi hiç çalışmıyor, üssün etrafında > 270° dolanan 5 iz puan almıyor (R7.1–R7.3).
- **"Ağır araç yok" gibi olumsuz raporlar ana kodda tersine okunuyor** (kamyon görülmesi sanılıyor) (R6.2).

---

## 2. Nasıl okunur / nasıl çalıştırılır

**Okuma:** Bölüm 3 tüm maddelerin özet tablosu; Bölüm 4 her maddenin ayrıntısı (akış sırasıyla);
Bölüm 5 güncel sonuçlar; Bölüm 10 uygulayıcılar için öncelik sırası. Madde kimlikleri `R<adım>.<sıra>`
biçimindedir ve kod dosyalarının başlığındaki `AR-GE ID` ile aynıdır. Furkan'ın notlarında
(`arge/arge_f/STAGE2_DESIGN_NOTES.md`) da geçen fikirler "(bkz. arge_f …)" diye işaretlidir; belge onun
notları gibi adım adım gruplanmıştır.

**Durum etiketleri:** `fikir` = yalnızca yazılı · `prototip` = kod var, kısmen denendi ·
`test edildi` = kod + otomatik test var.

**Çalıştırma** (Python ≥ 3.10 gerekir; sistemdeki `python` 3.9 olduğundan repo dışında ayrı bir ortam
kullanın). `arge/` klasöründen:

```
python -m arge_m.run                          # 137 raporun her biri: kategori, iddia kontrolleri, Admiralty kodu
python -m arge_m.run --quiet                  # yalnızca özet
python -m arge_m.run --json <dosya.json>      # tüm sonuç JSON olarak (arayüz için örnek veri)
python -m arge_m.run --detections <dosya>     # tespit dosyasıyla (backend PrecomputedDetector biçimi)
python -m arge_m.hareket_analizi.hareket      # duruş eşiği ve dolanma ölçümleri
python -m arge_m.risk.kalibrasyon             # risk faktörlerinin gerçek veride devreye girme oranı
python -m arge_m.konumlandirma.konum --out <dosya.geojson>   # GeoJSON çıktısı
python -m pytest arge_m/tests -q              # tüm testler
```

Repoyu kirletmemek için `python -B` ve `pytest -p no:cacheprovider` önerilir.

**Sayıların kaynağı:** Bu belgedeki sayılar tek bir çalıştırmadan alınmıştır (`main` @ `b44cd41`, 62 test
geçti): `run.py`, `risk.kalibrasyon`, `hareket_analizi.hareket` ve aynı `arge_m` koduyla yazılmış salt-okunur
bir ölçüm betiği (repo dışında). Başka kaynaktan gelen birkaç sayı yanında belirtilmiştir.

---

## 3. Özet tablo

| ID | Başlık | Akış adımı | Zorluk | Durum |
|---|---|---|---|---|
| R1.1 | Kare→bölge ataması: iki yöntem 40/40 aynı | 1 load_frame | Kolay | test edildi (değişiklik gerekmez) |
| R2.1 | Ajana özel, sınıf başına güven eşiği | 2 detect | Orta | fikir |
| R2.2 | imgsz 1280 mi 960 mı | 2 detect | Kolay | fikir |
| R2.3 | 40 kare için tespitleri önceden hesaplamak | 2 detect | Kolay | fikir |
| R2.4 | Rapordaki renk iddiası için renk kontrolü | 2 detect | Orta | fikir |
| R3.1 | Görev tanımındaki uçtan uca örnek altın test olarak | 3 georeference | Kolay | test edildi |
| R3.2 | GeoJSON çıktısı, [boylam, enlem] sırası | 3 georeference | Kolay | test edildi |
| R4.1 | Eşleştirme kapısı (25 m) çözünürlüğe göre geniş | 4 match_tracks | Kolay | fikir |
| R4.2 | Eşleşmeyen tespit ve izlerin anlamı | 4 match_tracks | Kolay | fikir |
| R5.1 | "Hareketsiz" eşiği veriden: 100 m | 5 analyze_motion | Kolay | test edildi |
| R5.2 | Üs çevresinde dolanma (açı taraması) | 5 analyze_motion | Kolay | test edildi |
| R5.3 | Hız ve yön izin penceresinden | 5 analyze_motion | Kolay | test edildi |
| R6.1 | Genişletilmiş SALUTE: 7 rapor kategorisi | 6 assess_reports | Orta | test edildi |
| R6.2 | Türkçe anahtar kelime boşlukları ve olumsuzluk | 6 assess_reports | Kolay | test edildi |
| R6.3 | Bağlam / ilgisiz raporlar | 6 assess_reports | Kolay | test edildi |
| R6.4 | Prompt injection'a karşı rapor işleme | 6 assess_reports | Kolay | test edildi |
| R6.5 | Raporu rapor saatinde değil, çekim anında kontrol | 6 assess_reports | Orta | test edildi |
| R6.6 | Çok araçlı iddialar | 6 assess_reports | Kolay | test edildi |
| R6.7 | Kimlik iddiası riski düşürmez; aldatma şüphesi | 6 assess_reports | Kolay | test edildi |
| R6.8 | Yokluk iddiaları bölge izleriyle | 6 assess_reports | Orta | test edildi |
| R6.9 | Yoğunluk iddiası: "olağan 4 araç" | 6 assess_reports | Kolay | test edildi |
| R6.10 | NATO Admiralty kodu (A–F / 1–6) | 6 assess_reports | Orta | test edildi |
| R7.1 | "Üs yakınında duraklama" 206/226 izde puan veriyor | 7 score_risk | Kolay | prototip |
| R7.2 | Dolanmaya risk puanı | 7 score_risk | Kolay | prototip |
| R7.3 | Mesafe kademeleri: < 1 km kademesi hiç çalışmıyor | 7 score_risk | Kolay | prototip |
| R7.4 | Doğrulanan / çelişen raporların puana etkisi | 7 score_risk | Orta | fikir |
| R8.1 | GLM-5.3-Flash entegrasyonu ve 15 USD bütçe | 8 write_brief | Kolay | fikir |
| R8.2 | BLUF + ICD 203 belirsizlik dili | 8 write_brief | Kolay | fikir |
| R8.3 | Sayı ve kimlik uydurmasına karşı doğrulayıcı | 8 write_brief | Orta | fikir |
| R8.4 | Brief'te Admiralty kodu ve SALUTE karşılaştırması | 8 write_brief | Kolay | fikir |
| R9.1 | NATO Sorumlu YZ ilkeleri; operatör onayı | kesişen: güvenlik | Orta | fikir |
| R9.2 | OWASP LLM01/05/09/10 testleri | kesişen: güvenlik | Orta | prototip |
| R10.1 | Rapor inceleme ekranı: SALUTE tablosu + Admiralty | kesişen: arayüz | Orta | fikir |
| R10.2 | Harita sembolleri "bilinmeyen", "düşman" değil | kesişen: arayüz | Kolay | fikir |

---

## 4. Maddeler (ajan akışı sırasıyla)

Sıra `docs/AGENT_DESIGN.md` §3'teki 8 adımlık akıştır: `load_frame → detect → georeference →
match_tracks → analyze_motion → assess_reports → score_risk → write_brief`. İzleme modu
(`docs/AGENT_FLOW.md`, `AGENT_DESIGN.md` §12) aynı servisleri kullandığı için bulgular orada da geçerlidir;
fark olan yerde belirtilmiştir.

### Adım 1 — `load_frame` (klasör: `01_goruntu_meta`)

#### R1.1 – Kare→bölge ataması: en yakın merkez ile kerteriz aynı sonucu veriyor
- **Akıştaki yeri:** 1 load_frame (karenin bölgesi); izleme modunda sektör ataması.
- **Şu anki durum:** `backend/app/data/repository.py:_nearest_zone` ve `services/watch.py:sector_of` en yakın
  bölge merkezini kullanıyor. Furkan'ın notları kerterizi (üsten açı) öneriyor (bkz. arge_f Step 2 #1).
- **Neden gerekli:** Ölçüldü: 40 karenin **40'ında** iki yöntem aynı bölgeyi veriyor (bir karenin en yakın
  bölge merkezine uzaklığı en çok 2421 m olmasına rağmen). Kareler için değişiklik **gerekmez**.
- **Zorluk:** Kolay (0 saat; bilgi amaçlı).
- **Teknik anlatım:** `00_ortak/data.py:_zone_for` kareleri kerterizle atıyor; sonuç backend'inkiyle birebir
  aynı. Fark ancak bölge merkezinden uzaktaki **araç** konumlarında (izleme modu sektörleri) çıkabilir; o
  ayrıca ölçülmedi.
- **Herkesin anlayacağı anlatım:** Her fotoğrafın hangi bölgeye ait olduğunu iki farklı yöntemle
  hesapladık; ikisi de aynı cevabı verdi. Bu konuda bir şeyi düzeltmeye gerek yok.
- **Potansiyel kod:** `00_ortak/data.py:_zone_for`
- **Durum:** test edildi (değişiklik gerekmez)

### Adım 2 — `detect` (klasör: `02_tespit`)

#### R2.1 – Ajana özel, sınıf başına güven eşiği
- **Akıştaki yeri:** 2 detect.
- **Şu anki durum:** `core/config.py: detect_conf_min = 0.35`, tüm sınıflar için tek eşik
  (`services/detection/ultralytics_detector.py`). Kaggle'daki mAP değerlendirmesi çok düşük eşikleri
  (0.001 civarı) ödüllendirir; ajanın ihtiyacı farklıdır.
- **Neden gerekli:** Ajan kutuyu olgu kabul edip rapor çürütüyor ve puan veriyor. Tip hatası asimetrik:
  kamyon 10, otobüs 8, panelvan 5, otomobil 0 puan (`services/risk.py:TYPE_POINTS`). Yanlış bir "truck" hem
  riski yükseltir hem "ağır araç yok" raporunu yanlışlıkla çürütür (R6.8).
- **Zorluk:** Orta (3–4 saat; Aşama-1 doğrulama setinde sınıf başına kesinlik–eşik eğrisi).
- **Teknik anlatım:** Sınıf başına eşik = Aşama-1 val setinde kesinliğin ≥ 0.9 olduğu en düşük güven.
  Eşiğin altındaki kutular "aday" kalır; yanında bir iz noktası varsa olguya yükseltilir (bkz. arge_f Step 3
  #1). Kamyon/otobüs için "ağır" üst sınıfı (bkz. arge_f Step 3 #2); raporlar da "ağır araç" diyor.
- **Herkesin anlayacağı anlatım:** Yarışma puanı için model "belki araçtır" dediği her şeyi söyler. Karar
  veren bir sistem ise emin olmadığını söylememeli; her araç türü için ayrı bir "emin olma" çizgisi öneriyoruz.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

#### R2.2 – imgsz 1280 mi 960 mı
- **Akıştaki yeri:** 2 detect.
- **Şu anki durum:** `detector_imgsz = 960`; config yorumuna göre GTX 1650'de 1280'e göre ~2 kat hızlı ve
  "aynı kutular".
- **Neden gerekli:** Kare boyutları: 19 × 1360×765, 16 × 960×540, 5 × 1920×1080; yer çözünürlüğü
  0.108–0.198 m/piksel. 4.5 m'lik bir otomobil 23–42 piksel eder; 1920 px kare 960'a küçültülünce bu yarıya
  iner. "Aynı kutular" ölçümünün hangi karelerde yapıldığı belli değil.
- **Zorluk:** Kolay (1–2 saat).
- **Teknik anlatım:** 40 kareyi iki boyutla çalıştır; karenin içindeki 206 iz ucunun kaçının 3 m içinde bir
  kutuyla eşleştiğini (iz geri çağırımı, bkz. arge_f Step 3 #3) kare boyutuna göre karşılaştır. Karma seçim
  de olabilir: 1920 px kareler 1280, diğerleri 960.
- **Herkesin anlayacağı anlatım:** Büyük fotoğrafları küçültünce küçük arabalar kaybolabilir. Hız mı doğruluk
  mu daha önemli, gerçek fotoğraflarla ölçmeyi öneriyoruz.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

#### R2.3 – 40 kare için tespitleri önceden hesaplamak
- **Akıştaki yeri:** 2 detect (ve 6'daki tüm tip kontrolleri).
- **Şu anki durum:** `PrecomputedDetector` hazır (`services/detection/precomputed.py`), betik de var
  (`backend/scripts/precompute_detections.py`), ama gerçek veri için bir `detections.json` yok; `/api/health`
  "no precomputed detections" diyor (önceki oturumda kontrol edildi). İzleme modu YOLO'yu canlı çalıştırıyor.
- **Neden gerekli:** Bu çalıştırma tespitsiz: tip iddiaları, 6 "ağır araç yok" raporu ve izi olmayan araç
  iddiaları **doğrulanamaz** kalıyor; bu yüzden en sık Admiralty kodu B3 (57 rapor) ve 25 rapor B6.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** Takımın en iyi ağırlıklarıyla 40 kareyi bir kez çalıştırıp JSON üret (biçim:
  `{image_id: [{label, confidence, bbox:[x,y,w,h]}]}`); `python -m arge_m.run --detections <dosya>` aynı
  dosyayı okur (`00_ortak/data.py:load_detections`).
- **Herkesin anlayacağı anlatım:** Araç tespitini her seferinde yeniden yapmak yerine bir kez yapıp
  kaydedelim. Hem demo hızlanır hem de "raporda kamyon denmiş, gerçekten kamyon mu?" sorusu cevaplanır.
- **Potansiyel kod:** henüz yok (okuma tarafı: `00_ortak/data.py:load_detections`)
- **Durum:** fikir

#### R2.4 – Rapordaki renk iddiası için renk kontrolü
- **Akıştaki yeri:** 2 detect → 6 assess_reports.
- **Şu anki durum:** Renk yalnızca metinden çıkarılıyor (`services/reports.py:_COLORS`), görüntüyle
  karşılaştırılmıyor. AR-GE denetleyicisinde renk iddiası her zaman "doğrulanamaz".
- **Neden gerekli:** 137 raporun **8'inde** renk var (REP-09, 22, 23, 46, 106, 110, 123, 125); REP-46,
  REP-123 ve REP-125 "dost devriye" kimlik raporu. Renk, kimlik raporlarının görüntüden kontrol edilebilen
  tek parçası.
- **Zorluk:** Orta (3–5 saat).
- **Teknik anlatım:** Kutunun ortasında HSV baskın renk (gölge/yol pikselleri hariç). Belirsizse ikinci görüş
  olarak GLM'e yalnızca kırpılmış kutu gönderilir; görev tanımına göre 960×540 bir görüntü ~700, 1920×1080
  ~2.700 girdi token'ı tutar ve `reasoning_effort="low"` ile cevap ~10–15 s'de gelir, yani yalnızca birkaç
  rapor için kullanılmalı. Sonuç `color` iddiasını desteklendi/çelişiyor yapar; kimlik yine doğrulanamaz (R6.7).
- **Herkesin anlayacağı anlatım:** Rapor "mavi araç" diyorsa fotoğraftaki araç gerçekten mavi mi, bakabiliriz.
  Bu, aracın kim olduğunu kanıtlamaz ama raporun tutarlı olup olmadığını gösterir.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

### Adım 3 — `georeference` (klasör: `03_konumlandirma`)

#### R3.1 – Görev tanımındaki uçtan uca örnek altın test olarak
- **Akıştaki yeri:** 3 georeference.
- **Şu anki durum:** `backend/tests/test_golden_img_000860.py` sunum slaydındaki örneği (img_000860 → T0122)
  test ediyor; görev tanımındaki (PDF) ikinci örnek test edilmiyor.
- **Neden gerekli:** Görev tanımı örneği: 1360×765 kare, kutu (610, 380, 60, 28) → merkez (640, 394) →
  (39.94439, 32.86350); T0187 ≈ 2,5 m. Farklı kare boyutu ve köşelerle formülün ikinci, bağımsız kontrolü.
  `img_000123` gerçek veride yok (örnek "temsilidir"), bu yüzden köşeler elle verilir.
- **Zorluk:** Kolay (0.5 saat).
- **Teknik anlatım:** `konum.pixel_to_latlon` görev tanımındaki formülü birebir uygular
  (`boylam = SolÜst.boylam + x/genişlik × (SağÜst.boylam − SolÜst.boylam)`, `enlem = SolÜst.enlem +
  y/yükseklik × (SolAlt.enlem − SolÜst.enlem)`). Test 5e-6 derece toleransla geçiyor ve T0187 noktasına
  2–3.5 m uzaklığı doğruluyor. Gerçek veride img_000860 → (39.92531, 32.87183), T0122 < 1 m testi de var
  (`test_real_data.py`) (bkz. arge_f Step 4 #1).
- **Herkesin anlayacağı anlatım:** Organizatörün kendi çözdüğü örneği kodumuza da çözdürüyor ve aynı cevabı
  aldığımızı otomatik kontrol ediyoruz.
- **Potansiyel kod:** `03_konumlandirma/konum.py:pixel_to_latlon`; test: `tests/test_konum.py`
- **Durum:** test edildi

#### R3.2 – GeoJSON çıktısı, [boylam, enlem] sırası
- **Akıştaki yeri:** 3 georeference → arayüz haritası.
- **Şu anki durum:** API kendi JSON biçimini (`LatLon{lat, lon}`) kullanıyor; GeoJSON yok.
- **Neden gerekli:** Organizatör verisi `[enlem, boylam]`, GeoJSON (RFC 7946) `[boylam, enlem]` kullanır.
  Sıra karışırsa noktalar başka yere düşer. Standart biçim Leaflet ve QGIS'te doğrudan açılır.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** `to_geojson` üs, 8 bölge, 40 kare poligonu, 226 iz çizgisi ve 72 konumlu raporu tek
  FeatureCollection'da verir; test eksen sırasını, sayıları ve halkanın kapalı olduğunu doğrular. Backend'de
  `/api/scene.geojson` olarak sunulabilir.
- **Herkesin anlayacağı anlatım:** Harita verisini her harita programının tanıdığı standart bir biçimde de
  verelim; verimizi başka araçlarda açıp kontrol edebilelim.
- **Potansiyel kod:** `03_konumlandirma/konum.py:to_geojson`; test: `tests/test_konum.py`
- **Durum:** test edildi

### Adım 4 — `match_tracks` (klasör: `04_iz_eslestirme`)

#### R4.1 – Eşleştirme kapısı (25 m) çözünürlüğe göre geniş
- **Akıştaki yeri:** 4 match_tracks.
- **Şu anki durum:** `core/config.py: match_max_m = 25` + Macar algoritması (`services/tracks.py:match_detections`).
- **Neden gerekli:** Çözünürlük 0.108–0.198 m/piksel; 25 m = 126–231 piksel. Organizatörün örneklerinde
  doğru iz 1 m'nin altında. Buna karşılık 226 iz ucunun **139'unun** 25 m içinde başka bir iz ucu var (en
  yakın komşu: en az 1.7 m, medyan 18.8 m). Geniş kapı, izi olmayan park etmiş bir aracın tespitini komşu
  aracın izine bağlayabilir.
- **Zorluk:** Kolay (1–2 saat).
- **Teknik anlatım:** Kapıyı piksele bağla: `gate = max(3 m, k × kutu köşegeni × GSD)` (bkz. arge_f Step 5
  #1); en yakın ile ikinci en yakın farkını (zaten `second_best_m`) güven olarak kullan. Nihai değer tespitler
  hesaplandıktan sonra (R2.3) eşleşme mesafesi dağılımının p95'i ile seçilir.
- **Herkesin anlayacağı anlatım:** Fotoğraftaki aracı kayıtlardaki bir araçla eşleştirirken 25 metrelik bir
  tolerans kullanıyoruz; oysa araçlar çoğu zaman birbirine bundan yakın. Toleransı daraltmak yanlış
  eşleşmeyi azaltır.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

#### R4.2 – Eşleşmeyen tespit ve izlerin anlamı
- **Akıştaki yeri:** 4 match_tracks → 6 ve 7.
- **Şu anki durum:** Eşleşmeyen tespit `no_track` (0 puan + belirsizlik) oluyor; eşleşmeyen izlerin ayrı bir
  anlamı yok.
- **Neden gerekli:** Görev tanımı: "park halindeki araçların hareket kaydı olmayabilir; kaydı bulunan bir araç
  da çekim anında görüntü dışında kalmış olabilir." Ölçüm: 226 izin 206'sı çekim anında kendi karesinin
  içinde, 20'si dışında; kare başına 3–10 iz. (Başka bir repoda, hazır COCO modeliyle yapılan önceki bir
  denemede 206 iz ucunun 144'ü 3 m içinde bir kutuyla eşleşmişti; bu belge için yeniden çalıştırılmadı.)
- **Zorluk:** Kolay (2 saat).
- **Teknik anlatım:** Eşleşmeyen tespit → `parked_likely` (iz yok) / `false_positive_likely`; eşleşmeyen iz →
  `outside_near_edge` (kenara yakın) / `missed_detection` (karenin içinde ama kutu yok) (bkz. arge_f
  `schemas.py: OrphanTrack, UnmatchedDetection`). Kaçırılan tespit sayısı brief'in belirsizlik bölümüne yazılır.
- **Herkesin anlayacağı anlatım:** Fotoğrafta görülen ama kaydı olmayan araç büyük ihtimalle park etmiştir;
  kaydı olup fotoğrafta görülmeyen araç ya kenardan çıkmıştır ya da model onu kaçırmıştır. Bunu açıkça
  yazmak, sistemin neyi bilmediğini dürüstçe söylemesini sağlar.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

### Adım 5 — `analyze_motion` (klasör: `05_hareket_analizi`)

#### R5.1 – "Hareketsiz" eşiği veriden: 100 m
- **Akıştaki yeri:** 5 analyze_motion (ve 6'daki "duruyor" iddiaları).
- **Şu anki durum:** Backend durakları adım hızıyla buluyor (`STOP_SPEED_MS = 1.0`, `services/motion.py`);
  izleme modunda `MOVING_STEP_M = 30` (bir tikte > 30 m = hareketli).
- **Neden gerekli:** Son 60 dakikada park hâlindeki izler en fazla **39 m** kayıyor; diğer tüm izler en az
  **1087 m** gidiyor. 5 dakikalık adımların %57'si 5 m'nin altında (konum titreşimi). AR-GE
  denetleyicisinin ilk sürümündeki 30 m eşik park etmiş aracı "hareketli" sayıyordu (REP-91: 31 m).
- **Zorluk:** Kolay (0.5 saat).
- **Teknik anlatım:** Pencere boyunca son konumdan en büyük uzaklık (`drift_m`) ≤ 100 m → hareketsiz. Eşik
  iki kümenin arasındaki boşlukta; test bu boşluğu gerçek veride doğruluyor.
- **Herkesin anlayacağı anlatım:** Konum kayıtları park etmiş araçlarda bile birkaç on metre oynuyor. Park
  edenlerle hareket edenler arasında çok büyük bir fark var; sınırı tam bu boşluğa koyduk.
- **Potansiyel kod:** `05_hareket_analizi/hareket.py:drift_m, drift_gap`; kullanım:
  `06_rapor_degerlendirme/claims.py:STATIONARY_MAX_M`; test: `tests/test_hareket.py`
- **Durum:** test edildi

#### R5.2 – Üs çevresinde dolanma (açı taraması)
- **Akıştaki yeri:** 5 analyze_motion → 7 score_risk.
- **Şu anki durum:** İzleme modu `services/watch.py:behavior_class` içinde taramayı hesaplıyor
  (`LOOP_SWEEP_DEG = 270` → `loops_around_base`), ama bu sınıf **risk puanına girmiyor**; `MotionProfile`'da
  tarama alanı yok. `docs/AGENT_FLOW.md` §10 madde 4 bunu yapılacak iş olarak listeliyor.
- **Neden gerekli:** Görev tanımı: araçlar "üs çevresinde dolaşır". Taraması > 90° olan 45, > 180° olan 11,
  > 270° olan **5** iz: T0172 (549°, img_000926, üsse en çok 875 m), T0034 (544°, img_007664, 527 m), T0043
  (441°, img_006673, 630 m), T0158 (323°, img_005672, 697 m), T0198 (320°, img_002900, 823 m).
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** Üsse göre kerteriz farklarının açılmış (unwrapped) toplamının en büyük mutlak değeri.
  Yapay çemberde 0.5 / 1 / 1.5 tur → 180° / 360° / 540° (test). Eşik backend'deki 270° ile aynı.
- **Herkesin anlayacağı anlatım:** Bir aracın üssün etrafında tur atıp atmadığını, üsse göre açısının ne
  kadar değiştiğine bakarak ölçüyoruz. Gün içinde beş araç üssün etrafında neredeyse bir tur ya da daha
  fazlasını atmış.
- **Potansiyel kod:** `05_hareket_analizi/hareket.py:sweep_deg, circlers`; test: `tests/test_hareket.py`
- **Durum:** test edildi

#### R5.3 – Hız ve yön izin penceresinden
- **Akıştaki yeri:** 5 analyze_motion.
- **Şu anki durum:** `MotionProfile.heading_deg` son anlamlı adımdan (`MIN_MOVE_M`), `last10_speed_ms` son
  10 dakikadan hesaplanıyor (`services/motion.py`).
- **Neden gerekli:** Görev tanımı: "Hız ve yönü tek bir adımdan değil, kaydın tamamından okuyun." Adımların
  %57'si < 5 m; yani tek adımlık yön çoğu zaman titreşimdir.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** 30 dakikalık pencerede yol hızı (toplam yol / süre) ile net hız (başlangıç–bitiş) ayrı;
  yön yalnızca net yer değiştirme ≥ 100 m ise verilir. Park titreşimi yol hızını şişirir, net hızı şişirmez (test).
- **Herkesin anlayacağı anlatım:** Aracın hızını tek bir anlık ölçümden değil, son yarım saatin tamamından
  hesaplıyoruz; dur-kalk trafikte ya da konum titremesinde yanlış sonuç çıkmıyor.
- **Potansiyel kod:** `05_hareket_analizi/hareket.py:window_speed_heading`; test: `tests/test_hareket.py`
- **Durum:** test edildi

### Adım 6 — `assess_reports` (klasör: `06_rapor_degerlendirme`)

Kod: `claims.py` (ayrıştırma + kontrol), `admiralty.py` (notlama), `run.py` (137 raporun tablosu).
Tespitsiz sonuç: 67 rapor tutarlı, 6 çelişiyor, 25 doğrulanamaz, 39 bağlam (ayrıntı: Bölüm 5).

#### R6.1 – Genişletilmiş SALUTE: 7 rapor kategorisi
- **Akıştaki yeri:** 6 assess_reports (6a çıkarım).
- **Şu anki durum:** `domain/report.py: ClaimKind = SIGHTING | ALL_CLEAR | FRIENDLY_PRESENCE | TRAFFIC_NORMAL
  | OTHER`; her rapora tek tür. Kimlik + hareket içeren rapor yalnızca `FRIENDLY_PRESENCE` oluyor.
- **Neden gerekli:** Raporlar birleşik: "üsse doğru ilerleyen otomobil planlı ikmal aracıdır" = görülme +
  hareket + kimlik. Bu çalıştırmada 137 raporun ana kategorileri: bağlam 39, duruş 26, görülme 22, yokluk 22,
  kimlik 22, hareket 4, yoğunluk 2; **hepsi** bir kategoriye atanıyor (test).
- **Zorluk:** Orta (4–6 saat backend'e taşımak için; domain modeli değişir).
- **Teknik anlatım:** Rapor → atomik iddialar. SALUTE eşlemesi: Size → `existence, count`; Activity →
  `stationary, moving, toward_base, leaving_area`; Location → koordinat/bölge; Unit → `identity`; Time → rapor
  saati (R6.5); Equipment → `type`. Eklenenler: `above_usual_density`, olumsuz iddialar (`no_heavy_vehicles,
  no_notable_movement, no_anomaly, traffic_normal`), `color, cargo`. Her biri `supported | contradicted |
  unverifiable` + gerekçe + kanıt kimliği. Kategoriler iddialardan türetilir (çoklu etiket + öncelikli ana
  kategori: kimlik > yokluk > yoğunluk > hareket > duruş > görülme > bağlam). Furkan'ın `AtomicClaim`
  şemasıyla aynı fikir (bkz. arge_f Step 7).
- **Herkesin anlayacağı anlatım:** Bir rapor çoğu zaman birden fazla şey söyler ("orada bir araba var, üsse
  gidiyor, bizim aracımız"). Her parçayı ayrı kontrol ediyoruz; bazısı doğru, bazısı yanlış çıkabilir.
- **Potansiyel kod:** `06_rapor_degerlendirme/claims.py:parse_report`; test: `tests/test_claims.py`
- **Durum:** test edildi

#### R6.2 – Türkçe anahtar kelime boşlukları ve olumsuzluk
- **Akıştaki yeri:** 6a çıkarım (kural tabanlı yol).
- **Şu anki durum:** `services/reports.py:extract_claim` gerçek raporlarda (önceki oturumda backend koduyla
  denendi) şunları yanlış okuyor: "ağır araç hareketi yok, yalnızca binek araçlar" → **kamyon görülmesi**;
  "ağır **bir** aracın" → araç türü yok; "Lojistik konvoyu … yola çıkacak" → *hareketli*; "genellikle 4 araç"
  → iddia edilen sayı 4; "kayda değer hareketlilik bulunmuyor" → OTHER.
- **Neden gerekli:** Tersine okuma tersine sonuç doğurur: bölgede kamyon görülürse "ağır araç yok" raporu
  *doğrulanmış* sayılır. Bu kalıpta 6 rapor var.
- **Zorluk:** Kolay (2 saat).
- **Teknik anlatım:** Olumsuzluk kalıpları önce denenir (`agir arac (hareketi)? (yok|bulunmuyor|gorulmedi)`);
  `agir (bir )?arac` → ağır; bağlam kalıpları (gelecek plan, dün gece, telsiz, hava) konumsuzsa iddia
  üretmez; olağan sayı ayrı alan (`usual_count`). Her kalıbın testi var.
- **Herkesin anlayacağı anlatım:** Bilgisayar "kamyon yok" cümlesinde "kamyon" kelimesini görüp "kamyon var"
  sanıyordu. Olumsuz cümleleri ve gelecekle ilgili planları ayrı tanıyacak şekilde kuralları düzelttik.
- **Potansiyel kod:** `06_rapor_degerlendirme/claims.py` (`_ABSENCE_PATTERNS`, `_CONTEXT_PATTERNS`,
  `_VEHICLE_WORDS`); test: `tests/test_claims.py`
- **Durum:** test edildi

#### R6.3 – Bağlam / ilgisiz raporlar
- **Akıştaki yeri:** 6b ilgililik.
- **Şu anki durum:** Hava, telsiz arızası, "dün gece doğrulanmamış ihbar", lojistik planı `OTHER` oluyor;
  bölge adı geçtiği için o bölgenin karelerine ilgili sayılabiliyor.
- **Neden gerekli:** 137 raporun **39'u** bağlam (29 official, 10 third_party). Araç hakkında doğrulanabilir
  bir şey söylemiyorlar; ama "telsiz bağlantısı 40 dakikadır kurulamıyor" operatör için dikkat bilgisi.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** `CONTEXT` → `NOT_ASSESSED`, Admiralty kodu yok ("okundu, ilgisiz"). Telsiz kaybı
  ayrıca o sektör için brief'e bağlam notu olabilir (bkz. arge_f Step 7 #5).
- **Herkesin anlayacağı anlatım:** Hava durumu ya da dün geceki doğrulanmamış bir ihbar, şu anki bir aracı
  değerlendirmek için kanıt değildir. Bu raporları okuyup "ilgisiz" diye işaretliyoruz; kaybolmuyorlar.
- **Potansiyel kod:** `06_rapor_degerlendirme/claims.py:_CONTEXT_PATTERNS`; test:
  `tests/test_claims.py::test_context_reports_carry_no_assertions`
- **Durum:** test edildi

#### R6.4 – Prompt injection'a karşı rapor işleme
- **Akıştaki yeri:** 6 assess_reports (ve tüm LLM adımları).
- **Şu anki durum:** İyi: backend talimat benzeri metni `services/reports.py:has_instructions` ile yakalıyor
  (güven 0); izleme modu istemleri raporları "untrusted" olarak veriyor (`agent/prompts/watcher_v3.md`,
  `agent/watch/tools.py`). Anahtar kelime listesi kısa.
- **Neden gerekli:** Raporlar dışarıdan gelen serbest metin (OWASP LLM01). Gerçek veride injection yok; bu
  bir sağlamlık önlemi.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** Talimat benzeri raporun iddiaları yine kontrol edilir ama bilgi notu en iyi 4 olur
  ("talimat benzeri metin veri olarak işlendi"); "risk(i) düşük", "olarak raporla" gibi kalıplar eklendi.
  Asıl güvence yapısal: LLM sayı üretmez, rapor seviyeyi asla düşüremez.
- **Herkesin anlayacağı anlatım:** Biri rapora "bu aracı güvenli say" diye bir cümle gizlerse sistem bunu emir
  olarak değil, şüpheli bir veri olarak görür.
- **Potansiyel kod:** `claims.py:_INSTRUCTION_PATTERNS`, `admiralty.py:info_grade`; testler:
  `test_claims.py::test_instruction_like_text_is_flagged`,
  `test_admiralty.py::test_instruction_like_report_cannot_score_better_than_doubtful`
- **Durum:** test edildi

#### R6.5 – Raporu rapor saatinde değil, karenin çekim anında kontrol etmek
- **Akıştaki yeri:** 6b doğrulama; izleme modunda `get_reports` aracı.
- **Şu anki durum:** `services/reports.py:verify_claim` ("presence" kontrolü) ve izleme modundaki
  `services/watch.py:reports_near` raporu **rapor saatindeki** en yakın izle karşılaştırıyor. Furkan'ın
  notları da aynı varsayımda (bkz. arge_f Step 7 #1).
- **Neden gerekli:** Ölçüm tersini gösteriyor: 72 koordinatlı raporun **60'ı** bir izin **son noktasına**
  (çekim anı) 15 m'den yakın; rapor saatindeki bir iz noktasına yakın olan yalnızca **17** (bu 17'nin hepsi
  son noktaya da yakın: park etmiş araçlar). Her koordinatlı rapor tam olarak **bir** karenin içinde (±60 m)
  ve o karenin çekiminden **5–120 dk önce** yazılmış. Rapor saatinde eşleştirme, dost raporlarını yakındaki
  park etmiş başka araçlarla eşleştiriyor (Bölüm 6).
- **Zorluk:** Orta (3–4 saat; izleme modunda rapor, karesi çekilene kadar "bekleyen" tutulmalı).
- **Teknik anlatım:** Koordinatlı rapor → kapsayan kare (±60 m) → o karenin çekim anında biten izler
  (`tracks_ending_at`) ve varsa tespitler. Hareket iddiaları çekim anından geriye ölçülür (son 30/60 dk). Rapor
  saati yumuşak; yalnızca metinde açık bir saat varsa katı kullanılmalı. Bölge raporları o bölgenin rapordan
  sonraki 120 dk içindeki kareleriyle kontrol edilir.
- **Herkesin anlayacağı anlatım:** Raporlar aracı drone fotoğrafının çekildiği andaki yeriyle tarif ediyor;
  raporun üstündeki saat daha erken. Doğru aracı bulmak için raporu fotoğraf anıyla karşılaştırmak gerekiyor.
- **Potansiyel kod:** `claims.py:check_report, _frame_for, _check_point_claims`; test: `tests/test_real_data.py`
- **Durum:** test edildi

#### R6.6 – Çok araçlı iddialar ("5 kamyon", "3 araçlık konvoy")
- **Akıştaki yeri:** 6b doğrulama.
- **Şu anki durum:** Backend koordinatlı raporu en yakın `count` tespite bağlıyor; hareket kontrolü bu
  araçlar üzerinden yapılıyor.
- **Neden gerekli:** Kareler kalabalık (en yakın komşu medyanı 18.8 m). AR-GE denetleyicisinin ilk
  sürümündeki "en yakın N iz hepsi uymalı" kuralı yanlış çelişkiler üretti: REP-10, REP-18, REP-87, REP-94 (ve
  eşik yüzünden REP-91); yanından geçen bir araç "2 kamyon duruyor" raporunu çürütüyordu.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** 80 m içindeki izlerden en az N−1'i iddia edildiği gibi davranıyorsa desteklendi; hiçbiri
  davranmıyorsa çelişiyor; arada kalırsa "duruyor" iddiası doğrulanamaz (park araçların izi olmayabilir),
  "hareket" iddiası çelişiyor (hareket eden aracın izi olur). Çelişen rapor sayısı 11'den 6'ya indi. Örnek:
  REP-94 "2 kamyonun durduğu": 80 m içindeki 4 izin 2'si duruyor (T0045 17 m, T0066 12 m kaymış) → desteklendi.
- **Herkesin anlayacağı anlatım:** "Burada 5 kamyon duruyor" diyen raporu oradan geçen bir araba yüzünden
  yalanlamamak gerekiyor. Araçların çoğu söylendiği gibiyse doğru, hiçbiri değilse yanlış sayıyoruz.
- **Potansiyel kod:** `claims.py:_check_group_motion`; test: `tests/test_claims.py` (grup testleri),
  `tests/test_real_data.py`
- **Durum:** test edildi

#### R6.7 – Kimlik iddiası riski düşürmez; hareket çelişirse aldatma şüphesi
- **Akıştaki yeri:** 6c karar → 7 risk.
- **Şu anki durum:** Doğru ilke var: doğrulanamayan tehdit düşürücü iddia `UNVERIFIED` olur, seviyeyi
  düşürmez (`services/reports.py`, `AGENT_FLOW.md` §6). Eksik: kontrol edilebilir kısım (yön) ayrıca
  kontrol edilmiyor; "üsse doğru" yalnızca "hareketli" olarak okunuyor.
- **Neden gerekli:** 22 kimlik raporunun 18'i koordinatlı ve bu **18'in hepsi `official`**. "Üsse doğru / üsse
  gelen" diyen 15 raporun **13'ünde** araç gerçekten yaklaşıyor (ör. REP-78: T0168 7.8 → 1.7 km). **REP-61**'de
  T0075 son 30 dk'da üsten **uzaklaşıyor** (4.1 → 5.3 km), **REP-113**'te T0124 yaklaşmıyor (3.4 → 3.5 km).
  Resmî kaynaktan gelen, hareketle çelişen "dost" raporu en tehlikeli yanlış güven türüdür.
- **Zorluk:** Kolay (1–2 saat).
- **Teknik anlatım:** `identity` her zaman `unverifiable`. `toward_base`: son 30 dk'da üsse mesafe ≥ 200 m
  azaldı mı. Çelişirse `deception_indicator = True` ve bilgi notu 4 (varlık tuttuğu için 5 değil). Tutarlı olsa
  bile kimlik raporunun bilgi notu en iyi 3 (kimliğin kendisi doğrulanamaz). Furkan'ın önerisiyle aynı: aldatma
  göstergesi seviyeyi +1 artırabilir (bkz. arge_f §3 madde 3).
- **Herkesin anlayacağı anlatım:** "Bu bizim aracımız" cümlesini fotoğraftan doğrulayamayız, bu yüzden riski
  asla düşürmüyoruz. Ama raporun "üsse geliyor" kısmını kontrol edebiliriz; araç aslında uzaklaşıyorsa rapor
  şüphelidir.
- **Potansiyel kod:** `claims.py` (`toward_base`, `deception_indicator`), `admiralty.py:info_grade`; testler:
  `test_claims.py`, `test_admiralty.py`, `test_real_data.py`
- **Durum:** test edildi

#### R6.8 – Yokluk iddiaları bölge izleriyle
- **Akıştaki yeri:** 6b doğrulama.
- **Şu anki durum:** Yokluk iddiası türü yok (bkz. R6.2); "olağandışı durum bildirmedi" `ALL_CLEAR`.
- **Neden gerekli:** 22 yokluk raporu var. **REP-42** (15:00, official) "Kuzeybatı Yolu çevresinde kayda değer
  bir hareketlilik bulunmuyor" derken o bölgenin karelerinde (img_001733, img_004423) T0121, T0125 ve T0143
  son 30 dk'da üsse 2.0 / 4.0 / 1.5 km yaklaşmış. 6 "ağır araç yok" raporu tespit olmadan kontrol edilemiyor.
- **Zorluk:** Orta (2–3 saat).
- **Teknik anlatım:** Bölge raporu → o bölgenin rapordan sonraki 120 dk içindeki kareleri.
  `no_notable_movement`: bir iz son 30 dk'da üsse ≥ 1 km yaklaştıysa çelişiyor. `no_heavy_vehicles`: bu
  karelerde kamyon/otobüs tespiti varsa çelişiyor, tespit yoksa doğrulanamaz. `no_anomaly` ve
  `traffic_normal`: belirsiz; doğrulanamaz ve riski düşüremez.
- **Herkesin anlayacağı anlatım:** "Bölgede hareket yok" diyen raporu, o bölgenin fotoğraflarında üsse hızla
  yaklaşan araçlar varsa yanlış sayıyoruz. "Her şey normal" gibi belirsiz raporlar kontrol edilemez.
- **Potansiyel kod:** `claims.py:_check_area_claims`; test: `tests/test_claims.py`
- **Durum:** test edildi

#### R6.9 – Yoğunluk iddiası: "olağan 4 araç"
- **Akıştaki yeri:** 6b doğrulama.
- **Şu anki durum:** "beklenmedik yoğunluk" `OTHER`; "4 araç" iddia edilen sayı olarak okunuyor.
- **Neden gerekli:** 2 rapor: REP-20 (olağan 4, img_005978'de 9 araç) ve REP-117 (olağan 4, img_008001'de 7
  araç); ikisi de doğrulanıyor.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** `usual_count` ayrı alan; kontrol: karedeki iz sayısı (varsa tespit sayısı) > olağan.
  Sınır: şu an tüm kareyi sayıyor, koordinat çevresini değil.
- **Herkesin anlayacağı anlatım:** "Burada normalde 4 araç olur, bugün fazla" diyen rapor için fotoğraftaki
  araçları sayıyoruz; gerçekten 4'ten fazlaysa rapor doğru.
- **Potansiyel kod:** `claims.py:_check_density`; test: `tests/test_claims.py`
- **Durum:** test edildi

#### R6.10 – NATO Admiralty kodu (A–F / 1–6)
- **Akıştaki yeri:** 6c karar; arayüz ve brief.
- **Şu anki durum:** Sabit güven: official 0.8, third_party 0.5 (`services/reports.py:_TRUST`); güven sırası
  "official > third-party" (`AGENT_FLOW.md` §6).
- **Neden gerekli:** Kaynak türüne göre sabit güven veriyle desteklenmiyor: kontrol edilebilen raporlarda
  official **45/50**, third_party **22/23** tuttu. Çelişen 6 raporun 5'i resmî.
- **Zorluk:** Orta (3–4 saat backend'e taşımak için).
- **Teknik anlatım:** Kaynak notu: başlangıç official → B, third_party → C; o kaynağın **diğer** kontrol
  edilebilir raporlarının Beta(1+tutan, 1+çelişen) ortalamasına göre B (≥ 0.8) / C (≥ 0.6) / D (≥ 0.4) / E;
  en az 5 rapor gerekir, rapor kendi kaynağını notlamaz, A otomatik verilmez, bilinmeyen kaynak F. Bilgi notu:
  çelişiyor → 5 (bir kısmı tutuyorsa 4); tutarlı + **aynı araç** hakkında başka bir tutarlı raporla bağımsız
  teyit → 1; her şey doğrulandı → 2; doğrulanamayan kısım var → 3; hiçbir şey doğrulanamıyor → 6; bağlam →
  kod yok. Talimat benzeri metin → en iyi 4; kimlik raporu → en iyi 3.
- **Herkesin anlayacağı anlatım:** Her rapora iki ayrı not veriyoruz: kaynağın bugüne kadar ne kadar doğru
  çıktığı (harf) ve bu raporun kanıtla ne kadar desteklendiği (rakam). "Resmî kaynak" olmak tek başına doğru
  olmak demek değil.
- **Potansiyel kod:** `06_rapor_degerlendirme/admiralty.py`; test: `tests/test_admiralty.py`
- **Durum:** test edildi

### Adım 7 — `score_risk` (klasör: `07_risk`)

#### R7.1 – "Üs yakınında duraklama" 206/226 izde puan veriyor
- **Akıştaki yeri:** 7 score_risk (izleme modundaki `track_rubric` aynı fonksiyonu kullanıyor).
- **Şu anki durum:** `services/risk.py:motion_factors` → 6 km içinde ≥ 20 dk duruş = 10 (+5) puan.
- **Neden gerekli:** Gerçek veride **206/226** (%91) izde devreye giriyor. (AR-GE ölçüm kodu bu sayıyı veriyor;
  önceki bir oturumda backend'in kendi `score_vehicle` fonksiyonuyla da 206 ölçülmüştü.) Dur-kalk trafik ve
  6 km yarıçap neredeyse herkesi kapsıyor. `AGENT_FLOW.md` §10 madde 4 de bu faktörün düzeltilmesini istiyor.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:** Öneri: yalnızca **gelip duran** araç: duruştan önce ≥ 500 m yol yapmış, şu anda en az
  20 dk'dır duruyor ve üsse ≤ 3 km. Bu kural **7/226** (%3) izde çalışıyor: T0020, T0056, T0057, T0118, T0182,
  T0184, T0209. Ağırlık etiketli veri olmadan seçildi; takım kararı gerekir.
- **Herkesin anlayacağı anlatım:** "Üsse yakın bir yerde durmuş" kuralı neredeyse her araca puan veriyor,
  çünkü trafikte herkes bir ara duruyor. Yalnızca üsse doğru gelip yakınında bekleyen araçları işaretlemeyi
  öneriyoruz.
- **Potansiyel kod:** `07_risk/kalibrasyon.py:proposed_stop_rule, firing_table`; test: `tests/test_risk.py`
- **Durum:** prototip

#### R7.2 – Dolanmaya risk puanı
- **Akıştaki yeri:** 7 score_risk.
- **Şu anki durum:** `loops_around_base` sınıfı izleme modunda var ama puana eklenmiyor (R5.2).
- **Neden gerekli:** > 270° dolanan 5 iz (T0172, T0034, T0043, T0158, T0198). T0034 dışındakiler çekim anında
  üsse 1.6–1.8 km'de (T0034 4.5 km) ve hepsi gün içinde üsse 527–875 m'ye kadar yaklaşmış. Furkan'ın
  notlarındaki en güçlü tehdit adaylarıyla örtüşüyor (bkz. arge_f §2).
- **Zorluk:** Kolay (0.5 saat).
- **Teknik anlatım:** `sweep_deg > 270` → +20 puan (öneri, `CIRCLING_POINTS`). 5/226 (%2) izde çalışıyor.
- **Herkesin anlayacağı anlatım:** Üssün etrafında tur atan bir araç, geçip giden bir araçtan daha dikkat
  çekicidir; bunu puana yansıtmayı öneriyoruz.
- **Potansiyel kod:** `07_risk/kalibrasyon.py`, `05_hareket_analizi/hareket.py:sweep_deg`; test: `tests/test_risk.py`
- **Durum:** prototip

#### R7.3 – Mesafe kademeleri: < 1 km kademesi hiç çalışmıyor
- **Akıştaki yeri:** 7 score_risk.
- **Şu anki durum:** `services/risk.py:distance_factor`: < 1 km 30, < 2 km 20, < 4 km 10 puan.
- **Neden gerekli:** Hiçbir aracın son konumu üsse **1553 m**'den yakın değil; 30 puanlık kademe **0** izde
  çalışıyor. Herhangi bir mesafe puanı alan iz: 132/226 (%58).
- **Zorluk:** Kolay (0.5 saat).
- **Teknik anlatım:** Öneri: < 2 km 25, < 3 km 15, < 4 km 5 (`DISTANCE_TIERS_PROPOSED`); en üst kademe
  44/226 (%19) izde. Kademeler bu günün dağılımına göre seçildi; başka bir günde yeniden ölçülmeli.
- **Herkesin anlayacağı anlatım:** "Üsse 1 km'den yakın" için en yüksek puanı veriyoruz ama bugün hiçbir araç
  o kadar yaklaşmadı. Basamakları bugünkü gerçek mesafelere göre ayarlamayı öneriyoruz.
- **Potansiyel kod:** `07_risk/kalibrasyon.py`; test: `tests/test_risk.py`
- **Durum:** prototip

#### R7.4 – Doğrulanan / çelişen raporların puana etkisi
- **Akıştaki yeri:** 7 score_risk.
- **Şu anki durum:** Pipeline: doğrulanan `SIGHTING` → +10 (`services/risk.py:score_vehicle`). İzleme modu:
  "rapor puanları ajanlara bırakıldı" (`services/watch.py:track_rubric`); raporlar seviyeyi asla düşürmez.
- **Neden gerekli:** Aldatma şüphesi (REP-61, REP-113) puana hiç yansımıyor; doğrulanan bir "duruyor" raporu
  (SIGHTING değil) puan getirmiyor.
- **Zorluk:** Orta (2 saat + takım kararı).
- **Teknik anlatım:** Öneri: aldatma göstergesi → +1 seviye (Furkan'la aynı); doğrulanan tehdit iddiası (üsse
  yaklaşan, üs yakınında bekleyen) → +10; çelişen ya da doğrulanamayan rapor → 0 (asla eksi). Etki brief'te
  gerekçesiyle gösterilir.
- **Herkesin anlayacağı anlatım:** Doğrulanan tehdit raporları riski biraz artırmalı; bizi yanıltmaya çalışan
  bir rapor aracı daha şüpheli yapmalı. Hiçbir rapor tek başına riski düşürmemeli.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

### Adım 8 — `write_brief` (klasör: `08_brief`)

#### R8.1 – GLM-5.3-Flash entegrasyonu ve 15 USD bütçe
- **Akıştaki yeri:** 8 write_brief ve tüm LLM çağrıları.
- **Şu anki durum:** Büyük kısmı yapılmış (`agent/llm_client.py:GLMClient`, `core/config.py`): model
  `glm-5.3-flash`; `reasoning_content` iz için saklanıyor; `max_tokens = 8000`; `reasoning_effort` gözcüde
  `low`, denetçide `high`; 120 s zaman aşımı; 4 eşzamanlı istek; tam istek özetiyle disk önbelleği;
  `finish_reason == "length"` olan cevap önbelleğe yazılmıyor; gözcü başına ≤ 3 araç çağrısı
  (`watcher_max_tool_calls`) ve `MAX_ROUND_TRIPS_EXTRA = 3` (`agent/watch/loop.py`). **Kalan bütçeyi soran
  kod yok.**
- **Neden gerekli:** Görev tanımı: toplam 15 USD, sıfırlanmaz; 60 istek/dk, 500.000 token/dk, 4 eşzamanlı
  istek; "sonsuz döngüye giren bir agent'ı fark etmezseniz tükenebilir". Kalan bütçe için `/key/info`
  adresi veriliyor (`spend` ve `max_budget` alanları). Model her zaman önce düşündüğü için `max_tokens` düşük
  kalırsa cevap kesilir.
- **Zorluk:** Kolay (1–2 saat).
- **Teknik anlatım:** Çalıştırma başında ve her N çağrıda `GET {gateway}/key/info` → `max_budget − spend`;
  eşik altında izleme modu kayıtlı çalıştırmaya (recording) ya da deterministik yedeğe geçer ve
  `/api/health`'te gösterilir. `finish_reason == "length"` sayısı kaydedilip `max_tokens` buna göre ayarlanır.
- **Herkesin anlayacağı anlatım:** Dil modelini kullanmak için sınırlı ve yenilenmeyen bir bütçemiz var. Sistem
  ne kadar para kaldığını düzenli kontrol etmeli; bütçe biterse durmadan kayıtlı sonuçlarla devam etmeli.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

#### R8.2 – BLUF + ICD 203 belirsizlik dili
- **Akıştaki yeri:** 8 write_brief.
- **Şu anki durum:** `domain/brief.py:Brief`: başlık, özet, araç satırları, rapor notları, belirsizlikler,
  önerilen eylem; olasılık ifadeleri standart değil.
- **Neden gerekli:** Operatör en önemli sonucu ilk cümlede görmeli (BLUF). "Muhtemelen" gibi kelimeler
  kişiden kişiye farklı anlaşılır; ICD 203 ölçeği bunları sabitler.
- **Zorluk:** Kolay (1–2 saat; istem + yedek şablon).
- **Teknik anlatım:** Sıra: sonuç → durum → gerekçe → raporlar (Admiralty kodlu) → belirsizlikler → öneri.
  Ölçek: %95+ "neredeyse kesin", %80–95 "kuvvetle muhtemel", %55–80 "muhtemel", %45–55 "eşit olasılıkla",
  %20–45 "muhtemel değil", %5–20 "kuvvetle muhtemel değil", < %5 "neredeyse imkânsız". Dikkat: kural tabanlı
  risk puanı kalibre bir olasılık değildir; bu kelimeler yalnızca ölçülen olgular için ("yaklaştığı
  neredeyse kesin: iz verisi"), niyet için kullanılmaz.
- **Herkesin anlayacağı anlatım:** Rapor önce sonucu söylesin, sonra nedenini. "Muhtemel" gibi kelimeleri
  herkes aynı anlamda kullansın diye sabit bir ölçek kullanıyoruz.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

#### R8.3 – Sayı ve kimlik uydurmasına karşı doğrulayıcı
- **Akıştaki yeri:** 8 write_brief (doğrulayıcı).
- **Şu anki durum:** İzleme modunda kanıt kimlikleri doğrulanıyor (`agent/watch/tools.py:unknown_evidence`:
  TRK / REP / FRAME / NOTE / ZONE). Metindeki **sayılar** (mesafe, hız, araç sayısı) kontrol edilmiyor.
- **Neden gerekli:** OWASP LLM09: model "1.2 km" ya da "3 kamyon" uydurabilir. İlke "her sayı deterministik
  bir araçtan gelir" (`AGENT_FLOW.md` §9), ama bunu denetleyen kod yok.
- **Zorluk:** Orta (3 saat).
- **Teknik anlatım:** Brief metnindeki sayıları (km, m, m/s, dk, adet) regex ile çıkar; atıf yapılan kanıtın
  olgu tablosundaki değerle toleransla (±%5 / ±1 adet) karşılaştır; uyuşmazsa bir onarım denemesi, sonra
  şablon brief. Metinde geçen her iz kimliği (T0122 gibi) kanıt listesinde olmalı.
- **Herkesin anlayacağı anlatım:** Dil modelinin yazdığı rapordaki her sayıyı hesapladığımız gerçek sayılarla
  karşılaştırıyoruz. Uymayan bir sayı varsa o rapor kullanılmıyor.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

#### R8.4 – Brief'te Admiralty kodu ve SALUTE karşılaştırması
- **Akıştaki yeri:** 8 write_brief.
- **Şu anki durum:** Brief'teki `report_notes` serbest metin.
- **Neden gerekli:** Operatör bir raporun neden kabul/ret edildiğini tek satırda görmeli.
- **Zorluk:** Kolay (1 saat; R6.10 backend'e taşındıktan sonra).
- **Teknik anlatım:** İlgili her rapor için hazır satır: `REP-61 (B4): "üsse doğru" ↔ T0075 4.1 → 5.3 km,
  uzaklaşıyor; kimlik doğrulanamaz; aldatma şüphesi`. LLM bu satırları değiştirmez; yalnızca sıralar ve yorumlar.
- **Herkesin anlayacağı anlatım:** Kısa raporda her saha raporunun notu ve kontrolün sonucu tek satırda
  yazsın; okuyan kişi neyin doğru neyin yanlış çıktığını hemen görsün.
- **Potansiyel kod:** henüz yok (veri: `run.py --json`)
- **Durum:** fikir

### Kesişen — güvenlik ve standartlar (klasör: `09_guvenlik_standartlar`)

#### R9.1 – NATO Sorumlu YZ ilkeleri; operatör onayı
- **Akıştaki yeri:** tüm akış; izleme modunda `alert_operator`, `set_level`.
- **Şu anki durum:** `AGENT_DESIGN.md` §12: `alert_operator` operatöre açıklamalı uyarı gönderir, "onay
  adımı yok"; baş denetçi `set_level` ile seviyeyi doğrudan değiştirebilir. `AGENT_FLOW.md` §3'teki diyagram
  hâlâ "ilk alarm operatör onayı ister" diyor.
- **Neden gerekli:** Savunma alanında yönetilebilirlik ve hesap verebilirlik: son karar insanda olmalı, itiraz
  kaydedilmeli. Jüri sorusu: "Sistem kendi başına karar veriyor mu?"
- **Zorluk:** Orta (3–4 saat; arayüzde onay/itiraz + kayıt).
- **Teknik anlatım:** İlke → özellik: açıklanabilirlik ve izlenebilirlik → kanıt kimlikleri + ajan izi
  (`agent_trace`, var); güvenilirlik → testler + yedek yollar (var); yönetilebilirlik → operatör onayı /
  itirazı (**eksik**); önyargının azaltılması → kaynak türü değil kanıt (R6.10); sorumluluk ve hesap
  verebilirlik → analiz kaydında model, istem sürümü, veri özeti; hukuka uygunluk → otomatik eylem yok,
  "bilinmeyen" sembolleri (R10.2). Uyarı "öneri" olarak gelir; operatörün onayı/itirazı ve gerekçesi kaydedilir.
- **Herkesin anlayacağı anlatım:** Sistem öneri sunar; son kararı her zaman bir insan verir. İnsanın onayladığı
  ya da itiraz ettiği her durum kayda geçer.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

#### R9.2 – OWASP LLM01/05/09/10 testleri
- **Akıştaki yeri:** tüm LLM adımları.
- **Şu anki durum:** LLM01 (injection) için kural ve istem önlemi var; LLM05 (şema doğrulama + onarım + yedek)
  var; LLM09 için kanıt kimliği kontrolü var, sayı kontrolü yok (R8.3); LLM10 için önbellek ve döngü sınırı var,
  bütçe kontrolü yok (R8.1). Bunları birlikte gösteren bir test takımı yok.
- **Neden gerekli:** Mentorlar teknik kaliteyi puanlıyor; `PLAN.md`'deki "yanıltıcı rapor" demo senaryosu bu
  testlerle kanıtlanabilir.
- **Zorluk:** Orta (3 saat).
- **Teknik anlatım:** (LLM01) talimat içeren sahte rapor → seviye değişmemeli; (LLM05) bozuk JSON → onarım,
  sonra şablon; (LLM09) sayısı değiştirilmiş brief → reddedilmeli; (LLM10) sahte düşük bütçe → kayıtlı moda
  geçiş. AR-GE'de LLM01'in kural katmanı test edildi.
- **Herkesin anlayacağı anlatım:** Sistemi kasıtlı olarak kandırmaya çalışan testler yazıyoruz: sahte emir
  içeren rapor, bozuk cevap, uydurma sayı, biten bütçe. Her birinde sistemin güvenli davrandığını gösteriyoruz.
- **Potansiyel kod:** kısmen: `tests/test_claims.py::test_instruction_like_text_is_flagged`,
  `tests/test_admiralty.py::test_instruction_like_report_cannot_score_better_than_doubtful`
- **Durum:** prototip

### Kesişen — arayüz ve demo (klasör: `10_arayuz_demo`)

#### R10.1 – Rapor inceleme ekranı: SALUTE tablosu + Admiralty kodu
- **Akıştaki yeri:** arayüz (analiz ekranı ve ayrı rapor ekranı).
- **Şu anki durum:** Yer tutucu rapor sayfası kaldırıldı (commit `b445b02`); raporlar analiz ekranında karar
  rozetiyle (`components/reports/ReportVerdictChip.tsx`) gösteriliyor.
- **Neden gerekli:** "Raporlara körü körüne güvenmiyoruz" projenin ana mesajı; jüri bunu bir tabloda görmeli.
- **Zorluk:** Orta (4–6 saat).
- **Teknik anlatım:** Satır: saat, kaynak, metin, Admiralty kodu, kategori; açılınca iddia tablosu (iddia |
  rapor ne diyor | verimiz ne diyor | sonuç | kanıt). Filtre: çelişen, aldatma şüphesi, kaynak. Üstte günün
  özeti: "resmî 45/50, üçüncü taraf 22/23 tuttu". Örnek veri: `python -m arge_m.run --json`.
- **Herkesin anlayacağı anlatım:** Her saha raporu için "rapor ne dedi, biz ne gördük, sonuç ne" tablosunu
  gösteren bir ekran. Jüri sistemin raporları nasıl kontrol ettiğini tek bakışta görür.
- **Potansiyel kod:** henüz yok (örnek veri: `run.py --json`)
- **Durum:** fikir

#### R10.2 – Harita sembolleri "bilinmeyen", "düşman" değil
- **Akıştaki yeri:** arayüz haritası.
- **Şu anki durum:** Arayüzde "hostile / düşman" kelimesi ya da askerî sembol yok (önceki oturumda
  `frontend/src` tarandı); araçlar risk rengiyle gösteriliyor.
- **Neden gerekli:** Araçların kimliği bilinmiyor; "düşman" etiketi hukuka uygunluk ilkesine aykırı olur.
  APP-6 / MIL-STD-2525 "bilinmeyen" çerçevesi profesyonel görünür ve doğru mesajı verir.
- **Zorluk:** Kolay (2 saat; `milsymbol` JS kütüphanesi, çevrimdışı demo için yerel paket).
- **Teknik anlatım:** Kimlik her zaman "unknown"; risk seviyesi sembolün yanında ayrı işaret (renk/rozet).
  Hiçbir durumda "hostile" çerçevesi kullanılmaz.
- **Herkesin anlayacağı anlatım:** Haritada araçları "düşman" olarak değil "kimliği bilinmeyen" olarak
  gösteriyoruz; riskli olmaları ayrı bir işaretle belirtiliyor.
- **Potansiyel kod:** henüz yok
- **Durum:** fikir

---

## 5. Sonuçlar (bu sürümün `run.py` çıktısı, tespitsiz)

### 5.1 Ana kategori × kaynak × sonuç

Her rapor bir kez, ana kategorisinde sayılır (öncelik: kimlik > yokluk > yoğunluk > hareket > duruş >
görülme > bağlam). Hücre biçimi: **tutarlı / çelişen / doğrulanamaz / bağlam**.

| Ana kategori | Toplam | official | third_party |
|---|---|---|---|
| Kimlik (IDENTITY) | 22 | 16 / 2 / 3 / 0 | 0 / 0 / 1 / 0 |
| Yokluk (ABSENCE) | 22 | 0 / 1 / 16 / 0 | 0 / 0 / 5 / 0 |
| Yoğunluk (DENSITY) | 2 | 2 / 0 / 0 / 0 | – |
| Hareket (MOVEMENT) | 4 | – | 4 / 0 / 0 / 0 |
| Duruş (STATIONARY) | 26 | 15 / 2 / 0 / 0 | 8 / 1 / 0 / 0 |
| Görülme (SIGHTING) | 22 | 12 / 0 / 0 / 0 | 10 / 0 / 0 / 0 |
| Bağlam (CONTEXT) | 39 | 0 / 0 / 0 / 29 | 0 / 0 / 0 / 10 |
| **Toplam** | **137** | **98:** 45 / 5 / 19 / 29 | **39:** 22 / 1 / 6 / 10 |

Kontrol edilebilen raporlarda tutma oranı: official 45/50, third_party 22/23.

### 5.2 Admiralty kodları

| Kod | Anlamı (kaynak / bilgi) | official | third_party | Toplam |
|---|---|---|---|---|
| B1 | genellikle güvenilir / başka kaynaklarla doğrulanmış | 6 | 3 | 9 |
| B2 | genellikle güvenilir / muhtemelen doğru | 1 | 0 | 1 |
| B3 | genellikle güvenilir / olası | 38 | 19 | 57 |
| B4 | genellikle güvenilir / şüpheli | 3 | 1 | 4 |
| B5 | genellikle güvenilir / olasılık dışı | 2 | 0 | 2 |
| B6 | genellikle güvenilir / değerlendirilemez | 19 | 6 | 25 |
| – | okundu, ilgisiz (bağlam) | 29 | 10 | 39 |

İki kaynak türü de B aldı (ikisinin de diğer raporlarındaki tutma oranı 0.8 eşiğinin üstünde). B1 alan
raporlar: REP-20, REP-37, REP-53, REP-54, REP-87, REP-94, REP-95, REP-110, REP-134.

### 5.3 Çelişen raporların tamamı (6)

| Rapor | Saat, kaynak | Kod | Kare | Metin (kısa) | Tutmayan kontrol ve sayılar |
|---|---|---|---|---|---|
| REP-42 | 15:00, official | B5 | img_001733, img_004423 | "Kuzeybatı Yolu çevresinde kayda değer bir hareketlilik bulunmuyor." | `no_notable_movement`: T0121 2.0 km, T0125 4.0 km, T0143 1.5 km son 30 dk'da üsse yaklaştı |
| REP-55 | 14:25, official | B4 | img_001147 | "… 1 kamyonun durduğu bildirildi." | `stationary`: T0078 son 30 dk'da 4570 m kaydı |
| REP-61 | 14:50, official | B4 | img_006444 | "… üsse doğru ilerleyen otomobil planlı ikmal aracıdır, kimlik teyidi yapılmıştır." | `toward_base`: T0075 üsse 4.1 → 5.3 km (uzaklaşıyor); aldatma şüphesi |
| REP-68 | 12:15, third_party | B4 | img_002900 | "Bir kaynak, … ağır bir aracın beklemede olduğunu iletti." | `stationary`: T0188 son 30 dk'da 5232 m kaydı |
| REP-101 | 11:40, official | B5 | img_003464 | "… 7 kamyonun durduğu bildirildi." | `stationary`: 80 m içindeki 4 izin 0'ı duruyor (T0135 4030 m, T0028 5048 m, T0001 4525 m, T0068 1999 m) |
| REP-113 | 12:15, official | B4 | img_000733 | "… üsse gelen otomobil bize bağlı unsurdur, gelişi önceden bildirilmiştir." | `toward_base`: T0124 üsse 3.4 → 3.5 km (yaklaşmıyor); aldatma şüphesi |

---

## 6. Düzeltilen bulgular

1. **"Dost araç raporlarındaki araçlar park hâlinde" bulgusu yanlıştı.** İlk kaba analiz (standartlar
   belgesi): "üsse doğru ilerleyen" 15 raporun 8'inde 70 m içinde park etmiş bir araç var. Bu, raporu **rapor
   saatinde** 70 m içindeki en yakın izle eşleştirmekten geliyordu. Hassas eşleştirme (çekim anı, ≤ 25 m) her
   raporu 0–1 m uzaklıkta hareket eden başka bir araca bağlıyor: 15 iddianın 13'ü tutuyor, 2'si (REP-61,
   REP-113) çelişiyor. Furkan'ın notlarındaki "0/15 tutarlı" sonucu da aynı rapor-saati varsayımından geliyor.
2. **Raporlar rapor saatine göre değil, çekim anına göre üretilmiş** (R6.5): 60/72'ye karşı 17/72. Not:
   önceki, daha kaba bir ölçüm betiği 62 bulmuştu; `claims.py` dosya başlığında hâlâ 62 yazıyor. Bu belgedeki
   60, `arge_m` koduyla yapılan güncel ölçümdür.
3. **Görev tanımındaki 1360×765 / T0187 örneği organizatörün kendi örneğidir** (ilk incelemede kaynağından
   şüphe edilmişti); ama "temsilidir": `img_000123` veride yok ve T0187 veride başka bir yerde. Bu yüzden R3.1
   köşeleri elle veren bir testtir.
4. **`/key/info` bütçe adresi gerçekten var** (ilk incelemede doğrulanamamıştı): görev tanımında,
   `spend` ve `max_budget` alanlarıyla.
5. **"Duraklama faktörü 206/226" şüphesi doğrulandı** (ilk incelemede 206'nın "karenin içindeki iz ucu"
   sayısıyla karıştırıldığı düşünülmüştü; iki sayı tesadüfen aynı).
6. **AR-GE denetleyicisinin ilk sürümü 11 çelişki buluyordu; 5'i yanlıştı.** Çok araçlı iddialar (R6.6) ve
   30 m duruş eşiği (R5.1) düzeltilince REP-10, REP-18, REP-87, REP-91 ve REP-94 çelişkiden çıktı; 6 çelişki kaldı.
7. **Admiralty ilk sürümünde 36 rapor B1 alıyordu.** Kimlik raporları "1" alabiliyordu ve "bağımsız teyit",
   sayım için kullanılan komşu izlerden tetikleniyordu. Kimlik raporu en iyi 3'e sınırlandı, teyit **aynı araç**
   şartına bağlandı; B1 sayısı 9'a indi.
8. **Kare→bölge atamasında sorun beklenmişti, yok:** iki yöntem 40/40 aynı (R1.1).

---

## 7. Standartlar eşlemesi

Hackathonda uyulması zorunlu bir standart yoktur; aşağıdakiler **esinlenilen / temel alınan** çerçevelerdir.
"Uyumlu" ifadesi kullanılmaz (uyumluluk resmî bir sertifikasyon gerektirir).

| Veride gördüğümüz risk | Kanıt | Temel alınan standart / ilke | Madde |
|---|---|---|---|
| Resmî kaynaktan gelen, hareketle çelişen "dost" raporları | REP-61, REP-113 | NATO Admiralty sistemi (AJP-2.1'den esinlenen) + NATO Sorumlu YZ "önyargının azaltılması" | R6.7, R6.10 |
| Kaynak etiketine göre sabit güven | official 45/50 ≈ third_party 22/23 | Admiralty: kaynak ve bilgi iki ayrı eksen | R6.10 |
| "Ağır araç yok" gibi yokluk iddiaları | 22 yokluk raporu, REP-42 | SALUTE şeması (yokluk ve kimlik türleriyle genişletilmiş) | R6.1, R6.2, R6.8 |
| Doğrulanamayan kimlik iddiaları | 22 kimlik raporu; koordinatlı 18'inin hepsi resmî | SALUTE "Unit" alanı + NATO "yönetilebilirlik" (karar insanda) | R6.7, R9.1 |
| Güvenilmeyen serbest metin raporlar | 137 serbest metin | OWASP LLM Top 10 — LLM01 (prompt injection) | R6.4, R9.2 |
| LLM çıktısının kontrolsüz kullanımı / uydurma sayı | ilke var, sayı kontrolü yok | OWASP LLM05, LLM09 | R8.3, R9.2 |
| 15 USD'lik sabit bütçe | görev tanımı | OWASP LLM10 (sınırsız kaynak tüketimi) | R8.1 |
| Belirsizliğin tutarsız ifade edilmesi | brief serbest metin | BLUF + ICD 203'ten esinlenen tahmin dili | R8.2 |
| Kimliği bilinmeyen (büyük olasılıkla sivil) araçlar | kimlik görüntüden doğrulanamaz | NATO "hukuka uygunluk" + APP-6 "bilinmeyen" sembolünü temel alan gösterim | R10.2 |
| Harita verisinde eksen karışıklığı | veri [enlem, boylam], GeoJSON [boylam, enlem] | GeoJSON (RFC 7946) | R3.2 |

---

## 8. Demo için önerilen örnekler

1. **img_006444 — REP-61: "resmî ama yanlış dost raporu".** 14:50 resmî rapor: "üsse doğru ilerleyen otomobil
   planlı ikmal aracıdır, kimlik teyidi yapılmıştır." Karede eşleşen araç T0075 (1 m), ama son 30 dk'da üsten
   **uzaklaşıyor** (4.1 → 5.3 km). Sistem kimliği doğrulayamaz, riski düşürmez, raporu B4 ve "aldatma şüphesi"
   olarak işaretler. Projenin ana mesajını ("raporlara körü körüne güvenmiyoruz") tek karede gösterir.
2. **img_000926 — dolanan araç + resmî ikmal raporu.** Bu karedeki T0172 gün içinde üssün etrafında **549°**
   dönmüş ve üsse 875 m'ye kadar yaklaşmış; aynı karedeki başka bir araç (T0168) için REP-78 "planlı ikmal
   aracı" diyor (hareket kısmı tutuyor: 7.8 → 1.7 km). "Dost" raporu bölgeyi rahatlatmamalı; dolanan araç ayrıca
   dikkat istiyor. Aynı bölge için REP-92 "ağır araç yok" diyor (tespitle kontrol edilebilir, R2.3).
   Benzer kare: **img_006673** (T0043 441° dolanmış, üsse 630 m'ye kadar yaklaşmış; aynı karede REP-06 ikmal ve
   REP-123 "mavi araç dost devriye" raporları). Furkan'ın notları da bu iki kareyi "olası tuzak" olarak
   işaretliyor.
3. **img_001733 — REP-42: "bölgede hareket yok" raporu.** 15:00 resmî rapor hareket olmadığını söylüyor; aynı
   bölgenin karelerinde üç araç (T0121, T0125, T0143) son 30 dk'da üsse 1.5–4.0 km yaklaşmış. Yokluk
   iddialarının neden ayrı bir tür olması gerektiğini gösterir.

Yedek / altın örnek: **img_000860** (organizatör örneği, T0122 < 1 m); aynı karede REP-120 "bize bağlı unsur"
(T0192 7.6 → 1.6 km: hareket tutuyor, kimlik doğrulanamaz, B3).

---

## 9. Açık sorular ve sınırlar

- **Tespit yok:** Bu çalıştırma tespitsiz. Araç tipi, "ağır araç yok" (6 rapor), izi olmayan (park) araç
  iddiaları ve yoğunlukta park araçlar doğrulanamıyor; en sık kodun B3 olması bundan. R2.3 yapılınca sonuçlar
  değişir.
- **Renk ve yük hiç kontrol edilmiyor** (R2.4).
- **Yoğunluk** tüm kareyi sayıyor, koordinat çevresini değil.
- **"Bölgeden uzaklaşıyor"** için referans nokta yok; yalnızca "hareket" kısmı kontrol ediliyor.
- **Risk ağırlıkları** (R7.1–R7.3) gerçek dağılıma göre seçildi ama etiketli sonuç (gerçek tehdit listesi)
  olmadan; takım kararı gerekir. Mesafe kademeleri bu güne özgü.
- **Admiralty kaynak notu** kaynak **türü** başına tek not (veride birim/kişi bilgisi yok); iki tür de B çıktı.
  "A" otomatik verilmiyor.
- **Varsayımlar:** saatler günün dakikası (tarih ve saat dilimi yok); görüntüler kuşbakışı ve kuzey yukarıda
  (görev tanımı kuralı); rapor saati yumuşak, metinde açık saat yok.
- **Eşikler bu güne göre** seçildi (100 m duruş, 80 m grup, 25 m eşleşme, 200 m yaklaşma, 1 km "kayda değer"
  hareket); başka bir günün verisinde yeniden ölçülmeli.
- **İzleme modu sektörleri:** R1.1 yalnızca kareler için ölçüldü; araç konumları için ölçülmedi.
- **Tutarsızlık:** `claims.py` başlığında "62/72" yazıyor; güncel ölçüm 60/72 (Bölüm 6, madde 2).

---

## 10. Öncelik önerisi

Etki × kolaylık sırasıyla; ilk üçü demodaki en görünür yanlışları düzeltir.

1. **R6.5 + R6.7 — Raporu çekim anında kontrol et; kimlik raporlarının hareketini doğrula.** İzleme modu
   raporları şu an yanlış araçlarla eşleştiriyor; REP-61 / REP-113 demonun en güçlü anı olabilir.
   (Orta, ~4 saat)
2. **R7.1 + R7.2 + R7.3 — Risk kalibrasyonu.** %91 izde çalışan duraklama faktörünü daralt, dolanmayı ekle,
   hiç çalışmayan mesafe kademesini düzelt; ölçüm kodu hazır. (Kolay, ~2 saat)
3. **R2.3 — 40 karenin tespitlerini önceden hesapla.** Tip kontrollerinin ve "ağır araç yok" raporlarının
   önündeki tek engel; demoyu da hızlandırır. (Kolay, ~1 saat)
4. **R6.2 + R6.8 — Olumsuzluk ve yokluk iddiaları.** "Ağır araç yok" raporunun tersine okunması düzeltilmeli.
   (Kolay–Orta, ~3 saat)
5. **R8.1 + R8.3 — Bütçe kontrolü ve sayı doğrulayıcı.** Canlı demoda bütçenin bitmesi ve uydurma sayı en
   pahalı iki risk. (Orta, ~4 saat)
6. **R6.10 + R8.4 + R10.1 — Admiralty kodları brief'te ve rapor ekranında.** Jüriye "standartları temel
   aldık" mesajı. (Orta, ~6 saat)
7. **R9.1 — Operatör onayı / itirazı.** "Sistem kendi başına karar veriyor mu?" sorusuna doğrudan cevap.
   (Orta, ~4 saat)
8. **Kalanlar:** R2.1, R2.2, R2.4, R3.2, R4.1, R4.2, R5.3, R8.2, R9.2, R10.2 — zaman kalırsa.

Yapılmaması önerilen: R1.1 (kare→bölge ataması zaten doğru).
