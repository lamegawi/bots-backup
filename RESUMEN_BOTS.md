# 🤖 Resumen de los bots Polymarket (estado completo)

> Documento para que otra IA (o el propio usuario) pueda continuar el trabajo sin perder contexto. Última actualización: **2026-08-31**.

---

## 0. TL;DR

Hay **5 bots de trading** sobre mercados de Polymarket, todos basados en el **mismo motor de señal** (Poisson con ajuste empírico). Operan en **ventanas temporales** (48h / semanal / mensual) sobre **eventos de X/Twitter/Truth Social** (recuento de posts).

- **4 bots en producción** (Elon 48h, Elon semanal, Elon mensual, Zelenskyy).
- **1 bot nuevo en repo, pendiente de desplegar en producción**: **Trump** (semanal, Truth Social).
- **2 bots de Telegram** para visualizar el estado desde el móvil (uno para el grupo de Elon, otro para el grupo Zelenskyy). Trump no tiene bot de Telegram propio: usa ntfy.

**Servicios systemd en Hetzner (VM 46.225.146.21, usuario root):**

| Servicio | Descripción | Estado |
|---|---|---|
| `poly-elon` | Bot 48h Elon (rápido) | active |
| `poly-semanal` | Bot semanal Elon | active |
| `poly-mensual` | Bot mensual Elon | active |
| `poly-zelenskyy` | Bot semanal Zelenskyy | active |
| `poly-trump` | Bot semanal Trump | active (pero versión anterior a la del repo) |
| `poly-telegram` | Bot Telegram del grupo Elon | active |
| `poly-telegram-zelen` | Bot Telegram del grupo Zelenskyy | active |
| `poly-gestor` | Gestor de cierre anticipado de posiciones Elon | active |

Los servicios `-v2` (`poly-elon-v2`, `poly-semanal-v2`, `poly-mensual-v2`) están **parados** desde el 2026-08-19 (ver §6). Servían para probar el motor v2 en paralelo, ya no son necesarios.

---

## 1. Arquitectura general

```
                  +------------------+
                  |  Polymarket API  |
                  |  gamma + clob +  |
                  |  data-api        |
                  +---------+--------+
                            |
        +-------------------+---------------------+
        |                   |                     |
+-------+------+    +-------+-------+    +--------+-------+
| Tweets/data  |    | Mercado       |    | Cuenta /      |
| (X, Truth,   |    | (precios,     |    | posiciones    |
|  Instagram)  |    |  bins)        |    | reales        |
+-------+------+    +-------+-------+    +--------+-------+
        |                   |                     |
        v                   v                     v
+-------+----------------------------------------+-------+
|                  senal.py + senal_vivo.py            |
|     (motor de señal: Poisson + empírico + EV)         |
+-------+----------------------------------------+-------+
        |                                               |
        v                                               v
+-------+----------+   +----------------+   +-----------+--------+
| operar_real*.py  |   | papel_*.py     |   | gestionar_posiciones|
| (CLOB V2 SDK)    |   | (simulación)   |   | (cierre anticipado) |
+-------+----------+   +----------------+   +--------------------+
        |
        v
+-------+--------+
| check_*.py     |
| (salud, integ.)|
+----------------+
        |
        v
+-------+--------+
| Telegram/ntfy  |
| (notificación) |
+----------------+
```

**Carpetas clave** (todas bajo `/opt/polymarket/` en Hetzner):

- `bot-polymarket-elon/` — bot 48h de Elon
- `bot-polymarket-elon-semanal/` — bot semanal de Elon
- `bot-polymarket-elon-mensual/` — bot mensual de Elon
- `bot-polymarket-zelenskyy/` — bot semanal de Zelenskyy
- `bot-polymarket-trump/` — **bot semanal de Trump (NUEVO, en repo)**
- `codigo/` — scripts compartidos: `check_salud.py`, `check_integral.py`, `recolector_poly.sh`, `enviar_poly.sh`, `gestionar_posiciones.py`, `poly_telegram_bot.py`, `poly_telegram_zelen.py`, `posiciones_reales.py`, `motores.py`, `proxy_pc.py`, otros `check_*.py` auxiliares

---

## 2. Los 5 bots en detalle

