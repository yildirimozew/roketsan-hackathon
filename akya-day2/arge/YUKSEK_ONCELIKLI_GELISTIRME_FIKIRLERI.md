# Kesinlikle Yapılması Gereken İşler

`arge/ARGE_KARSILASTIRMA_F_M.md` karşılaştırmasından çıkan, **gerçekten yapılması gereken** maddeler. Agent
akışının sırasıyla dizildi.

## Kapsam

Bir madde bu listeye aşağıdaki üç ölçütten en az birini karşılıyorsa girdi:

1. **Sistem bugün yanlış sonuç veriyor.** Doğru raporu yanlış sayıyor, yanlış raporu doğru sayıyor ya da
   tehlikeli bir durumu "sorun yok" diye gösteriyor.
2. **Demo sahnede bozulabilir.** CLAUDE.md: "It never crashes on stage."
3. **Panelin açıkça istediği bir şey karşılanmıyor.** Panel notları (`arge_f/STAGE2_DESIGN_NOTES.md` §1):
   - Yapay zekâ doğrulanabilir ve açıklanabilir olmalı.
   - Kararı bağımsız bir "kontrol bilgisayarı" denetlemeli.
   - Simülasyon testleri olmalı.
   - Model "bilmiyorum" diyebilmeli (open-set).
   - Kademeli bozulma olmalı; bileşenler birbirinin yerini tutabilmeli.
   - Operasyonel verimlilik sağlanmalı.

Faydalı ama bu ölçütleri karşılamayan maddeler en sondaki "Bilerek dışarıda bırakılanlar" tablosunda.

**Durum tespiti:** 2026-09-26 tarihli güncel kod okunarak yapıldı. Ölçümler `data/` içindeki gerçek veride.

## Zorluk ölçeği

| Seviye | Tek geliştirici için |
|---|---|
| Kolay | 1–2 saat, tek modül + test |
| Orta | 3–5 saat, birkaç modül veya public contract (domain model → OpenAPI → `gen-types`) değişikliği |
| Zor | 1 gün+ |

---

## Özet tablo

| # | Madde | Akış adımı | Neden zorunlu | Zorluk |
|---|---|---|---|---|
| Z1 | Tespitler yoksa sessizce "LOW" verme; tespit dosyasını üret | 2 detect | Yanlış sonuç + demo + bozulma | Kolay |
| Z2 | Görüntüde görülmeyen ama track'i olan araçları değerlendir | 4 match_tracks | Yanlış sonuç + "bilmiyorum" | Orta |
| Z3 | "Hareketsiz" tanımını veriye göre düzelt | 5 analyze_motion | Yanlış sonuç | Kolay |
| Z4 | Raporu rapor saatine değil, çekim anına göre kontrol et | 6 assess_reports | **Yanlış sonuç (en kritik)** | Orta |
| Z5 | "Ağır araç yok" gibi olumsuz raporları doğru oku | 6 assess_reports | Yanlış sonuç | Kolay–Orta |
| Z6 | "Üsse doğru" yönünü kontrol et, aldatma göstergesi üret | 6 assess_reports | Yanlış sonuç + vakanın ana teması | Kolay |
| Z7 | Aldatma göstergesi seviyeyi +1 artırsın | 7 score_risk | Alınmış karar + ana tema | Kolay |
| Z8 | "Kanıt yetersiz" bayrağı | 7 score_risk | Panel: "bilmiyorum" diyebilmek | Kolay |
| Z9 | Kontrol bilgisayarı: LLM çıktısı doğrulayıcı | 8 write_brief (+ izleme modu) | Panel: bağımsız kontrol | Orta |
| Z10 | Bütçe kontrolü ve görünür bozulma modu | kesişen | Demo + panel: kademeli bozulma, verimlilik | Kolay |
| Z11 | Simülasyon / adversarial test takımı | kesişen | Panel: simülasyon testleri | Orta |

---

## Adım 2 — detect

