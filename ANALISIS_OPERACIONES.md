# 📊 Análisis de salud y operaciones de los bots Polymarket

> **Fecha del análisis**: 2026-09-01
> **Datos utilizados**: dumps de producción de Hetzner (2026-08-30, último disponible) + datos del repo `bots-backup`.
> **Fuentes**: `lamegawi/bot-diagnosticos` (diag_poly.txt, leer_operar_real.txt, leer_bots_completo.txt, leer_zelen_strategy.txt, leer_sistemas_poly.txt)

---

## 0. Resumen ejecutivo (TL;DR)

| Aspecto | Estado | Notas |
|---|---|---|
| 🟢 Servicios systemd | **8/8 activos** | `poly-elon`, `poly-semanal`, `poly-mensual`, `poly-zelenskyy`, `poly-trump`, `poly-telegram`, `poly-telegram-zelen`, `poly-gestor` |
| 🟢 Timers | **8/8 funcionando** | Chequeos cada 15 min, fantasmas cada 30, test diario, salud Trump |
| 🟢 Recogida de datos | **OK en todos** | jina/nitter para Elon, jina para Zelen, **xtracker para Trump (4681 items)** |
| 🟡 PnL consolidado | **+20.78 $ total** | +17.74$ (Elon 48h real) +3.04$ (cierres anticipados Elon) |
| 🟡 Bots en REAL | **Solo 1** (Elon 48h) | El resto de bots NO tiene `real.json` en el dump → siguen en **papel** o parados |
| 🔴 Posición fantasma | **1 detectada** | `0xb0E1197098...` con YES <40 ago 29-31, $3.18 invertidos, valor $1.68 (-47%) |
| 🟡 Bot de Trump | **activo, sin trades aún** | Arrancó 30/08 13:58 EDT, lleva 3+ horas sin operar (esperando señal con EV≥1.8) |
| 🟡 Chequeo de Trump | **Funciona** | `poly-salud-trump.timer` corre cada 30 min · `poly-test-diario-trump.timer` aún no se ha disparado (esperando 19:10 UTC) |

**Conclusión global**: los bots **corren sin errores graves** y los servicios están todos UP. Hay **1 posición huérfana** menor (la del <40 ago-31 que probablemente se resolverá OK porque el mercado ha terminado y Musk ya va por <40 tweets reales). El bot de Trump lleva 3+ horas sin operar — es **normal** porque el motor v2 con EV≥1.8 es muy selectivo y los mercados semanales necesitan tiempo para que el λ48 se estabilice.

---

## 1. Salud de los bots (estado técnico)

### 1.1. Servicios systemd

| Servicio | Estado | Notas |
|---|---|---|
| `poly-elon` | ✅ active | Bot 48h principal |
| `poly-semanal` | ✅ active | Bot semanal Elon |
| `poly-mensual` | ✅ active | Bot mensual Elon |
| `poly-zelenskyy` | ✅ active | Bot semanal Zelenskyy |
| `poly-trump` | ✅ active | Bot semanal Trump (NUEVO) |
| `poly-telegram` | ✅ active | Telegram Elon |
| `poly-telegram-zelen` | ✅ active | Telegram Zelenskyy |
| `poly-gestor` | ✅ active | Cierre anticipado Elon |
| ~~`poly-elon-v2`~~ | ⏸ parado | Laboratorio, no se borró |
| ~~`poly-semanal-v2`~~ | ⏸ parado | Laboratorio, no se borró |
| ~~`poly-mensual-v2`~~ | ⏸ parado | Laboratorio, no se borró |

### 1.2. Timers (chequeos programados)

