# 📅 BOT SEMANAL — Polymarket · Elon Musk # tweets (ventanas de 7 días)

**Mismo sistema que el bot de 48h, pero opera SOLO los mercados semanales**
(«Elon Musk # tweets Julio 25 - Agosto 1», etc., que cubren 7 días completos).

## Qué cambia vs el bot de 48h

| Aspecto | Bot 48h | Bot SEMANAL |
|---|---|---|
| Mercados que opera | ventanas de 48 h | ventanas de **7 días (168 h)** |
| Modelo de señal | λ48 = 2·AVG7·ajuste | **λ7 = 7·AVG7·ajuste** |
| Bins típicos | <40, 40-64, 65-89… | 20-39, 40-59, 60-79, 100-119… |
| Estado | papel.json / real.json | **papel_semanal.json / real_semanal.json** |
| Historial | resultados_papel.csv | **resultados_papel_semanal.csv** |
| Excel | Historial_Operaciones.xlsx | **Historial_Operaciones_Semanal.xlsx** |
| Log | bot.log | **bot_semanal.log** |
| Notificaciones | tema ntfy elon-poly-g2p7e8ev | mismo tema, con prefijo **[SEMANAL]** |

Todo lo demás es idéntico: tabla de apuestas (3.30 × 1.5^n, reinicio tras
ganar, stop en paso 7), reglas (cuota ≥ 3.00, p_modelo ≥ 60% YES / ≤ 30% NO,
una sola apuesta activa, entrada en la primera mitad de la ventana),
recogida de tweets, chequeo de cuenta, modo seco, etc.

## 🚀 Cómo usarlo (local, modo papel = sin dinero)

```powershell
cd C:\USERS\LAMEG\BITUNIX-BOT\estrategia_semanal
python -u bot_semanal.py --excel                 # una pasada (papel)
python -u bot_semanal.py --loop --intervalo 15 --excel   # continuo (papel)
python bot_semanal.py --estado                   # estado
```

## 💰 Cómo pasar a dinero real (solo cuando quieras)

1. Copia tu `config_real.json` desde la carpeta del bot 48h:
   ```powershell
   copy ..\estrategia_elon_tweets\config_real.json config_real.json
   ```
2. Verifica credenciales y saldo:
   ```powershell
   python chequear_cuenta.py
   ```
3. Prueba segura de orden:
   ```powershell
   python probar_orden_semanal.py
   ```
4. Activa:
   ```powershell
   notepad config_real.json    # "confirmado": false → true
   python -u bot_semanal.py --modo real --excel
   ```

## ⏰ 24/7 GRATIS (GitHub Actions) — PASO A PASO

Igual que con el bot 48h, pero **en un repo propio** para evitar conflictos
de push entre los dos bots:

1. GitHub → **New repository** → `bot-polymarket-elon-semanal` → **PÚBLICO**.
2. En la carpeta `estrategia_semanal`:
   ```powershell
   cd C:\USERS\LAMEG\BITUNIX-BOT\estrategia_semanal
   git init
   git add .
   git status          # comprueba que NO aparece config_real.json
   git commit -m "bot semanal v1"
   git branch -M main
   git remote add origin https://github.com/TU_USUARIO/bot-polymarket-elon-semanal.git
   git push -u origin main
   ```
3. GitHub → repo → **Settings → Secrets and variables → Actions** → crea:
   `POLY_PRIVATE_KEY`, `POLY_WALLET_ADDRESS`, `REAL_CONFIRMADO=1`.
   (El workflow usa `GITHUB_TOKEN`, no hace falta PAT.)
4. GitHub → **Actions** → **Run workflow** → comprueba que sale verde.
5. A partir de ahí: **cada 15 min** el bot semanal vigila y opera solo.

## ⚠️ IMPORTANTE: los dos bots a la vez

El bot de 48h y el semanal pueden tener **cada uno una apuesta activa** a la
vez → hasta **2 posiciones simultáneas** en tu cuenta de Polymarket. Con un
bankroll pequeño (tienes ~$36.55) eso significa más exposición.

**Opciones:**
- **Papel primero**: deja el semanal en papel (sin `REAL_CONFIRMADO=1`) hasta
  ver cómo se comporta con los mercados semanales.
- **Solo uno real**: usa real solo en el que prefieras.
- **Los dos reales**: aceptando hasta 2 posiciones concurrentes (stake por
  ciclo igual, $3.30 → ×1.5).

## 📌 Notas

- Los mercados semanales resuelven ~1-2 días después de cerrar (mediodía ET).
- Las señales semanales aparecen con menos frecuencia que las de 48h (el
  mercado tiene 20 bins de 20 tweets: la masa de probabilidad está repartida).
- El bin 140-159 llegó a cumplir la señal (p_modelo 61.5% a cuota 13.33) en
  el mercado «Ago 7-14» — el bot semanal en papel lo habría cazado.
- Todo lo demás (avisos móvil, Excel acumulativo, modo seco, chequeos) es
  idéntico al bot de 48h: consulta `GUIA_DINERO_REAL.md` y
  `GUIA_24H_PASO_A_PASO.md` de la carpeta principal si necesitas detalle.

*Documento de gestión personal. No constituye asesoramiento financiero.*
