# 📋 Plan de seguimiento — Bots Polymarket (post-filtros 10/09)

## ✅ Cambios desplegados (commit `9e6aed1` + `128e8a4` + `d57d2f6`)

### Bot ELON (48h)
| Parámetro | Antes | Ahora | Razón |
|---|---|---|---|
| `CUOTA_MINIMA` | 3.00 | **5.00** | Más conservador |
| `PRECIO_MAX` | (no existía) | **0.20** | No long shots (precio < 0.20) |
| Anti-bin-perdido | (no existía) | **t0 + λ_rest > hi → PASAR** | Evita comprar 120-139 cuando t0=129 |
| `decision()` | OK | Filtro adicional | Más estricto |

### Bot ZELENSKYY (semanal)
| Parámetro | Antes | Ahora | Razón |
|---|---|---|---|
| `CUOTA_MINIMA` | 2.50 | **3.00** | Más conservador |
| `PRECIO_MAX` | (no existía) | **0.30** | No long shots |
| `EDGE_MIN` | 0.12 | **0.15** | Ventaja mínima mayor |
| `P_FLOOR` | 0.15 | **0.20** | No entrar en colas |
| Anti-bin-perdido | (no existía) | **t0 + λ_rest > hi → PASAR** | Mismo que Elon |

### Bot TRUMP
**PENDIENTE** — código no está en este repo. Ver tareas pendientes.

## 🎯 Comportamiento actual (esperado)

Los bots ahora **NO entran** en:
- Bins con precio < 0.20 (Elon) o < 0.30 (Zelenskyy)
- Bins matemáticamente perdidos (t0 + λ_rest > hi)
- Bins sin ventaja real (p_modelo - precio < 15%)

## 📅 Plan de seguimiento (próximos 3-5 días)

### Día 1-2: validar filtros
- **Objetivo**: confirmar que los bots NO hacen tonterías
- **Métricas a observar**:
  - PASA: número de veces que el bot dice "PASAR" (debe ser mayoría)
  - APOSTAR: si entra en algún bin, **verificar manualmente** que la lógica tiene sentido
  - PnL: comparar con días anteriores
- **Acción si todo PASAR**: los filtros son correctos
- **Acción si APOSTAR en bin que no debería**: revisar lógica

### Día 3-4: afinar umbrales
- Si en 2 días seguidos dice "PASAR" para todo → considerar relajar
- **Candidatos a relajar** (en orden de agresividad):
  1. `PRECIO_MAX`: 0.20 → 0.15 (Elon), 0.30 → 0.20 (Zelenskyy)
  2. `CUOTA_MINIMA`: 5.00 → 4.00 (Elon)
  3. `EDGE_MIN`: 0.15 → 0.12 (Zelenskyy)
- **Acción si encuentra operación y PIERDE**: volver a endurecer

### Día 5: revisión
- ¿Cuántas operaciones se abrieron en 5 días?
- ¿Cuántas se ganaron vs perdieron?
- ¿Hay mercados con precios > 0.20 donde el bot debería estar entrando?

## 🛠️ Scripts de monitoreo (en `scripts_despliegue/`)

| Script | Función | Frecuencia |
|---|---|---|
| `diag_estadisticas_3bots.sh` | Resumen de PnL, posiciones, win rate | Diaria |
| `test_senal_vivo_detalle.sh` | Ver el veredicto por bin (con filtros nuevos) | Diaria |
| `dump_senal.sh` | Dump sin filtro ENTRADA_MAX_H para diagnóstico | Cuando hay dudas |
| `check_3bots.sh` | Servicios, posiciones CLOB, logs | Diaria |

## 🚨 TAREAS PENDIENTES

### 1. Investigar bot de TRUMP
**Por qué**: el bot de Trump lleva semanas sin abrir operaciones
**Síntoma**: `poly-trump : active` pero sin logs `poly-trump.log`
**Causa probable**:
- Cuotas mínimas del mercado Trump son muy bajas (todos los bins a 0.0005-0.01)
- El filtro `cuota ≥ 3.00` (precio ≤ 0.33) bloquea todos
- O el bot no encuentra mercados activos
**Acción cuando se reanude**:
- Pedir al user la ruta del código del bot de Trump (no está en este repo)
- O leer los logs `poly-fantasmas-trump.log` y `poly-salud-trump.log`
- Aplicar los mismos filtros (PRECIO_MAX, anti-bin-perdido) si están en su `senal.py`

### 2. Monitorear bots nuevos (próximas 24-48h)
- Verificar que `poly-elon`, `poly-elon-semanal`, `poly-elon-mensual`, `poly-zelenskyy` siguen activos
- Comprobar que NO están abriendo operaciones absurdas

### 3. Verificar el mercado 4-11 sept (cierra 11 sept)
- El bot cerró la posición YES 120-139 (perdiendo)
- Verificar que el script de cierre automático no dejó órdenes abiertas
- Limpiar `posicion.json` si es necesario

### 4. Evaluar impacto en bankroll
- Calcular pérdida total del periodo
- Decidir si reducir bankroll por bot o parar hasta que se recupere

## 📊 Métricas de éxito (criterios para considerar filtros correctos)

| Métrica | Valor aceptable |
|---|---|
| % de APOSTAR vs PASAR | 5-15% de APOSTAR (la mayoría PASAR) |
| Win rate (si hay apuestas) | > 50% |
| PnL medio por apuesta | > 0 |
| Operaciones absurdas (precio<0.05) | 0 |
| Operaciones en bin perdido | 0 |

## 🔗 Referencias

- **Repo**: https://github.com/lamegawi/bots-backup (rama `arena/01a058fe-bots-backup`)
- **HEAD actual**: `d57d2f6d`
- **Cambios en `senal.py`** (Elon y Zelenskyy): líneas con comentario `10/09`
- **Cambios en `senal_vivo.py`**: filtro `t0 + lam_rest > hi → PASAR` y `PRECIO_MAX`
- **Logs en diag-public**: carpeta `diag_hetzner/` con prefijo `senal_detalle_` o `dump_senal_`

## 📞 Para retomar

Cuando vuelvas a mirar esto:
1. Ejecuta `bash scripts_despliegue/diag_estadisticas_3bots.sh` desde Hetzner
2. Lee el log publicado en diag-public
3. Compara con este plan
4. Ajusta si es necesario

## 🗓️ Próximas acciones inmediatas (hoy/mañana)

1. **HOY**: validar que bots están activos y sin operaciones absurdas
2. **MAÑANA**: revisar primer análisis con datos reales
3. **EN 3 DÍAS**: evaluar si los filtros necesitan ajuste
4. **CUANDO TOQUE**: investigar bot de Trump (ruta código + logs)