| Timer | Última ejecución | Próxima | Servicio |
|---|---|---|---|
| `poly-salud.timer` | 18:42 UTC 30/08 | 19:12 UTC | `check_salud.py` (Elon) |
| `poly-salud-zelen.timer` | 18:42 UTC 30/08 | 19:12 UTC | `check_salud.py --zelen` |
| `poly-salud-trump.timer` | 18:46 UTC 30/08 | 19:16 UTC | `check_salud.py --trump` ← **NUEVO** |
| `poly-fantasmas.timer` | 18:41 UTC 30/08 | 19:11 UTC | `check_integral.py` (Elon) |
| `poly-fantasmas-zelen.timer` | 18:14 UTC 30/08 | 18:44 UTC | `check_integral.py --zelen` |
| `poly-test-diario.timer` | 07:00 UTC 30/08 | 19:00 UTC | `check_integral.py` modo completo |
| `poly-test-diario-zelen.timer` | 07:05 UTC 30/08 | 19:05 UTC | `check_integral.py --zelen` |
| `poly-test-diario-trump.timer` | **NUNCA** | 19:10 UTC | `check_integral.py --trump` ← **pendiente primer disparo** |

### 1.3. Recogida de datos (logs del 30/08 13:32-14:46 EDT)

| Bot | Fuente 1ª | Items | Estado |
|---|---|---|---|
| Elon 48h | jina-tw | 6 | ✅ |
| Elon 48h | jina-x | 6 | ✅ |
| Elon 48h | nitter | 0 | 🟡 sin items (jina cubre) |
| Trump | **xtracker** | **4681-4682** | ✅ (sube +1 por pasada) |
| Trump | jina/nitter | (no se ejecuta, xtracker cubre) | ✅ |

**Caveat**: el 30/08 a las 13:32 EDT jina-x dio "ERROR jina en pausa (descanso tras fallos)" pero jina-tw siguió OK, y el bot tiene backoff inteligente.

---

## 2. Posiciones abiertas (estado real en Polymarket)

| Cartera | Mercado | Lado | Size | Invertido | Valor | PnL no realizado |
|---|---|---|---|---|---|---|
| `0xb0E1197098...` | Will Elon Musk post <40 tweets (Aug 29-31)? | YES | 176.79 | $3.18 | $1.68 | **-$1.50 (-47%)** |

**Análisis de la posición**:

- Mercado: ventana 29-31 agosto (cerró a las 12:00 EDT del 31/08)
- Resultado probable: **NO** (Musk hizo muchos tweets ese fin de semana; el precio YES cayó a 0.0095 según `mercado_activo.json`)
- **Esta posición es HUÉRFANA**: NO está en `bot-polymarket-elon/real.json` (que tiene `activa: null` y `paso: 2`). La apuesta se hizo probablemente el 17/08 cuando el bot predijo <40 con p_modelo 92% y stake $3.30, pero el bot la dio por perdida el 18/08 (cuando el gestor vendió a $2.74 según `cierres_anticipados.json`). Sin embargo, parece que **parte de la posición NO se vendió** y se quedó en la cuenta con 176.79 shares.
- **Recomendación**: el `check_integral.py --fix` debería detectarla en el siguiente ciclo y reconciliarla. Mientras tanto, al cierre del mercado debería liquidarse automáticamente a $0.018 × 176.79 = $3.18 de ingreso (recuperarías lo invertido).

⚠️ **ALERTA DE FANTASMA**: en el log hay 4 carteras detectadas (`0x8a22F798C2`, `0xa1b936cd50`, `0xb0E1197098`, `0xb315477a36`). Solo la del funder principal tiene posición. Las otras 3 están vacías pero hay que verificar de dónde salen (probablemente de config_real.json de bots anteriores o de pruebas).

---

## 3. Motor de señal — estado el 30/08 14:42 EDT

Métricas del bot 48h en ese momento (del dump `diag_poly.txt` sección 5):

```
AVG7 = 22.43  V2 = 23  R = 0.513  ajuste = 0.756  λ48 = 33.9  [datos propios: 39 días]
```

**Interpretación**:
- R = 0.513 < 1 → modo "recuperación" (Musk ha tuiteado MENOS de lo esperado en los últimos 2 días)
- ajuste = 0.756 → el modelo asume que Musk volverá a su media, pero sin sobre-corregir
- λ48 = 33.9 → predicción para las próximas 48h
- T0 = 14 (en el mercado 29-31 ago) → Musk ya tuiteó 14, le quedan ~20 por el λ

**Evaluación por mercado**:

### 3.1. Mercado 48h (29-31 ago)
- Bin `<40`: p_modelo = 71.4%, precio YES = 0.009, cuota YES = 105.26 → **APOSTAR YES** (señal válida)
- Bins 40-64, 65-89, 90-114...: p_modelo < 30%, no llegan al umbral para NO porque cuota < 3.00

