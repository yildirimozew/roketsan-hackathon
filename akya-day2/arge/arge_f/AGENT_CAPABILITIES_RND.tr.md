# Agent Temeli ve Yetenekleri — Ar-Ge Listesi (Türkçe)

> Bu dosya `AGENT_CAPABILITIES_RND.md` dosyasının Türkçe karşılığıdır. İki dosya çelişirse İngilizce olan
> esas alınır (repo kuralı: dokümanlar İngilizce). Kod adları, alan adları ve ID'ler olduğu gibi
> bırakılmıştır.

SENTINEL agent'ı için çıkarılan tüm Ar-Ge maddeleri, analiz akışının çalıştığı sırayla listelenmiştir.
Her maddede şunlar var: kodun bugün nerede olduğu, maddenin neden önemli olduğu, ne kadar zor olduğu,
teknik olarak nasıl çalıştığı ve herkesin anlayabileceği bir açıklama.

- **Kaynaklar:** bu klasördeki `STAGE2_DESIGN_NOTES.md`, `schemas.py` ve `prompts.py`. Karşılaştırma
  `docs/AGENT_DESIGN.md`, `PLAN.md` ve 2026-09-26 tarihli backend koduyla yapıldı.
- **Ölçümler:** `data/` içindeki gerçek dosyalarda yapıldı. Detection cache'i ve model ağırlıkları
  repoda olmadığı için tespit gerektiren ölçümlerde, çekim anında kare içinde kalan track noktaları
  tespit yerine kullanıldı (hepsi `car` etiketli). Bu, dedektör için en iyimser senaryodur ve araç
  tipinden gelen puanlar dahil değildir.
- **Mevcut kodla ilişkisi:** buradaki maddeler mevcut pipeline'ı genişletir, onun yerine geçmez.

---

## Alınmış kararlar (2026-09-26)

| Konu | Karar | Bu listeye etkisi |
|---|---|---|
| Orkestrasyon | **Sadece pipeline.** Sabit 8 adımlı durum makinesi kalır; ana akışta LLM tool-calling döngüsü olmaz | Tasarım notlarında "agent karar verir" denen her şey bir pipeline adımı içinde deterministik kurala dönüşür. LLM yalnızca 6. ve 8. adımlarda iyileştirme yapar |
| "Kanıt yetersiz" (BELIRSIZ) | **Seviye değil, bayrak.** `RiskLevel` `LOW / MEDIUM / HIGH / CRITICAL` olarak kalır | Kanıt yetersizse `uncertainties` alanına bir satır eklenir ve `recommended_action = VERIFY` olur |
| Aldatma | **+1 seviye.** Tehdidi düşüren bir beyanın ("dost", "ikmal", "bizim devriye") doğrulanabilir kısmı verimizle çelişirse, aracın seviyesi bir kademe artar | `docs/AGENT_DESIGN.md` §3 adım 6'daki "çelişen raporlar yok sayılır" kuralı aynı değişiklikte güncellenmeli |
| Veri yolu | Şimdilik olduğu gibi bırakıldı | Bu listede ele alınmıyor |

## Zorluk ölçeği

| Seviye | Tek geliştirici için anlamı |
|---|---|
| **Trivial** | < 1 saat, tek fonksiyon, sözleşme değişikliği yok |
| **Easy** | 1–3 saat, bir modül + testler, belki yeni opsiyonel alanlar |
| **Medium** | Yarım gün; birkaç modül veya public contract değişikliği (domain model → OpenAPI → `gen-types` → UI) |
| **Hard** | Bir gün veya fazlası; yeni harici bağımlılık, model çalışması ya da demoyu bozma riski yüksek |

**Durum etiketleri:** Done (bitti) · Partial (kısmen) · Missing (yok) · Dropped (elendi).
**Öncelik:** P1 = demonun doğruluğunu değiştirir, P2 = kaliteyi belirgin artırır, P3 = olsa iyi olur.

---

## Genel bakış

| # | Madde | Durum | Zorluk | Öncelik |
|---|---|---|---|---|
| **F** | **Temeller** | | | |
| F1 | Her yerde kanıt ID'leri | Partial | Easy | P1 |
| F2 | Ortak geometri modülü | Done | – | – |
| F3 | LLM istemcisi (cache, retry, bütçe) | Missing | Medium | P1 |
| F4 | Kademeli bozulma modları | Partial | Easy | P1 |
| F5 | Senaryo / adversarial testler | Partial | Easy | P1 |
| **1** | **load_frame** | | | |
| 1.1 | Kare bağlam paketi | Partial | Easy | P2 |
| 1.2 | Metadata bütünlük kontrolleri | Missing | Trivial | P2 |
| 1.3 | Dağılım dışı / görüntü kalitesi bayrağı | Missing | Easy | P3 |
| 1.4 | Kutupsal konum: sektör + halka | Missing | Trivial | P2 |
| 1.5 | Kapsama kaydı (footprint, GSD) | Partial | Easy | P2 |
| 1.6 | Kör nokta eşiği | Missing | Trivial | P3 |
| 1.7 | Üsse bakan kenar | Missing | Easy | P3 |
| 1.8 | Sektör kardeşleri | Missing | Easy | P3 |
| **2** | **detect** | | | |
| 2.1 | Hafif / ağır / bilinmeyen sınıflar | Missing | Trivial | P2 |
| 2.2 | Kalite metriği olarak track recall + model seçimi | Missing | Easy | P1 |
| 2.3 | Track rehberli tespit ve yerel yeniden tespit | Missing | Medium | P2 |
| 2.4 | Güven kalibrasyonu | Missing | Medium | P3 |
| 2.5 | Küçük kutularda kör nokta bayrağı | Missing | Trivial | P3 |
| 2.6 | Dedektör karnesi | Missing | Medium | P3 |
| 2.7 | Open-set filtresi | Missing | Hard | P3 |
| 2.8 | Ensemble uyuşmazlığı | Missing | Medium | P3 |
| 2.9 | Baskın renk | Missing | Easy | P3 |
| **3** | **georeference** | | | |
| 3.1 | Resmi formül + tersi | Done | – | – |
| 3.2 | Veriye göre kalibre edilmiş hata yarıçapı | Missing | Easy | P2 |
| 3.3 | Belgelenmiş projeksiyon varsayımı | Done | – | – |
| **4** | **match_tracks** | | | |
| 4.1 | Hungarian eşleme + veriye dayalı kapı | Partial | Easy | P2 |
| 4.2 | İki geçişli eşleme | Missing | Easy | P3 |
| 4.3 | Belirsizlik testi + "karar etkilenmedi" kontrolü | Partial | Easy | P2 |
| 4.4 | Eşleşmeyen nesneler için hipotezler | Partial | Easy | P1 |
| 4.5 | Yön tutarlılığıyla eşitlik bozma | Missing | Easy | P3 |
| **5** | **analyze_motion** | | | |
| 5.1 | Gürültüye duyarlı hareket / durma ayrımı | Partial | Easy | P1 |
| 5.2 | Üs merkezli geometri (sweep, en yakın geçiş, son 30 dk) | Missing | Easy | **P1** |
| 5.3 | Popülasyon yüzdelikleri | Missing | Easy | P1 |
| 5.4 | Davranış etiketleri | Missing | Easy | P2 |
| 5.5 | Raporlarla ortak hareket sözlüğü | Missing | Trivial | P2 |
| 5.6 | Aralık olarak ETA | Partial | Trivial | P3 |
| 5.7 | Fiziksel olabilirlik kontrolü | Missing | Trivial | P3 |
| 5.8 | Eşleşmeyen track'ler için hareket analizi | Missing | Easy | P1 |
| **6** | **assess_reports** | | | |
| 6.1 | Ayrıştırıcı: olumsuzluk, bölge temiz, kalıplar | Partial | Easy | P1 |
| 6.2 | Toleranslı rapor saati hizalaması | Partial | Trivial | P2 |
| 6.3 | Atomik iddia kontrolleri | Partial | Medium | P2 |
| 6.4 | Yön kontrolü ("üsse doğru") | Missing | Easy | P1 |
| 6.5 | Kimlik kuralı + aldatma göstergesi (+1) | Partial | Easy | **P1** |
| 6.6 | Öğrenilen kaynak güvenilirliği | Missing | Easy | P2 |
| 6.7 | Bölge ve genel raporlar | Partial | Medium | P2 |
| 6.8 | Kapsamı dikkate alan kararlar | Partial | Easy | P2 |
| 6.9 | Raporlar arası tutarlılık | Missing | Medium | P3 |
| 6.10 | LLM ile çıkarım + karar | Missing | Medium | P2 |
| 6.11 | Rapor penceresi / yarıçapı ayar olarak | Partial | Trivial | P2 |
| **7** | **score_risk** | | | |
| 7.1 | Eyleme dayalı seviye tanımları | Partial | Easy | P1 |
| 7.2 | Rubriğin hareket kanıtına göre yeniden tasarımı | Partial | Medium | **P1** |
| 7.3 | Aldatma ve kimlik düzelticileri | Missing | Easy | P1 |
| 7.4 | Kanıt yetersizliği bayrağı | Missing | Easy | P2 |
| 7.5 | Karşı-olgusal açıklamalar | Missing | Easy | P2 |
| 7.6 | Belirsiz girdilere karşı sağlamlık | Missing | Medium | P2 |
| 7.7 | Fuzzy kurallar + Dempster–Shafer | Missing | Hard | P3 |
| **8** | **write_brief** | | | |
| 8.1 | Kanıt atıflı LLM brief'i | Missing | Medium | P1 |
| 8.2 | Guard (doğrulayıcı) | Missing | Medium | P1 |
| 8.3 | Kırmızı takım eleştirmeni | Missing | Medium | P2 |
| 8.4 | Brief modeli genişletmeleri | Missing | Easy | P2 |
| 8.5 | Aldatmayı açıkça anlatan ifade | Missing | Easy | P1 |
| **9** | **Tek karenin ötesi** | | | |
| 9.1 | Gün tablosu (40 kare, öncelik listesi, ısı haritası) | Missing | Medium | P2 |
| 9.2 | Analist sohbeti araçları | Missing | Medium | P3 |
| 9.3 | Canlı adım olayları ve çizimler | Partial | Medium | P1 |
| **X** | **Elenen veya ertelenenler** | Dropped | – | – |

