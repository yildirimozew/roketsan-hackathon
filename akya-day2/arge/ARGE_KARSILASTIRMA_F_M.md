# AR-GE Karşılaştırması: arge_f ↔ arge_m

Karşılaştırılan belgeler:

- **F:** `arge/arge_f/AGENT_CAPABILITIES_RND.tr.md` (65 madde, F1–F5 + 1.1–9.3; yalnızca yazılı belge)
- **M:** `arge/arge_m/ARGE_M.md` (36 madde, R1.1–R10.2; çalışan prototip kod + otomatik testler)

Çelişkiler `data/` içindeki gerçek veride ve **güncel** backend koduyla yeniden ölçüldü (2026-09-26). Tespit
dosyası repoda olmadığından, tespit gerektiren ölçümlerde kare içindeki track uç noktaları tespit yerine
kullanıldı.

---

## 1. Özet

1. **İki belge büyük ölçüde aynı yönü gösteriyor.**
   - Konum ve eşleşme: kare→bölge ataması doğru, eşleşme kapısı fazla geniş, eşleşmeyen nesnelere
     hipotez verilmeli.
   - Hareket: "hareketsiz" eşiği yanlış, üs etrafında dolanma ayırt edici bir sinyal.
   - Raporlar: olumsuz raporlar ("ağır araç yok") tersine okunuyor. Kimlik beyanı seviyeyi düşüremez;
     doğrulanabilir kısmı çelişirse aldatma sayılıp seviye +1 artmalı. Kaynak güveni sabit değil, veriden
     öğrenilmeli.
   - Brief ve güvenlik: brief'teki sayılar doğrulanmalı, LLM bütçesi kontrol edilmeli.
2. **En önemli çelişki: raporlar hangi ana göre kontrol edilmeli?** M'nin bulgusu doğru. Raporlar aracın
   **karenin çekim anındaki** konumunu tarif ediyor, rapor saatindeki konumunu değil.
   - 72 koordinatlı raporun 60'ı bir track'in son noktasına 15 m'den yakın. Rapor saatindeki konuma 15 m'den
     yakın olan yalnızca 17.
   - Bu yüzden F'deki "dost raporların 15'inin 0'ı tutarlı" bulgusu ve buna dayanan demo önerisi
     (REP-06 / REP-78 / REP-120) **yanlış**.
   - Doğrusu: 15 "üsse doğru ilerleyen dost araç" iddiasının 13'ü tutuyor. Hareketle çelişen, yani gerçek
     aldatma adayı olanlar yalnızca **REP-61** ve **REP-113**.
3. **İki belge de kısmen eskimiş.** Repo iki belgeden sonra değişti.
   - İzleme modu (LLM gözcüler + baş denetçi) ve `GLMClient` eklendi.
   - `data_dir` artık `data/` gösteriyor.
   - Risk puanlaması 26 Eylül'de yeniden kalibre edildi: dolanma +35, sabit mesafede yörünge +30, seviye
     tavanı eklendi.
   - Sonuç: F'deki "22 HIGH, dört aday geride kalıyor" ölçümü ve M'deki "dolanma puana girmiyor" tespiti
     artık geçerli değil. Güncel kodla 40 kare **19 LOW, 13 MEDIUM, 8 HIGH, 0 CRITICAL** çıkıyor ve dört
     aday kendi karelerinde **1. sırada**.
4. **Kapsam farkı.**
   - F daha geniş ama yalnızca yazılı: pipeline'ın her adımı, açıklanabilirlik, LLM brief, critic, gün
     tablosu.
   - M daha dar ama çalışan kod ve testlerle geliyor. Rapor değerlendirmesinde çok daha derin: SALUTE,
     Admiralty, çok araçlı iddialar, yokluk iddiaları. Standartlar (NATO, OWASP, ICD 203) ve izleme modu da
     kapsamında.

---

## 2. Önce bilinmesi gereken: repo değişti, iki belgedeki eskimiş tespitler