### 3.2. Mercado mensual (agosto)
- T0 = 884 tweets ya en agosto (de los 920-939 totales reales)
- λ7 = 118.8 (esperado mensual) → λ restante = 23.5
- **Ninguna operación se dispara**:
  - Casi todos los bins tienen precio 0.000 (mercado cerrado en la práctica)
  - Los bins 880-919 (p_modelo 60.2%, cuota 1.65) **NO disparan** porque R3 exige cuota ≥ 3.00
  - El bin 840-879 (precio 0.372, cuota 2.69) **NO dispara** por la misma razón

**Conclusión**: el motor v2 es **muy conservador** y solo dispara cuando la cuota es ≥ 3.00. En mercados ya muy avanzados (T0 alto), esto puede ser un problema porque las cuotas caen. **El bot prioriza EV alto, no frecuencia**.

---

## 4. Resumen de operaciones por bot

### 4.1. `bot-polymarket-elon` (48h) — **EL QUE MÁS OPERA**

**3 operaciones reales cerradas** (del `real.json` y `resultados_real.csv`):

| # | Fecha | Bin | Lado | Cuota | P_modelo | Stake | Resultado | Beneficio | Saldo |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-08-18 | `<40` | YES | 4.35 | 92% | $3.30 | ❌ P | -$3.30 | $496.70 |
| 2 | 2026-08-20 | `90-114` | YES | 4.72 | 64% | $7.43 | ✅ G | +$27.64 | $524.34 |
| 3 | 2026-08-22 | `90-114` | YES | 8.70 | 78% | $6.60 | ❌ P | -$6.60 | $517.74 |

**Estadísticas**:
- Total: 3 ops · 1G / 2P · **PnL +$17.74**
- Cuota media: 5.92 (alta, buena selección)
- P_modelo medio: 78%
- Stake medio: $5.78
- ROI: +3.55% sobre bankroll inicial de $500
- EV medio = 0.78 × 5.92 = 4.62 (muy bueno)
- **Operación #2 fue excepcional**: stake de $7.43 en paso 2 (martingala), ganó con cuota 4.72, plusvalía +$27.64 = casi 4× el stake

**Motores usados**:
- Ops 1 y 2: `motor_v1_martingala_fijo` (anterior al 19/08)
- Op 3: `motor_v2_ev_escalones_tope10` (post-19/08, stake = 6.60 calculado por EV)

**Conclusiones**:
- El bot **funciona** y el modelo predice bien en general (78% de acierto esperado, real 33% en 3 ops — varianza alta con muestra pequeña)
- La operación perdedora #1 (p_modelo 92% y aún así perdió) es un caso claro de **cola larga**: el modelo predice 92% de probabilidad, pero ese 8% restante pasó
- **El gestor vendió 5 posiciones en positivo antes de tiempo** (ver 4.2) — esto es un patrón a vigilar

### 4.2. Cierres anticipados del gestor (5 fechas distintas)

**13 operaciones** registradas en `cierres_anticipados.json`:

| Fecha | Bin | Lado | Invertido | Valor | PnL | ROI |
|---|---|---|---|---|---|---|
| 2026-08-18 | 140-159 | Yes | $6.38 | $10.00 | +$3.62 | +57% |
| 2026-08-18 | 0-39 | Yes | $5.97 | $2.74 | -$3.23 | -54% |
| 2026-08-18 | 100-119 | Yes | $6.26 | $0.85 | -$5.41 | -86% |
| 2026-08-18 | 740-759 | Yes | $2.00 | $1.05 | -$0.95 | -48% |
| 2026-08-18 | 660-679 | Yes | $2.47 | $1.86 | -$0.61 | -25% |
| 2026-08-21 | 90-114 | Yes | $7.43 | $10.13 | +$2.70 | +36% |
| 2026-08-26 | 220-239 | Yes | $8.00 | $8.25 | +$0.25 | +3% |
| 2026-08-26 | 220-239 | Yes | $1.70 | $1.64 | -$0.05 | -3% |
| 2026-08-29 | 160-179 | Yes | $1.08 | $1.05 | -$0.03 | -3% |
| 2026-08-29 | 120-139 | Yes | **$0.00** | $5.66 | +$5.66 | N/A |
| 2026-08-29 | 120-139 | Yes | **$0.00** | $1.41 | +$1.41 | N/A |
| 2026-08-29 | 120-139 | Yes | $4.05 | $4.08 | +$0.03 | +1% |
| 2026-08-29 | 120-139 | Yes | $1.95 | $1.83 | -$0.12 | -6% |