---

## F. Temeller

Her adımın dayandığı, akışı kesen ortak parçalar.

### F1. Her yerde kanıt ID'leri
- **Şu anki durum:** Kısmen. Varlıkların ID'leri zaten var (`DET-n`, `TRK-<id>`, `REP-nn`,
  `ZONE-<ad>`). Yedek brief bunları `Brief.evidence_ids` içinde topluyor. Türetilmiş olguların (bir
  hareket özelliği, bir risk faktörü, bir rapor kontrolü) kendi ID'si yok.
- **Neden:** jüri ve mentorlar "doğrulanabilir ve açıklanabilir" olmasını istiyor. Brief doğrulayıcısı
  (8.2) uydurma sayıları ancak her sayı kayıtlı bir olguya bağlanabiliyorsa reddedebilir.
- **Zorluk:** Easy.
- **Teknik:** mevcut önekler korunur; UI'daki `EvidenceChip`, mock'lar ve golden test bunlara bağlı.
  Türetilmiş ID'ler aynı düzende eklenir: `MOT-T0122` (hareket profili), `RISK-DET-1`,
  `CHK-REP-07-activity`. Notlardaki `E12` şeması kullanılmaz. Sadece pipeline modunda tam bir
  "blackboard" deposuna gerek yok: `Analysis` nesnesi zaten kanıt kaydıdır. Sadece bu ID'lere ve bir
  analizin geçerli tüm ID'lerini listeleyen bir yardımcı fonksiyona ihtiyaç var.
- **Kısacası:** son rapordaki her cümle, geldiği ölçüme işaret eden bir etiket taşır. Herkes tıklayıp
  kontrol edebilir.

### F2. Ortak geometri modülü
- **Şu anki durum:** Bitti. `services/geo.py` içinde haversine, yön açısı, yerel doğu/kuzey metre
  (`to_enu_m`), köşe interpolasyonu ve tersi var. Golden test geçiyor.
- **Neden:** herkes için tek bir mesafe fonksiyonu, adımlar arasındaki küçük tutarsızlıkları önler.
- **Zorluk:** –
- **Teknik:** yeni özellikler (sektör, halka, sweep, footprint) üsse ortalanmış `to_enu_m`'yi kullanmalı.
- **Kısacası:** bütün adımlar mesafeyi aynı cetvelle ölçer.

### F3. LLM istemcisi (cache, retry, bütçe)
- **Şu anki durum:** Yok. `agent/llm_client.py` sadece bir protokol tanımlıyor. `Settings.llm_model`
  hâlâ `glm-4` diyor.
- **Neden:** 6. ve 8. adımlar buna ihtiyaç duyuyor. Bütçe $15, dakikada 60 istek, aynı anda 4 istek ve
  model her zaman reasoning yapıyor. Maliyet ve gecikme kontrol altında olmalı.
- **Zorluk:** Medium.
- **Teknik:** `base_url` ile `openai` SDK. Model `glm-5.3-flash`, `reasoning_effort="low"` aktarılır
  (eleştirmen `high` kullanabilir). Timeout, 429/5xx durumunda backoff ile 2 tekrar, eşzamanlılık ≤ 4.
  `sha256(prompt_version + model + input_json)` anahtarlı disk cache'i. Token ve gecikme loglanır.
  Harcama gateway'in `key/info` ucundan okunur. Doğrulama hatasıyla bir onarım denemesi, sonra yedek
  yol (AGENT_DESIGN §6–7).
- **Kısacası:** dil modeline güvenli, ucuz ve tekrarlanabilir biçimde soru sormanın yolu. Aynı soru
  gelirse cevap cache'ten döner, hata olursa tekrar denenir, yine olmazsa şablona düşülür.

### F4. Kademeli bozulma modları
- **Şu anki durum:** Kısmen. Dedektör hatasında `PrecomputedDetector`'a düşülüyor ve adım uyarı
  veriyor. Henüz LLM olmadığı için brief her zaman şablondan geliyor (`generated_by="fallback"`).
- **Neden:** demo sahnede asla çökmemeli.
- **Zorluk:** Easy.
- **Teknik:** modlar açık ve görünür hale getirilir:
  - `full`: LLM açık.
  - `llm_off`: kurallar + şablon.
  - `detector_degraded`: yalnız track ve raporlar, belirsizlik eklenir.
  - `no_tracks`: düşük güven, `VERIFY`.

  Mod analizde saklanır ve rozet olarak gösterilir.
- **Kısacası:** bir parça bozulursa sistem kalanla çalışmaya devam eder ve bunu açıkça söyler.

### F5. Senaryo / adversarial testler
- **Şu anki durum:** Kısmen. Golden test, birim testleri ve kural tabanlı rapor testleri var (40 test).
  Gerçek karelerde aldatma tuzağını kapsayan test yok.
- **Neden:** panel "simülasyon testleri" istedi. Aldatma, vakanın ana teması.
- **Zorluk:** Easy.
- **Teknik:** fixture'lar üzerinde tablo tabanlı testler:
  1. Dolaşan bir araca "dost araç yaklaşıyor" raporu eklenir (`img_006673` / T0043, `img_000926` /
     T0172). Seviyenin düşmediği ve bir kademe arttığı doğrulanır.
  2. Sahte "bölge temiz" raporu → seviye düşmez.
  3. Yanlış araç tipi → CONTRADICTED.
  4. Prompt injection → UNVERIFIED, güven 0.

  Testlerde gerçek LLM kullanılmaz (`FakeLLMClient`).
- **Kısacası:** demodan önce sistemi bilerek kandırmaya çalışır, kanmadığını kanıtlarız.

---

## 1. load_frame

Notlardaki `open_image` ve `place_on_map` adımlarını kapsar. Buradaki her şey kareyle ilgili
deterministik metadatadır.

### 1.1 Kare bağlam paketi
- **Şu anki durum:** Kısmen. `ImageMeta` boyut, saat, köşeler ve bölgeyi içeriyor. Bu çekim saatinde
  biten track'lerin listesi daha sonra, `match_tracks` içinde hesaplanıyor ve sadece kare içindekiler
  tutuluyor (`TrackSnapshot`).
- **Neden:** "bu karede N araç bekleniyor" bilgisini baştan bilmek, 2. adımın kendini kontrol etmesini
  sağlar. Beklenen 6 aracın 1'ini bulan bir dedektör bu karede zayıf demektir.
- **Zorluk:** Easy.
- **Teknik:** 1. adımda son noktası çekim saatine eşit olan track'ler listelenir. Her çekim saati
  benzersiz olduğundan bu, karenin 3–10 track'ini belirler. Track'ler kare içi ve dışı olarak ayrılır,
  zaman penceresindeki raporlar sayılır. Bunlar `StepResult.data` içine yazılır ve bir
  `expected_vehicles` alanı eklenir.
- **Kısacası:** sistem daha resme bakmadan içinde kaç hareketli araç olması gerektiğini bilir.

### 1.2 Metadata bütünlük kontrolleri
- **Şu anki durum:** Yok.
- **Neden:** pikselden koordinata formül yalnızca köşeler eksenlere hizalı ve pikseller kare ise
  geçerlidir. Bozuk bir metadata satırı araçları sessizce yanlış yere koyar.
- **Zorluk:** Trivial.
- **Teknik:**
  - Kontroller: dosya var mı, görüntü boyutu meta ile aynı mı, köşeler hizalı mı, GSD x/y ≈ 1 mi
    (40 karenin hepsinde 0.99 ölçüldü), saat biçimi doğru mu.
  - Hata olursa adım `warning` verir ve bozulma moduna geçilir.
- **Kısacası:** karenin harita bilgisine güvenilip güvenilemeyeceğine hızlıca bakılır.

### 1.3 Dağılım dışı / görüntü kalitesi bayrağı
- **Şu anki durum:** Yok.
- **Neden:** dedektör Aşama 1 görüntüleriyle eğitildi.
  - Üç 1920×1080 kare (`img_003880`, `img_003189`, `img_000267`), o çözünürlükteki Aşama 1 p95 değeri
    olan 145'e kıyasla çok daha parlak (182–187).
  - Bir kare karanlık (`img_008589`).
  - Böyle karelerde tespitlere daha az güvenilmeli.
- **Zorluk:** Easy.
- **Teknik:** parlaklık ve kontrastın aynı çözünürlükteki Aşama 1 dağılımına göre z-skorları (eski
  repodaki `image_features_v1.csv`). Laplacian varyansıyla bulanıklık ve aşırı pozlama oranı eklenir.
  |z| > 2 ise bayrak kalkar. Sadece piksel istatistiği, model yok.
- **Kısacası:** sistem, bir fotoğrafın dedektörün öğrendiklerine benzemediğini fark eder ve güvenini
  düşürür.