### 2.1. `bot-polymarket-elon` (48h)

| Campo | Valor |
|---|---|
| Mercado | "Elon Musk # tweets" (48h) |
| Fuente datos | X/Twitter vía nitter + jina |
| Ventana | 48h |
| Cadencia | 15 min |
| Servicio systemd | `poly-elon` |
| Modo producción | Real (con bankroll pequeño) |
| Archivos clave | `bot.py`, `operar_real.py`, `senal.py`, `senal_vivo.py`, `recoger_tweets.py`, `mercado_polymarket.py`, `notificar.py`, `saldo_ntfy.py`, `chequear_cuenta.py` |
| Particularidades | El más antiguo; usa `bot.py` (no `bot_*`) como entry point. Tiene scripts extra: `compara_senal.py`, `construir_serie.py`, `simulador.py`, `generar_excel_resultados.py`, `generar_xlsx.py`. También `datos_ejemplo.csv` (plantilla). |
| Estado | `estado_tweets.json` (runtime, no en repo) |
| Excel | `Historial_Operaciones.xlsx` |

### 2.2. `bot-polymarket-elon-semanal` (semanal)

| Campo | Valor |
|---|---|
| Mercado | "Elon Musk # tweets" (semanal, 7 días) |
| Fuente datos | X/Twitter vía nitter + jina |
| Ventana | 168h (7 días) |
| Cadencia | 15 min |
| Servicio systemd | `poly-semanal` |
| Modo producción | Real |
| Archivos clave | `bot_semanal.py`, `operar_real_semanal.py`, `senal.py`, `senal_vivo.py`, `recoger_tweets.py`, `mercado_polymarket.py`, `notificar.py`, `notificar_semanal.py`, `saldo_ntfy.py`, `chequear_cuenta.py`, `excel_historial.py`, `diagnostico.py` |
| Estado | `estado_tweets.json` (runtime) |
| Excel | `Historial_Operaciones_Semanal.xlsx` |

### 2.3. `bot-polymarket-elon-mensual` (mensual)

| Campo | Valor |
|---|---|
| Mercado | "Elon Musk # tweets" (mensual, 30 días) |
| Fuente datos | X/Twitter vía nitter + jina |
| Ventana | 720h (30 días) |
| Cadencia | 15 min |
| Servicio systemd | `poly-mensual` |
| Modo producción | Real |
| Archivos clave | `bot_mensual.py`, `operar_real_mensual.py`, `senal.py`, `senal_vivo.py`, `recoger_tweets.py`, `mercado_polymarket.py`, `notificar.py`, `saldo_ntfy.py`, `chequear_cuenta.py`, `excel_historial.py` |
| Estado | `estado_tweets.json` (runtime) |
| Excel | `Historial_Operaciones_Mensual.xlsx` |
| Particularidad | NO tiene `diagnostico.py` (los otros 2 sí). |

### 2.4. `bot-polymarket-zelenskyy` (semanal)

| Campo | Valor |
|---|---|
| Mercado | "Zelenskyy suit color" (semanal) |
| Fuente datos | X/Instagram vía nitter + jina |
| Ventana | semanal |
| Cadencia | 15 min |
| Servicio systemd | `poly-zelenskyy` |
| Modo producción | Real (adaptado de Elon semanal) |
| Archivos clave | `bot_semanal.py`, `operar_real_semanal.py`, `senal.py`, `senal_vivo.py`, `recoger_tweets.py`, `mercado_polymarket.py`, `notificar.py`, `notificar_semanal.py`, `saldo_ntfy.py`, `chequear_cuenta.py`, `excel_historial.py`, `diagnostico.py` |
| Particularidad | Bot propio de Telegram: `Lamegawi_zelenskyy_bot`, controlado por `poly_telegram_zelen.py` (servicio `poly-telegram-zelen`). Tiene botón extra "🩺 Salud". |
| CSV | `datos_zelen.csv` (en vez de `datos_elon.csv`) |
| Estado | usa `estado_tweets_zelen.json` (el nombre aparece hard-coded en `senal_vivo.py`) |
| Excel | `Historial_Operaciones_Semanal.xlsx` |

### 2.5. `bot-polymarket-trump` (semanal) — **NUEVO**