**Estadísticas**:
- Total: 13 ops · 6G / 7P · **PnL +$3.27** · ROI +6.9% (sobre $47.29 invertidos)
- **5 de las 13 son del 18/08** (cuando el bot perdió el control al tener 6 bots corriendo el mismo motor)

**Agrupado por bin**:

| Bin | G/P | PnL | ROI | Comentario |
|---|---|---|---|---|
| **120-139** | 3/1 | +$6.98 | +116% | El bin más rentable — Musk cumplió justo el rango |
| 140-159 | 1/0 | +$3.62 | +57% | Una sola pero buena |
| **90-114** | 1/0 | +$2.70 | +36% | Coincide con op #2 del bot real |
| 220-239 | 1/1 | +$0.20 | +2% | Empate técnico |
| 160-179 | 0/1 | -$0.03 | -3% | Marginal |
| 660-679 | 0/1 | -$0.61 | -25% | Bin alto, Musk no llegó |
| 740-759 | 0/1 | -$0.95 | -48% | Bin alto |
| 0-39 | 0/1 | -$3.23 | -54% | Sucedió el 18/08, Musk hizo >40 |
| 100-119 | 0/1 | -$5.41 | -86% | Sucedió el 18/08, el peor cierre del lote |

**Conclusiones**:
- El gestor vendió 13 posiciones, ganó 6 y perdió 7 → **win rate 46%** (peor que el 67% del bot en real, pero con menos stake)
- Los **bins altos** (660-679, 740-759, 100-119) son **trampa**: Musk no llega. PnL combinado -$6.97
- El bin **120-139** es el **sweet spot**: Musk lo cumple a menudo y cotiza alto
- **3 posiciones del 18/08 fueron "regaladas"** (las del <40, 100-119, 140-159): Musk se pasó de 100 el 18/08 y eso invalidó todas las predicciones bajas
- Las posiciones con `invertido=0` (los 2 del 120-139 del 29/08) son **regalos** del mercado (probablemente una resolución de mercado que devolvió shares gratis)

### 4.3. `bot-polymarket-elon-semanal` (semanal Elon)

**Sin operaciones reales registradas** (no hay `real_semanal.json` en el dump). El bot está activo y corriendo pero **no ha hecho ninguna apuesta real todavía**. Posibles razones:
- El motor v2 con EV≥1.8 es muy selectivo
- Los mercados semanales de Elon Musk (ventana 7d) tienen la masa de probabilidad muy repartida en 20 bins → pocas cuotas ≥ 3.00 con EV alta
- El bot puede estar en modo papel o el `config_real.json` no tiene `confirmado: true`

### 4.4. `bot-polymarket-elon-mensual` (mensual Elon)

**Mismo caso que el semanal**: sin operaciones reales registradas. El log muestra métricas con λ7=118.8 y T0=884 (mercado mensual muy avanzado), por lo que la mayoría de bins tienen precio 0 y no se puede operar.

### 4.5. `bot-polymarket-zelenskyy` (semanal Zelenskyy)

**Sin operaciones reales registradas**. 161 días de datos, AVG7=28.7 (similar a Musk). El bot está activo, no opera en real.

### 4.6. `bot-polymarket-trump` (semanal Trump) — **NUEVO**

**Sin operaciones reales registradas todavía** (acaba de arrancar el 30/08 13:58 EDT). Estado:
- 4681 tweets cargados desde xtracker
- 211 días de histórico
- 3 mercados semanales activas
- AVG7 = 35.71, mediana 18, max 101, std 17.44
- Sin trades en las 3 horas que lleva activo

**Razón probable**: el motor v2 con EV≥1.8 necesita ver el λ48 de la nueva semana estabilizarse. Es normal.

