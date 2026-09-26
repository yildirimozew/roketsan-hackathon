# Situational Awareness Dashboard

ROKETSAN Yapay Zekâ Hackathonu ikinci aşaması için geliştirilen React tabanlı operasyon dashboard prototipidir.

Bu frontend'in amacı; araç tespiti, konum/rota, hareket geçmişi, saha raporları ve AI risk değerlendirmesini tek bir arayüzde birleştirmektir.

> Bu sürüm entegrasyona hazır bir mock prototiptir. Gösterilen araç, koordinat, rota, hareket, saha raporu ve risk verileri gerçek yarışma verileri değildir.

---

## Mevcut Durum

Dashboard'un temel fonksiyonel yapısı tamamlandı.

Şu anda:

- Drone görüntüsü üzerinde araç bounding box gösterimi
- Araç seçimi (V001 / V002)
- Seçili araç ile diğer paneller arasında senkronizasyon
- Leaflet tabanlı harita
- Araç konumu ve rota gösterimi
- Son 2 saatlik hareket timeline'ı
- Saha raporları
- Saha raporu durumları:
  - Destekleniyor
  - Çelişiyor
  - Doğrulanamadı
- AI Risk Assessment paneli
- Risk seviyesi
- Risk confidence
- Contributing factors
- Evidence alanı

çalışmaktadır.

Araç seçildiğinde ilgili drone bounding box, harita/rota, hareket geçmişi, saha raporu ve risk değerlendirmesi birlikte güncellenmektedir.

---

## Veri Akışı

Mevcut prototip:

```text
mockData.js
     |
     v
React Dashboard
     |
     +-- DroneViewer
     +-- MapViewer
     +-- MovementTimeline
     +-- FieldReports
     +-- Risk Assessment / Evidence
```

Planlanan gerçek sistem:

```text
Stage-1 Vehicle Detector
          |
          v
Pixel -> Geo Conversion
          |
          v
Movement Matching
          |
          v
Field Report Evaluation
          |
          v
LLM / Risk Agent
          |
          v
Backend API
          |
          v
React Dashboard
```

---

## Neden Mock Veri Kullanılıyor?

İkinci aşamanın gerçek veri formatları henüz sisteme entegre edilmediği için frontend şu anda merkezi mock veri üzerinden çalışmaktadır.

Mock veriler:

```text
src/data/mockData.js
```

dosyasında tutulmaktadır.

Bu yapı bilinçli olarak seçildi. Böylece gerçek veri ve backend hazır olduğunda UI componentlerini baştan yazmak yerine veri kaynağının API ile değiştirilmesi hedeflenmektedir.

---

## Neden Bu Aşamada Durduk?

Frontend'in temel amacı olan veri akışı ve kullanıcı etkileşimi kurulmuş durumda.

Bu noktadan sonra gerçek veriler gelmeden;

- detaylı UI polish,
- gerçek koordinat dönüşümü,
- gerçek hareket eşleştirmesi,
- saha raporu güvenilirlik algoritması,
- gerçek AI/LLM risk çıktısı,
- final animasyonlar ve görsel iyileştirmeler

üzerinde fazla ilerlemek gereksiz yeniden çalışma oluşturabilir.

Bu nedenle mevcut dashboard entegrasyona hazır prototip olarak burada dondurulmuştur.

Gerçek Stage-2 verileri geldiğinde öncelik backend ve AI pipeline entegrasyonu olacaktır. Görsel iyileştirmeler gerçek veri akışı çalıştıktan sonra yapılacaktır.

---

## Proje Yapısı

```text
frontend/
├── public/
├── src/
│   ├── components/
│   │   ├── DroneViewer.jsx
│   │   ├── MapViewer.jsx
│   │   ├── MovementTimeline.jsx
│   │   └── FieldReports.jsx
│   │
│   ├── data/
│   │   └── mockData.js
│   │
│   ├── App.jsx
│   ├── App.css
│   ├── index.css
│   └── main.jsx
│
├── package.json
├── package-lock.json
└── vite.config.js
```

---

## Kurulum

Node.js kurulu olmalıdır.

Repository klonlandıktan veya güncellendikten sonra:

```bash
cd sude/frontend
npm install
```

Windows PowerShell execution policy nedeniyle `npm` komutu çalışmazsa:

```powershell
npm.cmd install
```

kullanılabilir.

---

## Çalıştırma

```bash
npm run dev
```

PowerShell'de gerekirse:

```powershell
npm.cmd run dev
```

Terminalde gösterilen local adres tarayıcıda açılır.

Genellikle:

```text
http://localhost:5173/
```

---

## Kullanılan Teknolojiler

- React
- Vite
- JavaScript
- CSS
- Leaflet
- React Leaflet

---

## Sonraki Aşama

Gerçek Stage-2 verileri geldiğinde planlanan entegrasyon sırası:

```text
Detection
   ↓
Geo Conversion
   ↓
Movement Analysis
   ↓
Field Report Evaluation
   ↓
Risk Agent / LLM
   ↓
API
   ↓
Dashboard
```

Frontend'in mevcut component yapısı bu entegrasyona uygun şekilde ayrıştırılmıştır.

---

## Not

Bu sürümde gösterilen V001/V002 araçları, koordinatlar, rotalar, hareket kayıtları, saha raporları, confidence değerleri ve risk sonuçları yalnızca arayüz geliştirme/test amacıyla oluşturulmuş mock verilerdir.