### 1.4 Kutupsal konum: sektör + halka
- **Şu anki durum:** Yok. Karenin bölgesi, merkezi en yakın olan bölgedir.
- **Neden:** kareler üssün çevresinde tam olarak 8 sektör × 5 halkalık bir ızgara oluşturuyor
  (~1.7 / 2.6 / 3.5 / 4.4 / 5.3 km). Halka, risk kuralları için doğal bir "üsse ne kadar yakın"
  girdisidir (seviye tanımlarında "halka 1" geçiyor). UI için de katmanlı savunma dili sağlar.
- **Ölçülen:** en yakın merkezli bölge ile yön sektörü **40/40** karede aynı. Yani bölge atamasının
  kendisinin değişmesi gerekmiyor.
- **Zorluk:** Trivial.
- **Teknik:** `ImageMeta`'ya `sector_index`, `bearing_from_base_deg`, `ring` ve `base_distance_km`
  eklenir. Alanlar opsiyonel → `gen-types`.
- **Kısacası:** her fotoğrafa "doğu, birinci halka" gibi bir adres verilir. Hangi yönde ve üsse ne
  kadar yakın olduğu bir bakışta anlaşılır.

### 1.5 Kapsama kaydı (footprint, GSD)
- **Şu anki durum:** Kısmen. Karenin metre cinsinden genişliği ve yüksekliği 3. adımda hesaplanıyor
  (`frame_size_m`). Footprint poligonu veya GSD alanı yok.
- **Neden:** 6. adımın bir rapor konumunun bu karede gerçekten görünüp görünmediğini bilmesi gerekiyor.
  "Baktık, bir şey yok" (çelişiyor) ile "bakamadık" (doğrulanamaz) farklı şeylerdir.
- **Zorluk:** Easy.
- **Teknik:** footprint poligonu (TL, TR, BR, BL), `gsd_m_per_px` (x, y) ve çekim saati tutulur. 6. adım
  için bir `covers(point, time)` yardımcısı sağlanır.
- **Kısacası:** bu fotoğrafın yerde tam olarak hangi alanı gösterdiği kaydedilir. Böylece dışında kalan
  bir şeyi "gördük" demeyiz.

### 1.6 Kör nokta eşiği
- **Şu anki durum:** Yok.
- **Neden:** 200 px² tespit tabanı yerde 2.3–7.9 m²'ye denk geliyor. Bir otomobil ~8 m² olduğu için
  kaba çözünürlüklü karelerde otomobiller bile sınıra yakın, motosikletler hiç sayılmıyor.
- **Zorluk:** Trivial.
- **Teknik:** `min_detectable_area_m2 = 200 × gsd_x × gsd_y` kare başına saklanır, 2.5 ve 4.4'te
  kullanılır.
- **Kısacası:** sistem her fotoğrafta görebileceği en küçük şeyi bilir ve daha küçük araçları
  kaçırabileceğini kabul eder.

### 1.7 Üsse bakan kenar
- **Şu anki durum:** Yok.
- **Neden:** UI'da üsse doğru oklar gösterilebilir. "Üs tarafından girdi" gibi bir ifade brief'te işe
  yarar.
- **Zorluk:** Easy.
- **Teknik:** kare merkezinden üsse yön açısı → 8 kenar/köşeden biri.
- **Kısacası:** fotoğrafın üzerinde üssün hangi yönde olduğunu gösteren bir ok.

### 1.8 Sektör kardeşleri
- **Şu anki durum:** Yok.
- **Neden:** esas olarak gün tablosu (9.1) için: aynı yöndeki diğer kareler ve ne zaman çekildikleri.
- **Zorluk:** Easy.
- **Teknik:** aynı `sector_index`'e sahip kareler, halkaya göre sıralı, çekim saatleriyle birlikte.
- **Kısacası:** "aynı yöne bakan diğer fotoğraflar".

---

## 2. detect

Görüntü modelinin çalıştığı tek adım.

### 2.1 Hafif / ağır / bilinmeyen sınıflar
- **Şu anki durum:** Yok. Tespitler ince bir etiket (`car`, `van`, `truck`, `bus`) ve güven değeri
  taşıyor.
- **Neden:** raporların kendisi "ağır araç" diyor ve küçük kutularda ince sınıflar güvenilmez. Hafif/ağır
  düzeyinde karşılaştırmak yanlış çelişkileri önler.
- **Zorluk:** Trivial.
- **Teknik:** `Detection`'a `super_class` (car+van → light, truck+bus → heavy) ve `class_decision`
  (`fine | super | unknown`) eklenir. Rapor tip kontrolü truck/bus'ı zaten aynı aile sayıyor
  (`_same_kind`); `super_class`'ı kullanacak şekilde değiştirilir.
- **Kısacası:** kamyon mu otobüs mü emin değilsek bile güvenle "ağır araç" deriz.

### 2.2 Kalite metriği olarak track recall + model seçimi
- **Şu anki durum:** Yok. Canlı dedektör conf 0.35 / imgsz 960 ile tek bir `.pt` dosyası kullanıyor.
  Hangi ağırlık dosyasının ardahan'ın RFS YOLO11m'i olduğu doğrulanmadı (`Downloads/`:
  `hakan_yolo11m.pt`, `yolo11l_ardahan.pt`, `last.pt`, `last (1).pt`).
- **Neden:** 40 Aşama 2 karesinin etiketi yok (Kaggle setlerinde değiller). Ama 206 track uç noktası
  kendi karesinin içinde ve her biri gerçek, hareketli bir aracı işaret ediyor. Bu, model, eşik ve TTA
  seçimi için etiketsiz bir recall ölçüsü verir.
- **Zorluk:** Easy.
- **Teknik:** her aday yapılandırma için 40 kare çalıştırılır ve kapı içinde bir kutuyla karşılanan kare
  içi track noktaları sayılır. Recall çözünürlük bazında raporlanır. Yapılandırma seçilir, sonra
  `make detections` ile cache'lenir.
- **Kısacası:** araç rotaları arabaların gerçekte nerede olduğunu söylüyor. Böylece tek bir fotoğrafı
  elle etiketlemeden her dedektöre not verebiliriz.

### 2.3 Track rehberli tespit ve yerel yeniden tespit
- **Şu anki durum:** Yok.
- **Neden:** bir track noktasının tam üzerindeki düşük güvenli kutu neredeyse kesin gerçek bir araçtır.
  Kutusu olmayan bir track noktası muhtemelen kaçırılmış bir araçtır.
- **Zorluk:** Medium. `Detector` protokolünde değişiklik gerekiyor.
- **Teknik:**
  1. Düşük eşikle (ör. 0.05) çalıştırılır, kutular `candidate` olarak tutulur.
  2. Çekim anındaki bir track noktasının kapısı içindeki aday `fact`'e yükseltilir.
  3. Kutusu olmayan kare içi bir track noktası için, çevresindeki kesit üzerinde yeniden çalıştırılır
     (düşük eşik, opsiyonel SAHI döşeme), kare başına en fazla 2 kez.
  4. Sadece pipeline modunda tetikleyici LLM kararı değil bir kuraldır: kare içinde öksüz track ya da
     kare içinde rapor çelişkisi.

  `PrecomputedDetector` yeniden tespit yapamaz, sadece "mevcut değil" bildirir.

  **Risk:** döngüsel kanıt. Track, yalnızca track sayesinde tutulmuş bir kutuyu "doğrulamış" olur. Bu
  kutular işaretlenir (`from_local_redetect`, `promoted_by_track`) ve o track'in bağımsız teyidi olarak
  asla sayılmaz.
- **Kısacası:** rota verisi "burada bir araba olmalı" dediğinde sistem tam o noktaya daha dikkatli
  yeniden bakar.

### 2.4 Güven kalibrasyonu
- **Şu anki durum:** Yok.
- **Neden:** ham YOLO skorları olasılık değildir. Kalibre edilmiş 0.8, "%80 oranında doğru" anlamına
  gelmeli.
- **Zorluk:** Medium.
- **Teknik:** Aşama 1 doğrulama tahminleri üzerinde sınıf başına isotonic regresyon.
  `confidence_raw` ve `confidence_calibrated` saklanır.
- **Kısacası:** dedektörün iç skorunu dürüst bir "ne kadar eminiz" değerine çeviririz.

### 2.5 Küçük kutularda kör nokta bayrağı
- **Şu anki durum:** Yok.
- **Neden:** 200 px² tabanına yakın bir kutunun sınıfı güvenilmez.
- **Zorluk:** Trivial.
- **Teknik:** `near_blind_threshold = area_px < 1.5 × 200` → `class_decision = super`.
- **Kısacası:** çok küçük araçlara bir not düşülür: "bir şey görüyoruz ama tam olarak ne olduğunu
  söyleyemiyoruz".

### 2.6 Dedektör karnesi
- **Şu anki durum:** Yok.
- **Neden:** operatöre ve brief'e dedektörün bu tür karede (çözünürlük, karanlık) ne kadar iyi olduğunu
  söyler.
- **Zorluk:** Medium.
- **Teknik:** Aşama 1 doğrulamasından katman başına sınıf AP'si. Karanlık katmanlarda yalnızca 1–6
  görüntü var, bu yüzden genel değere doğru çekilir: `AP = (n·AP_katman + k·AP_genel)/(n + k)`. Adım
  çıktısına eklenir.
- **Kısacası:** bu tür fotoğraf için dedektörün küçük bir "karnesi".