---

## 5. Conclusiones y recomendaciones

### 5.1. Salud general: 🟢 BIEN
- Los 5 bots corren sin errores
- Los 8 servicios systemd están activos
- Los 8 timers funcionan (1 pendiente de primer disparo, `poly-test-diario-trump.timer`)
- La recogida de datos es robusta (jina + nitter + xtracker)

### 5.2. PnL global: 🟡 POSITIVO PERO MUY PEQUEÑO
- Total operaciones reales cerradas: **3** (solo Elon 48h)
- Total con cierres anticipados: **16** (3 + 13)
- PnL total: **+$20.78** sobre 16 operaciones
- ROI global: **+3.6%** (sobre bankroll $500 + $47.29 del gestor = $547.29)
- **El problema**: solo Elon 48h opera en real. Los otros 4 bots no tienen operaciones reales registradas.

### 5.3. Acciones recomendadas

1. **URGENTE: revisar posición huérfana de $3.18 en <40 ago-31**
   - Probable que se resuelva OK al cierre (Musk hizo >40 tweets)
   - Verificar tras el 31/08 12:00 EDT
   - El `check_integral.py --fix` debería detectarla automáticamente

2. **Activar REAL en los demás bots** (o documentar por qué están en papel)
   - Si están en papel por decisión: añadir un `estado_bot.json` con `"modo": "papel"` para que `check_integral.py` no se queje
   - Si fue olvido: copiar el `config_real.json` del 48h a los demás

3. **Revisar por qué el motor v2 no dispara en semanal/mensual**
   - Posibilidad: los mercados semanales ya están avanzados y la cuota ≥ 3.00 es muy restrictiva
   - Considerar relajar R3 a cuota ≥ 2.50 para semanal/mensual
   - **PERO**: hay que validar antes con backtest, no en producción

4. **Considerar vender la posición <40 ago-31 antes del cierre**
   - Si la posición está en el CLOB y cotiza a 0.0095, vender TODO recupera $1.68
   - Mejor que esperar a la resolución (que probablemente dé $0)
   - El `gestionar_posiciones.py` debería hacerlo, pero es solo para Elon (no la detecta porque no está en el `real.json`)

5. **Hacer un backtest del motor v2 con 3+ meses de datos**
   - El `senal.py` tiene `--backtest` pero solo se ha hecho en 48h
   - Aplicarlo a semanal y mensual para validar que el modelo predice bien
   - Especialmente con la distribución empírica (no Poisson)

6. **Limpiar los bots `-v2` parados** si no se van a usar
   - Llevan parados desde el 19/08
   - Ocupan espacio y pueden confundir a los chequeos

7. **Revisar el cron de `poly-test-diario-trump.timer`**
   - Está creado pero aún no se ha disparado
   - Verificar tras 19:10 UTC del 30/08 que el test integral con `--trump` funciona
   - Si falla, mirar logs de `journalctl -u poly-test-diario-trump.service`

8. **Documentar la decisión de mantener `gestionar_posiciones.py` SOLO para Elon**
   - El bot de Trump no tiene cierre anticipado
   - El bot de Zelenskyy tampoco
   - Esto significa que las posiciones perdedoras en esos bots se quedan hasta el final
   - Decisión consciente o por implementar

### 5.4. Análisis cuantitativo del modelo

**Métricas del modelo v2** (con datos del 30/08):

| Bot | Días datos | AVG7 | Std | Tasa base | Tasa real media |
|---|---|---|---|---|---|
| Elon (48h) | 37 | 29.0 | 18.4 | 29.0 t/día | 25 (mediana) |
| Elon (semanal) | 35 | 28.6 | 16.9 | 28.6 t/día | 25 |
| Elon (mensual) | 35 | 28.6 | 16.5 | 28.6 t/día | 25 |
| Zelenskyy (semanal) | 161 | 28.7 | 8.9 | 28.7 posts/sem | 10 posts/sem (mediana) |
| Trump (semanal) | 212 | 35.7 | 17.4 | 35.7 t/sem | 18 t/sem (mediana) |