| Campo | Valor |
|---|---|
| Mercado | "Donald Trump # Truth Social posts weekly" |
| Fuente datos | **Truth Social** vía cascada: **xtracker.polymarket.com** → **jina.ai** → **nitter** |
| Ventana | semanal (7 días) |
| Cadencia | 15 min |
| Servicio systemd | `poly-trump` |
| Modo producción | Real |
| Archivos clave | `bot_semanal.py`, `operar_real_semanal.py`, `senal.py`, `senal_vivo.py`, `recoger_tweets.py`, `mercado_polymarket.py`, `notificar.py`, `notificar_semanal.py`, `saldo_ntfy.py`, `chequear_cuenta.py`, `excel_historial.py`, `diagnostico.py` |
| Particularidades | Es el **bot más completo**: trae sistema de notificaciones semanales con **cooldown** y registro de **ventanas vistas** (anti-duplicado). Tiene `GUIA_SEMANAL.md` y `config_real.json.example`. NO tiene bot de Telegram propio (usa ntfy). |
| CSV | `datos_trump.csv` (211 días a 2026-08-31) |
| Estado runtime | `estado_tweets_trump.json` (1.1MB), `estado_bot_trump.json`, `mercado_activo.json`, `avisos_cooldown.json`, `ventanas_vistas.json` |
| Excel | `Historial_Operaciones_Semanal.xlsx` |

---

## 3. Motor de señal (`senal.py` + `senal_vivo.py`)

### 3.1. Modelo matemático

**Métricas (sobre los últimos días COMPLETOS en hora ET):**

```
AVG7 = media de tweets/día de los últimos 7 días
V2   = total de tweets de los últimos 2 días
R    = V2 / (2 × AVG7)              (ratio de actividad reciente)
ajuste = clamp(1 + 0.5·(R−1), 0.5, 1.5)   (momentum con regresión a la media)
λN    = N_días × AVG7 × ajuste     (tweets esperados en N días)
```

**Distribución:**
- **Original**: Poisson(λ) — `p_bin(lo, hi, lam)`.
- **Empírica (v2)**: distribución REAL de los últimos 14 días del CSV, convolucionada, con la misma media que el Poisson. **Activa por defecto**. Interruptor: variable de entorno `SENAL_EMP=0` o `senal._EMP["on"] = False` en código.

### 3.2. Reglas de entrada (todas obligatorias)

```
R1  Mercado de ventana clara (48h, 7d, 30d) con conteo estándar
R2  Volumen ≥ $5.000 y liquidez ≥ $1.000
R3  Cuota ≥ 3.00  →  precio del lado elegido ≤ 0.33
R4  p_modelo ≥ 0.60  → candidato a YES
    p_modelo ≤ 0.30  → candidato a NO
R5  AVG7 ≥ 5  (base mínima)
R6  UNA sola apuesta activa por bot (secuencial)
R7  Progresión 3.30 × 1.5^(paso−1), reinicio a 3.30 tras ganar, stop-loss 7
```

### 3.3. Stake — motor v2 (EV escalonado)

Definido en `senal_vivo.py`:

```python
MOTOR_ACTUAL = "motor_v2_ev_escalones_tope10"
EV_MIN_ENTRADA = 1.8
EV_MAX_TOPE = 10.0

def stake_motor_v2(stake_base, p_lado, cuota):
    ev = p_lado * cuota
    if ev < EV_MIN_ENTRADA:        return None  # no entrar
    if ev >= 4.0:                  mult = 2.0
    elif ev >= 2.5:                mult = 1.5
    else:                          mult = 1.0
    return min(stake_base * mult, EV_MAX_TOPE)
```

**Distinto al motor v1** (martingala fijo 3.30×1.5, paso 7): ahora el stake depende de la **ventaja (EV)**, no solo del paso del ciclo. Filtro extra de entrada: EV ≥ 1.8 (porque en mercados semanales/mensuales aparecen "certezas" más a menudo).

### 3.4. Ventanas de entrada (FIXWIN-VENTANAS_ARENA, 30/08)

```python
ENTRADA_MAX_H = {"48h": 12.0, "semanal": 24.0, "mensual": 72.0}
_CIERRES      = {"48h": 6.0,  "semanal": 12.0, "mensual": 24.0}
```