### Z1. Tespitler yoksa sessizce "LOW" verme; tespit dosyasını üret
- **Şu anki durum:**
  - Varsayılan dedektör `precomputed` (`core/config.py:66`) ve `backend/.cache/detections.json` dosyasını
    okuyor. Bu makinede o dosya da, `models/` altında bir model ağırlığı da yok.
  - `PrecomputedDetector.detect` dosya yoksa hata vermeden **boş liste** döndürüyor
    (`services/detection/precomputed.py:33, 44`). Pipeline yalnızca `DetectorError` durumunda uyarı üretiyor
    (`agent/pipeline.py`, adım 2).
  - Sonuç: her kare "0 araç" görünüyor ve `frame_level` boş listede **LOW** döndürüyor
    (`services/risk.py:231`). Ekranda hiçbir uyarı yok.
  - Tespit üretme betiği hazır: `backend/scripts/precompute_detections.py`.
- **Neden gerekli:**
  - Sistem göremediği bir kareye "tehdit yok" diyor. Bu, panelin istediği "bilmiyorum diyebilme" ilkesinin
    tam tersi ve demoda en tehlikeli hata türü.
  - Araç tipi kontrolleri de ancak tespitlerle çalışır ("raporda kamyon denmiş, gerçekten kamyon mu?",
    "ağır araç yok" raporları). M'nin ölçümünde tespit olmadığı için 25 rapor değerlendirilemedi.
- **Zorluk:** Kolay (1–2 saat; takımın en iyi ağırlık dosyasına erişim gerekiyor).
- **Teknik anlatım:**
  1. `PrecomputedDetector` dosya yoksa ya da istenen kare dosyada yoksa `DetectorError` fırlatsın. Böylece
     pipeline adımı `warning` olur ve fallback zinciri çalışır.
  2. Hiç dedektör yoksa adım `warning` verir ve Z2'deki "yalnız track" moduna geçilir. Kare seviyesi sessiz
     LOW değil, "kanıt yetersiz" bayrağıyla (Z8) gelir.
  3. Takımın en iyi ağırlığıyla 40 kare bir kez çalıştırılır ve `detections.json` üretilir. `data/` repoya
     commit'lendiği için dosya `data/detections.json` altına konup `SENTINEL_DETECTIONS_FILE` ile
     gösterilebilir; böylece her checkout demoyu çalıştırabilir. Ağırlık dosyası repoya girmez.
  4. `/api/health` dedektör durumunu zaten gösteriyor. Analiz ekranında da görünür olmalı (Z10).
- **Herkesin anlayacağı anlatım:** Şu an sistemin "gözü" kapalıyken bile "her şey yolunda" diyebiliyor.
  Göz kapalıysa bunu açıkça söylemeli. Ayrıca fotoğraflardaki araçları bir kez tespit edip kaydedelim ki demo
  her bilgisayarda aynı şekilde çalışsın.

---

## Adım 4 — match_tracks

### Z2. Görüntüde görülmeyen ama track'i olan araçları değerlendir
- **Şu anki durum:**
  - Hareket ve risk yalnızca bir tespitle eşleşen track'ler için hesaplanıyor.
  - Karenin içinde olup tespiti olmayan track'ler yalnızca `TrackSnapshot` olarak listeleniyor
    (`matched_detection_id = None`), risk hesabına girmiyor.
  - `VehicleRisk.detection_id` zorunlu bir alan (`domain/risk.py`). Yani tespiti olmayan bir araç için risk
    satırı bugün oluşturulamıyor.
- **Neden gerekli:**
  - Dedektörün kaçırdığı ya da hiç çalışmadığı (Z1) bir karede, üssün etrafında dolanan bir araç bile
    değerlendirmeye girmiyor.
  - Ölçüm: 226 track'in 206'sı çekim anında kendi karesinin içinde. Tespitsiz çalışmada bu araçların hiçbiri
    risk hesabına girmiyor.
  - Panel: bileşenler birbirinin yerini tutabilmeli. Dedektör yoksa track'ler devreye girmeli.
- **Zorluk:** Orta (3–4 saat; `VehicleRisk` ve `Brief` araç satırları public contract, önce kısa plan gerekir).
- **Teknik anlatım:**
  1. Kare içindeki eşleşmemiş track'ler "yalnız track" araç olarak 5. adımdan (hareket), 7. adımdan (risk) ve
     8. adımdan (brief) geçer. `VehicleRisk.detection_id` opsiyonel olur.
  2. Her birine bir hipotez eklenir: `missed` (kare içinde ama kutu yok) veya `outside_near_edge` (kenardan
     ≤ 30 m dışarıda; ölçüm: 20 track 7–26 m dışarıda).
  3. Brief'te "görüntüde görülmedi, yalnızca track verisi" belirsizliğiyle yer alır.
  4. Tersi durum, yani track'i olmayan tespit, `parked_likely` olarak belirsizliğe yazılır. Bugünkü
     "no_track" faktörü buna bir açıklama cümlesi kazanır.