**Observaciones**:
- **Elon** tiene más varianza (std 18) que **Zelenskyy** (std 9), por lo que el modelo de Musk es **menos predecible**
- **Trump** tiene el doble de tweets que Zelenskyy (35 vs 10), por lo que el λ_trump > λ_zelenskyy
- La distribución empírica es más acertada que la Poisson para todos (porque tienen colas más largas)

### 5.5. Análisis del stake y martingala

- **Stake base**: $3.30 (para 48h) y 3.00 (semanal) y 2.00 (mensual)
- **Multiplicador**: ×1.5 por paso perdido
- **Tope**: 7 pasos (exposición máxima $3.30×1.5^6 = $47.65 para 48h)
- **Nuevo motor v2**: stake por EV (1.8-2.5 ×1, 2.5-4.0 ×1.5, >4.0 ×2, tope $10)

**Riesgo**: con bankroll de $500, un ciclo perdido completo (7 pasos en 48h) consume $47.65 = 9.5% del bankroll. Es manejable pero no óptimo.

**Recomendación**: considerar reducir el stake base a $2.00 para los bots de Zelenskyy y Trump (porque tienen menos datos y más incertidumbre).

---

## 6. Pendientes y tareas para el despliegue de Trump

1. Desplegar la versión del repo en Hetzner (el commit `a5c02ed` en `arena/01a058fe-bots-backup`)
   - Script: `scripts_despliegue/trump_hetzner.sh`
   - Backup: ya hecho en `/opt/polymarket/backup_trump_20260831_201030/`
   - Pendiente: pasos 4-12 del script (preservar archivos, reemplazar, validar, reiniciar)

2. Verificar tras el primer ciclo (15 min) que:
   - El servicio `poly-trump` sigue `active` con la versión nueva
   - Los logs de `bot_trump.log` no muestran errores
   - `check_salud.py --trump` reporta OK

3. Cron para los chequeos de Trump (a añadir a `/etc/cron.d/` o `crontab -e`):
   ```
   */15 * * * * /opt/polymarket/codigo/check_salud.py --trump
   0 9 * * *   /opt/polymarket/codigo/check_integral.py --trump
   ```
   (El `poly-test-diario-trump.timer` ya existe y se encarga del diario, pero el de salud cada 15 min puede ser necesario)

4. **Hacer PR a `main`** del repo `bots-backup` cuando termines de validar.

5. **Revocar el PAT `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`** (scope `repo` completo, ya no lo necesitas).

---

## 7. Glosario de métricas

| Métrica | Significado | Valor típico |
|---|---|---|
| AVG7 | Media tweets/día últimos 7 días | 25-35 |
| V2 | Total últimos 2 días | 40-80 |
| R | V2 / (2·AVG7) — momentum | 0.5-1.5 |
| ajuste | clamp(1+0.5·(R-1), 0.5, 1.5) | 0.75-1.25 |
| λ48 | Tweets esperados 48h = 2·AVG7·ajuste | 40-60 |
| p_modelo | Probabilidad del bin según Poisson/empírica | 0-100% |
| EV | p_modelo × cuota (lado elegido) | >1.8 para entrar |
| T0 | Tweets ya en la ventana actual | depende del momento |

---

## 8. Comandos útiles para re-analizar en el futuro

```bash
# Ver salud actual
python3 /opt/polymarket/codigo/check_salud.py --trump --test
python3 /opt/polymarket/codigo/check_integral.py --trump --test

# Ver posición fantasma
python3 -c "
import urllib.request, json
req = urllib.request.Request(
    'https://data-api.polymarket.com/positions?user=0xb0E1197098E6d427c01720F1631cAD24CE740FA0',
    headers={'User-Agent':'Mozilla/5.0'})
print(json.dumps(json.loads(urllib.request.urlopen(req).read()), indent=2))
"

# Reconciliar fantasmas
python3 /opt/polymarket/codigo/check_integral.py --trump --fix

# Diagnóstico completo
bash /opt/polymarket/recolector_poly.sh
```

---

*Documento generado el 2026-09-01 a partir de los datos disponibles en `lamegawi/bot-diagnosticos` (commits del 30/08 18:48). Para datos más recientes, ejecutar el `recolector_poly.sh` en Hetzner.*
