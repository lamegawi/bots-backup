# 📉 Análisis de PnL REAL (corrección del análisis anterior)

> **Fecha**: 2026-09-01
> **Importante**: este análisis corrige el `ANALISIS_OPERACIONES.md` previo, que daba un PnL positivo (+$20.78) basado solo en lo que el bot **creía** tener. El PnL **REAL** de la cuenta de Polymarket es **negativo** y más alto.

---

## 0. Resumen ejecutivo

| Concepto | Valor | Fuente |
|---|---|---|
| Bankroll inicial (depósito en Polymarket) | **$500.00** | Confirmado por el usuario |
| Saldo real actual en la cuenta | **~$450** | Confirmado por el usuario |
| **Pérdida neta REAL** | **-~$50** | (-10% sobre bankroll) |
| Lo que el `real.json` del bot 48h cree tener | $517.74 | FALSO — no es saldo real |
| Lo que el `real.json` del bot 48h cree que ha ganado | +$17.74 | FALSO — solo refleja 3 ops aisladas |

**Conclusión principal**: el registro interno de los bots (`real.json`) **NO refleja la realidad de la cuenta de Polymarket**. Las pérdidas reales son mucho mayores que las que el bot lleva. Esto se debe a:

1. **Operaciones manuales** (13 cierres del gestor que están en `cierres_anticipados.json` pero no se sincronizan con el bot).
2. **Posiciones huérfanas** (la del mercado `<40 ago 29-31` está en la cuenta pero el bot no la sabe).
3. **Probablemente más operaciones manuales** (compras directas en Polymarket o desde otros dispositivos) que no están en ningún registro del bot.

---

## 1. Por qué el `real.json` miente

### 1.1. El `real.json` del bot 48h dice:

```json
{
  "saldo": 517.74,
  "paso": 2,
  "activa": null,
  "historial": [
    {"fecha":"2026-08-18", "bin":"<40", "stake":3.30, "resultado":"P", "beneficio":-3.30, "saldo":496.70},
    {"fecha":"2026-08-20", "bin":"90-114", "stake":7.43, "resultado":"G", "beneficio":+27.64, "saldo":524.34},
    {"fecha":"2026-08-22", "bin":"90-114", "stake":6.60, "resultado":"P", "beneficio":-6.60, "saldo":517.74}
  ]
}
```

**Esto dice**: bankroll implícito $500, PnL virtual +$17.74 sobre 3 operaciones.

### 1.2. La realidad en la cuenta de Polymarket

- Bankroll real depositado originalmente: $500
- Saldo real actual: ~$450
- PnL real: **-$50**

**Diferencia**: 17.74 - (-50) = **$67.74 de operaciones que el bot no sabe que pasaron**.

### 1.3. ¿De dónde vienen esos $67.74?

| Fuente | Importe | ¿Está en el bot? |
|---|---|---|
| 13 cierres anticipados del gestor | +$3.27 | NO |
| Posición huérfana `<40 ago 29-31` | -$1.50 (a 30/08) | NO |
| **Subtotal identificado** | **+$1.77** | — |
| **Faltan por identificar** | **-$69.51** | NO |

Hay **-$69.51 de operaciones que NO están en ningún registro** del bot. Esto puede ser:
- Compras manuales en Polymarket (no rastreadas)
- Operaciones del gestor que se le olvidó apuntar
- Errores en la sincronización del `real.json` con el CLOB
- Comisiones, fees o pérdidas en posiciones que se resolvieron automáticamente

---

## 2. Análisis de las operaciones conocidas

### 2.1. Bot 48h de Elon (lo que el bot SÍ sabe)

3 operaciones reales, 1G/2P, PnL virtual +$17.74:

| # | Fecha | Bin | Lado | Cuota | P_mod | Stake | Resultado | Benef | Saldo bot |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 2026-08-18 | <40 | YES | 4.35 | 92% | $3.30 | ❌ P | -$3.30 | $496.70 |
| 2 | 2026-08-20 | 90-114 | YES | 4.72 | 64% | $7.43 | ✅ G | +$27.64 | $524.34 |
| 3 | 2026-08-22 | 90-114 | YES | 8.70 | 78% | $6.60 | ❌ P | -$6.60 | $517.74 |

**Observación crítica**: la op #2 reporta "vendido por el gestor en positivo (+2.70 a nivel cuenta)" — esto significa que **el gestor SÍ ganó $2.70 a nivel de cuenta** (lo que aparece en `cierres_anticipados.json`), pero el `real.json` del bot registra $27.64 (que es stake×cuota-beneficio_previo). **El bot y la cuenta están midiendo cosas distintas**.

**Diferencia op #2**: $27.64 (bot) vs $2.70 (cuenta real) = **$24.94 de discrepancia** que explicaría parte de los $69.51 faltantes.

### 2.2. Cierres anticipados del gestor (lo que la cuenta SÍ registra)

13 operaciones del gestor (de `cierres_anticipados.json`):