El bot **solo entra al inicio** de la ventana o en el **tramo final** (cierre). En el medio no opera para evitar bins ya casi decididos. La probabilidad mínima sube en el cierre (0.70) y en la reentrada (0.68).

### 3.5. T0 (tweets ya en la ventana) — FIX_VENTANAS_TRUMP

Para que el bot cuente bien cuántos tweets lleva la ventana en curso:

- **Días completos** (en el CSV): se cuentan los días `d_inicio < d < hoy`.
- **Día de inicio y día actual** (parciales): se cuentan vía `estado_tweets_*.json` con timestamps exactos.
- Si la ventana empieza a las 00:00 ET (caso mensual), el día de inicio ya está cubierto por el CSV y NO se duplica desde el JSON.

---

## 4. Trading real (`operar_real*.py`)

SDK: **py-clob-client-v2** (pip install py-clob-client-v2). IMPORTANTE: Polymarket V2 usa **pUSD** (no USDC) como colateral.

**Pipeline (idéntico en los 5 bots):**
1. Lee `config_real.json` (o env vars).
2. Comprueba `confirmado: true` (si no, modo seco `--simular`).
3. Recoge señal con `senal.cargar_csv` + `senal.metricas`.
4. Refresca `mercado_activo.json` con `mp.actualizar_mercado()`.
5. Evalúa mercados 48h/semanal/mensual con `senal_vivo.evaluar()`.
6. Elige la **mejor ventana libre** (mayor EV) que no esté ocupada por otro bot (lock compartido `apuestas_compartidas.json`).
7. Salvaguardas:
   - paso > 7 → stop
   - stake > 50% bankroll → bloquea
   - saldo CLOB/on-chain insuficiente → bloquea
8. **Tamaño**: shares = `stake / precio` (redondeado a 2 dec), mínimo 5 shares.
9. Crea orden con `create_and_post_order` (V2 SDK).
10. Vigila fill (60 min), cancela si no se llena.
11. Anota en `resultados_real*.csv` y notifica.

**Lock compartido** (`/home/bots/apuestas_compartidas.json`): evita que dos bots operen sobre el mismo `(slug, bin)`. La ruta se autodetecta (env `LOCK_APUESTAS`, o `/home/bots/`, o local). **Importante**: si los bots corren en máquinas distintas, el lock debe estar en un sitio accesible por todas (NFS, S3, etc.). En Hetzner todos los bots corren en la misma VM y comparten `/home/bots/`.

**Anti-duplicados por bot**: cada bot tiene `BOT_NOMBRE` ("48H", "SEMANAL", "MENSUAL", "ZELEN", "TRUMP") en su `operar_real*.py`.

---

## 5. Recogida de tweets (`recoger_tweets.py`)

**Elon / Zelenskyy (X/Twitter)**:
1. `jina.ai` (`r.jina.ai/https://x.com/...`) — preferido, da timestamps exactos.
2. `nitter` (xcancel.com, nitter.poast.org, etc.) — respaldo.
3. **Parche v2**: `x_hasta` (parámetro de fecha fin) para no descargar todo el histórico.
4. **Parche v3**: `x-no-cache` header.

**Trump (Truth Social)** — cascada distinta:
1. `xtracker.polymarket.com` (API propia de Polymarket, fuente principal).
2. `jina.ai` sobre `truthsocial.com/@realDonaldTrump` — respaldo.
3. Nitter — último recurso.

**Backoff inteligente** en jina: si falla 3 veces, pausa 5 min y reintenta; si falla 5, pausa 30 min. Esto evita ban.

---

## 6. Historia de los motores (`poly/datos/motores.json`)

| Motor | Fechas | Descripción | PnL |
|---|---|---|---|
| `motor_v1_martingala_fijo` | 2026-08-15 → 2026-08-19 | Original: martingala 3.30×1.5 fijo | +6.41 (6 apuestas: 1G / 5P) |
| `motor_v2_ev_escalones_tope10` | 2026-08-19 → activo | EV escalonado, entrada solo al inicio/cierre, Poisson + empírico | n/d |

