# Özet: Agent Ar-Ge listesi

> `AGENT_CAPABILITIES_RND.tr.md` dosyasının kısa özeti. Ayrıntılar, gerekçeler ve teknik anlatım o
> dosyada.

**Bu doküman ne?** `arge/` tasarım notlarındaki bütün fikirler, mevcut koda göre tek tek değerlendirildi:
65 madde, analiz akışının sırasıyla. Her maddede şu anki durum, neden gerektiği, zorluk, teknik anlatım
ve sade anlatım var. Fikirler mevcut pipeline'ı geliştirir, onun yerine geçmez.

## Alınmış kararlar
- Sadece pipeline kullanılacak, LLM her adımı kendisi yönetmeyecek.
- "Kanıt yetersiz" ayrı bir seviye değil. Bir uyarı olarak eklenir ve "tekrar bak" (`VERIFY`) önerilir.
- Sahte "dost araç" raporu yakalanırsa aracın seviyesi bir kademe artar.

## Ölçümlerden çıkan 3 kritik bulgu
1. **Puanlama yanlış aracı öne çıkarıyor.** Üssün etrafında dönen ve çok yaklaşan dört şüpheli araç
   (T0043, T0158, T0172, T0198) kendi karelerinde ilk sırada değil. Sebebi, puanlamanın "yakın ve
   yaklaşıyor" ölçütünü ödüllendirmesi. Oysa bu verideki araçların yarısından fazlası (129/226) zaten
   yaklaşıyor.
2. **Alarm yorgunluğu.** Pipeline'da 4 seviye var (LOW / MEDIUM / HIGH / CRITICAL; eylemler MONITOR /
   VERIFY / ESCALATE). Mevcut puanlamada 40 karenin 22'si HIGH, 17'si MEDIUM, 1'i LOW çıkıyor, hiçbiri
   CRITICAL değil. Yani operatöre 22 kez "kontrol et" deniyor, ama "hemen müdahale et" hiç çıkmıyor. Dört
   şüpheli aracın kareleri de sıradan karelerle aynı HIGH seviyesinde kalıyor.
3. **Aldatma tuzağı yakalanıyor ama kullanılmıyor.** "Dost araç üsse geliyor" diyen resmi raporlar
   (REP-06, REP-78, REP-120) zaten "çelişiyor" olarak işaretleniyor. Ama sonra sadece yok sayılıyorlar.
   Bu bir uyarı işareti olarak kullanılmalı.

> Ölçümler `data/` içindeki gerçek veride yapıldı. Dedektör çıktısı repoda olmadığı için tespit yerine
> kare içindeki track noktaları kullanıldı.

## Akış içindeki en önemli maddeler
| Adım | En önemli iş |
|---|---|
| Hareket analizi | Üs etrafında dönme (net açı), en yakın geçiş, son 30 dakikada içeri giriş, günün diğer araçlarıyla kıyas |
| Eşleme | Görüntüde görülmeyen ama rotası olan araçlar da değerlendirilmeli (kaçırılmış ya da karenin hemen dışında olabilir) |
| Raporlar | "Ağır araç yok" gibi olumsuz cümleleri doğru okumak, "üsse doğru" iddiasında yönü kontrol etmek, sahte dost raporunu uyarıya çevirmek |
| Risk | Puanlamayı dönme ve yakın geçişe göre yeniden kurmak. Hedef: ~4 CRITICAL, 6–10 HIGH |
| Brief | LLM'in yazacağı kanıt atıflı özet, bunu kontrol eden kod tabanlı bir denetçi (guard) ve "şeytanın avukatı" rolünde ikinci bir LLM (critic) |

## Elenenler
LLM'in bütün adımları yönetmesi, 5. seviye, bölge atamasının değişmesi (ölçümde gerek olmadığı çıktı),
görüntüye ikinci LLM bakışı, Kalman tahmini.

## Önerilen sıra
1. Hareket özellikleri
2. Yeni puanlama
3. Aldatma zinciri ve testleri
4. LLM brief'i, guard ve critic
5. Açıklamalar ve belirsizlik
6. Dedektör iyileştirmeleri
7. Gün tablosu ve sohbet

İlk üç adım hem kolay hem de demonun doğruluğunu doğrudan değiştiriyor.
