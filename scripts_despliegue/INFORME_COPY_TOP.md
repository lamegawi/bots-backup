# Copy-trading de los TOP de Polymarket — estudio con datos reales
**12-sep-2026 ~00:20 Madrid · medido sobre la API pública, no sobre suposiciones**

## 0. Lo que hay hoy en el bot
El botón **🏆 Top** (`cmd_top`) es una **lista fija escrita a mano** en el código:

```
1. pleaseplease123 +$1.0M   2. ferrariChampions2026 +$791K   3. balthazar +$534K …
```

No llama a ninguna API y **no se corresponde con la realidad**. El top real de las
últimas 24 h (API oficial `lb-api.polymarket.com/profit?window=1d`) es
`ripley86alien +$1.084M`, `00gringo00 +$918K`, `Diabolical-Prize +$789K`…
El histórico (`window=all`) lo encabeza `swisstony +$23.6M`. O sea: el botón
además de estático está **desactualizado/inventado**. Arreglarlo es trivial.

En el bot **no queda maquinaria de copy-trading**: sólo el nombre heredado
`trades_copiados` para las abiertas. Sí sigue viva la vía CLOB de línea suelta
(`ejecutar_trade`, era v10), desactivada en AUTO, que es la que haría falta.

## 1. ¿Se puede vigilar a un trader? Sí
- `lb-api.polymarket.com/profit?window={1d,7d,30d,all}&limit=N` → ranking con
  **`proxyWallet`** (la dirección que hay que vigilar), nombre y beneficio.
  También `/volume`. Ventanas `1m`, `6m`, `1h` → 400.
- `data-api.polymarket.com/activity?user=<wallet>&type=TRADE` → sus fills con
  `timestamp`, `side`, `price`, `size`, `usdcSize`, `asset` (token_id),
  `conditionId`, `title`, `slug`, `transactionHash`.
- **Retraso medido**: el fill más reciente de la muestra tenía **5.7 min** y su
  hora on-chain (RPC Polygon) coincidía al décimo de minuto ⇒ data-api publica
  en cuanto ocurre. Nuestro retraso real sería el **intervalo de sondeo** (1-2 min).

## 2. ¿Sería rentable? Tres mediciones, y la buena noticia se cae

### A) Muestra "dentro" (los top del día, sus fills de ayer, mercados ya resueltos, $5/fill)
| Selección | Fills | Acierto | PnL | ROI |
|---|---|---|---|---|
| todas sus compras | 874 | 68.4% | **+$1.656,73** | **+37.9%** |
| sólo cuota 1.20-2.50 (tu filtro) | 768 | 68.4% | +$1.163,19 | +30.3% |
| lo anterior con tope de 10 ops/día | 10 | 0.0% | −$50,00 | −100% |

**Esto es trampa**: están en la lista *porque* ganaron ayer. Es mirar el pasado.

### B) Fuera de muestra (lo que importa): top **histórico** y top **30d**, sólo sus fills de las últimas 48 h
- **Top histórico (`window=all`)**: 9 de 10 están **inactivos** (swisstony, Theo4,
  Fredi9999, kch123, mintblade…). El único activo, **RN1 (+$13.3M)**: 127 fills
  resueltos · acierto 45.7% · **−$309,71 · ROI −48.8%**.
- **Top 30d**: 1.731 fills · acierto 52.5% · **+$1.157 · ROI +13.4%**… con una
  dispersión enorme:

| Trader (top 30d) | Fills resueltos | Acierto | ROI con $5/fill |
|---|---|---|---|
| Diabolical-Prize | 422 | 99.8% | **+130.6%** (+$2.755) |
| ripley86alien | 40 | 100% | +113.1% (+$226) |
| balthazar | 58 | 25.9% | +102.7% (+$298) · gana con cuotas altas |
| totoro3miyazaki | 17 | 100% | +94.7% (+$81) |
| 00gringo00 | 116 | 100% | +81.7% (+$474) |
| BreakTheBank | 424 | 51.2% | −3.2% (−$67) |
| TheReturnOfDarthMaul | 0 | — | sin resolver aún |
| 0x2c335066… | 465 | 17.8% | **−71.6% (−$1.664)** |
| pleaseplease123 | 189 | 0.0% | **−100% (−$945)** |