**Por qué se pausaron los `-v2`**: los 6 bots (3 Elon + sus 3 v2) corrían el mismo motor y **duplicaban riesgo** (ej. -3.30×2 en el bin <40 el 18/08). Se dejaron parados como laboratorio para el siguiente motor. No se borraron.

---

## 7. Chequeos de salud (los que SÍ importan)

### 7.1. `check_salud.py` (rápido, cada 15 min)

Comprueba **servicios systemd + Tailscale + proxy + CLOB**. Notifica solo cuando cambia el estado.

Modos:
- (defecto) → `poly-elon`, `poly-semanal`, `poly-mensual`, `poly-telegram`, `poly-gestor` (notifica a `TELEGRAM_BOT_TOKEN`)
- `--zelen` → `poly-zelenskyy`, `poly-telegram-zelen` (notifica a `ZELEN_BOT_TOKEN`)
- `--trump` → `poly-trump` (notifica a `TRUMP_BOT_TOKEN`) ← **NUEVO**

Estado independiente por grupo en `/opt/polymarket/salud_estado{,_zelen,_trump}.json`.

### 7.2. `check_integral.py` (1 vez al día, en horas)

10 chequeos A–J: servicios, proxy, telegram, motor, frescura mercado, frescura CSV, lock, **posiciones fantasma**, huérfanas, funciones del bot de Telegram.

Modos:
- (defecto) → bots de Elon
- `--zelen` → Zelenskyy
- `--trump` → Trump ← **NUEVO** (verifica `notificar_semanal` en vez de `posiciones_reales`)

**Posición fantasma**: bot con `activa` en su `real*.json` pero la cuenta ya no tiene esa posición → bot atascado. Con `--fix` lo reconcilia automáticamente.

### 7.3. Otros checks auxiliares (en `codigo/`)
- `check_abiertas.py`, `check_abiertas2.py` — listar posiciones abiertas
- `check_estado.py` — estado actual
- `check_final.py` — finalizadas
- `check_ganadoras.py` — solo ganadoras
- `check_ordenes.py` — órdenes pendientes
- `check_posiciones.py` — posiciones
- `check_ventanas.py`, `check_ventanas2.py`, `check_ventanas_ahora.py` — mercados activos

---

## 8. Telegram + ntfy

**Telegram** (2 bots):
- `Elon_polymarket_bot` (`poly_telegram_bot.py`, servicio `poly-telegram`) — para los 3 bots de Elon.
- `Lamegawi_zelenskyy_bot` (`poly_telegram_zelen.py`, servicio `poly-telegram-zelen`) — para Zelenskyy. Tiene botón extra "🩺 Salud".

**Botones comunes**: 🟢 Abiertas, 📅 Finalizadas, 💰 Saldo, 🪟 Ventanas.

**ntfy** (notificaciones push):
- Tema ntfy por bot: `elon-poly-XXXXXXXX` (8 chars random).
- Trump añade prefijo `[SEMANAL]` para distinguir.
- Salida al móvil: `saldo_ntfy.py` consulta saldo CLOB + on-chain (pUSD + USDC + USDC.e + POL) y lo formatea.

---

## 9. Gestión de posiciones

**`gestionar_posiciones.py`**: cada N minutos:
1. Lee posiciones abiertas de Elon del data-api.
2. Proyecta tweets al final de la ventana con el ritmo real.
3. Si la proyección cae fuera del bin apostado, **vende** (en positivo si puede, con pérdida mínima si no).
4. NO vende en las últimas 2h (deja resolver).
5. **Solo para Elon** (las demás no se tocan).

---

## 10. Estado del bot de Trump (pendiente de desplegar)

### 10.1. Lo que está en el repo (commit `e32cde0` en `arena/01a058fe-bots-backup`)

- `poly/codigo/bot-polymarket-trump/` — 19 archivos (todos los `.py` + `GUIA_SEMANAL.md` + `config.json` con placeholders + `datos_trump.csv` con 211 días + `.gitignore` + `config_real.json.example`).
- `poly/codigo/check_salud.py` — actualizado con `--trump`.
- `poly/codigo/check_integral.py` — actualizado con `--trump`.
- `poly/ESTADO.md` — cobertura de los 5 bots.
- `poly/datos/motores.json` — añade `cobertura_por_bot` con los 5.
- `scripts_despliegue/trump_hetzner.sh` + `INSTRUCCIONES.txt` — script todo-en-uno para Hetzner (preserva config_real.json y estado).

