# Level-Up AI | ROKETSAN Yapay Zekâ Hackathonu: Case Bilgilendirme

**Araç Tespiti ve Saha Raporu Destekli LLM Agent**
Tarih: 25 Eylül Cuma · 27 Eylül Pazar

> Konuşmacı notu: Açılış, hackathonun iki aşamalı yapısını ve tarihleri kısaca tanıt.

---

## 2. Yarışma Akışı

**1. Aşama · Kaggle (25-26 Eylül): Araç Tespiti**
Drone görüntülerindeki araçları tespit edip car, van, truck ve bus olarak sınıflandıran bir model geliştirin. Modelinizi iyileştirerek Kaggle sıralamasında üst sıralara çıkmak için yarışın.
Değerlendirme: mAP@0.5 · Private Leaderboard

**2. Aşama · Ajan (26-27 Eylül): Saha Raporu Destekli LLM Agent**
Tespit modelinizi kullanan bir LLM agent geliştirin. Agent, görüntüyü hareket kayıtları ve saha raporlarıyla birlikte değerlendirip durumun ne kadar kritik olduğuna karar verir ve kararını gerekçelendirir.
Değerlendirme: Mentor kod incelemesi · Jüri sunumu

> Konuşmacı notu: İki aşamanın birbirini nasıl beslediğini anlat. Birinci gün tespit modeli geliştiriliyor, ikinci gün bu modeli kullanan ve karar veren agent kuruluyor.

---

## 3. Aşama 1 · Kaggle: Özet: Araç Tespiti

- Drone görüntülerinde alanı **200 px² veya daha büyük** araçları tespit edin. (200 px² = etiketlenen en küçük araç alanı)
- Her aracı dört sınıftan birine yerleştirin: **car, van, truck, bus**.
- Eğitim verisinde konum ve sınıf hazır; test görüntülerini modeliniz etiketleyecek.
- Değerlendirme metriği: **mAP@0.5**
- İlgili tüm dosyalar Kaggle'daki yarışma sayfasında.

> Konuşmacı notu: Aşama 1 görevini anlat. 200 px² eşiğini ve dört sınıfı vurgula.

---

## 4. Aşama 1 · Veri: Etiketlenmiş bir örnek

*(Görsel: etiketli örnek drone karesi)*

- Eğitim setindeki her araç için kutu (x, y, w, h) ve sınıf etiketi verilir.
- Etiketler `train/annotations.csv` dosyasındadır; koordinatlar her görüntünün kendi piksel ölçülerine göredir.

---

## 5. Aşama 1 · Veri: Kaggle'daki dosyalar

Kaggle Data Explorer (1.94 GB):
```
test/
  images/
train/
  images/
  annotations.csv
sample_submission.csv
```

- train: **6.471** etiketli görüntü · test: **2.118** etiketsiz görüntü
- `annotations.csv` kolonları: `image_id, x, y, w, h, label`

`annotations.csv` ekran görüntüsünden (4.87 MB): 6181 benzersiz image_id; x aralığı 0–1988, y 0–1477, w 8–983, h 6'dan başlıyor. Örnek satırlar:

| image_id | x | y | w | h |
|---|---|---|---|---|
| img_000005 | 0 | 639 | 109 | 55 |
| img_000005 | 0 | 665 | 81 | 65 |
| img_000005 | 2 | 613 | 148 | 56 |

---

## 6. Aşama 1 · Submission dosyası

```
image_id,PredictionString
img_000001,car 0.93 976 533 98 95 van 0.71 1012 276 150 76
img_000002,none
```

- Test setindeki her görüntü için tam bir satır; PredictionString boşlukla ayrılmış `label confidence x y w h` gruplarından oluşur.
- Tahmin yoksa PredictionString alanına `none` yazın; hücreyi boş bırakmayın.
- `sample_submission.csv` doğru satır kümesiyle gelir; satır eklemeyin, silmeyin. (Ekran görüntüsü: 33.91 kB, 2118 image_id, hepsi `none`.)

---

## 7. Aşama 1 · Değerlendirme: Ne doğru, ne yanlış sayılır?