### 2.7 Open-set filtresi
- **Şu anki durum:** Yok.
- **Neden:** üç tekerlekliler, motosikletler ve başka nesneler zorla 4 sınıftan birine sokuluyor.
- **Zorluk:** Hard.
- **Teknik:** kesit embedding'leri (mevcut `ardahan_embedding.pt` veya ConvNeXt reranker). Sınıf
  prototiplerine kosinüs benzerliği; düşük skor → `unknown`.
- **Kısacası:** dedektör "bu tanıdığım araçlardan biri değil" demeyi öğrenir.

### 2.8 Ensemble uyuşmazlığı
- **Şu anki durum:** Yok.
- **Neden:** iki model bir kutu üzerinde anlaşamıyorsa o kutu belirsizdir.
- **Zorluk:** Medium. İki model = iki kat çıkarım süresi.
- **Teknik:** modeller arasında IoU × sınıf uyumu → `ensemble_agreement` 0–1.
- **Kısacası:** iki dedektöre sorulur. Anlaşamıyorlarsa dikkatli olunur.

### 2.9 Baskın renk
- **Şu anki durum:** Yok.
- **Neden:** bazı raporlar renk belirtiyor ("mavi araç", "sarı araç").
- **Zorluk:** Easy.
- **Teknik:** kutu kesiti üzerinde k-means veya HSV histogramı → rapor ayrıştırıcısının renkleriyle
  eşleşen küçük bir renk sözlüğü.
- **Kısacası:** sistem her aracın rengini not eder ve renk söyleyen raporları kontrol edebilir.

---

## 3. georeference

### 3.1 Resmi formül + tersi
- **Şu anki durum:** Bitti. Kutu merkezi + doğrusal köşe interpolasyonu ve tersi (Newton). Golden
  kontrol `img_000860` → (39.925313, 32.871833) sonucunu üretiyor; bu nokta T0122'ye **0.02 m**
  uzaklıkta. Track noktaları tam olarak bu formülle üretilmiş.
- **Neden:** –
- **Zorluk:** –
- **Teknik:** homography'ye veya alt-orta noktaya geçilmemeli; bu eşlemeyi bozar. PDF örneği
  (`img_000123` → 39.94439, 32.86350) ikinci bir birim testi olarak eklenir.
- **Kısacası:** pikselden harita konumuna dönüşüm çalışıyor ve organizatörün örneğiyle birebir tutuyor.

### 3.2 Veriye göre kalibre edilmiş hata yarıçapı
- **Şu anki durum:** Yok.
- **Neden:** her konuma dürüst bir belirsizlik verir ve 4. adıma tahmine değil veriye dayalı bir kapı
  sağlar.
- **Zorluk:** Easy (dedektör 2.2 ile sabitlendikten sonra).
- **Teknik:** eşleşmiş kutu merkezleri ile track noktaları arasındaki mesafeler → çözünürlük başına
  p50 / p95. Tespit başına `error_radius_m` = p95 (veya `0.5 × kutu köşegeni × GSD`, hangisi büyükse).
- **Kısacası:** "bu araç burada, artı eksi N metre" deriz. N gerçek veriden ölçülür.

### 3.3 Belgelenmiş projeksiyon varsayımı
- **Şu anki durum:** Bitti. Brief her zaman "eğik kareler tepeden görünüm gibi işlendi" belirsizliğini
  listeliyor. PLAN ve AGENT_DESIGN bu kararı kaydediyor.
- **Neden:** mentorlar eğik görüntülerin neden düzeltilmediğini soracak.
- **Zorluk:** –
- **Teknik:** gerekçe olarak 0.02 m sonucu eklenir: veri sözleşmesi doğrusal merkez formülünü kullanıyor.
- **Kısacası:** fotoğrafları neden tam tepeden çekilmiş gibi ele aldığımızı açıkça anlatırız.

---

## 4. match_tracks

### 4.1 Hungarian eşleme + veriye dayalı kapı
- **Şu anki durum:** Kısmen. Global bire bir eşleme var (`scipy.linear_sum_assignment`). Kapı 25 m ve
  ikinci en yakın mesafe tutuluyor.
- **Neden:** kare içi track uç noktaları birbirine yakın: en yakın komşu mesafesi en az 1.7 m, p5
  3.1 m, medyan 17 m; 31 noktanın 5 m içinde bir komşusu var. Geniş bir kapı araçların kimlik
  değiştirmesine yol açar.
- **Zorluk:** Easy.
- **Teknik:** sabit 25 m yerine 3.2'den gelen `gate = max(3 m, error_radius_m)` kullanılır (tespit veya
  çözünürlük başına). `match_max_m` `Settings` içinde üst sınır olarak kalır. Golden test (T0122 < 1 m,
  ikinci T0032 ≈ 41 m) geçerli kalır.
- **Kısacası:** fotoğraftaki her araba onu en iyi açıklayan rotayla eşleşir, fazla uzak eşleşmeler
  reddedilir.

### 4.2 İki geçişli eşleme
- **Şu anki durum:** Yok. 2.3'e bağlı (aday ve olgu kutular).
- **Neden:** güvenli kutular track'leri önce almalı. Zayıf kutular yalnızca kalanları alabilir.
- **Zorluk:** Easy.
- **Teknik:** 1. geçiş `fact` kutuları eşler. 2. geçiş `candidate` kutuları kalan track noktalarına
  eşler. Eşleşen aday `fact` olur. `pass_no` kaydedilir.
- **Kısacası:** emin olunan tespitler rotalarını önce seçer, şüpheliler kalanlarla yetinir.

### 4.3 Belirsizlik testi + "karar etkilenmedi" kontrolü
- **Şu anki durum:** Kısmen. `TrackMatch.confidence` (high/medium/low) mesafeyi ve ikinci track'e olan
  farkı kullanıyor. Açık bir "ambiguous" durumu ve belirsizliğin sonucu değiştirip değiştirmediği
  kontrolü yok.
- **Neden:** operatörün iki durumu ayırabilmesi gerekiyor: "bu arabanın hangi rotaya ait olduğundan
  emin değiliz ama cevabı değiştirmiyor" ile "…ve cevabı değiştiriyor".
- **Zorluk:** Easy (sağlamlık kısmı 7.6'da).
- **Teknik:**
  - Lowe oranı `d1/d2 > 0.7` ise `status = ambiguous` olur ve `alternatives` listesi tutulur.
  - 7. adım iki alternatifi de puanlar. Kare seviyesi aynıysa "belirsiz ama karar etkilenmedi" yazılır.
  - Farklıysa yüksek seviye seçilir ve bir belirsizlik eklenir.
- **Kısacası:** aynı arabaya iki rota uyuyorsa ikisini de kontrol ederiz. İkisi aynı sonuca çıkıyorsa
  bunu söyleriz, çıkmıyorsa güvenli olanı seçeriz.

### 4.4 Eşleşmeyen nesneler için hipotezler
- **Şu anki durum:** Kısmen. Tespiti olmayan kare içi track'ler `matched_detection_id = None` ile
  `TrackSnapshot` olarak listeleniyor. Eşleşmeyen tespitler `track_id = None` ve bir "no track" faktörü
  alıyor. Hiçbirine açıklama verilmiyor.
- **Neden:** en tehlikeli araç dedektörün kaçırdığı veya fotoğrafın hemen dışında kalan araç olabilir.
  Ölçülen: 226 track uç noktasının 20'si kendi karesinin kenarından 7–26 m dışarıda. Bugün bu araçlar
  risk skoruna hiç katılmıyor.
- **Zorluk:** Easy.
- **Teknik:**
  - Tespiti olmayan track: `missed` (kare içinde → 2.3'ü tetikler), `blind_spot` (düşük GSD'li kare,
    1.6) veya `outside_near_edge` (≤ 30 m dışarıda).
  - Track'i olmayan tespit: `parked_likely` (park halindeki arabaların track'i yok) veya
    `false_positive_likely` (düşük güven, kör nokta eşiğine yakın).
  - Öksüz track'ler 5. adıma gider (bkz. 5.8).
- **Kısacası:** rotası olmayan her araba ve arabası olmayan her rota için sistem, sessizce görmezden
  gelmek yerine en olası nedeni söyler.

### 4.5 Yön tutarlılığıyla eşitlik bozma
- **Şu anki durum:** Yok.
- **Neden:** yakın iki track arasındaki eşitliği bozabilir.
- **Zorluk:** Easy.
- **Teknik:** kutunun uzun ekseni track yönüyle karşılaştırılır. Yalnızca oran testi `ambiguous`
  dediğinde kullanılır.
- **Kısacası:** rotayla aynı yöne bakan araba daha iyi eşleşmedir.

---

## 5. analyze_motion

Mevcut sistemin ölçülmüş zayıf noktası (bkz. 7.2).

### 5.1 Gürültüye duyarlı hareket / durma ayrımı
- **Şu anki durum:** Kısmen. Durma, 1.0 m/s'den yavaş adımların ≥ 10 dk süren dizisi olarak
  tanımlanmış. 1.0 m/s = 5 dakikalık adımda 300 m.
- **Ölçülen:** 5 dakikalık adımların %57'si 5 m'nin altında hareket ediyor (GPS titreşimi düzeyi), ama
  mevcut eşik adımların **%76'sını** "durma" sayıyor. Her 5 dakikada 250 m ilerleyen bir araç park
  etmiş sayılıyor.
- **Neden:** "hareket ediyor mu, duruyor mu" rapor doğrulamanın özüdür ("araç üsse doğru geliyor" ile
  hareket etmeyen bir araç).