| Konu | F ne diyor | M ne diyor | Güncel kod |
|---|---|---|---|
| LLM istemcisi | F3: "Yok, sadece protokol, model `glm-4`" | R8.1: "Büyük kısmı yapılmış (`GLMClient`)" | **M doğru.** `agent/llm_client.py:GLMClient` var, `llm_model = "glm-5.3-flash"` |
| Veri yolu | "Şimdilik olduğu gibi bırakıldı (`data/stage2`)" | `data/` üzerinde çalışıyor | `config.py: data_dir = REPO_DIR / "data"`; CLAUDE.md de `data/` diyor. **F eskimiş** |
| Risk puanlaması | 7.2: "22 HIGH / 17 MEDIUM / 1 LOW; dört aday 3.–5. sırada; dolanma rubrikte yok" | R5.2 / R7.2: "`loops_around_base` puana girmiyor"; R7.1: "duraklama 10 (+5)" | Kalibrasyon (AGENT_DESIGN §3 adım 7): dolanma **+35**, yörünge **+30**, duraklama **5 (+5)**, yaklaşma 15/8, seviye tavanı. Ölçüm: **19 LOW, 13 MEDIUM, 8 HIGH, 0 CRITICAL**, dört aday kendi karelerinde **1. sırada** (T0043 65, T0158 70, T0172 65, T0198 65 puan). **İki belge de eskimiş** |
| Ajan modları | "Sadece pipeline" kararı; X tablosunda "LLM tool-calling döngüsü elendi" | İzleme modunu biliyor, oradaki araçlara atıf yapıyor | Üçüncü mod olarak **izleme modu** var: gözcü ve denetçi LLM'leri tool-calling yapıyor (AGENT_DESIGN §2, §12). F'deki karar yalnızca **tek karelik analiz akışı** için geçerli; bu açıkça yazılmalı |

> F'deki 7.2 maddesinin "neden" kısmı (dolanma ve yakın geçiş gerçek sinyal) kalibrasyonla büyük ölçüde
> karşılandı. Kalan açıklar: CRITICAL hiç çıkmıyor, "< 1 km" kademesi hiç çalışmıyor (M R7.3), popülasyon
> yüzdelikleri ve karşı-olgusallar yok.

---

## 3. Ortak noktalar

İki belgenin aynı sonuca vardığı maddeler. "Kim daha ileride" sütunu, hangisinin kod veya ölçümle daha somut
olduğunu gösterir.