- **Herkesin anlayacağı anlatım:** Kamera bir aracı kaçırdı diye o araç zararsız hale gelmez. Kayıtlarda
  aracın rotası varsa, onu fotoğrafta göremesek de değerlendirir ve "fotoğrafta görülmedi" notunu düşeriz.

---

## Adım 5 — analyze_motion

### Z3. "Hareketsiz" tanımını veriye göre düzelt
- **Şu anki durum:**
  - Duraklama 1 m/s'den yavaş adımlarla tanımlanıyor (`STOP_SPEED_MS = 1.0`). Bu, 5 dakikada 300 m demek.
  - Rapordaki "duruyor / hareket halinde" kontrolü tek bir 5 dakikalık adıma bakıyor
    (`services/reports.py:_moving_at`, `haversine(a, b) / 300 >= stop_speed_ms`).
  - Ölçüm: mevcut eşik 5 dakikalık adımların %76'sını "durma" sayıyor, gerçekte adımların %57'si 5 m'nin
    altında.
- **Neden gerekli:**
  - Rapor doğrulamanın temeli "araç duruyor mu, hareket mi ediyor". Yanlış tanım, "1 kamyon duruyor"
    raporlarının yanlışlıkla doğru ya da yanlış sayılmasına yol açıyor.
  - M'nin ölçümü: son 60 dakikada park halindeki track'ler en fazla **39 m** kayıyor, diğer tüm track'ler en
    az **1087 m** gidiyor. Arada çok net bir boşluk var.
- **Zorluk:** Kolay (1 saat).
- **Teknik anlatım:**
  - Yeni fonksiyon `drift_m`: çekim anından geriye 60 dakikalık pencerede, son konumdan en büyük uzaklık.
    ≤ 100 m ise hareketsiz, değilse hareketli.
  - Rapor iddiaları (Z4) bu fonksiyonu kullanır.
  - Mevcut `stops` listesi korunur. Golden testteki ≈ 40 ve ≈ 45 dakikalık duraklamalar ona göre kalibre
    edilmiş.
  - Kod ve test hazır: `arge/arge_m/05_hareket_analizi/hareket.py:drift_m`, `tests/test_hareket.py`.
- **Herkesin anlayacağı anlatım:** Konum kayıtları park etmiş araçlarda bile birkaç on metre oynuyor. Park
  edenlerle yol alanlar arasında çok büyük bir fark var; "duruyor" sınırını tam bu boşluğa koyuyoruz.

---

## Adım 6 — assess_reports

### Z4. Raporu rapor saatine değil, çekim anına göre kontrol et
- **Şu anki durum:**
  - Pipeline raporu **rapor saatindeki** track konumlarıyla karşılaştırıyor (`services/reports.py:verify_claim`:
    `position_at(t, claim.time_min)` ve `_moving_at(..., claim.time_min)`).
  - İzleme modu da aynısını yapıyor (`services/watch.py:reports_near`: `tracks_at(tracks, c.time_min)`).
  - Belgeler de aynı varsayımda: `docs/AGENT_DESIGN.md` §3 adım 6b ("tracks at the report's own time") ve
    `docs/AGENT_FLOW.md` §7'deki REP-120 / REP-126 anlatımı.
- **Neden gerekli:** En kritik yanlış bu. Ölçüm, raporların aracı **karenin çekim anındaki** konumuyla
  anlattığını gösteriyor:

  | Mesafe | Track'in son noktasına (çekim anı) | Rapor saatindeki track konumuna |
  |---|---|---|
  | ≤ 15 m | **60 / 72** | 17 / 72 |
  | ≤ 60 m | **71 / 72** | 47 / 72 |

  Bugünkü kod bu yüzden doğru raporları "çelişiyor" sayıyor (ör. REP-06, REP-78, REP-120). Gerçekten
  yanlış olan raporları ise gözden kaçırıyor. Z6 ve Z7 bu düzeltme olmadan yanlış araçları cezalandırır.