- **Zorluk:** Easy.
- **Teknik:** mevcut `stops` korunur (golden testteki ≈40 ve ≈45 dk'lık duraklamalar buna göre
  kalibre). Yanına ayrı bir kavram eklenir:
  - `moving` = adım > 5 m (gürültü tabanı).
  - Hız yalnızca hareketli adımlardan hesaplanır.
  - Bekleme listesi.
  - `moving_share`.
  - Son 30 dakika özeti.
- **Kısacası:** "gerçekten duruyor" ile "küçük GPS kıpırtısı"nı, "yavaş gidiyor" ile "park etmiş"i
  birbirinden ayırırız.

### 5.2 Üs merkezli geometri (sweep, en yakın geçiş, son 30 dk)
- **Şu anki durum:** Yok. Şu an / 30 / 60 dk önceki mesafe, en küçük mesafe, yaklaşma hızı ve yön–üs
  açısı var. Dolaşmayla ilgili hiçbir şey yok.
- **Ölçülen:**
  - "2 saatte 0.8 km'den fazla yaklaşma" 226 track'in **129'unda** doğru, yani yaklaşma **ayırt edici
    değil**. Bu yapısal bir durum, çünkü bütün kareler üsse 1.6–5.4 km uzaklıkta.
  - 41 track üssün etrafında 90°'den fazla dolaşıyor.
  - Dördü öne çıkıyor: T0043 441°, T0158 323°, T0172 549°, T0198 320°. Her biri üsse < 0.9 km
    yaklaşmış ve son 30 dakikada 1.8–2.5 km içeri girmiş.
- **Neden:** dolaşma + yakın geçiş, bu verideki gerçek tehdit sinyali. Bu olmadan rubrik yanlış aracı
  seçiyor (bkz. 7.2).
- **Zorluk:** Easy.
- **Teknik:**
  - `sweep_deg` = üs etrafındaki yön değişimlerinin **net işaretli** toplamı. Mutlak değişimlerin
    toplamı kullanılmaz: yoksa sadece ileri geri giden T0047 1029° alır (net değeri 60°).
  - `closest_ever_m` ve `closest_ever_time`.
  - `inward_last30_m`.
  - Radyal hız.
- **Kısacası:** sadece "yaklaşıyor mu?" diye sormak yerine şunları sorarız: üssün etrafında dönüyor mu,
  en fazla ne kadar yaklaştı, son dakikalarda hızla içeri girdi mi?

### 5.3 Popülasyon yüzdelikleri
- **Şu anki durum:** Yok.
- **Neden:** sabit eşikler ("> 20 m/dk") keyfidir. "Bugünkü araçların %98'inden fazla dolaştı" ifadesi
  kendini açıklar ve sağlamdır.
- **Zorluk:** Easy.
- **Teknik:** 226 track'in özellikleri açılışta bir kez hesaplanır (veya cache'te
  `population_features.csv` olarak dondurulur). `sweep`, `closest_ever`, `inward_last30`,
  `approach_rate` ve `moving_share` yüzdelikleri track başına `MotionProfile.population_percentiles`
  içinde saklanır.
- **Kısacası:** her araç günün diğer bütün araçlarıyla karşılaştırılır. "Sıra dışı", birinin tahminine
  göre değil bu veriye göre sıra dışı demektir.

### 5.4 Davranış etiketleri
- **Şu anki durum:** Yok.
- **Neden:** kısa etiketler operatörün ilk göz attığı şeydir ve brief de bunları kullanabilir.
- **Zorluk:** Easy.
- **Teknik:** 5.1–5.3 üzerinde kurallar: `approaching`, `loitering`, `circling`, `waiting`,
  `stop_and_go`, `transit`, `leaving`.
- **Kısacası:** her araç için "dolaşıyor" ya da "bekliyor" gibi bir iki kelime.

### 5.5 Raporlarla ortak hareket sözlüğü
- **Şu anki durum:** Yok. Rapor ayrıştırıcısının kendi hareket kelimeleri var (`moving`, `stationary`,
  `loading`), hareket analizinde ise "şu anki durum" yok.
- **Neden:** raporu veriyle karşılaştırmak, ikisi aynı kelimeleri aynı tanımlarla kullanırsa işe yarar.
- **Zorluk:** Trivial.
- **Teknik:** 5.1'den `state_now ∈ {moving, stopped, parked}` üretilir. Rapordaki `activity` aynı kümeye
  eşlenir.
- **Kısacası:** rapor ve sensör aynı dili konuşur, böylece karşılaştırılabilirler.

### 5.6 Aralık olarak ETA
- **Şu anki durum:** Kısmen. Yaklaşıyorsa tek bir ETA = mesafe / son 10 dk hızı.
- **Neden:** dur-kalk trafikte tek bir sayı yanıltıcıdır.
- **Zorluk:** Trivial.
- **Teknik:** son hareketli segmentlerin en yavaş ve en hızlısıyla bir aralık verilir. Sabit hız /
  Kalman projeksiyonu bu veri için reddedildi.
- **Kısacası:** yanıltıcı derecede kesin bir "17 dakika" yerine "10–25 dakikada gelebilir".

### 5.7 Fiziksel olabilirlik kontrolü
- **Şu anki durum:** Yok.
- **Neden:** bozuk veya sahte track'leri yakalar. Ölçülen: en fazla 9.3 m/s, bugün imkânsız sıçrama yok.
- **Zorluk:** Trivial.
- **Teknik:** ~40 m/s'yi aşan adımlar veya konum sıçramaları işaretlenir.
- **Kısacası:** bir araba ışınlanmış gibi görünüyorsa inanmak yerine veriyi işaretleriz.

### 5.8 Eşleşmeyen track'ler için hareket analizi
- **Şu anki durum:** Yok. Hareket yalnızca bir tespitle eşleşen track'ler için hesaplanıyor.
- **Neden:** dedektörün kaçırdığı veya karenin hemen dışında kalan dolaşan bir araç (4.4) yine de
  tehdittir.
- **Zorluk:** Easy.
- **Teknik:** `missed` veya `outside_near_edge` hipotezli öksüz track'ler için 5.1–5.4 çalıştırılır.
  Bunlar 7. adıma "görüntüde görülmedi" belirsizliğiyle, yalnız track'i olan araçlar olarak girer.
- **Kısacası:** kamera kaçırdı diye bir araç zararsız hale gelmez.

---

## 6. assess_reports

### 6.1 Ayrıştırıcı: olumsuzluk, bölge temiz, kalıplar
- **Şu anki durum:** Kısmen. Kural tabanlı çıkarıcı koordinatları, bölge adlarını, araç kelimelerini,
  renkleri, hareketi ve iddia türünü (`SIGHTING`, `ALL_CLEAR`, `FRIENDLY_PRESENCE`, `TRAFFIC_NORMAL`,
  `OTHER`) buluyor.
  - 137 raporda ölçülen: 57 SIGHTING, 22 FRIENDLY_PRESENCE, 10 TRAFFIC_NORMAL, 8 ALL_CLEAR, 40 OTHER.
  - Olumsuzluğu işlemiyor. REP-92 "Kuzeydoğu Kavşağı bölgesinde ağır araç hareketi yok" ağır araç
    *görüldü* olarak ayrıştırılıyor. Orada bir kamyon tespit edilirse kod raporu CORROBORATED sayar,
    oysa rapor tam tersini söylüyor.
- **Neden:** raporlar 34 yüzey kalıbından ve birkaç tekil metinden oluşuyor. Bir kalıp ayrıştırıcısı
  neredeyse hepsini ucuz ve deterministik şekilde kapsar.
- **Zorluk:** Easy.
- **Teknik:**
  - Olumsuzluk kalıpları ("… yok", "görülmedi", "sadece otomobil") → `ALL_CLEAR` / bölge durumu.
  - `UNVERIFIED_TIP` ("dün gece", "ihbar") ve `IRRELEVANT` iddia türleri eklenir.
  - Sözlük: panelvan → van (hafif), ağır araç → heavy, otomobil → car, kamyon → truck.
  - Her eşleşme için bir `template_id` kaydedilir. LLM (6.10) yalnızca uzun kuyruğu işler.
- **Kısacası:** sistem "burada ağır araç yok" cümlesini "burada ağır araç var" olarak değil, bölgenin
  temiz olduğu beyanı olarak okur.

### 6.2 Toleranslı rapor saati hizalaması
- **Şu anki durum:** Kısmen. Varlık kontrolü track'leri zaten raporun kendi saatine göre
  interpolasyonla buluyor. Hareket kontrolü rapor saatinden önceki 5 dakikayı kullanıyor.
- **Neden:** raporlar rapor saatindeki track konumlarından üretilmiş gibi görünüyor: konumlu 72 raporun
  47'sinde o dakikada 60 m içinde bir track var.
- **Zorluk:** Trivial.
- **Teknik:** rapor saatinin ±15 dk çevresi taranır ve en iyi eşleşen durum alınır.
  `track_at_report_time` (track, mesafe, durum, radyal yön) saklanır.
- **Kısacası:** bir raporu fotoğrafın çekildiği an değil, raporun yazıldığı an araçların nerede
  olduğuyla karşılaştırırız.

### 6.3 Atomik iddia kontrolleri
- **Şu anki durum:** Kısmen. Kontroller: `location`, `presence`, `type`, `activity` ve `instructions`.
- **Neden:** bir rapor yarı doğru olabilir (konum doğru, iddia edilen kimlik doğrulanamaz). Parçalara
  ayırmak, doğrulanabilir kısma güvenmemizi ve geri kalanını işaretlememizi sağlar.