| Fecha | Bin | Invertido | Valor | PnL | ROI |
|---|---|---|---|---|---|
| 18/08 | 140-159 | $6.38 | $10.00 | +$3.62 | +57% |
| 18/08 | 0-39 | $5.97 | $2.74 | -$3.23 | -54% |
| 18/08 | 100-119 | $6.26 | $0.85 | -$5.41 | -86% |
| 18/08 | 740-759 | $2.00 | $1.05 | -$0.95 | -48% |
| 18/08 | 660-679 | $2.47 | $1.86 | -$0.61 | -25% |
| 21/08 | 90-114 | $7.43 | $10.13 | +$2.70 | +36% |
| 26/08 | 220-239 | $8.00 | $8.25 | +$0.25 | +3% |
| 26/08 | 220-239 | $1.70 | $1.64 | -$0.05 | -3% |
| 29/08 | 160-179 | $1.08 | $1.05 | -$0.03 | -3% |
| 29/08 | 120-139 | $0.00 | $5.66 | +$5.66 | N/A |
| 29/08 | 120-139 | $0.00 | $1.41 | +$1.41 | N/A |
| 29/08 | 120-139 | $4.05 | $4.08 | +$0.03 | +1% |
| 29/08 | 120-139 | $1.95 | $1.83 | -$0.12 | -6% |
| **Total** | — | **$47.29** | — | **+$3.27** | **+6.9%** |