- **Zorluk:** Orta (3–4 saat; izleme modu da değişiyor).
- **Teknik anlatım:**
  - **Koordinatlı rapor:**
    1. Koordinatın düştüğü kare (±60 m) bulunur. Her koordinatlı rapor tam bir karenin içinde ve o karenin
       çekiminden 5–120 dk önce yazılmış.
    2. Karşılaştırma o karenin çekim anındaki track konumlarıyla ve tespitlerle yapılır.
    3. Hareket iddiaları çekim anından geriye ölçülür (son 30 / 60 dk; Z3).
  - **Bölge raporu:** o bölgenin, rapordan sonraki 120 dk içindeki kareleriyle kontrol edilir.
  - **Pipeline:** `verify_claim` içindeki referans zaman `claim.time_min` yerine `meta.capture_min` olur.
    Mevcut rapor penceresi (çekimden önceki 120 dk) zaten doğru.
  - **İzleme modu:** rapor saatinde araç henüz tarif edilen yerde değil. Rapor, karesi çekilene kadar
    "bekliyor" (UNVERIFIED, "kare bekleniyor") olarak tutulur ve çekim tikinde kontrol edilir.
  - **Belgeler:** AGENT_DESIGN §3 adım 6b ve AGENT_FLOW §7 aynı değişiklikte güncellenir.
  - Kod ve test hazır: `arge/arge_m/06_rapor_degerlendirme/claims.py:check_report, _frame_for`,
    `tests/test_real_data.py`.
- **Herkesin anlayacağı anlatım:** Raporlar aracı, drone fotoğrafının çekildiği andaki yeriyle tarif ediyor;
  raporun üstündeki saat daha erken. Biz raporu yanlış anla karşılaştırdığımız için doğru raporlara "yalan"
  diyorduk. Raporu fotoğraf anıyla karşılaştırınca doğru araç bulunuyor.

### Z5. "Ağır araç yok" gibi olumsuz raporları doğru oku
- **Şu anki durum:** Kural tabanlı ayrıştırıcıda (`services/reports.py:extract_claim`) olumsuzluk yok.
  - "Ağır araç hareketi yok, yalnızca binek araçlar" → **kamyon görüldü** olarak okunuyor (ör. REP-92).
  - "Kayda değer hareketlilik bulunmuyor" → OTHER.
  - "Ağır bir aracın" → araç türü bulunamıyor.
- **Neden gerekli:** Tersine okuma tersine sonuç doğuruyor. O bölgede bir kamyon tespit edilirse "ağır araç
  yok" raporu **doğrulanmış** sayılıyor.
  - Bu kalıpta 6 "ağır araç yok" raporu var, toplam 22 yokluk raporu var.
  - Örnek: REP-42 (15:00, resmi) "Kuzeybatı Yolu'nda kayda değer hareketlilik yok" diyor, ama o bölgenin
    karelerinde üç araç son 30 dakikada üsse 1.5–4.0 km yaklaşmış.
- **Zorluk:** Kolay–Orta (2–3 saat).
- **Teknik anlatım:**
  1. Olumsuzluk kalıpları araç kelimelerinden önce denenir (`agir arac (hareketi)? (yok|bulunmuyor|gorulmedi)`,
     `kayda deger ... bulunmuyor`). Eşleşirse yeni bir iddia türü `ABSENCE` oluşur.
  2. `agir (bir )?arac` → ağır.
  3. Kontrol kuralları:
     - "Hareket yok": bölge karelerinde son 30 dakikada üsse ≥ 1 km yaklaşan bir track varsa çelişiyor.
     - "Ağır araç yok": bölge karelerinde kamyon veya otobüs tespiti varsa çelişiyor; tespit yoksa
       doğrulanamaz (Z1).
     - "Her şey normal": doğrulanamaz ve seviyeyi asla düşürmez.
  4. `ClaimKind` literal'ine `ABSENCE` eklenir → `gen-types`.
  - Kod ve test hazır: `arge/arge_m/06_rapor_degerlendirme/claims.py` (`_ABSENCE_PATTERNS`,
    `_check_area_claims`), `tests/test_claims.py`.
- **Herkesin anlayacağı anlatım:** Bilgisayar "kamyon yok" cümlesinde "kamyon" kelimesini görüp "kamyon
  var" sanıyordu. Olumsuz cümleleri ayrı tanıyıp, "bölgede hareket yok" diyen raporu bölgenin
  fotoğraflarıyla karşılaştırıyoruz.