- **Zorluk:** Medium (`ReportCheck`'e ve UI çiplerine dokunuyor).
- **Teknik:** `CheckName`'e `count`, `color`, `direction`, `identity` ve `area_status` eklenir. Her biri
  `supported / contradicted / unverifiable` + nasıl + kanıt ID'leri alır. Mevcut karar adları
  (`CORROBORATED / CONTRADICTED / UNVERIFIED / IRRELEVANT`) korunur.
- **Kısacası:** bir raporu cümle cümle kontrol ederiz: bu kısım doğru, bu kısım yanlış, bu kısım
  bilinemez.

### 6.4 Yön kontrolü ("üsse doğru")
- **Şu anki durum:** Yok. "Üsse doğru ilerleyen" yalnızca `activity = moving` yapıyor.
- **Ölçülen:** konumlu 15 "dost araç üsse doğru ilerliyor" raporunun 8'inde 60 m içinde track yok. 7'si
  mevcut 1 m/s kuralına göre duran bir araçla eşleşiyor. 5 m gürültü tabanında (5.1) REP-78 ve REP-83
  hareketli sayılır. Yani yön de kontrol edilmezse bu iki rapor tutarlı görünür.
- **Neden:** 5.1 devreye girdiğinde aldatma tespitinin doğru kalmasını sağlar.
- **Zorluk:** Easy.
- **Teknik:** eşleşen track'in rapor saatindeki radyal hızı (5.2'den) → `toward_base / away / none`.
  İddia edilen yönle karşılaştırılır.
- **Kısacası:** "üsse doğru geliyor" iddiasının iki parçası da kontrol edilir: hareket ediyor mu, ve
  gerçekten bize doğru mu geliyor?

### 6.5 Kimlik kuralı + aldatma göstergesi (+1)
- **Şu anki durum:** Kısmen.
  - Tehdidi düşüren iddialar (`ALL_CLEAR`, `FRIENDLY_PRESENCE`) zaten UNVERIFIED oluyor ve skoru asla
    düşürmüyor.
  - Doğrulanabilir kısımları veriyle çelişirse güven 0 ile CONTRADICTED oluyorlar ve sonra sadece yok
    sayılıyorlar.
  - Kilit karelerde ölçülen: `img_006673`'te REP-06, `img_000926`'da REP-78 ve golden kare
    `img_000860`'ta REP-120 bugün CONTRADICTED çıkıyor ve hiçbir etkisi yok.
- **Neden:** hepsi "resmi" kaynaklı 18 dost/ikmal kimlik iddiası var. Doğrulanabilir olanların 15'inde
  0'ı tutarlı. En şüpheli dört aracın ikisi bu tür iddiaların kapsadığı karelerde. Bu büyük olasılıkla
  vakanın amaçlanan tuzağı ve demonun en güçlü anı.
- **Zorluk:** Easy. Karar: +1 seviye.
- **Teknik:**
  - `deception_indicator = lowers_threat and verdict == CONTRADICTED`, iddia edilen konumun yakınındaki
    araç(lar)a bağlanır.
  - 7. adım bu araçlara +1 seviye uygular (7.3).
  - AGENT_DESIGN §3 adım 6 aynı değişiklikte güncellenir.
  - Kimliğin kendisi doğrulanamaz olarak kalır: hiçbir sensör "dost" olduğunu teyit edemez.
- **Kısacası:** biri "o bizim içeri giren ikmal kamyonumuz" diyor ama veri içeri giren bir araç
  göstermiyorsa, bu sadece yanlış bir rapor değil bir uyarı işaretidir ve alarm seviyesi yükselir.

### 6.6 Öğrenilen kaynak güvenilirliği
- **Şu anki durum:** Yok. Güven ağırlıkları sabit: resmi 0.8, üçüncü taraf 0.5.
- **Neden:** burada "resmi" otomatik olarak güvenilir değil. Ölçülen: resmi "araç duruyor" gözlemleri
  16/17 tutarlı, resmi "dost araç yaklaşıyor" 0/15.
- **Zorluk:** Easy.
- **Teknik:** günün doğrulanabilir iddiaları üzerinden (kaynak × iddia türü) başına Beta–Bernoulli
  sayımı: `mean = (1 + desteklenen) / (2 + desteklenen + çelişen)`. Bu değer, o türdeki doğrulanamayan
  iddiaların güven ağırlığı olarak kullanılır. Açılışta tüm raporlar üzerinden bir kez hesaplanır
  (deterministik).
- **Kısacası:** her rapor türü, bugün ne sıklıkla doğru çıktığına göre güven kazanır veya kaybeder.

### 6.7 Bölge ve genel raporlar
- **Şu anki durum:** Kısmen. Koordinatsız genel raporlar yalnızca bu karenin bölgesini adıyla anıyorsa
  ilgili sayılıyor ve çoğunlukla UNVERIFIED oluyor.
- **Neden:** birkaç rapor türünün kendi kuralına ihtiyacı var:
  - "Ağır araç yok, sadece otomobil"
  - "Olağan trafik N araç"
  - Hava durumu
  - "Dün gece, teyitsiz ihbar" (zaman penceresi dışında)
  - "Planlı tatbikat, bugün dost unsurlar" (genel beyan)
  - "Devriyeyle N dakikadır telsiz teması yok" (dikkati artırır)
- **Zorluk:** Medium.
- **Teknik:**
  - Bölge iddiaları karedeki tespitlerle üst sınıf bazında kontrol edilir.
  - Trafik sayıları tespit sayısı + öksüz track'lerle kontrol edilir.
  - Hava durumu 1.3'teki parlaklıkla kontrol edilir.
  - "Dün gece" → `IRRELEVANT`.
  - "Planlı tatbikat" → seviyeyi asla düşüremez.
  - "Telsiz teması yok" → o sektör için dikkat notu (belirsizlik, puan yok).
- **Kısacası:** her genel mesaj türü, hepsi aynı torbaya atılmak yerine sağduyuyla ele alınır.

### 6.8 Kapsamı dikkate alan kararlar
- **Şu anki durum:** Kısmen. Konum uyuşmazlığı, yalnızca rapor saatinde yakında hiçbir track da yoksa
  çelişki sayılıyor. Açık bir "görebildiğimiz alanın dışında" durumu yok.
