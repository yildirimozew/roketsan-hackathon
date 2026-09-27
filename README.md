# Roketsan Hackathon — AKYA

Level-Up AI | Roketsan Yapay Zekâ Hackathonu için takımımızın iki aşamadaki çalışması. İki aşama başlangıçta ayrı
repolardaydı. Geçmişleri korunarak tek repoda, iki bağımsız klasör halinde birleştirildi.

| Klasör | Aşama | Ne yapıyor | Stack |
|---|---|---|---|
| [`akya-day1/`](akya-day1/README.md) | 1. aşama | Drone görüntülerinde araç tespiti (`car`, `van`, `truck`, `bus`, mAP@0.5). Final çözüm dört detektörlü bir ensemble: RF-DETR L, iki YOLO11m ve YOLO26-S-P2 | Python, PyTorch, Ultralytics, Kaggle / Slurm |
| [`akya-day2/`](akya-day2/README.md) | 2. aşama | **SENTINEL**: drone karesi, araç izleri ve güvenilmez saha raporlarından üs güvenliği riski çıkaran LLM ajanı. Kanıta dayalı LOW / MEDIUM / HIGH / CRITICAL brief yazıyor | FastAPI + uv, Vite / React / TypeScript + pnpm, GLM (OpenAI uyumlu) |

2. aşamadaki canlı detektör, 1. aşamada eğitilen YOLO modellerini kullanıyor.

## Önemli: her proje kendi klasöründen çalışır

İki proje birbirinden bağımsız. Kök dizinde ortak bir kurulum, bağımlılık dosyası ya da Makefile yok. Her klasörün
içindeki README, `CLAUDE.md`, script docstring'leri ve `.env` açıklamalarında geçen **"repo kökü" / "repo root"**
ifadesi o projenin klasörü demek (`akya-day1/` ya da `akya-day2/`). Kodda da öyle: yollar dosyanın kendi konumundan
hesaplanıyor, çalışma dizininden değil.

```bash
# 1. aşama: ensemble notebook'u, değerlendirme scriptleri
cd akya-day1
pip install -r requirements.txt          # ayrıntılar: akya-day1/README.md

# 2. aşama: SENTINEL (API :8000 + web :5173)
cd akya-day2
make install && make dev                 # ayrıntılar: akya-day2/README.md
```

## Repo yapısı

```text
akya-day1/                    1. aşama: araç tespiti
  roketsan_ensemble.ipynb     final model: eğitim, tahmin, füzyon, submission
  splits/                     ortak train/val manifest'leri (final: scene_holdout_v2)
  ardahan/ furkan/ hakan/     üye klasörleri: deneyler, Kaggle koşuları, EDA
  mustafa/ yildirim/ sude/
  collective_summary.txt      takımın deney günlüğü
  data/                       Kaggle verisi (Git'e dahil değil)
akya-day2/                    2. aşama: SENTINEL ajanı
  backend/                    FastAPI: domain, services, agent (pipeline + watch mode), api
  frontend/                   React arayüzü
  data/                       organizatör verisi (commit'li)
  docs/                       AGENT_DESIGN.md (tasarımın referans dokümanı), akış, prompt'lar, örnek koşular
  arge/                       Ar-Ge notları ve backend'e taşınmayı bekleyen kodlar (core_upgrades/)
  PLAN.md, CLAUDE.md          kapsam ve çalışma kuralları
```

## Git'e dahil olmayanlar

Model ağırlıkları, tahmin çıktıları, 1. aşamanın Kaggle verisi, `.env` dosyaları ve önbellekler Git'e dahil değil.
İlgili `.gitignore` dosyaları her projenin kendi klasöründe.

## Geçmiş

Klasör bazında `git log -- akya-day2/...` birleştirme commit'inde durur, çünkü eski commit'lerde dosyalar önek
olmadan duruyordu. Eski geçmişi görmek için:

```bash
git log 34524cf -- backend/     # 2. aşamanın birleştirmeden önceki son commit'i
git log 0906b17 -- ardahan/     # 1. aşamanın birleştirmeden önceki son commit'i
```