### Z6. "Üsse doğru" yönünü kontrol et, aldatma göstergesi üret
- **Şu anki durum:**
  - "Üsse doğru ilerleyen" ifadesi yalnızca `activity = moving` olarak okunuyor (`services/reports.py`), yön
    kontrol edilmiyor.
  - Kimlik beyanları (`FRIENDLY_PRESENCE`) doğru biçimde seviyeyi düşürmüyor. Ama doğrulanabilir kısımları
    çelişince sadece "CONTRADICTED, güven 0" olup yok sayılıyorlar. Aldatma kavramı yok.
- **Neden gerekli:** Vakanın ana teması aldatma. Çekim anı eşlemesiyle (Z4) 15 "üsse doğru ilerleyen dost
  araç" raporunun 13'ü tutuyor. İki resmi rapor hareketle çelişiyor:
  - **REP-61** (14:50, `img_006444`): "planlı ikmal aracı üsse doğru ilerliyor", oysa eşleşen T0075 üsten
    **uzaklaşıyor** (4.1 → 5.3 km).
  - **REP-113** (12:15, `img_000733`): "bize bağlı unsur üsse geliyor", oysa T0124 **yaklaşmıyor**
    (3.4 → 3.5 km).

  Resmi kaynaktan gelen, veriyle çelişen bir "dost" raporu, en tehlikeli yanlış güven türüdür.
- **Zorluk:** Kolay (1–2 saat).
- **Teknik anlatım:**
  - `toward_base` iddiası: eşleşen track'in üsse uzaklığı çekimden 30 dk önce ile çekim anı arasında ≥ 200 m
    azaldıysa tutarlı.
  - `deception_indicator = kimlik beyanı var VE doğrulanabilir kısmı (yön, konumda araç varlığı) çelişiyor`.
    Rapor değerlendirmesine alan olarak eklenir ve bağlı araç(lar)ın ID'si tutulur.
  - Kimliğin kendisi her zaman doğrulanamaz; hiçbir sensör "dost" olduğunu teyit edemez.
  - Kod ve test hazır: `arge/arge_m/06_rapor_degerlendirme/claims.py` (`toward_base`, `deception_indicator`).
- **Herkesin anlayacağı anlatım:** "Bu bizim aracımız" cümlesini fotoğraftan doğrulayamayız. Ama raporun
  "üsse geliyor" kısmını kontrol edebiliriz. Araç aslında uzaklaşıyorsa rapor şüphelidir ve bunu işaretleriz.

---

## Adım 7 — score_risk

### Z7. Aldatma göstergesi seviyeyi +1 artırsın
- **Şu anki durum:** Karar alındı (2026-09-26), uygulanmadı.
  - Tehdidi düşüren raporlar seviyeyi zaten düşüremiyor (`services/risk.py`, test:
    `test_threat_lowering_report_never_lowers_score`).
  - Çelişen raporlar puanlamada tamamen yok sayılıyor (AGENT_DESIGN §3 adım 6, "ignored for scoring").
- **Neden gerekli:** Bizi yanıltmaya çalışan bir rapor, ilgili aracı daha şüpheli yapmalı. Bu sistemin
  "raporlara körü körüne güvenmiyoruz" mesajının ölçülebilir karşılığı.
- **Zorluk:** Kolay (1 saat). **Önkoşul: Z4 ve Z6.** Yoksa yanlış araçlar cezalandırılır.
- **Teknik anlatım:**
  1. Temel seviye hesaplandıktan sonra, `deception_indicator`'a bağlı araçlara +1 kademe uygulanır (en fazla
     CRITICAL).
  2. Faktör dökümüne `deception_indicator: REP-61` satırı eklenir.
  3. **Seviye tavanıyla ilişki** (`services/risk.py:level_ceiling`, 26 Eylül kalibrasyonu): +1, tavanı bir
     kademe aşabilir. Aldatma, hareket desenlerinden bağımsız bir kanıttır. Bu kural açıkça yazılmalı.
  4. İzleme modunda aynı kural gözcü ve denetçi seviyelerine uygulanır.
  5. AGENT_DESIGN §3 adım 6 ve 7 ile §12 aynı değişiklikte güncellenir.
- **Herkesin anlayacağı anlatım:** Yanlış bir "o bizden" mesajı sistemi daha az değil, daha dikkatli yapar.