- **Doğru tahmin:** sınıf doğru ve tahmin kutusu ile gerçek kutu arasındaki IoU en az 0.5.
- **Skor:** dört sınıfın AP değerlerinin ortalaması (mAP@0.5).
- 200 px²'den küçük araçlar ile yaya ve bisiklet gibi nesneler etiketlenmedi; küçük bir aracı işaretlemek puanınızı etkilemez.
- Yaya, boş alan ya da yanlış sınıf için çizilen kutu yanlış tahmin sayılır.
- Düşük confidence'lı kutular göndermek zarar vermez; puanı, doğru tahminlerin daha yüksek confidence ile sıralanması belirler.
- Gördüğünüz skor test setinin Public bölümünden (%40) hesaplanır; final sıralamayı yarışma bitince açıklanan Private bölüm (%60) belirler.

> Konuşmacı notu: Değerlendirme kurallarını netleştir. Etiketlenmemiş küçük araçların puanı etkilemediğini, yaya ve boş alan kutularının yanlış sayıldığını mutlaka söyle.

---

## 8. Aşama 1 · Kurallar: Kaggle Katılım Kuralları

| Takım hesabı | Günlük gönderim | Toplam gönderim |
|---|---|---|
| 1 (Coderspace'e bildirilen tek hesap) | 5 (sınır her gece yenilenir) | 10 (Cuma öğlen · Cumartesi öğlen arası) |

**Süreç**
1. Kaggle aşaması Cuma öğlen başlar.
2. Birden fazla hesapla giriş ya da gönderim yapılamaz.
3. Kaggle aşaması Cumartesi öğlen kapanır.
4. Final notebook Coderspace ve ROKETSAN ekipleriyle paylaşılır.

**Puanlama**
- **Private Leaderboard:** Yarışma bitince oluşan Private Leaderboard skorunuz final sunum puanınıza doğrudan eklenir.
- **Eleme yok:** Kaggle sıralaması düşük olan ekipler elenmez.

> Konuşmacı notu: Hesap ve gönderim kurallarını tek tek geç. Toplam 10 gönderim hakkını ve final notebook paylaşımını hatırlat.

---

## 9. Destek: Sık Sorulan Sorular

**Kaggle'a birden fazla hesapla katılabilir miyiz?**
Hayır. Takım başına yalnızca Coderspace'e bildirilen tek hesap geçerli.

**Günde kaç gönderim hakkımız var?**
Günlük sınır 5 ve her gece yenilenir. Kaggle aşamasında toplam 10 gönderim hakkınız var; finalde bunlardan 2'sini kullanabilirsiniz.

**Aşama 1 skorumuz düşükse dezavantajlı mı oluruz?**
Private Leaderboard skoru final puanının belirli bir yüzdesini oluşturur, bu yüzden iyi bir skor avantaj sağlar. Sıralaması düşük ekipler elenmez.

Yarışmaya ait tüm dosyalara Kaggle'daki yarışma sayfasından ulaşabilirsiniz.

> Konuşmacı notu: Sık sorulan soruları kısaca geç, ardından katılımcıların sorularını al.

---

## 10. Aşama 2 · Ajan: Elinizdeki Veri: Saha Raporu Destekli LLM Agent

- **Görev:** bir üssü korumak; çevredeki **8 bölge** gün boyu drone'larla izleniyor.
- **40** adet bir günlük drone görüntüsü.
- Sahadaki birimlerden serbest metin gözlem raporları geliyor.
- Araçların son **2 saatlik** hareket kayıtları.
- Birinci gün geliştirdiğiniz tespit modelini kullanan bir LLM agent kuracaksınız.
- **Çıktı:** araçların üs için risk oluşturup oluşturmadığını açıklayan kısa bir brief.

---

## 11. 2. Gün · Ajan: Agent Akışı

**Girdiler**
- Drone görüntüleri: 8 bölgeden 40 görüntü
- Hareket kayıtları: araçların son iki saatlik hareket verisi
- Saha raporları: serbest metin gözlem raporları

**Ajan akışı**
1. **Tespit:** Görseldeki araçları doğru biçimde tespit etmek
2. **Konumlandırma:** Piksel konumlarını harita bilgisiyle gerçek koordinatlara çevirmek
3. **Hareket analizi:** Son iki saatteki hız, yön ve rotayı hareket verisinden çıkarmak
4. **Risk analizi:** Bulguları saha raporlarıyla değerlendirip gerekçeli brief üretmek

> Konuşmacı notu: Agent'ın dört adımını sırayla anlat ve hangi girdinin hangi adımda kullanıldığını göster.

---

## 12. Aşama 2 · Ajan: LLM API kredisi

- Her takıma, agent'ınızın LLM çağrıları için **15 $ GLM API kredisi** veriliyor.
- API anahtarları ve bağlantı detayları 2. aşamaya geçildiğinde dağıtılacak.
- Bu aşamayla ilgili daha ayrıntılı bilgi de 2. aşamaya geçilen gün paylaşılacak.

---

## 13. Aşama 2 · Veri: image_meta.json ve zones.json

**image_meta.json**
```json
"img_000860": {
  "width_px": 960,
  "height_px": 540,
  "capture_time": "14:10",
  "corner_coordinates": {
    "top_left":     [39.925651, 32.870729],
    "top_right":    [39.925651, 32.872131],
    "bottom_left":  [39.925045, 32.870729],
    "bottom_right": [39.925045, 32.872131]
  }
}
```

**zones.json**
```json
{
  "base":  {"name": "Merkez Us",
            "lat": 39.92184, "lon": 32.85306},
  "zones": [
    {"name": "Kuzey Yolu",
     "center": [39.950586, 32.853060]},
    {"name": "Dogu Yolu",
     "center": [39.921840, 32.890542]},
    ...
  ]
}
```

Köşe koordinatları, pikselleri gerçek koordinata çevirmenizi sağlar; raporlardaki bölge adlarını `zones.json`'da bulursunuz.

---

## 14. Aşama 2 · Veri: tracks.csv ve field_reports.json

**tracks.csv**
```
track_id,time,lat,lon
T0001,10:15,39.988691,32.880750
T0001,10:20,39.978233,32.885015
T0001,10:25,39.978232,32.884969
T0001,10:30,39.978288,32.885002
...
```
Her track_id: bir aracın son 2 saati, 5 dakikalık adımlarla.

**field_reports.json**
```json
{"time": "13:05", "source": "official",
 "text": "39.9374N 32.8483E civarinda 1 kamyon goruldu, yukleri tespit edilemedi."},

{"time": "11:55", "source": "third_party",
 "text": "Planli tatbikat nedeniyle gun icinde bolgede dost unsurlar bulunacak."}
```

Kayıtlar ve raporlar tek havuzdur; hangi görüntüyle ilgili oldukları verilmez. Bağlamı çekim saati ve köşe koordinatlarıyla siz kurarsınız.

---

## 15. Dikkat: Saha Raporları

**Raporların tamamı doğru değil.**
Bazı raporlar kasıtlı ya da yanlışlıkla hatalı, bazıları ise konuyla ilgisiz olabilir. Agent'ınızın raporları olduğu gibi kabul etmek yerine kendi tespitine güvenmesi bekleniyor.

**Beklenen yaklaşım:** Önce kendi tespitinize ve hareket verisine dayanın; raporları bu bulgularla karşılaştırarak değerlendirin.

> Konuşmacı notu: Saha raporlarının güvenilir olmadığını vurgula. Agent'ın kendi tespitine dayanması bekleniyor.

---

## 16. Aşama 2 · Kaynaklar: Canlı örnek

Uçtan uca örnek: agent'ın tüm adımları, gerçek bir kare üzerinde.
Link: claude.ai/artifact/WPuR3WDVPV2va8z8piWYzJ

---

## 17–25. Uçtan Uca Örnek (ekran görüntüleri)

*Aşama 2 · agent'ın bir görüntüyü adım adım değerlendirmesi · gerçek veri: img_000860 (Doğu Yolu). Kare, sayılar ve rapor metni 2. aşama veri paketinden alınmıştır.*

**Başlangıç (slayt 17):** img_000860 değerlendirilmeyi bekliyor.
**Kullanıcı:** "img_000860'ı değerlendir."

**Adım 1/8 · Görüntüyü aç**
Boyut, çekim saati ve köşe koordinatlarını `image_meta.json`'dan okudum.
960×540 px · 14:10 · sol üst 39.925651, 32.870729
(Köşeler: sol üst 39.925651, 32.870729 · sağ üst 39.925651, 32.872131 · sol alt 39.925045, 32.870729. Üst kenar kuzey, sol kenar batı.)

**Adım 2/8 · Haritaya yerleştir**
Kuşbakışı kabulüyle kareyi koordinat düzlemine oturttum: üst kenar kuzey, sol kenar batı; köşeler `image_meta.json`'daki koordinatlara denk geliyor.
Kare yerde ~120 × 67 m · bölge: Doğu Yolu · üsse ~1,6 km

**Adım 3/8 · Aracı tespit et**
1. gün modelim görüntüde bir kamyon buldu.
truck · kutu (727, 284, 58, 34) · merkez piksel (756, 301)

**Adım 4/8 · Pikseli koordinata çevir**
Kutunun merkezini köşe koordinatlarından doğrusal orantıyla çevirdim.
```
boylam = sol_üst + (756 / 960) × köşe farkı
enlem  = sol_üst + (301 / 540) × köşe farkı
```
Sonuç: 39.92531, 32.87183

**Adım 5/8 · Hareket kaydını bul**
`tracks.csv`'de çekim saatindeki (time == 14:10) konumları süzdüm; en yakın kayıt eşleşti.
T0122 · <1 m (ikinci en yakın: T0032 · 41 m)
Not: birebir eşitlik değil, sınır içinde en yakın nokta.

**Adım 6/8 · Hareketi çıkar**
T0122'nin 2 saatlik kaydından hız ve yönü okudum.
- 12:10 · 40 dk bekledi
- 12:55 · 20 dk
- 13:15 · 45 dk bekledi · üsse 5,5 km
- 14:10 · üsse 1,6 km

Üsse uzaklık: 13:15 → 5,5 km · 14:10 → 1,6 km. Son 10 dk ~6 m/s · 2 saatlik yol 10,5 km · yol boyunca uzun duraklamalar. **Üsse yaklaşıyor.**

**Adım 7/8 · Raporlarla karşılaştır**
Konumu kapsayan raporları taradım; biri bu aracı anlatıyor.
12:35 · official · field_reports.json: "39.9253N 32.8718E cevresinde 1 agir arac bulunuyor, hareketleri olagan."
Konum ✓ tespitle aynı nokta · tip ✓ ağır araç = kamyon · tespitle uyumlu.
Not: Raporun iddiasını kendi bulgunuzla karşılaştırın; çelişki varsa raporu değil tespitinizi esas alın.

**Adım 8/8 · Değerlendir**
Bu görüntüde üsse 1,6 km mesafede bir kamyon var; son bir saatte 5,5 km'den 1,6 km'ye duraklamalarla yaklaştı, hakkındaki resmi rapor tespitle uyumlu. Dikkat gerektirip gerektirmediğine bu bulgularla karar veriyorum.

> **Değerlendirme · img_000860:** Üsse 1,6 km mesafede bir kamyon; son bir saatte 5,5 km'den 1,6 km'ye yaklaştı, yol boyunca uzun duraklamalar yaptı. 12:35 tarihli resmi rapor konum ve tiple uyumlu.
> Tespit: 1. gün modeli · konum: köşe koordinatları · hareket: T0122 · rapor: field_reports.json

Not: Dikkat gerektirip gerektirmediğine, hangi gerekçeyle gerektirdiğine agent'ınız karar verir.

---

## 26. Aşama 2 · Kaynaklar: Saha haritası

3B saha haritası: kareler, hareket kayıtları ve rapor akışı bir arada. Zamanı oynatın, kareye tıklayıp fotoğrafı açın.
Link: claude.ai/artifact/RDA7jxgLaG2wEgZ7GtSeLR

---

## 27. Final Süreci

**Adımlar**
1. Kod teslimi
2. Sunum dosyası teslimi
3. Mentor kod oturumu
4. Jüri sunumu ve demo

**Detaylar**
- **Mentor (teknik kalite ve mimari):** Kodlarınız mentorlarla kod değerlendirme oturumunda incelenir. Mentor puanı final puanınızın belli bir yüzdesini oluşturur.
- **Jüri (final sunumu):** Çalışmanızı sunumunuzla jüriye aktarırsınız. Jüri, final puanınızı dört başlık üzerinden belirler.
- **Canlı demo:** Agent'ı chatbot arayüzü, web uygulaması, komut satırı ya da sesli asistan olarak canlı gösterebilirsiniz. Verilen görüntülerden en az bir ya da ikisinde gerçekten çalıştığını görmek istiyoruz.

> Konuşmacı notu: Teslim ve final sürecini sırayla anlat. Demo formatı serbest, ama agent'ın en az bir ya da iki görüntüde gerçekten çalıştığı görülmeli.

---

## 28. Değerlendirme: Jüri Kriterleri ve Puanlama

**Jüri kriterleri**
1. İş Değeri: problemin önemi ve iş değeri
2. Çalışan Ürün: çalışan ürün ortaya koyabilme
3. Ürün ve UX: ürün düşüncesi ve UX
4. Sunum ve Demo: sunum ve demo kalitesi

**Puan bileşenleri:** Kaggle + Mentor + Jüri
- **Private Leaderboard:** Kaggle aşamasının Private Leaderboard skoru final sunum puanınıza doğrudan eklenir.
- **Mentor puanı:** İkinci aşamadaki teknik kalite ve mimariniz mentorlar tarafından değerlendirilir.

Final puanı; Kaggle Private Leaderboard skoru, mentor teknik değerlendirmesi ve jüri puanından oluşur.

> Konuşmacı notu: Final puanının üç bileşenini ve dört jüri kriterini açıkla.

---

## 29. Değerlendirme: Teknik Mentörlerimiz

- Serkan Öztürk · Müdür
- Bilge Kaan Görür · Müdür
- Seyit Tunç · Müdür
- Bülent Öktem · Kıdemli Lider Müh.
- Mehmet Akif Ahrazoğlu · Birim Yöneticisi
- Barış Çağlar Ayyıldız · Birim Yöneticisi
- Ertan Demiral · Kıdemli Lider Müh.
- Mehmet Ali Yılmaz · Kıdemli Lider Müh.
- Hüseyin Avni Yaşar · Lider Mühendis
- Melih Doğanay Sazak · Lider Mühendis
- Mehmet Can Baytekin · Lider Mühendis
- Rıza Can Temizel · Lider Mühendis
- Özlem Demirtaş Altıntaş · Lider Mühendis
- Şükrü Can Özer · Lider Mühendis
- Uğurcan Çelik · Kıdemli Uzman Müh.
- Mehmet Serkan Tan · Kıdemli Uzman Müh.
- Muhammed Ali Aşgit · Kıdemli Uzman
- Ahmet Cihat Çetindağ · Uzman Mühendis
- Onur Oydu · Uzman Mühendis
- Burak Aktaş · Uzman Mühendis
- Eray Turan · Uzman Mühendis
- Recep Yerebakan · Uzman Mühendis
- Furkan Yıldız · Mühendis
- Furkan Oruç, Emre Erdem · Mühendis
- Barış Bayramoğlu · Mühendis
- Ömer İlbilgi · Mühendis
- Sare Naz Ersoy · Mühendis

---

## 30. Teşekkürler

Sorularınız için. İyi yarışmalar!
Tarih: 25 Eylül Cuma · 27 Eylül Pazar
Kaggle: dosyalar yarışma sayfasında

> Konuşmacı notu: Soru-cevap boyunca bu sayfa ekranda kalsın.