- **Neden:** drone'un görmediği bir yer hakkındaki rapor yanlış değil, doğrulanamazdır.
- **Zorluk:** Easy (1.5'ten sonra).
- **Teknik:** 1.5'ten kapsama durumu: `in_frame / near_frame / out_of_coverage / no_location`. Yalnızca
  `in_frame` yoklukları CONTRADICTED olabilir, o da mümkünse bir yerel yeniden tespitten (2.3) sonra.
- **Kısacası:** bir rapora ancak o yere gerçekten baktıysak yanlış deriz.

### 6.9 Raporlar arası tutarlılık
- **Şu anki durum:** Yok.
- **Neden:** aynı yer ve zaman hakkında birbiriyle çelişen iki rapor, ikisine olan güveni de azaltır.
- **Zorluk:** Medium.
- **Teknik:** raporlar konum ve zaman dilimine göre gruplanır, bir çatışma skoru hesaplanır
  (Dempster–Shafer çatışma K'si veya basit bir anlaşmazlık oranı) ve belirsizlik olarak eklenir.
- **Kısacası:** iki mesaj aynı nokta hakkında anlaşamıyorsa bunu belirtiriz.

### 6.10 LLM ile çıkarım + karar
- **Şu anki durum:** Yok (AGENT_DESIGN §3 6a/6c'de P2 için planlı; kurallar yedek yol).
- **Neden:** kalıpların kaçırdığı uzun kuyruktaki ifadeleri kapsar ve her rapor için okunabilir tek
  cümlelik bir gerekçe verir.
- **Zorluk:** Medium.
- **Teknik:** İngilizce prompt dosyaları `report_extraction_v1.md` ve `report_verdict_v1.md`. Raporlar
  `<untrusted_reports>` etiketleri içine konur. JSON Pydantic ile doğrulanır, bir onarım denemesi
  yapılır, sonra kurallara düşülür.
  - Kod tarafının kararı ipucu olarak verilir.
  - Güven politikası kodda uygulanmaya devam eder: LLM bir rapor üzerinden seviyeyi düşüremez.
  - `prompts.py` içindeki Türkçe prompt metni kullanılmadan önce çevrilmeli.
- **Kısacası:** dil modeli alışılmadık mesajları okumaya yardım eder, ama güvenlik kurallarını yine kod
  kontrol eder.

### 6.11 Rapor penceresi / yarıçapı ayar olarak
- **Şu anki durum:** Kısmen. `report_radius_m = 300` bir ayar. 120 dakikalık pencere `is_relevant`
  içinde ve pipeline'da (`motion.WINDOW_MIN`) sabit yazılmış.
- **Neden:** tasarım notları 150 dk / 500 m öneriyor. Doğru değer kod değiştirmeden denenebilmeli.
- **Zorluk:** Trivial.
- **Teknik:** `Settings`'e `report_window_min` eklenir ve aşağıya aktarılır.
- **Kısacası:** raporlar için ne kadar geriye ve ne kadar çevreye bakacağımız basit bir ayar olur.

---

## 7. score_risk

### 7.1 Eyleme dayalı seviye tanımları
- **Şu anki durum:** Kısmen. Seviyeler skor aralıklarıyla tanımlı (0–24 LOW … 75–100 CRITICAL). Önerilen
  eylem seviyeden türetiliyor (`MONITOR / VERIFY / ESCALATE`).
- **Neden:** operatörün bir sayıya değil, ne yapacağına ihtiyacı var. Notlardaki taslağın bizim 4
  seviyemize eşlenmesi:

  | Seviye | Operatör eylemi | Taslak ölçüt |
  |---|---|---|
  | CRITICAL | Hemen teyit et ve müdahale et (`ESCALATE`) | (net sweep > 180° veya en yakın geçiş < 1 km) VE halka 1 VE son 30 dk içeri hareket; ya da ağır araç + iç halkaya yaklaşma + aldatma göstergesi |
  | HIGH | Bildir, sonraki drone geçişinde kontrol et (`VERIFY`) | İki güçlü sinyal (popülasyonun üst %10'u) veya karede bir aldatma göstergesi |
  | MEDIUM | Rutin takip (`MONITOR`) | Tek bir sıra dışı sinyal |
  | LOW | Yok (`MONITOR`) | Sinyal yok |

  "Kanıt yetersiz" bir seviye değil, bayraktır (7.4).
- **Zorluk:** Easy (eşikler ekip kararı).
- **Teknik:** tablo, bir politika sürümüyle AGENT_DESIGN §3 adım 7'ye yazılır. Rubrik (7.2) bu
  seviyeleri üretmelidir.
- **Kısacası:** her alarm seviyesi operatör için net bir talimatla gelir.

### 7.2 Rubriğin hareket kanıtına göre yeniden tasarımı
- **Şu anki durum:** Kısmen. Toplamalı 0–100 skor: mesafe (30/20/10), yaklaşma hızı (25/15/5), üsse
  yönelme (10), uzun duraklamalar (10/+5), araç tipi (10/8/5), doğrulanmış rapor (10).
- **Ölçülen** (vekil tespitlerle, tip puanı yok):
  - Mevcut 4 seviyeli puanlamada (LOW / MEDIUM / HIGH / CRITICAL) kare seviyeleri: **22 HIGH,
    17 MEDIUM, 1 LOW, 0 CRITICAL**. Yani operatöre 22 kez "kontrol et" (`VERIFY`) deniyor, ama "hemen
    müdahale et" (`ESCALATE`) hiç çıkmıyor.
  - Gerçek tespitler tip puanı ekler. Bazı kareler CRITICAL'a çıkabilir, ama kamyon içerdikleri için
    çıkar, dönme davranışı yüzünden değil.
  - Dört şüpheli araç kendi karelerinde en üstte **çıkmıyor**:

    | Track | Kare | Skor | Karedeki sırası |
    |---|---|---|---|
    | T0043 | `img_006673` | 50 | 5 / 6 |
    | T0158 | `img_005672` | 45 | 3 / 4 |
    | T0172 | `img_000926` | 50 | 3 / 5 |
    | T0198 | `img_002900` | 50 | 4 / 4 |

    Brief en yüksek skorlu aracı öne çıkardığı için bugün yanlış aracı anlatıyor.
- **Neden:** alarm yorgunluğu (karelerin yarısından fazlası HIGH, yani "kontrol et" alarmı o kadar sık ki
  ciddiye alınmaz) ve yanlış odak (gerçekten acil olan kareler diğerlerinden ayrılmıyor). Saf bir "yaklaşıyor =
  alarm" kuralı 129 kez alarm verirdi.
- **Zorluk:** Medium. Sözleşme aynı kalır (`VehicleRisk.factors`), ağırlıklar ve faktörler değişir,
  golden beklentileri yeniden kontrol edilmelidir.
- **Teknik:**
  - Faktör dökümü yapısı korunur.
  - `circling` (net sweep yüzdeliği), `closest_pass` (en yakın geçiş yüzdeliği / < 1 km) ve
    `inward_last30` eklenir.
  - Bu veride yapısal olan `approach_rate` ve `distance_to_base`'in ağırlığı düşürülür.
  - 40 karede hedef dağılım: ~4 CRITICAL, 6–10 HIGH, geri kalanı MEDIUM/LOW. Dört aday kendi karelerinde
    birinci olmalı.
  - Dağılımı yazdıran bir `pytest -m eval` kontrolü eklenir.
- **Kısacası:** puanlama şu an "yakın ve yaklaşıyor" olanı ödüllendiriyor, ama bu verideki neredeyse her
  araba bunu yapıyor. Gerçekten sıra dışı olanı ödüllendirmeli: üssün etrafında dönmek ve çok yakından
  geçmek.

### 7.3 Aldatma ve kimlik düzelticileri
- **Şu anki durum:** Yok. Doğrulanamayan düşürücü iddialar zaten skoru düşüremiyor.
- **Neden:** kararlaştırılan +1 kuralını uygular (6.5).
- **Zorluk:** Easy.
- **Teknik:** temel seviyeden sonra `deception_indicator`'a bağlı araçlara +1 kademe uygulanır (en fazla
  CRITICAL). Dökümde görünmesi için `deception_indicator: REP-xx` faktör satırı eklenir. Kimlik
  iddiaları asla düşürmez. Sağlamlık `sensitive` ise (7.6) yüksek seviye alınır.
- **Kısacası:** yanlış bir "o bizden" mesajı sistemi daha az değil, daha dikkatli yapar.

### 7.4 Kanıt yetersizliği bayrağı
- **Şu anki durum:** Yok. Hiçbir şey tespit edilmezse → LOW.
- **Neden:** "bilmiyoruz" geçerli ve kendinden emin bir LOW'dan daha güvenli bir cevap (panelin
  open-set noktası).
- **Zorluk:** Easy.
- **Teknik:** örneğin şu durumlarda `insufficient_evidence = true` yapılır: dedektör bozulmuş ve track
  yok, bu karede recall (2.2) çok düşük, ya da OOD bayrağı (1.3) kalkmış ve track desteği yok. Etkisi:
  bir belirsizlik satırı + `recommended_action = VERIFY`. Seviye değişmez.
- **Kısacası:** sistem yeterince iyi göremediğinde "her şey yolunda" yerine "bir kez daha baktırın" der.

### 7.5 Karşı-olgusal açıklamalar
- **Şu anki durum:** Yok.
- **Neden:** "dolaşma olmasaydı bu MEDIUM olurdu" mümkün olan en net açıklama. Skorlayıcı deterministik
  olduğu için neredeyse bedava gelir.
- **Zorluk:** Easy.
- **Teknik:** `score_vehicle` bir faktör çıkarılarak veya bir rapor tersine çevrilerek yeniden
  çalıştırılır. Seviyeyi değiştiren 1–2 değişiklik tutulur ve
  `Counterfactual(subject, change, level_before, level_after)` olarak saklanır.
- **Kısacası:** sistem farkı hangi tek bilginin yarattığını açıklar.

### 7.6 Belirsiz girdilere karşı sağlamlık
- **Şu anki durum:** Yok.
- **Neden:** belirsiz bir eşleşme (4.3) veya belirsiz bir sınıf (2.1) seviyeyi sessizce belirlememeli.
- **Zorluk:** Medium.
- **Teknik:** alternatifler (diğer track adayları, hafif/ağır) küçük bir üst sınıra kadar sıralanır ve
  her biri puanlanır. Hepsi aynı kare seviyesini veriyorsa `robustness = robust`, vermiyorsa `sensitive`
  olur. Bu durumda yüksek seviye seçilir ve nedeni belirtilir.
- **Kısacası:** belirsiz tahminlerimiz yanlış çıksa cevabın değişip değişmeyeceğini kontrol ederiz.

### 7.7 Fuzzy kurallar + Dempster–Shafer
- **Şu anki durum:** Yok.
- **Neden:** belirsiz kanıtları birleştirmenin ve "bilinmeyen" kütleyi göstermenin ilkeli bir yolu.
  Mentor soruları için iyi, ama karmaşıklık katıyor ve doğru bir demo için gerekli değil.
- **Zorluk:** Hard.
- **Teknik:** popülasyon yüzdelikleri üzerinde fuzzy üyelikler. Kanıt kaynağı başına güvenilirlik
  indirimli (6.6) DS kütleleri {threat, benign, unknown}, ardından birleştirme. Tetiklenen kurallar
  metin olarak gösterilir.
- **Kısacası:** "kısmen emin" ipuçlarını birleştirmenin daha resmi bir yolu. Opsiyonel, her şeyden sonra.

---

## 8. write_brief

### 8.1 Kanıt atıflı LLM brief'i
- **Şu anki durum:** Yok. Deterministik bir Türkçe/İngilizce şablon kullanılıyor (`fallback.py`,
  `generated_by = "fallback"`).
- **Neden:** doğal, kısa ve iyi gerekçelendirilmiş brief jürinin ilk gördüğü şey.
- **Zorluk:** Medium.
- **Teknik:** `brief_v1.md` (İngilizce prompt, çıktı dili `BRIEF_LANGUAGE`'dan). Tüm olgular JSON olarak,
  raporlar `<untrusted_reports>` içinde verilir. Yapı, en fazla 5 cümle:
  1. Durum (seviye + tek satır).
  2. Gerekçe (en güçlü 2–3 kanıt).
  3. Raporlar (destekleyen / çelişen / aldatma).
  4. Belirsizlik + eylem.

  Her cümle en az bir ID'ye atıf yapar. LLM kare seviyesini atıflı bir gerekçeyle en fazla bir kademe
  değiştirebilir. Şablon yedek olarak kalır.
- **Kısacası:** son özeti dil modeli yazar, ama yalnızca doğrulanmış olgulardan ve her cümle için bir
  kaynakla.

### 8.2 Guard (doğrulayıcı)
- **Şu anki durum:** Yok (brief doğrulayıcısı AGENT_DESIGN ve backend/CLAUDE.md'de planlı).
- **Neden:** panelin istediği, yapay zekânın kararını kontrol eden "bağımsız kontrol bilgisayarı" bu.
- **Zorluk:** Medium.
- **Teknik:** LLM brief'i üzerinde deterministik kontroller:
  - **şema:** zorunlu alanlar boş değil.
  - **dayanak:** her ID analizde var (F1) ve metindeki her sayı, yuvarlama payı içinde kayıtlı bir
    değerle eşleşiyor.
  - **seviye:** rubriğe göre ±1 içinde.
  - **politika:** hiçbir rapor seviyeyi düşürmedi, aldatma göstergesi varsa brief'te geçiyor.
  - **sapma gerekçesi:** seviye rubrikten farklıysa mutlaka var.

  Başarısız olursa: başarısız kontrollerle bir onarım turu, sonra şablon brief'i, UI'da "doğrulanmadı"
  olarak işaretlenir.
- **Kısacası:** düz koddan oluşan katı bir düzeltmen, yapay zekânın raporunu kimse görmeden kontrol eder.

### 8.3 Kırmızı takım eleştirmeni
- **Şu anki durum:** Yok. `prompts.py` içinde Türkçe bir taslak var (`CRITIC`).
- **Neden:** aldatma vakanın ana teması. Analistin nasıl kandırıldığını bulmaya çalışan ikinci,
  bağımsız bir bakış, guard'ın sabit kurallarının yakalayamadığı hataları yakalar.
- **Zorluk:** Medium (kare başına bir ek LLM çağrısı, en fazla bir revizyon turu).
- **Teknik:** girdi = final brief + kanıt paketi, konuşma geçmişi **yok**. Sabit kontrol listesi:
  1. Aldatıcı bir rapora dayanıldı.
  2. Seviye dolaşma / en yakın geçişle tutarsız.
  3. Belirsiz bir eşleşme kesinmiş gibi kullanıldı.
  4. Kapsam içindeki bir rapor göz ardı edildi, ya da kapsam dışındaki bir rapora çelişiyor denildi.
  5. Dayanaksız bir sayı kullanıldı.

  Yalnızca seviyeyi değiştiren sorunlar engelleyicidir. Çıktı `CriticReview` JSON'u. Prompt İngilizceye
  çevrilir, `<untrusted_reports>` eklenir, guard geçtikten sonra kullanılır.
- **Kısacası:** ikinci bir yapay zekâ "şeytanın avukatı" rolünü oynar ve yalnızca ilk sonucun nasıl
  yanlış olabileceğini arar.

### 8.4 Brief modeli genişletmeleri
- **Şu anki durum:** Yok. `Brief` başlık, özet, araç satırları, rapor notları, belirsizlikler, eylem ve
  kanıt ID'lerinden oluşuyor.
- **Neden:** yeni açıklamaları (7.3–7.6, 8.3) sözleşmeyi değiştirmeden UI'a taşır.
- **Zorluk:** Easy (ekleme türünde sözleşme değişikliği → `gen-types`).
- **Teknik:** opsiyonel `rubric_level`, `deviation_reason`, `counterfactuals`, `robustness`,
  `deception_report_ids`, `insufficient_evidence`, `critic_notes` alanları eklenir. Notlardaki ayrı
  `Assessment` modeli benimsenmez.
- **Kısacası:** rapor kartına birkaç kutu daha eklenir: "kuraldan neden farklı", "cevabı ne
  değiştirirdi", "ne kadar eminiz".

### 8.5 Aldatmayı açıkça anlatan ifade
- **Şu anki durum:** Yok.
- **Neden:** demoda şu cümle en parlak an olur: "resmi bir rapor bunun yaklaşan dost bir ikmal aracı
  olduğunu iddia ediyor, ama track'lerimiz orada hareket eden bir araç göstermiyor; aldatma göstergesi
  olarak ele alındı" (`img_006673`, `img_000926` ve golden karedeki REP-120).
- **Zorluk:** Easy.
- **Teknik:** özel bir şablon cümlesi (`fallback_templates.py` içinde TR/EN) ve `brief_v1.md`'de bir
  kural: her aldatma göstergesi rapor ve track ID'leriyle anılır. Guard bunun anıldığını kontrol eder.
- **Kısacası:** sistem yanıltıcı bir mesaj yakaladığında bunu açıkça söyler ve kanıtını gösterir.

---

## 9. Tek karenin ötesi

### 9.1 Gün tablosu (40 kare, öncelik listesi, ısı haritası)
- **Şu anki durum:** Yok (PLAN P4: toplu ön hesaplama, genel bakış paneli).
- **Neden:** operasyonel değer. Operatör 40 fotoğraf açmak yerine şu an dikkat gerektiren 4–10 kareyi
  görür.
- **Zorluk:** Medium.
- **Teknik:** pipeline tüm karelerde çalıştırılır (≤ 4 eşzamanlı LLM çağrısı, cache'li). Sıralama
  seviyeye, sonra halkaya, sonra ETA'ya göre. 8 × 5 sektör × halka ısı haritası, kareler arası notlar
  (1.8) ve kısa bir vardiya brief'i gösterilir.
- **Kısacası:** günün bütün fotoğraflarını aciliyetine göre sıralayan tek bir ekran.

### 9.2 Analist sohbeti araçları
- **Şu anki durum:** Yok (`agent/tools.py` ve `chat_agent.py` yer tutucu, P4).
- **Neden:** agent özerkliği burada sergileniyor (operatörün takip soruları), AGENT_DESIGN §2'ye göre.
- **Zorluk:** Medium.
- **Teknik:** `schemas.py`'deki araç girdi/çıktı tasarımı, bitmiş bir analiz üzerinde salt okunur
  araçlar olarak yeniden kullanılır (track, hareket, rapor, risk sorguları). `DomainModel` + `Literal`
  stiline çevrilir. Tur başına en fazla 6 araç çağrısı.
- **Kısacası:** operatör "bu kamyon neden yüksek riskli?" diye sorabilir ve aynı veriye dayanan bir
  cevap alır.

### 9.3 Canlı adım olayları ve çizimler
- **Şu anki durum:** Kısmen. Adımlar özet ve veriyle `StepResult` olarak kaydediliyor. SSE olay
  modelleri var, ama `POST /analyses` senkron çalışıyor (SSE akışı P2).
- **Neden:** akıl yürütmeyi adım adım izlemek demonun özü.
- **Zorluk:** Medium.
- **Teknik:** SSE, mevcut 8 adım adıyla AGENT_DESIGN §5'e göre uygulanır. Yeniden tespit, guard ve
  eleştirmen ilgili adımın `data` / uyarıları içinde, gerekirse tek bir yeni olay tipiyle bildirilir
  (public contract değişikliği → önce plan). Çizim verisi (kutular, öksüz noktalar, rota) UI çizimleri
  için `StepResult.data` içine konur.
- **Kısacası:** ekran her adımı olduğu anda gösterir, kutular ve rotalar canlı çizilir.

---

## X. Elenen veya ertelenenler

| Tasarım notlarındaki madde | Durum | Neden |
|---|---|---|
| Tüm adımları LLM tool-calling döngüsünün yürütmesi | Elendi | Karar: sadece pipeline (tekrarlanabilirlik, maliyet, gecikme) |
| 5. seviye olarak BELIRSIZ | Elendi | Karar: bayrak + `VERIFY` (7.4) |
| Bölge atamasını yön sektörüne çevirmek | Elendi | 40/40 uyum ölçüldü; sektör/halka yalnızca bilgi olarak eklenir (1.4) |
| GLM vision "ikinci bakış" (`VISION_SECOND_LOOK`) | Elendi | Notlarda zaten çıkarılmıştı; görüntü modeli yalnızca `detect`'te çalışır |
| Kalman / CPA-TCPA projeksiyonu | Elendi | Dur-kalk hareket sabit hız projeksiyonunu güvenilmez yapıyor; yerine ETA aralığı (5.6) |
| `E12` kanıt ID'leri ve ayrı blackboard deposu | Elendi | `DET-/TRK-/REP-` ID'leri ve `Analysis` nesnesi korunur (F1) |
| `schemas.py` / `prompts.py` içindeki Türkçe adlar, prompt'lar ve açıklamalar | Çevrilecek | Repo kuralı: kod ve prompt'lar İngilizce |
| Kamerada yeniden görme, takipçi yaşam döngüsü, gözcü görevlendirme | Ertelendi | PLAN §10 backlog |

---

## Önerilen yapım sırası

Önce bağımlılıklar, genişlikten önce demonun doğruluğu:

1. **5.1 → 5.2 → 5.3 → 5.8**: hareket özellikleri.
2. **7.2 + 7.1**: hareket kanıtına dayalı rubrik. Hedef: dört aday birinci sırada ve makul bir seviye
   dağılımı.
3. **6.1, 6.4, 6.5, 7.3, 8.5**: F5 senaryo testleriyle birlikte uçtan uca aldatma zinciri.
4. **F3 → 6.10 → 8.1 → 8.2 → 8.3**: guard ve eleştirmenle birlikte LLM yolu.
5. **1.x, 4.3–4.4, 7.4–7.6, 8.4**: açıklamalar ve belirsizlik.
6. **2.x**: dedektör iyileştirmeleri (model seçimi hâlâ açıksa 2.2 erken yapılır).
7. **9.x**: gün tablosu, sohbet.

Her adımdan sonra: golden test yeşil olmalı, domain modeli değiştiyse `gen-types` çalıştırılmalı, her
politika değişikliği için AGENT_DESIGN güncellenmeli.