**Observación crítica**: la op del 21/08 muestra **invertido $7.43 (mismo stake que la op #2 del bot)** pero el `real.json` registra el cierre con +$27.64 (que es el cálculo del bot, no la realidad de la cuenta). El gestor cerró esa posición cuando iba +$2.70 en la cuenta. La discrepancia entre $27.64 (bot) y $2.70 (cuenta) es porque el bot asume un cobro completo a cuota 4.72, pero el gestor vendió antes y solo cobró $2.70.

### 2.3. Posición huérfana

Detectada en el dump del 30/08:
- **Mercado**: Will Elon Musk post <40 tweets (Aug 29-31, 2026)?
- **Lado**: YES, 176.79 shares
- **Invertido**: $3.18
- **Valor al 30/08**: $1.68
- **PnL no realizado**: -$1.50

Esta posición **NO está en el `real.json` del bot** (que tiene `activa: null` y solo 3 ops en historial). El bot cree que no tiene nada abierto, pero la cuenta tiene 176.79 shares YES del mercado que cierra el 31/08 a las 12:00 EDT.

**¿De dónde viene?**: probablemente de la op #1 del 18/08 (bin `<40`). El bot la dio por perdida, pero parece que solo se vendió una parte y la otra (176.79 shares) se quedó. O fue una compra duplicada que el bot no detectó.

**Estado probable al cierre del 31/08**: como Musk hizo >40 tweets el 30 y 31 de agosto (los logs muestran 30+30+26 = 86 tweets en solo 3 días), el mercado cayó a `precio_yes ≈ 0.009`. Las 176.79 shares valen ~$1.68 hoy, y al cierre el mercado dará **NO como ganador** → las shares YES se liquidan a $0. Pérdida total: -$3.18.

### 2.4. Discrepancia total identificada

| Concepto | Importe |
|---|---|
| PnL virtual del bot 48h | +$17.74 |
| PnL real cierres gestor | +$3.27 |
| PnL posición huérfana (30/08) | -$1.50 |
| **Subtotal conciliado** | **+$19.51** |
| **PnL real en la cuenta** | **-$50.00** |
| **DIFERENCIA NO EXPLICADA** | **-$69.51** |

**Faltan $69.51** que no se corresponden con NINGÚN registro disponible. Esto es un problema serio de **trazabilidad de operaciones**.

---

## 3. Posibles causas de la discrepancia

### 3.1. Compras manuales en Polymarket (principal sospechoso)

Es muy probable que el usuario (o alguien con acceso a su cuenta) haya hecho operaciones manuales desde la web de Polymarket que:
- NO se reflejan en `real.json` (porque el bot no las ve)
- NO se reflejan en `cierres_anticipados.json` (porque el gestor no las apuntó)
- SÍ afectan la cuenta real (porque Polymarket las registra en blockchain)

**Cómo verificar**: revisar el historial de trades en `https://polymarket.com/profile/0xb0E1197098E6d427c01720F1631cAD24CE740FA0` y comparar con lo que el bot sabe.

### 3.2. Errores en `real.json`

El bot podría haber tenido un bug al registrar cierres. Por ejemplo, en la op #2, el bot registra `beneficio: +27.64` cuando en realidad el gestor vendió con `pnl: +2.70`. Esto significa que **el bot suma $24.94 de "beneficio virtual" que no es real**.

**Si esto pasa en otras ops**, el `real.json` está inflando el saldo virtual. El saldo real es:
```
saldo_real = bankroll_inicial - perdidas_reales
           = 500 - X
```

### 3.3. Posiciones automáticas del cierre de mercado

Cuando un mercado se cierra, Polymarket canjea automáticamente las shares ganadoras. Esto puede generar pequeñas diferencias por:
- Fees de la red Polygon
- Fees del exchange
- Slippage en la venta automática

### 3.4. Bots que no registran en su `real_*.json`

Los bots semanal, mensual, zelenskyy y trump están en "MODO: REAL" (lo dice el log) pero **no han hecho NINGUNA operación** (el Excel dice "añadidas 0, total 0"). Esto es porque el motor v2 con EV≥1.8 es muy selectivo y no ha disparado ninguna señal.

**PERO** hay un riesgo: si en el pasado esos bots hicieron alguna operación que se borró o se perdió, no la tenemos registrada. Aunque por los logs parece que no.

---

## 4. Recomendaciones

### 4.1. Inmediato (hoy)

1. **Ejecutar el script de diagnóstico** que subí a `scripts_despliegue/diagnostico_pnl.sh` en Hetzner. Eso te dará:
   - Saldo real actual (CLOB + on-chain)
   - Estado completo de los `real_*.json` y `papel_*.json` de los 5 bots
   - Lista de posiciones abiertas en la cuenta
   - Bankroll configurado en cada `config_real.json`

2. **Cruzar el historial de trades de Polymarket** (`https://polymarket.com/profile/0xb0E1197098E6d427c01720F1631cAD24CE740FA0`) con el `real.json` del bot. Si hay trades que NO están en el bot, esos son los que faltan.

3. **NO tomar más decisiones de trading** hasta haber conciliado el saldo. El bot cree que tiene $517.74 y la cuenta tiene $450 — si el bot ve "tengo $517" puede hacer una apuesta de $5 (que sería 1% del bankroll virtual pero 1.1% del real), y así sucesivamente.

### 4.2. Corto plazo (esta semana)

1. **Arreglar el bug del `real.json`**: el bot debe registrar el PnL **real de la cuenta** (lo que el gestor o el cierre automático obtuvo), no el cálculo virtual de `stake × (cuota-1)`. La fórmula correcta es:
   ```
   beneficio_real = valor_final - stake_inicial  (lo que dice cierres_anticipados)
   ```
   en vez de:
   ```
   beneficio_virtual = stake × (cuota - 1)  (lo que dice real.json)
   ```

2. **Añadir sincronización periódica con CLOB**: el bot debería consultar la API de Polymarket para verificar sus posiciones reales y compararlas con su `real.json`. Si no coinciden, marcar la diferencia y notificar.

3. **Hacer que el bot NO dependa del gestor humano**: el `gestionar_posiciones.py` debería ser el único que vende, y debería actualizar el `real.json` después de cada venta. Ahora mismo es al revés: el gestor vende a mano y luego actualiza `cierres_anticipados.json` por separado.

### 4.3. Medio plazo

1. **Unificar el registro**: crear un solo `pnl_real.csv` que registre TODAS las operaciones (bot + gestor + manuales), con timestamps y fuentes.

2. **Reconciliación diaria automática**: el `check_integral.py` debería comparar el `real.json` con el `data-api` de Polymarket y reportar discrepancias.

3. **Reconsiderar la frecuencia de trading**: si el bankroll es $450-$500, hacer 3 ops de $3.30 = 2% de exposición. OK. Pero si el gestor añade manualmente 5 ops más, son 5+3 = 8 posiciones simultáneas posibles. Demasiada exposición.

---

## 5. Tareas pendientes (actualizadas)

| Tarea | Prioridad | Estado |
|---|---|---|
| Ejecutar `diagnostico_pnl.sh` en Hetzner | 🔴 URGENTE | Pendiente |
| Conciliar `real.json` con historial de trades de Polymarket | 🔴 URGENTE | Pendiente |
| Desplegar Trump (pasos 4-12 de `trump_hetzner.sh`) | 🟡 | Pendiente (a la tarde) |
| Revocar PAT `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` | 🟡 | Pendiente |
| Arreglar bug del `real.json` (PnL virtual vs real) | 🟡 | Pendiente |
| Sincronización CLOB ↔ `real.json` | 🟢 | Diseño |
| Reconciliación diaria automática | 🟢 | Diseño |

---

## 6. Lo que el script `diagnostico_pnl.sh` te dirá

Cuando lo ejecutes en Hetzner (`bash scripts_despliegue/diagnostico_pnl.sh`), te dará:

1. **Saldo real actual** (CLOB + on-chain)
2. **Todas las posiciones abiertas** en la cuenta
3. **Estado de los 5 bots**: real_*.json, papel_*.json, su historial completo
4. **Bankroll configurado** en cada `config_real.json`
5. **Lista detallada de los 13 cierres del gestor**

Con esa info podrás:
- Confirmar si la pérdida es de $50 o de otra cifra
- Identificar qué trades manuales faltan
- Decidir si parar todos los bots hasta tener trazabilidad real

---

*Corrección: el análisis previo (`ANALISIS_OPERACIONES.md`) daba un PnL de +$20.78. El PnL real es de **-$50**. La diferencia es por operaciones no registradas en los bots (manuales o del gestor que no se sincronizan con el `real.json`).*