⇒ **"Empezar por el primero, el que más ha ganado" es justo la regla mala**: el
#1 de una ventana suele ser el perdedor de la siguiente (el top-1 histórico activo
da −48.8%; `pleaseplease123`, que aparece en tu botón 🏆, ha hecho −100% en 48 h).
El agregado sale positivo sólo porque 3-4 cuentas lo sostienen.

### C) ¿Cuánto cuesta llegar tarde? (precio minuto a minuto del CLOB tras su compra)
24 fills ya resueltos de los tres mejores, `prices-history` con fidelity=1:

| Retraso al copiar | 1 min | 3 min | 5 min | 10 min | 20 min | 30 min |
|---|---|---|---|---|---|---|
| Precio vs el suyo | −0.6 pts | −0.7 | −0.2 | −0.4 | −0.6 | −1.4 pts |
| ROI resultante | +97.5% | +97.9% | +95.7% | +96.4% | +98.2% | +102.1% |

En **deporte el mercado no se mueve al instante**: se puede entrar casi al mismo
precio minutos después (muestra pequeña y todos ganadores, ojo). En cambio, en el
conjunto de mercados aún vivos (367 fills) el mid actual está **+4.2% de media**
(+1.0% mediana) por encima de su precio y **248/367 subieron** ⇒ donde sí hay
movimiento, copiar cuesta ~1 punto y recorta ~$1 de beneficio por fill ganador.

## 3. Qué compran (y cómo encajaría con tus reglas)
- **59% deporte**, 41% política/cripto/otros.
- **88% caen dentro de tu rango de cuota 1.20-2.50** ✓ · precio mediano 0.550 (cuota 1.82).
- Tamaño mediano **$91** por fill (tú $5-10) ⇒ el tamaño no es problema de liquidez.
- **21 compras por mercado** (1.241 fills en 59 mercados): **escalan** la posición.
  Copiar fill a fill reventaría tu tope de 10 ops/día en un solo mercado ⇒ hay que
  **agregar por mercado** (una posición por mercado, con tope propio).
- **Ventas ≈ 0** en casi todos (408/0, 500/0, 500/0): mantienen hasta resolución ⇒
  **no hace falta copiar salidas**; la auditoría/curación/cierre 🔒 que ya tienes
  sirve. Excepción: `ArmageddonRewardsBilly` (213 compras / 287 ventas en 237
  mercados, mediana $29) es **market maker/arbitrajista** ⇒ copiar sólo sus compras
  sería catastrófico. Hay que **excluir** perfiles con ratio ventas/compras alto.
- **Choca con una regla tuya**: copiar es **línea suelta en el CLOB**, no combo
  multi-leg por RFQ. Necesitaría una vía nueva (la técnica ya existe: `ejecutar_trade`).
- **Bankroll**: 3 bots comparten wallet y tu regla es **no dividirlo nunca** ⇒ el
  copy-trading necesita un tope diario propio y explícito, o compartir el de 10.

## 4. Recomendación
**FASE 1 — en papel, sin dinero (v12.9).** El bot vigila el ranking real y los
fills de las wallets elegidas cada 1-2 min, aplica tus filtros y **registra lo que
habría comprado al precio realmente disponible en ese momento** (mid/ask del CLOB,
no el precio de él). La auditoría ya existente los resuelve. En ~7 días tendremos
el **ROI prospectivo por trader** (no el de ayer, que es el que engaña).
Además: botón 🏆 Top con la lista REAL y ventana elegible (1d/7d/30d/all).

**FASE 2 — sólo si la Fase 1 da ventaja real.** Dinero de verdad: $5 por posición
agregada por mercado, tope diario propio, kill-switch, y excluyendo
automáticamente al trader que pierda (regla de corte objetiva, no a ojo).

**Lo que NO recomiendo**: copiar ya, a ciegas, "desde el primero". Los datos dicen
que esa regla concreta habría dado −48.8% (top histórico) y −100% (pleaseplease123).

## 5. Ficheros de este estudio
- `estudio_copy_top.py` — mediciones A, B (parcial) y C + perfil de qué compran.
- Datos crudos de la pasada: `/tmp/top1d.json`, `/tmp/fills_top.json`,
  `/tmp/estudio_copy_top.json` (volátiles; los números importantes están arriba).