| Konu | F | M | Ortak sonuç | Kim daha ileride |
|---|---|---|---|---|
| Kare→bölge ataması | 1.4, X | R1.1 | İki yöntem 40/40 aynı; değişiklik gerekmez | Eşit (ikisi de ölçtü) |
| Hafif / ağır üst sınıfı | 2.1 | R2.1 (içinde) | Raporlar "ağır araç" diyor; kamyon + otobüs = ağır | F (ayrı madde) |
| Track recall ile dedektör seçimi | 2.2 | R2.2 | 206 kare içi track ucu etiketsiz bir recall ölçüsü verir | M (imgsz 960/1280 sorusuna uyguluyor) |
| Tespitleri önceden hesaplamak | 2.2 (`make detections`) | R2.3 | 40 karenin tespitleri bir kez üretilip kaydedilmeli | M (öncelikli ve gerekçeli) |
| Aday → olgu yükseltme | 2.3 | R2.1 (içinde) | Track noktası yanındaki düşük güvenli kutu olguya yükseltilir | F (döngüsel kanıt riskini de yazıyor) |
| Renk kontrolü | 2.9 | R2.4 | Rapordaki renk, kutudaki baskın renkle karşılaştırılır | M (8 renkli raporu listeliyor) |
| PDF örneği ikinci altın test | 3.1 | R3.1 | `img_000123` → (39.94439, 32.86350) testi eklenmeli | **M (test yazıldı)** |
| Eşleşme kapısı fazla geniş | 4.1 | R4.1 | `gate = max(3 m, k × köşegen × GSD)`, son değer p95'ten | Eşit |
| Eşleşmeyen nesne hipotezleri | 4.4 | R4.2 | `parked_likely`, `false_positive_likely`, `missed`, `outside_near_edge` | F (öksüz track'lerin risk hesabına girmesini de istiyor: 5.8) |
| "Hareketsiz" eşiği yanlış | 5.1 | R5.1 | Mevcut 1 m/s eşiği gerçek hareketi "durma" sayıyor | M (veriyle seçilmiş eşik, test) — eşik değeri farklı, bkz. Ç4 |
| Üs etrafında dolanma | 5.2 | R5.2 | Asıl tehdit sinyali; 4–5 araç öne çıkıyor | M (test; 5. aracı T0034'ü de buluyor) |
| Hız ve yön pencereden | 5.1 (kısmen) | R5.3 | Tek adımlık yön titreşimdir; pencere üzerinden hesaplanmalı | M (ayrı madde, test) |
| Olumsuzluk ("ağır araç yok") | 6.1 | R6.2 | Ana kod bunu kamyon görüldü diye okuyor | **M (düzeltildi, test)** |
| Bağlam / ilgisiz raporlar | 6.1, 6.7 | R6.3 | Hava, "dün gece", telsiz → ilgisiz; telsiz kaybı dikkat notu | M (39 raporu sınıflıyor) |
| Prompt injection | 6.10, F5 | R6.4, R9.2 | Rapor metni veri, talimat değil; testle kanıtlanmalı | M (kural katmanı test edildi) |
| Atomik iddialar | 6.3 | R6.1 | Rapor parçalara ayrılır, her parça ayrı kontrol edilir | **M (SALUTE + 7 kategori, kod)** |
| Yön kontrolü "üsse doğru" | 6.4 | R6.7 | "Üsse doğru" yalnızca "hareketli" diye okunmamalı | M (≥ 200 m / 30 dk kuralı, test) |
| Kimlik kuralı + aldatma +1 | 6.5, 7.3 | R6.7, R7.4 | Kimlik doğrulanamaz, seviyeyi düşüremez; doğrulanabilir kısım çelişirse +1 seviye | İlke aynı; **hangi raporlar** konusunda çelişki var, bkz. Ç1–Ç2 |
| Yokluk / bölge raporları | 6.7 | R6.8 | "Bölgede hareket yok" raporu bölge kareleriyle kontrol edilir | M (REP-42 örneği, kod) |
| Yoğunluk "olağan N araç" | 6.7 | R6.9 | Olağan sayı ayrı alan; karedeki araçla karşılaştırılır | M (kod) |
| Kaynak güvenilirliği | 6.6 | R6.10 | Sabit 0.8 / 0.5 güven veriyle desteklenmiyor; Beta sayımıyla öğrenilmeli | **M (Admiralty A–F / 1–6, kod)** |
| LLM bütçesi | F3 | R8.1 | `key/info` ile kalan bütçe kontrol edilmeli | M (mevcut kodu doğru tarif ediyor) |
| Sayı doğrulayıcı | 8.2 | R8.3 | Brief'teki sayılar kayıtlı değerlerle karşılaştırılmalı | Eşit (ikisi de fikir) |
| Adversarial testler | F5 | R9.2 | Sistemi kandırmaya çalışan testlerle güvenlik kanıtlanmalı | M (OWASP eşlemesi) |
| Brief yapısı | 8.1 | R8.2 | Önce sonuç, sonra gerekçe, raporlar, belirsizlik, eylem | M (BLUF + ICD 203 ölçeği) |
| Demo karesi `img_000926` | 8.5 | §8 | T0172'nin dolanması + aynı karedeki "dost" raporu iyi bir demo | Eşit (ama rapor yorumu farklı, bkz. Ç2) |

---

## 4. Ayrışan noktalar (yalnızca bir belgede olanlar)

### 4.1 Yalnızca M'de

| M | Konu | Not |
|---|---|---|
| R2.2 | imgsz 1280 mi 960 mı | 1920 px karelerde küçük araçlar kaybolabilir; F bu soruyu sormuyor |
| R3.2 | GeoJSON çıktısı, [boylam, enlem] | Kod + test var |
| R6.6 | Çok araçlı iddialar ("5 kamyon") | "En yakın N track hepsi uymalı" kuralının yanlış çelişkiler ürettiğini ölçmüş (11 → 6 çelişki); F'de yok |
| R7.1 | "Üs yakınında duraklama" 206/226 track'te puan veriyor | Kalibrasyonla puan 10 → 5 oldu ama faktör hâlâ neredeyse herkese çalışıyor; öneri: yalnızca "gelip duran" araç (7/226) |
| R7.3 | "< 1 km" mesafe kademesi hiç çalışmıyor | Hiçbir araç üsse 1553 m'den yakın değil; güncel kodda kademeler hâlâ 30/20/10 → **hâlâ geçerli** |
| R8.2 | ICD 203 olasılık dili | "Muhtemel" gibi kelimelere sabit yüzde aralıkları |
| R8.4 | Brief'te Admiralty kodu | Her rapor için tek satırlık hazır karşılaştırma |
| R9.1 | NATO Sorumlu YZ + operatör onayı | İzleme modunda `alert_operator` onaysız; AGENT_FLOW diyagramı hâlâ "onay ister" diyor (dokümanlar arası tutarsızlık) |
| R10.1 | Rapor inceleme ekranı | SALUTE tablosu + Admiralty; F'de yalnızca UI çipleri geçiyor |
| R10.2 | "Bilinmeyen" harita sembolleri | APP-6 çerçevesi; F'de yok |
| §7 | Standartlar eşlemesi | NATO Admiralty, SALUTE, OWASP LLM Top 10, ICD 203, RFC 7946 |
| – | İzleme modu | M'nin bulguları izleme modunu da kapsıyor (`services/watch.py`, `get_reports`); F yalnızca tek kare akışını ele alıyor |
| – | Çalışan kod + testler | `arge_m/` bağımsız paket, 62 test; `python -m arge_m.run` 137 raporu işliyor |

### 4.2 Yalnızca F'de

| F | Konu | Not |
|---|---|---|
| F1 | Türetilmiş kanıt ID'leri (`MOT-`, `RISK-`, `CHK-`) | Sayı doğrulayıcının (8.2 / R8.3) önkoşulu |
| F4 | Kademeli bozulma modları | `full / llm_off / detector_degraded / no_tracks` |
| 1.1–1.3 | Kare bağlam paketi, metadata bütünlüğü, OOD bayrağı | 3 aşırı parlak 1920×1080 kare |
| 1.5–1.8 | Kapsama poligonu, kör nokta eşiği, üsse bakan kenar, sektör kardeşleri | 1.5, 6.8'in önkoşulu |
| 2.4–2.8 | Güven kalibrasyonu, küçük kutu bayrağı, dedektör karnesi, open-set, ensemble | Dedektör kalitesi |
| 3.2 | Veriye göre hata yarıçapı | M R4.1 aynı p95 fikrini kapıya uyguluyor |
| 4.2, 4.3, 4.5 | İki geçişli eşleme, "karar etkilenmedi" kontrolü, yön ile eşitlik bozma | |
| 5.3–5.8 | Popülasyon yüzdelikleri, davranış etiketleri, ortak hareket sözlüğü, ETA aralığı, fiziksel olabilirlik, öksüz track'ler için hareket analizi | 5.4'ün bir kısmı artık `services/behavior.py:behavior_class` olarak var |
| 6.8, 6.9 | Kapsamı dikkate alan kararlar, raporlar arası tutarlılık | |
| 6.10, 6.11 | LLM ile çıkarım + karar, rapor penceresi ayarı | |
| 7.1 | Eyleme dayalı seviye tanımları | |
| 7.4–7.7 | Kanıt yetersizliği bayrağı, karşı-olgusallar, sağlamlık, fuzzy + DS | |
| 8.3–8.5 | Kırmızı takım eleştirmeni, Brief genişletmeleri, aldatma ifadesi | |
| 9.1–9.3 | Gün tablosu, analist sohbeti, SSE canlı olaylar | |

---

## 5. Çelişen noktalar

Her çelişki güncel kod ve gerçek veriyle yeniden ölçüldü. "Karar" sütunu ölçüme göre hangi belgenin
doğru olduğunu söyler.

### Ç1. Rapor hangi ana göre kontrol edilmeli? — **M doğru**
- **F (6.2):** "Raporlar rapor saatindeki track konumlarından üretilmiş gibi görünüyor: 72 raporun 47'sinde o
  dakikada 60 m içinde bir track var." Öneri: rapor saatinin ±15 dk çevresi.
- **M (R6.5):** "Raporlar aracı karenin çekim anındaki yeriyle anlatıyor." 60/72 rapor bir track'in son
  noktasına 15 m'den yakın.
- **Ölçüm:**

  | Mesafe | Track'in son noktasına (çekim anı) | Rapor saatindeki track konumuna |
  |---|---|---|
  | ≤ 15 m | **60 / 72** | 17 / 72 |
  | ≤ 60 m | **71 / 72** | 47 / 72 |

  F'deki 47 sayısı doğru ama yanlış yorumlanmış. Rapor saatindeki yakınlıkların çoğu park halindeki
  araçlardan geliyor; park etmiş bir aracın konumu iki anda da aynı.
- **Etki:** mevcut `services/reports.py:verify_claim` ("presence" ve "activity" kontrolleri),
  `docs/AGENT_DESIGN.md` §3 adım 6b ("tracks at the report's own time") ve `docs/AGENT_FLOW.md` §7'deki
  REP-120 / REP-126 anlatımı aynı hatalı varsayıma dayanıyor. F'nin 6.2 maddesi M'nin R6.5 maddesiyle
  değiştirilmeli.

### Ç2. Hangi "dost" raporları aldatıcı? — **M doğru**
- **F (6.4, 6.5, 8.5):** "15 dost araç iddiasının 0'ı tutarlı. REP-06 (`img_006673`), REP-78 (`img_000926`) ve
  REP-120 (`img_000860`) CONTRADICTED; demonun en güçlü anı."
- **M (R6.7, §8):** "15 iddianın 13'ü tutuyor. REP-61 (T0075 uzaklaşıyor 4.1 → 5.3 km) ve REP-113 (T0124
  yaklaşmıyor 3.4 → 3.5 km) çelişiyor. Demo: `img_006444` / REP-61."
- **Ölçüm** (çekim anı eşlemesi; 15 raporun hepsi bir track'in son noktasına **0.2–0.6 m**):

  | Durum | Raporlar |
  |---|---|
  | Tutarlı (son 30 dakikada üsse yaklaşıyor, ≥ 200 m) | 13 rapor: REP-06 (T0109, 3.3 → 1.8 km), REP-78 (T0168, 7.8 → 1.7 km), REP-120 (T0192, 7.6 → 1.6 km) dahil |
  | **Çelişiyor** | **REP-61** (T0075, 4.1 → 5.3 km) ve **REP-113** (T0124, 3.4 → 3.5 km) |

  F'nin ölçümü (bu oturumda benim yaptığım ölçüm) mevcut kodun rapor saati varsayımını kullanıyordu. Bu
  yüzden doğru raporları "çelişiyor" gösterdi.
- **Etki:**
  - F'deki demo önerisi (8.5) ve 6.5'teki örnekler değişmeli: aldatma demosu `img_006444` / REP-61 ve
    `img_000733` / REP-113 olmalı.
  - `img_000926` ve `img_006673` yine iyi demo kareleri, ama **dolanan araç** yüzünden. Oradaki dost raporlar
    tutarlı ve başka bir araçla ilgili.
  - Mevcut kod bugün bu doğru raporları "çelişiyor" olarak işaretliyor. Aldatma +1 kuralı Ç1 düzeltilmeden
    uygulanırsa **yanlış araçların seviyesini artırır**. Uygulama sırası: önce R6.5, sonra +1.

### Ç3. Risk puanlamasının durumu — **ikisi de eskimiş**
- **F (7.2):** 22 HIGH, dört aday 3.–5. sırada, dolanma rubrikte yok.
- **M (R5.2, R7.2):** dolanma puana girmiyor; öneri +20.
- **Güncel kod:** dolanma +35, yörünge +30, seviye tavanı. Ölçüm: 19 LOW, 13 MEDIUM, 8 HIGH, 0 CRITICAL;
  dört aday 1. sırada. T0034 (M'nin 5. dolanan aracı, üsse 4.5 km) MEDIUM kalıyor, çünkü 5 km içindeki
  dolanmaya HIGH izni veriliyor ama puanı yetmiyor.
- **Karar:** F 7.2 ve M R7.2 "büyük ölçüde yapıldı" olarak güncellenmeli. Kalanlar: CRITICAL hiç çıkmıyor,
  "< 1 km" kademesi hiç çalışmıyor (M R7.3), duraklama faktörü neredeyse herkese çalışıyor (M R7.1).

### Ç4. "Hareketsiz" eşiği — **kısmi çelişki; ikisi farklı soruyu cevaplıyor**
- **F (5.1):** adım başına 5 m gürültü tabanı; `moving` = 5 dakikalık adım > 5 m.
- **M (R5.1):** son 60 dakikada son konumdan en büyük uzaklık ≤ 100 m → hareketsiz. Park halindeki
  track'ler en fazla 39 m, diğerleri en az 1087 m gidiyor; eşik bu boşlukta.
- **Karar:**
  - Rapordaki "duruyor" iddiası için M'nin pencere tabanlı eşiği daha doğru. Veriyle seçilmiş ve tek bir
    titreyen adıma takılmıyor.
  - F'nin adım tabanlı ayrımı `moving_share` ve dwell listesi için kullanılabilir.
  - F'deki "5 m eşiğinde REP-78 ve REP-83 tutarlı görünür" uyarısı Ç2 nedeniyle anlamını yitirdi. O raporlar
    zaten tutarlı.

### Ç5. Dolanma (sweep) tanımı — **küçük çelişki; backend M'nin tanımını kullanıyor**
- **F (5.2):** net işaretli toplam. T0047'nin mutlak toplamı 1029° ama net değeri 60° olduğu için "sadece
  ileri geri gidiyor" deniyor.
- **M (R5.2) ve güncel kod (`services/behavior.py`):** biriken açının en büyük mutlak değeri (`max|cum|`),
  eşik 270°.
- **Ölçüm:** beş dolanan araçta iki tanım aynı sonucu veriyor (T0043 441°, T0158 323°, T0172 549°, T0198
  320°, T0034 544°). T0047 için `max|cum|` = 158°, dolanma değil. Ama backend onu ayrı bir desen olan
  `fixed_range_orbit` (sabit mesafede yörünge, +30) olarak sınıflıyor.
- **Karar:** F, backend'deki `max|cum|` tanımına uymalı. F'deki "T0047 zararsız ileri geri" yorumu backend'in
  yörünge sınıfıyla çelişiyor ve düzeltilmeli.

### Ç6. Görüntüye LLM ile ikinci bakış — **karar gerekiyor**
- **F (2.9, X):** GLM vision "ikinci bakış" elendi; görüntü modeli yalnızca `detect` adımında çalışır.
- **M (R2.4):** renk belirsizse kırpılmış kutu GLM'e gönderilir (cevap ~10–15 s); yalnızca birkaç rapor için.
- **Karar önerisi:** varsayılan olarak kapalı, sadece HSV renk. GLM ile bakış, 8 renkli rapor için opsiyonel
  bir ayar olabilir. Bu, F'nin elediği genel "ikinci bakış"tan dar bir kullanım. Takımın karar vermesi
  gerekiyor.

### Ç7. Kaynak güvenilirliği örneği — **F'nin örneği yanlış**
- **F (6.6):** "resmi durma gözlemleri 16/17, resmi 'dost araç yaklaşıyor' 0/15."
- **M (R6.10):** kontrol edilebilen raporlarda official **45/50**, third_party **22/23**. İki kaynak türü de
  Admiralty B alıyor.
- **Karar:** yöntem aynı (Beta–Bernoulli). F'nin "0/15" örneği Ç2 yüzünden yanlış. M'nin sayıları esas
  alınmalı. Önemli sonuç: "resmi kaynak daha güvenilir" varsayımı da, "resmi kaynak güvenilmez" varsayımı
  da veriyle desteklenmiyor. İki kaynak türü benzer oranda tutuyor.

### Ç8. Mesafe faktörü — **uyumlu, M daha somut**
- **F (7.2):** mesafe ve yaklaşma ağırlığı düşürülmeli (genel öneri).
- **M (R7.3):** yeni kademeler: < 2 km 25, < 3 km 15, < 4 km 5.
- **Karar:** çelişki yok. Yaklaşma ağırlığı kalibrasyonda zaten düşürüldü (15/8), mesafe kademeleri hâlâ
  eski. M'nin önerisi uygulanabilir.

---

## 6. Önerilen düzeltmeler ve birleşik sıra

### 6.1 F belgesinde düzeltilmesi gerekenler
1. **6.2:** "rapor saati ±15 dk" yerine M R6.5 (çekim anı eşlemesi).
2. **6.4 / 6.5 / 8.5 / 7.3:** aldatma örnekleri REP-06 / 78 / 120 değil, REP-61 / REP-113. Demo karesi
   `img_006444`.
3. **6.6:** güvenilirlik örneği M'nin sayılarıyla (45/50, 22/23).
4. **7.2:** kalibrasyon sonrası durum (19 / 13 / 8 / 0, adaylar 1. sırada). Kalan açıklar: CRITICAL,
   "< 1 km" kademesi, duraklama faktörü.
5. **5.2:** sweep tanımı `max|cum|`. T0047 yorumu düzeltilmeli.
6. **F3:** `GLMClient` var. Kalan: bütçe kontrolü (`key/info`), sayı doğrulayıcı.
7. **Kararlar tablosu:** "sadece pipeline" kararının tek kare akışı için olduğu, izleme modunun ayrı bir mod
   olarak var olduğu yazılmalı. Veri yolu satırı artık geçersiz.

### 6.2 Belgelerin dışında düzeltilmesi gerekenler
- `backend/app/services/reports.py:verify_claim`: rapor saati yerine çekim anı eşlemesi (M R6.5).
- `docs/AGENT_DESIGN.md` §3 adım 6b ve `docs/AGENT_FLOW.md` §7 (REP-120 / REP-126 anlatımı): aynı hatalı
  varsayım.
- `docs/AGENT_FLOW.md` §3 diyagramı ("ilk alarm operatör onayı ister"), §12'deki "onay adımı yok" ile
  çelişiyor (M R9.1).

### 6.3 Birleşik öncelik sırası
1. **M R6.5 + R6.7:** raporu çekim anında kontrol et, "üsse doğru" yönünü doğrula. Aldatma +1 kuralı
   (F 6.5 / 7.3) **bundan sonra** gelir.
2. **M R2.3:** 40 karenin tespitlerini hesapla. Tip kontrolleri, "ağır araç yok" raporları ve F'deki bütün
   dedektör maddeleri buna bağlı.
3. **M R6.2 + R6.8 (= F 6.1, 6.7):** olumsuzluk ve yokluk iddialarını backend'e taşı. M'nin kodu ve testleri
   hazır.
4. **M R7.1 + R7.3:** kalan puanlama açıkları (duraklama faktörü, mesafe kademeleri). CRITICAL'ın hiç
   çıkmamasının değerlendirilmesi (F 7.1).
5. **M R8.1 + R8.3 (= F F3, 8.2):** bütçe kontrolü ve sayı doğrulayıcı. F1'deki türetilmiş kanıt ID'leri
   bunun önkoşulu.
6. **M R6.10 + R8.4 + R10.1:** Admiralty kodları; F 6.6 bununla birleştirilir.
7. **F'ye özgü açıklanabilirlik maddeleri:** 4.4 / 5.8 (öksüz track'ler riske girsin), 7.4–7.6 (kanıt
   yetersizliği, karşı-olgusal, sağlamlık), 8.3 (critic).
8. **Kalanlar:** F 1.x, 2.4–2.8, 9.x; M R2.2, R2.4, R3.2, R8.2, R9.1, R10.2.

---

## 7. Ölçüm notları
- **Güncel kod:** ölçümler, AGENT_DESIGN §3 adım 7'deki kalibrasyonun uygulanmış olduğu backend koduyla yapıldı
  (`services/risk.py`, `services/behavior.py`).
- **Vekil tespitler:** tespit yerine kare içindeki track uç noktaları kullanıldı, hepsi `car` etiketli.
  Gerçek dedektörle araç tipi puanları eklenir; bazı seviyeler yükselebilir.
- **Ç1 ve Ç2:** tespitten bağımsız ölçümler (yalnızca raporlar ve track'ler), bu yüzden kesin.
- **Betik:** ölçüm betiği repo dışında (oturum scratchpad'i). İstenirse `arge/` altına alınabilir.