### Z8. "Kanıt yetersiz" bayrağı
- **Şu anki durum:** Yok. Hiçbir şey tespit edilmezse kare LOW oluyor (`frame_level`, boş liste → LOW).
  Yetersiz kanıtla "tehdit yok" arasında fark yok.
- **Neden gerekli:** Panel açıkça istedi: model "bilmiyorum" diyebilmeli. "Emin değilim, tekrar bakılsın",
  kendinden emin bir yanlış "sorun yok"tan her zaman daha güvenli.
- **Zorluk:** Kolay (1–2 saat).
- **Teknik anlatım:**
  - Seviye değişmez (karar: ayrı seviye değil, bayrak). Analize `insufficient_evidence: bool` ve bir neden
    listesi eklenir.
  - Tetikleyiciler:
    - Dedektör çalışmadı ya da fallback'e düştü (Z1).
    - Karede beklenen araç sayısı (kare içindeki track'ler) ile tespit sayısı çok farklı; ör. tespitle
      karşılanan track oranı < %50.
    - Kare içindeki araçların çoğu yalnızca track ile biliniyor (Z2).
  - Etkisi: brief'e bir belirsizlik satırı ve `recommended_action = VERIFY`.
  - UI'da seviye rozetinin yanında "kanıt yetersiz" işareti. `Brief` modelinde opsiyonel alan → `gen-types`.
- **Herkesin anlayacağı anlatım:** Sistem yeterince iyi göremediğinde "her şey yolunda" demek yerine "bu
  karede emin değilim, bir kez daha baktırın" der.

---

## Adım 8 — write_brief

### Z9. Kontrol bilgisayarı: LLM çıktısı doğrulayıcı
- **Şu anki durum:**
  - Tek kare akışında brief yalnızca şablondan geliyor. Doğrulayıcı yok (`agent/pipeline.py:277`,
    `TODO(P2): LLM brief + validator`).
  - İzleme modunda LLM gözcü ve denetçi çıktılarındaki kanıt ID'leri kontrol ediliyor
    (`agent/watch/tools.py:245 unknown_evidence`). Ama metindeki **sayılar** (mesafe, hız, araç sayısı)
    kontrol edilmiyor.
  - İlke var ("her sayı deterministik bir araçtan gelir", AGENT_FLOW §9), onu denetleyen kod yok.
- **Neden gerekli:** Panelin en net isteği: yapay zekânın kararını bağımsız bir kontrol bilgisayarı
  denetlemeli. LLM "1.2 km" ya da "3 kamyon" gibi bir sayı uydurabilir (OWASP LLM09). Doğrulanmamış bir sayı
  operatörü yanıltır.
- **Zorluk:** Orta (3–5 saat).
- **Teknik anlatım:** Her LLM çıktısına deterministik kontroller uygulanır. Bu çıktılar: gözcü gerekçeleri ve
  notları, denetçi uyarıları, LLM brief'i eklendiğinde brief.
  1. **Kanıt:** her ID analizde veya kayıtta var. İzleme modunda zaten var, tek kare akışına da taşınır.
  2. **Sayılar:** metindeki sayılar birimleriyle (km, m, m/s, m/dk, dk, adet) regex ile çıkarılır. Atıf
     yapılan kanıtın olgu tablosundaki değerle karşılaştırılır (±%5 veya ±1 adet).
  3. **Seviye:** kural tabanlı seviyeden en fazla ±1 kademe fark.
  4. **Politika:** hiçbir rapor seviyeyi düşürmedi. Aldatma göstergesi varsa metinde anılıyor.

  Başarısız olursa bir onarım denemesi yapılır (hata mesajıyla), sonra şablona veya kural tabanlı sonuca
  düşülür. Çıktı UI'da "doğrulanmadı" olarak işaretlenir ve olay kaydına yazılır. Türetilmiş olgular için ID
  gerekir (ör. `MOT-T0122`), yoksa sayıların hangi olguya ait olduğu bilinemez.
- **Herkesin anlayacağı anlatım:** Dil modelinin yazdığı her cümleyi, düz koddan oluşan katı bir denetçi
  kontrol eder. Uydurma bir sayı ya da kaynağı olmayan bir iddia varsa o metin operatöre gösterilmez.

---

## Kesişen maddeler

### Z10. Bütçe kontrolü ve görünür bozulma modu
- **Şu anki durum:**
  - LLM tarafında önlemler var (M R8.1'in tespiti): `GLMClient`, disk cache, eşzamanlılık sınırı, gözcü başına
    araç çağrısı üst sınırı, kayıtlı çalıştırmalar (`agent/watch/recordings.py`).
  - Kalan bütçeyi soran kod yok (`key/info` hiçbir yerde çağrılmıyor).
  - Dedektör ve LLM fallback'leri var ama analiz ekranında hangi modda çalışıldığı tek bir yerde görünmüyor.
- **Neden gerekli:** Görev tanımı: 15 USD, sıfırlanmaz. "Sonsuz döngüye giren bir agent'ı fark etmezseniz
  tükenebilir." Bütçe sahnede biterse demo durur. Panel ayrıca kademeli bozulma ve operasyonel verimlilik
  istedi.
- **Zorluk:** Kolay (1–2 saat).
- **Teknik anlatım:**
  - **Bütçe:** çalıştırma başında ve her N çağrıda `GET {gateway}/key/info` → `max_budget − spend`. Eşiğin
    altında izleme modu kayıtlı çalıştırmaya, tek kare akışı şablon brief'e geçer.
  - **Görünürlük:** `/api/health` kalan bütçeyi gösterir. Her analiz ve çalıştırma, çalıştığı modu
    (`full / llm_off / detector_degraded / tracks_only / replay`) bir alan olarak taşır ve UI bunu rozet
    olarak gösterir.
- **Herkesin anlayacağı anlatım:** Dil modeli için sınırlı ve yenilenmeyen bir bütçemiz var. Sistem ne kadar
  para kaldığını düzenli kontrol eder; biterse durmadan kayıtlı sonuçlarla devam eder ve hangi modda
  çalıştığını ekranda söyler.

### Z11. Simülasyon / adversarial test takımı
- **Şu anki durum:**
  - Birim testleri ve golden test var.
  - Tehdidi düşüren raporun seviyeyi düşürmediğini gösteren bir test var
    (`tests/services/test_reports_risk.py:113`).
  - İzleme modu için seviye kuralı testleri var (`tests/agent/test_watch_registry.py`).
  - Gerçek karelerde aldatma, sahte sayı, bütçe bitişi ya da tespitsiz çalışma senaryosunu kapsayan bir test
    takımı yok.
- **Neden gerekli:** Panel "simülasyon testleri" istedi. Mentorlar teknik kaliteyi puanlıyor. Yukarıdaki
  maddelerin çalıştığını ancak bu testler kanıtlar; sonuçlar bir sunum slaytına da dönüşür.
- **Zorluk:** Orta (3–4 saat; LLM gerektiren testler `FakeLLMClient` ile yazılır, gerçek LLM çağrılmaz).
- **Teknik anlatım:** Senaryo tabanlı `pytest` testleri, her biri tek satırlık beklenen sonuçla:
  1. **Gerçek aldatma:** `img_006444` / REP-61 ve `img_000733` / REP-113 → `deception_indicator` ve ilgili
     araçta +1 seviye (Z4, Z6, Z7).
  2. **Doğru dost raporu cezalandırılmıyor:** REP-06, REP-78, REP-120 → tutarlı, seviye değişmiyor (Z4).
  3. **Sahte dost raporu:** dolanan bir araca (T0043 / `img_006673`) "dost araç" raporu eklenir → seviye
     düşmüyor.
  4. **Sahte "bölge temiz" ve olumsuzluk:** "ağır araç yok" + karede kamyon → CONTRADICTED (Z5).
  5. **Prompt injection:** talimat içeren rapor → güven 0, seviye değişmiyor.
  6. **Uydurma sayı:** LLM çıktısında mesafe değiştirilmiş → doğrulayıcı reddediyor, şablona düşülüyor (Z9).
  7. **Bütçe bitti:** sahte düşük `key/info` → kayıtlı moda geçiş (Z10).
  8. **Tespit yok:** dedektör dosyası yok → sessiz LOW değil; uyarı + "kanıt yetersiz" + yalnız track
     araçlar (Z1, Z2, Z8).
- **Herkesin anlayacağı anlatım:** Sistemi bilerek kandırmaya ve bozmaya çalışan testler yazıyoruz: sahte
  raporlar, uydurma sayılar, biten bütçe, kapalı kamera. Her birinde sistemin güvenli davrandığını otomatik
  olarak kanıtlıyoruz.

---

## Panel notları ↔ maddeler

| Panel notu | Karşılayan maddeler |
|---|---|
| Doğrulanabilir ve açıklanabilir yapay zekâ | Z9 (her sayı ve ID doğrulanır), Z6 / Z7 (aldatma gerekçesi faktör dökümünde), Z2 (görülmeyen araç açıklaması) |
| Bağımsız "kontrol bilgisayarı" | Z9 |
| Simülasyon testleri | Z11 |
| "Bilmiyorum" diyebilmek (open-set) | Z1 (sessiz LOW yok), Z8 (kanıt yetersiz), Z2 (yalnız track notu) |
| Kademeli bozulma, bileşenlerin birbirini tutması | Z1 (dedektör → track), Z2 (track'ler dedektörün yerini tutar), Z10 (bütçe → kayıt; görünür mod) |
| Operasyonel verimlilik | Z10 (bütçe), Z4 / Z5 (yanlış çelişki ve yanlış doğrulamalar operatörün zamanını harcamaz) |

## Önerilen uygulama sırası

Maddeler akış sırasıyla yazıldı. Bağımlılıklar nedeniyle uygulama sırası farklı:

1. **Z1:** tespit dosyası + sessiz LOW'un kaldırılması (diğer tip kontrollerinin önkoşulu).
2. **Z3 → Z4:** hareketsiz tanımı, sonra çekim anı eşlemesi.
3. **Z5, Z6:** olumsuz raporlar ve yön kontrolü.
4. **Z7:** aldatma +1 (Z4 ve Z6'dan sonra).
5. **Z2, Z8:** yalnız track araçlar ve kanıt yetersiz bayrağı.
6. **Z10:** bütçe ve mod görünürlüğü.
7. **Z9:** doğrulayıcı.
8. **Z11:** test takımı. Her maddenin kendi testi o maddeyle birlikte yazılır; burada senaryo takımı
   tamamlanır.

Her adımdan sonra golden test yeşil kalmalı, domain modeli değiştiyse `gen-types` çalıştırılmalı ve politika
değişikliği AGENT_DESIGN'a işlenmeli.

---

## Bilerek dışarıda bırakılanlar

Değerli ama bu listenin ölçütlerini karşılamıyor. Zaman kalırsa ele alınmalı.

| Madde | Kaynak | Neden zorunlu değil |
|---|---|---|
| Admiralty kodları, SALUTE tablosu, rapor ekranı | M R6.10, R8.4, R10.1 | Sunum değeri yüksek ama bugünkü sonuçları düzeltmiyor |
| Hiç çıkmayan CRITICAL, "< 1 km" kademesi, duraklama faktörü | M R7.1, R7.3; F 7.1 | 26 Eylül kalibrasyonu odak sorununu çözdü (dört aday 1. sırada). Kalanlar ince ayar ve takım kararı gerektiriyor |
| Operatör onayı / itiraz kaydı | M R9.1 | Güçlü bir jüri cevabı ama panel notlarında yok. AGENT_FLOW §3 ile §12 arasındaki tutarsızlık yine de düzeltilmeli |
| Kırmızı takım eleştirmeni (ikinci LLM) | F 8.3 | Panelin "kontrol bilgisayarı" isteği Z9'daki deterministik doğrulayıcıyla karşılanıyor |
| Karşı-olgusal açıklamalar, sağlamlık testi, popülasyon yüzdelikleri | F 7.5, 7.6, 5.3 | Açıklanabilirliği artırır; faktör dökümü ve kanıt ID'leri temel ihtiyacı karşılıyor |
| Dedektör kalibrasyonu, open-set filtresi, ensemble, imgsz | F 2.4–2.8, M R2.2 | Tespit kalitesini artırır; Z1 olmadan ölçülemez bile |
| Renk kontrolü (GLM ile bakış dahil) | F 2.9, M R2.4 | 8 raporu etkiliyor; GLM ile bakış takım kararı bekliyor |
| GeoJSON, ICD 203 dili, "bilinmeyen" sembolleri | M R3.2, R8.2, R10.2 | Kalite ve sunum |
| Gün tablosu, analist sohbeti | F 9.1, 9.2 | Kapsam genişliği; CLAUDE.md'ye göre 1. ve 2. önceliklerden sonra gelir |