### 10.2. Lo que NO está en el repo (runtime, no se commitea)
- `config_real.json` (secretos: clave privada, API keys, Telegram) — `.gitignore`
- `estado_tweets_trump.json` (1.1MB, último estado de tweets)
- `estado_bot_trump.json` (estado de pasos/ciclo)
- `mercado_activo.json` (precios de los 3 mercados semanales)
- `avisos_cooldown.json` (anti-spam de notificaciones)
- `ventanas_vistas.json` (anti-duplicado de señales)
- `real_trump.json` (apuesta activa + historial)
- `historial_trump.json` (si existe)
- `datos_raw_trump/` (87 snapshots de ~1MB cada uno, total ~100MB) — tampoco va

### 10.3. Lo que está en Hetzner (versión de producción, ANTES del despliegue)

`/opt/polymarket/bot-polymarket-trump/` con 7 archivos adaptados. La versión del repo es **más reciente** (incluye las adaptaciones de `motores.py` v2, `gestionar_posiciones.py` con `cierre_anticipado` Elon, `check_integral.py` con `BOTS_TRUMP`, `senal_vivo.py` con `MOTOR_ACTUAL="motor_v2_ev_escalones_tope10"` y `EV_MIN_ENTRADA=1.8`, `recoger_tweets.py` con FIXT jina smart backoff). El servicio `poly-trump` está **active** y operando con la versión antigua.

**El despliegue preserva el `config_real.json` y todos los `estado_*.json`**; solo reemplaza los `.py` y `.md` por los del repo.

### 10.4. Diferencias Trump vs los demás

| Característica | Trump | Elon semanal | Zelenskyy |
|---|---|---|---|
| Tamaño `senal.py` | 460 líneas | 276 líneas | 276 líneas |
| `senal_vivo.py` | 291 líneas | más simple | más simple |
| Fuente tweets | xtracker + jina + nitter | nitter + jina | nitter + jina |
| T0 / ventanas | FIX_VENTANAS_TRUMP (lógica especial para días parciales) | estándar | estándar |
| Notificaciones | `notificar_semanal.py` propio con cooldown | `notificar_semanal.py` | `notificar_semanal.py` |
| `GUIA_SEMANAL.md` | sí | no | no |
| `config_real.json.example` | sí | no | no |
| Bot de Telegram | no (usa ntfy) | sí (compartido en `poly-telegram`) | sí (`poly-telegram-zelen`) |
| `avisos_cooldown.json` + `ventanas_vistas.json` | sí | no | no |
| `datos_raw_*` | sí (87 snapshots) | no | no |

**Conclusión**: Trump es el **bot más completo** de los 5. Es la referencia a la que deberían tender los demás.

---

## 11. Pendientes inmediatos

1. **Desplegar Trump en Hetzner** (commit `a5c02ed` ya en repo, script `scripts_despliegue/trump_hetzner.sh` listo). Estado: **a medias** — el repo se hizo público, se clonó en `/tmp/repo-trump/` en la VM, se hizo backup en `/opt/polymarket/backup_trump_20260831_201030/`. **Faltan los pasos 4-12 del script de despliegue** (preservar archivos, reemplazar, actualizar chequeos, validar sintaxis, reiniciar `poly-trump`, probar `--trump`).
2. **Revocar el PAT `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`** (scope `repo` completo). Ya está en uso, pero sigue siendo un riesgo. https://github.com/settings/tokens
3. **Hacer PR a `main`** en `bots-backup` (ahora está en la rama `arena/01a058fe-bots-backup`).
4. **Revisar si los chequeos de Trump deben tener su propio cron**: ahora mismo los chequeos del Elon son cada 15 min. Para Trump habría que añadir las líneas `*/15 * * * * /opt/polymarket/codigo/check_salud.py --trump` y `0 9 * * * /opt/polymarket/codigo/check_integral.py --trump`.
5. **Bots `-v2` parados**: `poly-elon-v2`, `poly-semanal-v2`, `poly-mensual-v2`. Decidir si se eliminan o se reutilizan como laboratorio.

---

## 12. Glosario de archivos críticos

| Archivo | Qué hace | Notas |
|---|---|---|
| `senal.py` | Motor: métricas + Poisson/empírica + reglas R1-R7 | Compartido, distintas versiones por bot |
| `senal_vivo.py` | Integra datos + mercado + evalúa candidatas | Define `MOTOR_ACTUAL` |
| `operar_real*.py` | Trading real con CLOB V2 SDK | El más importante: 800+ líneas, muchos FIX |
| `recoger_tweets.py` | Cascada jina + nitter (xtracker para Trump) | |
| `mercado_polymarket.py` | Descarga y parsea mercados de gamma-api | Genera `mercado_activo.json` |
| `notificar.py` / `notificar_semanal.py` | Notificaciones ntfy | Trump tiene cooldown |
| `saldo_ntfy.py` | Saldo real (CLOB + on-chain) | pUSD, USDC, USDC.e, POL |
| `chequear_cuenta.py` | Diagnóstico de cuenta y entorno | |
| `excel_historial.py` | Genera Excel acumulativo | |
| `diagnostico.py` | Diagnóstico del bot | |
| `gestionar_posiciones.py` | Cierre anticipado de posiciones Elon | Solo Elon |
| `check_salud.py` | Health check rápido | Soporta `--trump` |
| `check_integral.py` | Health check diario completo | Soporta `--trump` |
| `poly_telegram_bot.py` | Bot Telegram de Elon | Servicio `poly-telegram` |
| `poly_telegram_zelen.py` | Bot Telegram de Zelenskyy | Servicio `poly-telegram-zelen` |
| `apuestas_compartidas.json` | Lock compartido entre bots | Ruta: `/home/bots/...` |
| `config_real.json` | Secretos (NO en repo) | `.gitignore` lo excluye |
| `datos_*.csv` | Histórico de tweets/día | 1 fila por día |
| `mercado_activo.json` | Mercados + bins + precios | Generado por `mercado_polymarket.py` |
| `real*.json` | Estado de la apuesta activa + historial | 1 por bot |

---

## 13. Cosas aprendidas / warnings para otra IA

- **NO uses la web console de Hetzner para scripts largos**: rompe `--`, `:`, `_`, y mete espacios. Usa SSH desde el PC del usuario.
- **NO commitees `config_real.json`**: ya está en `.gitignore` en los 5 bots, pero cuidado al añadir archivos nuevos.
- **El SDK es V2** (`py-clob-client-v2`). El saldo de trading es **pUSD** (no USDC). El SDK necesita el funder (wallet_address) + private key.
- **El motor v2 NO es solo martingala**: usa EV (probabilidad × cuota) con un mínimo de 1.8 y escalones 1× / 1.5× / 2×. El tamaño depende de la ventaja, no del paso.
- **Solo se entra al inicio o al cierre** de la ventana (FIXWIN-VENTANAS_ARENA). En el medio no se opera.
- **El T0 importa**: para Trump, `conteo_ventana()` mira tanto el CSV (días completos) como el JSON (timestamps exactos), y NO duplica el día de inicio si la ventana empieza a las 00:00 ET.
- **El lock compartido** evita apuestas duplicadas entre bots. Verificar que la ruta (`/home/bots/apuestas_compartidas.json`) sea accesible desde TODOS los bots que corran (en Hetzner sí, pero en GitHub Actions NO — el bot semanal de Elon GitHub-Actions tiene un lock local porque no comparte máquina con los demás).
- **El bot de Trump NO tiene bot de Telegram propio**: solo ntfy. Si quieres añadir uno, crea un nuevo servicio `poly-telegram-trump` (copia de `poly_telegram_zelen.py` con otro TOKEN).
- **El `diagnostico.py` no existe en el bot mensual** de Elon (los otros 4 sí lo tienen). No es crítico, pero si quieres homogeneizar, cópialo del semanal.
- **Hay 9 servicios systemd** en producción + 3 parados (`-v2`). `poly-gestor` es el gestor de cierres anticipados de Elon.
- **El repo es PÚBLICO** desde el 2026-08-31 (`isPrivate: false`). No hay secretos en él. El `.gitignore` excluye `config_real.json`, `*.key`, `*.pem`.
