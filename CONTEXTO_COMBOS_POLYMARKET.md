# CONTEXTO COMPLETO: Bot de Combos de Polymarket

## 📋 RESUMEN

Bot de Telegram que opera **Combos (parlays) de Polymarket** automáticamente. **OPERATIVO**: el 7 sept 2026 la v10.9 ejecutó el primer trade real vía CLOB (Cagliari, `success:true`). PERO se descubrió que operaba **LEGS SUELTOS** (el endpoint `combo-markets` es un catálogo de piernas, NO combos formados) y **sin deduplicación** (repitió Cagliari 4× = $20, confirmado en data-api). **v11.0**: combos REALES de 2-3 legs vía Requester API RFQ oficial + deduplicación + tope diario + `/testcombo` (gratis) + `/fills`. 🏆 **PRIMER COMBO REAL CONFIRMADO ON-CHAIN**: 8 sept 14:06:59 UTC — CS2 G2-Astralis Map1 (0.61) + WTA Sabalenka-Noskova (0.71), cuota real 1.71, $5.00, 8.38 shares, tx `0x23a0de4decb5b79b81a1900f`. **v11.1**: botones ⏱ 5/10/20/30/60 min en el teclado fijo para elegir el intervalo entre pasadas AUTO (persistido en estado, efecto inmediato). **v11.2**: pre-check de saldo CLOB (`/balance-allowance`) antes de firmar + reintento único idempotente del accept ante 503/`PRE_EXECUTION_BALANCE_RESERVATION_FAILED (v11.2)` + aviso 💸 por Telegram. **v11.3 (ANTI-DUPLICIDAD)**: tras el incidente de las 14:15 (dos pasadas concurrentes —la del auto_loop y un hilo de `/start`— eligieron y ejecutaron el MISMO combo: 2×$5), ahora hay un ÚNICO ejecutor de pasadas (auto_loop con lock), `/start` y 🟢 solo reprograman `NEXT_PASADA_TS`, y la huella del combo se RESERVA en estado antes de crear el RFQ (se libera solo si el intento falla terminalmente). **v11.4**: HORARIO PERSISTENTE — `proximo_paso_ts` y `chat_id` se guardan en estado; los reinicios/despliegues respetan la próxima pasada programada y ya NO provocan pasada inmediata (bug reportado: 'le di a 30 min y a los 5 min otra pasada' → causa: cada reinicio ponía NEXT_PASADA_TS=0). **v11.5**: PANEL DE OPERACIONES EN VIVO — 📋/📂/✅ sincronizan contra `clob.polymarket.com/markets/<cid>` (público): las resueltas pasan de ABIERTAS a CERRADAS con 🟢/🔴 y PnL exacto; los combos se resuelven POR LEGS (el token combo da 404 en CLOB) con cierre temprano si un leg pierde; cada abierta muestra 🏁 hora de fin (Madrid, max endDate de legs); sync también al arrancar; fallback gamma por slug. **v11.6 (petición user)**: 📋 Trades = SOLO INFORMATIVO — top 1-10 del catálogo por VOLUMEN EN $ (mayor primero) dentro del rango de cuota; las operaciones viven únicamente en 📂 Abiertas / ✅ Cerradas; registros basura (sin pregunta/stake) filtrados de la vista. **v11.7**: el catálogo `combo-markets` son LEGS sueltas y la v11.6 las mostraba crudas (user: 'no son combos, son líneas únicas') → `generar_combos_catalogo()` construye COMBOS CANDIDATOS reales (2-3 legs, eventos distintos, cuota est. en rango, filtros precio/volumen/pending) con la misma lógica de selección del bot pero sin estado, y 📋 Trades muestra el top-10 por volumen con los legs desglosados y nota 'cuota estimada, la real la da el RFQ'. **v11.8 (petición user)**: cada combo del catálogo muestra su PROBABILIDAD DE ACIERTO (producto de precios de legs ≈ 1/cuota, etiqueta alta 🟢 ≥65% / media 🟡 ≥50% / baja 🔴) y un BOTÓN INLINE ▶️ por combo que lo ejecuta en Polymarket al instante (RFQ real, $5): hilo propio serializado con PASADA_LOCK, check anti-duplicados dentro del lock, catálogo cacheado por hash8 de los tokens (caduca a 1h → alerta 'pulsa 📋 otra vez'), callback_query respondido con answerCallbackQuery. El botón manual NO está limitado por MAX_COMBOS_DIA (decisión explícita del user) pero SÍ por la deduplicación. **v11.9 (petición user: ampliar cuotas)**: FRANJA EXTENDIDA 🚀 — cuota estimada (2.5, 3.0] solo si TODOS los legs p≥0.70, máx 2/día, cuota real aceptada hasta 3.2, etiquetada en registro/historial/paneles. NOTA MATEMÁTICA: el user eligió p≥0.75 pero con 0.75 el techo de 3 legs es 1/0.75³=2.37 (<2.5 → la franja no existiría); se implementó 0.70 (0.70³→2.92) y se le explicó. PRIORIDAD: la extendida va PRIMERO mientras haya cupo (si no, sus mismos legs formarían siempre un par base ~1.9-2.0 y la franja nunca saldría); fallidas no consumen cupo. Constantes: CUOTA_MAX_EXT=3.0, CUOTA_REAL_MAX_EXT=3.2, LEG_P_MIN_EXT=0.70, MAX_EXT_DIA=2. **v12.0 (petición user)**: TRES FRANJAS INDEPENDIENTES — 🤖 BASE (1.2-2.5) es la ÚNICA automática (tope 6/día; seleccionar_combo vuelve a devolver solo base); 🚀 EXTENDIDA (2.5-3.0) y 💥 SÚPER (cuota 5-15, 3-5 legs, p≥0.55, real aceptada 3.5-18) son SOLO MANUALES vía botón, con cupos propios (2+2/día) que NO consumen el tope AUTO. 📋 Trades: un mensaje por combo con SU botón ▶️ debajo (Telegram no intercala botones en un mensaje); nuevo botón de teclado 💥 SúperCombos (top 10 informativo, prefijo callback 'sp:'); estadísticas y ✅ Cerradas con subtotales por franja (franja_of compatible con registros antiguos). Constantes: SUPER_CUOTA_MIN/MAX=5/15, SUPER_LEGS=(3,5), SUPER_P_MIN=0.55, SUPER_POOL_N=20, SUPER_REAL_MIN/MAX=3.5/18, MAX_SUPER_DIA=2. **v12.1 (petición user)**: 📂 ABIERTAS sin duplicados — fills repetidos de la misma apuesta/conjunta se agrupan en UNA línea (×N, stake/shares totales, clave = huella de legs o real_token); títulos enteros (160 chars, legs 120); por posición: 📈 precio actual (midpoint CLOB público, cache 60s; combo = producto de mids de legs), probabilidad viva %, valor vs pago, y consejo (💰 cerrar si valor ≥90% del pago / 🔴 muy caída si ≤55% del stake / 🟢 mantener). Smoke test real OK (Seyboth Wild mid 0.535). **v12.2 (petición user)**: STAKE DINÁMICO $5-10 + TOPE DIARIO CONFIGURABLE CON PIN — (1) el bot decide la apuesta entre $5 y $10 según la CUOTA (base = 5 + 6/cuota: 1.2⇒$10 · 2.0⇒$8 · 2.5⇒$7.4 · 5⇒$6.2) y CÓMO VA LA COMBINADA (ventaja real = precio implícito de los legs menos precio RFQ; suma 25% de la ventaja; si el RFQ sale ≥0.5% PEOR que el mercado, AUTO NO acepta —el botón manual siempre opera, mínimo $5—); el stake se pide al RFQ con la base por cuota estimada y se REAJUSTA tras la cotización con la cuota real (log 'stake AUTO ajustado'). Botones de teclado 💵 Stake AUTO / 💵 Stake $5 (fuera $1/$2 —suelo $5—), menú inline st:menu/st:auto/st:fijo, /stake auto|N (fijo $5-50, persiste en estado stake_mode+stake; FIJO usa estado.stake). (2) 🔢 MÁX OPS/DÍA: botón de teclado + menú mx: con 5/10/20/30/50 (✅ en el vigente); el tope cuenta TODAS las ops pagadas del día (filled/pendiente, todas las franjas — ops_pagadas_hoy) y lo respetan seleccionar_combo (AUTO) y lanzar_combo_manual (manuales); desde 10 exige CÓDIGO PIN de 4 cifras: teclado numérico inline (pn:0-9, ⌫, 👁 ver código, ❌ cancelar) o texto plano, progreso (n/4), PIN generado una vez con random y guardado en /opt/polymarket/codigo_pin.txt chmod 600 (override env POLY_PIN_OPS), persiste max_ops_dia en estado. (3) TÍTULOS ENTEROS: ABIERTAS 240 chars (legs 160), CERRADAS 240 (antes 46 con '…' — de ahí los títulos cortados que veía el user), y enviar_largo() parte paneles >3900 chars en varios mensajes (Telegram corta a 4096). Tests sandbox completos OK (fórmula + 4000 aleatorios: manual siempre [5,10]; PIN flujos bueno/malo/cancelar/borrar; integración RFQ: AUTO 8.59→ajuste 10.0 con RFQ mejor, skip $0 sin accept con RFQ peor, FIJO/forzado respetados; tope bloquea AUTO y manual; chunking 12 ops → 2 mensajes ≤4096). **v12.3 (petición user)**: (1) **AUTO SOLO CON PROBABILIDAD SUFICIENTE** — el user pidió que AUTO opere "solo y exclusivamente probabilidad alta; si no, se descarta y se pasa a la siguiente". Se implementaron 3 niveles (botón 🎯 Prob AUTO + `/prob`, persistido en `prob_min_auto`): **alta ≥65% (cuota ≤1.54)** · **media-alta ≥60% (≤1.67, NIVEL ELEGIDO por el user: "pasarlo a media-alta")** · **media+ ≥50% (≤2.00)**. El filtro va dentro del bucle de candidatos de `seleccionar_combo` (`if prod < _pmin: descartados_prob += 1; continue`) → descarta y sigue con el siguiente; si ninguno vale, log "N candidato(s) descartados por probabilidad". `etiqueta_prob` gana el nivel "media-alta 🟢". MATEMÁTICA COMUNICADA: prob = 1/cuota, así que exigir ≥65% limita la cuota a ≤1.54 (y con el suelo CUOTA_MIN=1.20 la ventana AUTO queda 1.20-1.54); por eso se eligió media-alta. El filtro NO afecta a 🚀/💥 (manuales). (2) **ESTADO A LA DERECHA** en 📂 Abiertas: `render_grupo(g, num)` numera cada posición (#1, #2…) y añade al final de cada línea ✅ (terminada y positiva) / ❌ (perdida) / ⏳ (en juego), usando `resolver_operacion` (título y cada leg); leyenda al pie. (3) **🔒 CERRAR POSICIÓN REAL** — un botón 🔒 por posición debajo del panel (cache `ABIERTAS_CACHE` h8→clave_grupo, caduca 1h): **combos** vía RFQ con `direction="SELL"` (nuevo parámetro de `crear_rfq`) + orden Exchange v3 `side=1` (nuevo parámetro de `firmar_orden_v3`); **simples** vía `vender_clob()` nuevo (SDK `OrderArgs(side="SELL")`, precio = mid − 1 tick). Notional de venta = shares_totales × mid vivo. Guarda anti-regalo: si el precio de venta implícito < 60% del mid → no vende y avisa. `dry_run` en AMBAS ramas (`/testcerrar N` = cotización sin vender, $0). Al cerrar: `archivar_cierre` mueve TODAS las fills del grupo a historial repartiendo lo recibido **proporcionalmente a las shares** (PnL por fill = su parte − su stake; la suma cuadra con el PnL conjunto y 📊 Stats no cuenta doble), con `cerrada_manual`, `motivo_cierre` (cerrada_rfq_sell/cerrada_clob_sell), `neto_recibido`, `cerrada_en_grupo`, `tx_cierre`. También `/cerrar N` (exige número, anti-accidente). Cierre serializado con PASADA_LOCK. VERIFICADO en sandbox: body RFQ SELL exacto + firma L2 HMAC(ts+POST+path+body) correcta; EIP-712 side=1 firma válida y recuperable al signer; flujo completo (2 fills agrupados → 1 venta → PnL −9.85 repartido −4.92/−4.93, stats −9.85); dry-run no vende; guarda rechaza venta a 0.095/sh con mid 0.36; NO se puede probar contra la API real sin dinero → estrenar con `/testcerrar`. **DESPLEGADA Y VERIFICADA 8-sep 20:37 UTC** (commit del bot `f21c4627`, rama HEAD `a0e4121`, log diag-public `combos_update_v106_20260908_203717.log`): 144528 bytes, `POLY COMBOS BOT v12.3`, servicio active (running) 20:37:20 UTC, arranque con **`stake=AUTO · max ops/día=6 · prob AUTO ≥60%`**, `Test proxy: 200`, `v12.3 iniciado`, sin errores. Pendiente de probar por el user: 🎯 Prob AUTO, iconos ✅/❌/⏳ en 📂 y —sobre todo— `/testcerrar 1` antes del primer cierre real. **v12.4 (petición user)**: **CÓDIGO PIN FIJO** — el user quiere que el código que confirma los topes ≥10 ops/día sea uno elegido por él (constante `PIN_FIJO_OPS`, 4 cifras) y no el aleatorio de la v12.2: `codigo_pin()` ahora devuelve `POLY_PIN_OPS` (env, si son 4 cifras) y si no `PIN_FIJO_OPS`; **ya NO genera ni lee ni escribe** `/opt/polymarket/codigo_pin.txt` (ese archivo de la v12.2 queda sin efecto y se puede borrar; si existe con otro código, manda el fijo). El flujo es el mismo de la v12.2 y lo exige el user explícitamente: 🔢 Máx ops/día → elegir 10/20/30/50 → el bot **saca el teclado numérico** (1-9, fila `👁 Código | 0 | ⌫ Borrar`, `❌ Cancelar`; callbacks `pn:<d|v|b|x>`) y también vale escribir las 4 cifras como texto (el 0 inicial funciona); bajar a 5 NO pide código. **SEGURIDAD: el PIN nunca se escribe en `log()`** (los logs se publican en diag-public, que es público) — la línea de arranque solo dice `PIN ops fijo (4 cifras)`; sí se puede ver en el chat privado con 👁 (`mxp:v`/`pn:v`). ⚠️ El repo `lamegawi/bots-backup` es PÚBLICO, así que el código fijo es legible en el fuente; si el user quiere que sea secreto, la vía es `Environment=POLY_PIN_OPS=xxxx` en la unit de systemd (tiene prioridad) y dejar otro valor por defecto en el código. Tests sandbox OK: PIN fijo, override env (y env inválido ignorado), teclado por botones y por texto, PIN malo no cambia el tope y reinicia las cifras, ⌫ borra, ❌ cancela, persistencia en estado, archivo viejo ignorado, y ninguna fuga del PIN al log. **DESPLEGADA Y VERIFICADA 9-sep 16:21 UTC** (`ef9d7912`, log `combos_update_v106_20260909_162114.log`): arranque con `PIN ops fijo (4 cifras)`, servicio active, proxy 200, md5 del servidor idéntico al de GitHub. **v12.5 (petición user vía ask_user)**: **REINTENTO ÚNICO CON $5 ANTE `SIZE_TOO_LARGE`** — cuando el maker del RFQ responde que no cubre ese tamaño, el bot vuelve a pedir cotización UNA vez con el stake mínimo ($5) si el pedido inicial era mayor (si ya iba al mínimo, no reintenta: volvería a fallar); avisa por Telegram (🔁 *El RFQ rechazó el tamaño* … Reintento único con $5.00) y lo registra en el log. La contabilidad NO se resiente porque `stake_dolares` se guarda con `total_required_e6` del quote (dinero real), no con la variable `stake`. **NO se aplica al cierre (SELL)**: vender solo una parte dejaría el resto de la posición colgando y sin archivar — ahí se avisa y decide el user. `NO_QUOTES` tampoco se reintenta (con menos tamaño no aparecería un maker que no estaba). Motivo: el 9-sep el RFQ rechazó 3 intentos (2× `SIZE_TOO_LARGE` 12:02/12:22 + 1× `NO_QUOTES` 12:12) y el bot se limitaba a liberar el combo y pasar de largo. Tests sandbox 7 bloques OK (fill tras reintento con stake real $5, sin reintento al mínimo, doble fallo libera huella, NO_QUOTES sin reintento, flujo normal intacto, SELL sin reintento y posición abierta, regresión PIN/prob/stake). **v12.6/v12.7 (denuncia user: "las cerradas no son reales")**: RESULTADOS REALES + AUTO-CURACIÓN — el catálogo de combos devuelve `position_ids` que no son los `token_id` del CLOB, así que la comparación con el token ganador nunca acertaba y cada leg que cerraba archivaba el combo como PERDIDA (−stake); ahora el ganador se lee por OUTCOME/índice 0, un mercado cerrado sin ganador declarado es ⏳ PENDIENTE y manda la verdad real (cobros REDEEM de la wallet en data-api + saldo on-chain del token de combo en el ERC1155 `0x006f…efef`, que NO es el CTF `0x4D97…6045`). `reauditar_estado()` corre SOLA al arrancar (~25 s) y cada 4 h: reabre las mal archivadas, corrige resultado/PnL, cierra las ya resueltas y no toca los cierres manuales; `/reauditar [seco]` a mano. Auditoría real de 77 combos: **PnL realizado +$231.79** en la era del bot (25 ganadas cobradas, 33 aún en cartera) frente al "−$18.37" que reportaba el panel.

## 🎯 OBJETIVO

El bot debe:
1. Leer el **catálogo de LEGS** (piernas combinables) del endpoint público `https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets` y CONSTRUIR combos reales de 2-3 legs vía **Requester API RFQ** (`combos-rfq-gateway-requester-api.polymarket.com`)
2. Filtrar **solo deportes** (fútbol, MLB, NBA, UFC, tennis, esports, etc.) por tags
3. Filtrar por **cuota 1.20-2.50** (multiplicación de las probs de cada leg)
4. Resolver el **token_id real** tradable (no el `position_id` del endpoint combos, que NO es tradable)
5. Firmar la orden con `py_clob_client_v2` usando solo `POLY_PRIVATE_KEY` (deriva API creds automáticamente, como hace el bot de Elon)
6. Enviar la orden firmada via **HTTP POST directo con proxy** (porque el SDK no respeta env vars de proxy)

## 🏗️ ARQUITECTURA

```
/home/user/bots-backup/
├── scripts_despliegue/
│   ├── poly_combos_bot.py         # BOT PRINCIPAL (v10.7)
│   ├── actualizar_v106.sh         # Actualizador con HASH FIJO
│   ├── inline_actualizar.sh       # Actualizador inline
│   ├── test_salud.sh              # Verifica IP via proxy
│   ├── ver_v106.sh                # Lee log en vivo
│   ├── buscar_creds_elon.sh       # Busca credenciales
│   ├── diff_creds.sh              # Compara credenciales
│   ├── ver_elon.sh                # Ver estado bot Elon
│   └── [otros scripts de diag]
├── poly/codigo/                   # Códigos del bot de Elon (referencia)
│   ├── bot-polymarket-elon*/      # Bots de Elon funcionando
│   ├── proxy_pc.py                # Proxy HTTP en PC
│   └── check_salud.py             # Verifica IP via proxy
└── diag_hetzner/                  # Logs publicados
```

## 🖥️ INFRAESTRUCTURA

### Hetzner (VPS donde corre el bot)
- IP: `46.225.146.21`
- SSH: `ssh root@46.225.146.21`
- Wallet: `0xb0e1197098e6d427c01720f1631cad24ce740fa0`
- Servicio systemd: `poly-combos-bot.service`
- Bot instalado en: `/opt/polymarket/poly_combos_bot.py`
- Estado: `/opt/polymarket/combos_estado.json`
- Env vars: `/etc/polymarket.env`
- Token Telegram: `/root/poly_combos_token.txt`
- Log: `/var/log/poly-combos-bot.log`

### PC del usuario (para proxy)
- IP Tailscale: `100.83.57.99` (hostname: `ferpc`)
- IP pública: `85.85.41.76`
- Proxy HTTP: `http://100.83.57.99:8888` (sirve HTTP y HTTPS via CONNECT)
- Script: `/home/user/bots-backup/poly/codigo/proxy_pc.py`
- ⚠️ CRÍTICO: PC debe estar ENCENDIDO para que los trades se ejecuten (el proxy es obligatorio para evitar 403 geoblock)

### Telegram
- Bot: `poly_combos_bot`
- Token: `8724334813:AAGV2-RBeoSDeIBS4Lv0s_bD9jAyuM-QMUY`
- Chat ID: `250818720`
- Funcionalidades: `/start`, `/trades`, `/saldo`, `/abiertas`, `/cerradas`, `/stats`, `/top`, `/status`, `/auto`, `/stake`, botones inline

## 🔑 CREDENCIALES

El bot usa `/etc/polymarket.env` que contiene:
- `POLY_PRIVATE_KEY` (66 chars) ← **CRÍTICO, único que necesita**
- `POLY_WALLET_ADDRESS` (42 chars) ← wallet de Polymarket
- `POLY_RELAYER_API_KEY` y `POLY_RELAYER_API_KEY_ADDRESS`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `HTTP_PROXY=http://100.83.57.99:8888`, `HTTPS_PROXY`, `ALL_PROXY`

**NO tiene `POLY_API_KEY` ni `POLY_API_SECRET`** — el bot debe **derivar** las creds con `client.derive_api_key()` usando la private key (igual que hace el bot de Elon).

## 🐛 BUGS SOLUCIONADOS (HISTORIAL)

### v7 → v8: filtro de deportes
- **Problema**: `tags=[]` y `category=""` están vacíos en gamma-api para markets individuales
- **Fix**: filtrar por **TÍTULO** con keywords (MLB, UFC, NFL, NBA, etc.)
- **Resultado**: 500 markets revisados, todos de política, **0 deportes**

### v8 → v9: endpoint de Combos
- **Descubrimiento**: Polymarket tiene **Combos (parlays)** con 2-10 legs
- **Endpoint correcto**: `https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets` (NO `clob.polymarket.com`)
- **Resultado**: 363 combos de deportes en 500 totales

### v9 → v10: token real tradable
- **Problema**: `position_ids[0]` del endpoint combos da **404** en CLOB (es un índice, no token_id)
- **Solución**: usar `condition_id` para llamar `clob.polymarket.com/markets/{condition_id}` que devuelve `tokens[0].token_id` (78 dígitos, SÍ tradable)
- **Resultado**: token se resuelve, precio se lee correctamente

### v10 → v10.1: stake mínimo
- **Problema**: stake=$2 da `size < 5 shares` (mínimo de CLOB)
- **Solución**: stake=$5

### v10.1 → v10.6: HTTP POST con proxy
- **Problema**: `py_clob_client_v2` se conecta DIRECTO desde Hetzner (IP alemana) → 403 "Trading restricted in your region"
- **Solución**: firmar orden con `client.create_order()` y enviar via `urllib` con `ProxyHandler` a `clob.polymarket.com/order`
- **Resultado**: ya NO hay 403, IP de salida es la del PC

### v10.6 → v10.7: derive_api_key con private key
- **Problema**: `POLY_API_KEY` y `POLY_API_SECRET` no existen en `/etc/polymarket.env` → error `sin_credenciales`
- **Solución**: usar `client.derive_api_key()` con la private key (igual que el bot de Elon)
- **Resultado**: ✅ FUNCIONA — log 16:36 UTC: "Creds derivadas automaticamente" + orden firmada `SignedOrderV2(...)`

### v10.7 → v10.8: SignedOrderV2 no serializable
- **Problema**: `json.dumps(signed_order)` → `Object of type SignedOrderV2 is not JSON serializable`
- **Fix v10.8**: `signed_order.__dict__` — INSUFICIENTE (el problema real era otro, ver v10.9)

### v10.8 → v10.9: el SDK usa HTTPX + envelope v2 + headers L2 (FIX DEFINITIVO)
- **Investigación** (leyendo el source de `py_clob_client_v2==1.1.0`):
  1. El SDK usa **httpx**, NO requests → los monkey-patch v10.2-10.4 parcheaban la librería equivocada
  2. httpx crea su cliente **al importar el módulo**: `helpers._http_client = httpx.Client(http2=True)` → setear env vars después NO afecta al cliente ya creado
  3. `POST /order` en la API v2 NO acepta el signed order crudo: espera el envelope `{"order":{salt:int, maker, signer, tokenId, makerAmount, takerAmount, side, expiration, signatureType, timestamp, metadata, builder, signature}, "owner":api_key, "orderType":"GTC", ...}` que construye `order_to_json_v2()`
  4. Los headers L2 requieren `POLY_SIGNATURE` = base64(HMAC-SHA256(api_secret, timestamp+method+path+body_serializado_exacto)) — el POST manual v10.6-10.8 enviaba api_key/passphrase VACÍOS y sin firma HMAC → habría dado 401 aunque serializara bien
- **Solución v10.9**:
  1. `inyectar_proxy_sdk()`: reemplaza EXPLÍCITAMENTE `py_clob_client_v2.http_helpers.helpers._http_client` por `httpx.Client(http2=True, proxy=PROXY_URL)` (con fallbacks por versión de httpx)
  2. `enviar_orden()` usa `client.create_and_post_order(OrderArgs(...))` NATIVO del SDK (patrón exacto del bot de Elon) → el SDK construye envelope + headers L2 con las creds derivadas
- **Resultado**: ✅ **PRIMER TRADE REAL EJECUTADO** 7 sept 17:30:30 UTC — `SDK resp: {"success": true, "orderID": "0x60beb7ef...", "status": "delayed"}`. Verificado después en data-api: las órdenes `delayed` SÍ se llenaron.

### v10.9 → v11.0: eran LEGS sueltos + sin deduplicación (FIX ACTUAL)
- **Problema 1 (crítico)**: `/v1/rfq/combo-markets` es *"Catalog page of **combo-able** markets"* (docs oficiales) — devuelve **legs individuales**, no parlays. La v9-v10.9 compró piernas sueltas creyendo que eran combos (ej. "Will Cagliari win" solo).
- **Problema 2 (crítico)**: `auto_pasada` no consultaba el historial → **recompraba el mismo mercado cada 5 min** (4 fills Cagliari ~$20 total, confirmado via `data-api.polymarket.com/trades?user=<wallet>`).
- **Solución v11.0 — Requester API RFQ oficial** (docs.polymarket.com/trading/combos/requesters):
  1. `POST {gateway}/v1/requester/rfq/requests` con `leg_position_ids` (2-3 YES position_ids del catálogo, = `position_ids[0]` de cada leg), `direction BUY`, `side YES`, `requested_size {unit:notional, value_e6}` → subasta entre market makers (400ms) → `quote` con `blended_price_e6`, `net_receive_e6`, `total_required_e6` (rate limit: 15 create/min)
  2. Validar **cuota real** = 1/blended en [1.20-2.50] (si no, NO aceptar — expira solo, coste $0)
  3. Firmar orden **Exchange v3** EIP-712: dominio `Polymarket CTF Exchange` v`3`, chainId 137, contrato `0xe3333700cA9d93003F00f0F71f8515005F6c00Aa`; `tokenId`=combo `yes_position_id`, `maker`=proxy wallet, `signer`=EOA, `side`=0, `signatureType`=1, `metadata`/`builder`=bytes32 cero; firma 65-byte con v∈{27,28} (eth_account)
  4. `POST .../requests/{rfq_id}/accept` con `{quote_id, signed_order}` (ventana ~5s)
  5. `GET .../requests/{rfq_id}` → poll hasta `FILLED` (con `tx_hash`) / `FAILED`/`EXPIRED`/`CANCELED`; timeout local ≠ fallo (re-consultar)
  - Headers L2 en cada llamada: `POLY_ADDRESS`(EOA signer), `POLY_API_KEY`, `POLY_PASSPHRASE`, `POLY_TIMESTAMP`, `POLY_SIGNATURE`=base64url(HMAC-SHA256(b64decode(secret), ts+METHOD+path+body_exacto)) — reutiliza `py_clob_client_v2.signing.hmac.build_hmac_signature`
- **Selección de legs**: deportes, yes_price 0.60-0.96, volumen ≥$20k, `pending=False`, fecha del slug ≥ hoy, **eventos distintos** (clave = slug hasta la fecha: `mlb-laa-bos-2026-09-07-total-8pt5` y `mlb-laa-bos-2026-09-07` son el mismo evento → no combinar), top-30 por volumen, pares preferidos sobre tríos, cuota estimada en rango
- **Deduplicación**: huella sha1 de position_ids ordenados + cooldown por leg (6h) + tope 6 combos/día + 1 combo por pasada
- **Nuevos comandos**: `/testcombo` (RFQ completo SIN aceptar, coste $0 — valida pipeline) y `/fills` (re-poll de RFQs pendientes + reconciliación data-api)
- **Testeado en sandbox**: firma EIP-712 con recovery correcto del signer, headers L2, selección live (Udinese+Zverev cuota 1.84), dedup, tope diario

## 🔧 CÓDIGO CLAVE (v10.9)

### `inyectar_proxy_sdk()` + `enviar_orden()` — v10.9 (DEFINITIVO)
```python
def inyectar_proxy_sdk(proxy_url=None):
    """El SDK usa HTTPX y crea su cliente AL IMPORTAR (helpers._http_client).
    Hay que REEMPLAZARLO explícitamente por uno con proxy (env vars no bastan)."""
    proxy_url = proxy_url or PROXY_URL  # http://100.83.57.99:8888
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ[k] = proxy_url
    import httpx
    from py_clob_client_v2.http_helpers import helpers as _hh
    # con fallbacks por versión de httpx: proxy= (>=0.26), proxies={"all://":...}, sin http2
    _hh._http_client = httpx.Client(http2=True, proxy=proxy_url)
    return True

def enviar_orden(token_id, precio, stake_dolares):
    # ... size_shares, throttle 10s, cargar_env (solo POLY_PRIVATE_KEY) ...
    proxy_ok = inyectar_proxy_sdk()
    client = ClobClient(host=HOST_CLOB, chain_id=137, key=signer, funder=wallet,
                        signature_type=int(SignatureTypeV2.POLY_PROXY))
    creds = client.derive_api_key()          # ✅ funciona con solo la private key
    client.set_api_creds(creds)
    order_args = OrderArgs(token_id=token_id, price=precio, size=size_shares, side="BUY")
    resp = client.create_and_post_order(order_args)   # NATIVO del SDK (patrón Elon)
    # El SDK construye el envelope {"order":{salt, maker, signer, tokenId, makerAmount,
    # takerAmount, side, expiration, signatureType, timestamp, metadata, builder, signature},
    # "owner": api_key, "orderType": "GTC"} y firma los headers L2
    # (POLY_SIGNATURE = base64(HMAC-SHA256(api_secret, ts+method+path+body_exacto)))
    if isinstance(resp, dict) and (resp.get("success") or resp.get("orderID")):
        return True, {"oid": resp.get("orderID"), "status": resp.get("status"), ...}
    # Errores: PolyApiException trae .status_code y .error_msg reales de la API
```

### `listar_combos()` — leer combos activos
```python
COMBOS_API = "https://combos-rfq-api.polymarket.com"

def listar_combos():
    combos = []
    cursor = ""
    while paginas < 5:  # 5 páginas = 250 combos
        url = f"{COMBOS_API}/v1/rfq/combo-markets?limit=50"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"
        status, body = http_get(url, timeout=15)
        data = json.loads(body)
        for m in data.get("markets", []):
            tags_str = " ".join(m.get("tags", [])).lower()
            if not any(t in tags_str for t in ["sport", "soccer", ...]):  # filtro deportes
                continue
            yes_price = float(m.get("outcome_prices", ["0"])[0])
            if not (0.02 <= yes_price <= 0.95):
                continue
            # guardar con condition_id
            combos.append({
                "condition_id": m.get("condition_id"),
                "question": m.get("title"),
                "yes_price": yes_price,
                "tags": m.get("tags"),
                ...
            })
    return combos
```

### `resolver_token_real()` — CRÍTICO
```python
def resolver_token_real(condition_id):
    """v10: dado el condition_id, devuelve el token_id REAL tradable."""
    url = f"{HOST_CLOB}/markets/{condition_id}"
    status, body = http_get(url, timeout=10)
    data = json.loads(body)
    if not data.get("accepting_orders") or data.get("closed"):
        return None
    tokens = data.get("tokens", [])
    yes = tokens[0]  # tokens[0] = YES
    return yes.get("token_id")
```

## 📊 ESTADO ACTUAL

- **HEAD del repo**: v11.0 (ver último commit de la rama)
- **Bot en Hetzner**: **v11.0 desplegada y OPERANDO** (8 sept 14:01:44 UTC, hash `f93ce31b`, modo AUTO, proxy 200)
- **PRIMER COMBO REAL**: 14:06:59 UTC ✅ `rfq-56e1ce29e6a77b0edd57bffd` status **CONFIRMED** tx `0x23a0de4decb5b79b81a1900f` — 2 legs (CS2 G2-Astralis Map1 p=0.61 $291k + WTA Sabalenka-Noskova p=0.71 $217k), cuota est. 2.27 → cuota REAL del quote 1.71 (blended 0.584), 8.38 shares, $5.00
- **Ojo margen MM**: el quote del market maker empeora la cuota estimada (~25% en este caso); la cuota que manda es la REAL (blended). Opcional: filtro `cuota_real >= cuota_est*0.75`
- **Posiciones legacy**: ~4 fills Cagliari ($5 c/u, se resuelve 7 sept) vía CLOB single-leg
- **PRIMER TRADE CLOB**: 17:30:30 UTC ✅ `success:true` orderID `0x60beb7ef...` status `delayed` → fill confirmado en data-api
- **Lo que se ve en el log ahora**:
  - `[TRADE] ...` → `token real resuelto` → `precio/cuota/stake`
  - `  · Creds derivadas automaticamente (proxy_sdk=OK)`
  - `  enviando orden via SDK (httpx+proxy)...`
  - `  SDK resp: {"success": true, "orderID": "0x...", "status": "delayed|live|matched"}`
  - ⚠️ En AUTO el éxito NO se loggea ni notifica a Telegram (solo `if chat_id:`) — el trade SÍ se guarda en estado (`/abiertas` lo ve). Mejora pendiente v10.9.1
  - `ERROR: throttle` = hubo otra orden <10s antes (normal: reintenta en la siguiente pasada)

## 🛠️ CÓMO CONTINUAR

### Verificar estado del bot
1. SSH: `ssh root@46.225.146.21`
2. Ver log: `tail -50 /var/log/poly-combos-bot.log`
3. O ejecutar ver_v106.sh:
   ```
   curl -sL -o /tmp/ver.sh https://raw.githubusercontent.com/lamegawi/bots-backup/8b241a50/scripts_despliegue/ver_v106.sh && bash /tmp/ver.sh
   ```
4. Leer log en diag-public: `https://github.com/lamegawi/bots-backup/tree/diag-public/diag_hetzner/`

### Actualizar el bot
1. Hacer cambios en `scripts_despliegue/poly_combos_bot.py`
2. Commit y push:
   ```bash
   cd /home/user/bots-backup
   git add scripts_despliegue/poly_combos_bot.py
   git -c user.email="lamegawi@users.noreply.github.com" -c user.name="lamegawi" commit -m "descripcion"
   git push origin arena/01a058fe-bots-backup        # SIN --force: la rama la comparte otra sesión Arena
   ```
   ⚠️ El `.git/config` del clon del sandbox es VOLÁTIL (se pierde entre turnos) y ha llegado a quedar
   apuntando a `Albina15/bots-backup`, que **no existe** (404). El repo correcto es
   **`lamegawi/bots-backup`**: `git -c remote.origin.url="https://x-access-token:<PAT>@github.com/lamegawi/bots-backup.git" push origin arena/01a058fe-bots-backup`.
   El PAT caduca/se revoca (avisa al user para que lo revoque tras el arranque) → si el push responde
   `Invalid username or token`, hace falta pedir un PAT NUEVO (fine-grained, repo lamegawi/bots-backup,
   permiso Contents: Read and write). Verificar que el push llegó con
   `curl -sI https://raw.githubusercontent.com/lamegawi/bots-backup/<HASH>/scripts_despliegue/poly_combos_bot.py` → 200.
3. Obtener HEAD: `gh api repos/lamegawi/bots-backup/commits/arena/01a058fe-bots-backup -q '.sha[:8]'`
4. Ejecutar en Hetzner:
   ```
   curl -sL -o /tmp/v.sh https://raw.githubusercontent.com/lamegawi/bots-backup/<HASH>/scripts_despliegue/actualizar_v106.sh
   sed -i 's/HASH="abe93c7e"/HASH="<NUEVO_HASH>"/' /tmp/v.sh
   bash /tmp/v.sh
   ```

### Test rápido (test_salud.sh — creado el 8 sept, ya existe en el repo)
```
ssh root@46.225.146.21
cd /opt/polymarket/scripts_despliegue
curl -sL -o test_salud.sh "https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/test_salud.sh"
bash test_salud.sh
```
Comprueba 9 bloques y **publica el informe en `diag-public/diag_hetzner/salud_combos_<TS>.log`**
(usa `/root/diag_token.txt`), así que se puede leer sin SSH:
1. servicio (`is-active`, PID, memoria) · 2. código (tamaño, md5, banner, `py_compile`,
contador de menciones v12.3/v12.4) · 3. `combos_estado.json` (max_ops_dia, prob_min_auto,
stake_mode, fills de hoy, próxima pasada) · 4. **proxy Tailscale** (IP de salida debe ser
`85.85.41.76`) · 5. APIs públicas (gamma, catálogo combos, data-api, **midpoint con un
token REAL de la wallet** — con un token inventado da 404 y sería un falso fallo; gateway
RFQ sin credenciales L2 responde 400/401/403/404/405 = vivo) · 6. wallet (posiciones y
últimos fills; **en data-api `size` son SHARES, el coste en $ = size × price**) ·
7. recursos (disco, memoria, tamaño del log) · 8. errores/tracebacks del log (el
`read operation timed out` es ruido benigno) · 9. últimas 25 líneas. Termina con
`RESULTADO: ✅ SALUD OK` o `⚠️ N FALLO(S)`.

## 📚 ENDPOINTS CLAVE

| Endpoint | URL | Uso |
|----------|-----|-----|
| Combos | `https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets` | Listar combos activos (público) |
| Market by condition_id | `https://clob.polymarket.com/markets/{condition_id}` | Obtener token_id real tradable |
| Midpoint | `https://clob.polymarket.com/midpoint?token_id={id}` | Precio actual del token |
| Order | `https://clob.polymarket.com/order` | POST con proxy (orden firmada) |
| Gamma (markets individuales) | `https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=N&offset=M` | Markets individuales (mayoría son política) |
| **RFQ Requester (v11)** | `https://combos-rfq-gateway-requester-api.polymarket.com/v1/requester/rfq/requests` | Crear/aceptar/consultar combos REALES (headers L2) |
| **Data-API trades** | `https://data-api.polymarket.com/trades?user={wallet}&limit=N` | Fills reales de la wallet (público, sin auth) |
| **Data-API positions** | `https://data-api.polymarket.com/positions?user={wallet}` | Posiciones abiertas (público) |

## ⚠️ RESTRICCIONES CRÍTICAS

- **3 bots comparten wallet** — NUNCA dividir bankroll
- **Proxy Tailscale `100.83.57.99:8888` OBLIGATORIO** para ejecutar trades
- **PC debe estar ENCENDIDO** (Tailscale activo)
- **Stake por trade**: $5.0 (mínimo 5 shares en CLOB)
- **Cuota objetivo**: 1.20-2.50
- **Wallet**: `0xb0e1197098e6d427c01720f1631cad24ce740fa0`
- **Formato 2-part sin password**: SIEMPRE `📌 Commit: <hash>` + Parte 1 (SSH) + Parte 2 (comandos)
- **User responde "Hecho"** → leer log publicado en `diag-public`
- **STANDING**: `backup_completo.py` cuando diga "haz backup"
- **STANDING**: auto-publicar log a `diag-public`
- **Modo AUTO**: ejecución 100% automática, SIN botones de aprobación

## 🐞 ERRORES CONOCIDOS A EVITAR

- ❌ **NUNCA** usar `clob.polymarket.com/v1/rfq/combo-markets` (da 404)
- ✅ USAR `combos-rfq-api.polymarket.com/v1/rfq/combo-markets`
- ❌ **NUNCA** usar `position_ids[0]` del endpoint combos (NO tradable)
- ✅ USAR `tokens[0].token_id` de `clob.polymarket.com/markets/{condition_id}`
- ❌ **NUNCA** enviar orden con POST manual de urllib: la API v2 espera el envelope de `order_to_json_v2()` + header `POLY_SIGNATURE` (HMAC sobre el body exacto) — imposible de replicar a mano con creds derivadas
- ❌ **NUNCA** monkey-patchear `requests` para el proxy: el SDK usa **httpx**
- ✅ USAR `inyectar_proxy_sdk()` (reemplaza `helpers._http_client` por `httpx.Client(proxy=...)`) + `client.create_and_post_order(OrderArgs(...))` nativo del SDK
- ❌ **NUNCA** tratar las entradas de `combo-markets` como combos: son LEGS sueltos (catálogo de combinables)
- ✅ Los combos reales se CREAN por RFQ combinando 2+ `leg_position_ids` (Requester API)
- ❌ **NUNCA** ejecutar en AUTO sin deduplicación (la v10.9 repitió Cagliari 4×)
- ✅ v11: huella de combo + cooldown por leg + tope diario + 1 combo/pasada
- ❌ **NUNCA** combinar legs del mismo evento (correlacionados; clave = slug hasta la fecha)
- ❌ **NUNCA** lanzar hilos de pasada desde `/start`/cmd_modo: con AUTO activo y una pasada en vuelo, dos hilos concurrentes leen el mismo estado y duplican el combo (incidente 14:15, 2×$5 al mismo parlay)
- ✅ v11.3: único ejecutor (auto_loop + PASADA_LOCK) + `programar_pasada_ahora()` + reserva de huella pre-RFQ
- ❌ **NUNCA** requerir `POLY_API_KEY` y `POLY_API_SECRET` (no existen)
- ✅ USAR `client.derive_api_key()` con `POLY_PRIVATE_KEY`

## 📈 MÉTRICAS DE PROGRESO

- ✅ Token de Telegram funcional
- ✅ Operaciones automatizadas via proxy (test 200 OK)
- ✅ Botones inline + ReplyKeyboard fijo
- ✅ Integración copy-trading
- ✅ Ejecución real en Polymarket CLOB
- ✅ `/trades`, `/abiertas`, `/cerradas`, `/saldo`, `/top`, `/estado`, `/start`
- ✅ `/copiar N`
- ✅ Combos automáticos, sin verificación, AUTO
- ✅ Estadísticas + historial
- ✅ Endpoint correcto de combos
- ✅ Token real tradable resuelto
- ✅ HTTP POST con proxy
- ✅ derive_api_key con private key (confirmado en log 16:36 UTC)
- ✅ v10.9: proxy inyectado en httpx del SDK + create_and_post_order nativo (fix definitivo del envío)
- ✅ **PRIMER TRADE EJECUTADO** (v10.9, CLOB single-leg — NO era combo real)
- ✅ v11.0 escrita y testeada en sandbox: combos REALES via RFQ + dedup + /testcombo + /fills
- ✅ **PRIMER COMBO REAL CONFIRMED** (v11.0 en producción, 8 sept 14:06:59 UTC, tx on-chain)
- ⏳ Pendientes/propuestas: SEMI con botones de aprobación (v11.1), filtro de margen MM, fase 2 copy-trading de combos
- 🔮 Fase 2 (propuesta user): replicar combos de grandes traders (data-api expone posiciones públicas)

## 🔗 URLs ÚTILES

- **Repo principal**: https://github.com/lamegawi/bots-backup/tree/arena/01a058fe-bots-backup
- **Logs publicados**: https://github.com/lamegawi/bots-backup/tree/diag-public/diag_hetzner
- **Polymarket CLOB docs**: https://docs.polymarket.com/
- **Polymarket Combos docs**: https://docs.polymarket.com/api-reference/combo-markets/get-combo-markets
- **py-clob-client-v2**: https://pypi.org/project/py-clob-client-v2/

## 📝 PRÓXIMOS PASOS INMEDIATOS

1. ✅ **v11.0 desplegada y AUTO activo** (8 sept 14:01-14:07): primer combo real CONFIRMED a las 14:06:59
2. ✅ `/testcombo` disponible (validación gratis sin aceptar quote)
3. ✅ `/fills` para confirmar fills (RFQ status + reconciliación data-api)
4. **Observar margen de MM**: cuota est. 2.27 → real 1.71; opcional filtro `cuota_real >= cuota_est * 0.75` para descartar quotes caros
5. ✅ **v11.1 desplegable**: botones ⏱ de intervalo (5/10/20/30/60 min) + bucle tick 5s + persistencia
6. **v11.2 propuesta**: modo SEMI = propone el combo con botones ✅/❌ y solo ejecuta con aprobación
6. **Fase 2**: replicar combos de grandes traders (posiciones públicas via data-api)
5. **Fase 2 — replicar grandes traders**: investigar posiciones en combo-tokens de top traders via data-api/leaderboard (`/positions?user=...`), detectar legs de sus combos y pedir quotes de los mismos
6. **Mejoras futuras**: stop-loss, P&L tiempo real, venta de combos (direction SELL vía RFQ), filtros de deportes más específicos

## 💬 CONVERSACIÓN RESUMIDA

- 5 sept 21:00 — User cambió estrategia: leer mercados activos en vez de copiar trades viejos
- 5 sept 22:00 — v7 implementado con gamma-api
- 5 sept 22:25 — Descubierto que tags están vacíos, fix v8 con keywords en título
- 5 sept 22:30 — User mostró screenshot: hay Combos en Polymarket
- 5 sept 23:00 — Investigado endpoint combos, encontrado `combos-rfq-api.polymarket.com`
- 5 sept 23:30 — v9 con endpoint correcto, 363 deportes encontrados
- 5 sept 23:45 — Descubierto 404 en tokens del endpoint combos
- 6 sept 00:00 — v10 con `condition_id` para resolver token real
- 6 sept 00:30 — v10.1 con stake=$5 (mínimo 5 shares)
- 6 sept 01:00 — v10.2-10.4 con monkey-patch (no funcionó)
- 7 sept 14:00 — v10.5 patrón simple (no funcionó)
- 7 sept 14:30 — v10.6 con HTTP POST directo + proxy (resolvió 403)
- 7 sept 15:00 — v10.7 con `derive_api_key` (resolvió sin_credenciales)
- 7 sept 15:30 — PENDIENTE confirmar ejecución de primer trade
- 7 sept 16:36 — Log confirma: creds derivadas OK + orden firmada OK, pero `SignedOrderV2 is not JSON serializable` → v10.8 (__dict__)
- 7 sept 16:41 — inspect falla: SignedOrderV2 NO está en clob_types (está en order_utils.model.order_data_v2)
- 7 sept ~17:15 — Análisis del source del SDK (v1.1.0): usa httpx, envelope v2 y L2 HMAC → POST manual inviable → v10.9 con inyectar_proxy_sdk() + create_and_post_order nativo
- 7 sept 17:24 — v10.9 desplegado en Hetzner (commit a6b91e5c), bot iniciado 17:24:52
- 7 sept 17:30 — 🎉 PRIMER TRADE REAL (CLOB): Cagliari cuota 1.40 stake $5, success=true, status delayed → fill confirmado
- 7 sept ~19:45 — USER DETECTA: los trades NO son combos (legs sueltos) y repitió la misma línea 4× ($20). Pone el bot en OFF
- 7 sept ~20:00 — Confirmado en data-api (fills Cagliari 17:30/17:35/17:41). Investigación: combo-markets = CATÁLOGO DE LEGS; descubierta la Requester API RFQ oficial para combos reales (quote → orden Exchange v3 → accept → FILLED con tx_hash)
- 7 sept ~20:15 — v11.0 escrita: motor RFQ + selección 2-3 legs (eventos distintos, 0.60-0.96, vol≥20k, fecha≥hoy) + dedup (huella+cooldown 6h+tope 6/día) + /testcombo + /fills. Tests sandbox OK
- 8 sept 14:01 — v11.0 desplegada en Hetzner (hash f93ce31b, modo AUTO persistido, proxy 200)
- 8 sept 14:06 — 🏆 PRIMER COMBO REAL CONFIRMADO ON-CHAIN: pasada AUTO v11 → CS2 G2-Astralis Map1 + WTA Sabalenka-Noskova → RFQ create 200 → quote cuota 1.71 → accept 200 EXECUTING → **CONFIRMED** tx 0x23a0de4decb5b79b81a1900f. Pipeline RFQ completo en producción
- 8 sept ~14:15 — v11.1 desplegada: botones ⏱ 5/10/20/30/60 min (teclado fijo); auto_loop tick 5s + NEXT_PASADA_TS; intervalo persistido y restaurado al arrancar
- 8 sept 14:12 — INCIDENTE: 2º combo (Genoa Seyboth Wild p=0.61 + RMA-Inter O/U 1.5 p=0.86) → quote cuota 1.77 OK → accept 200 pero status FAILED `PRE_EXECUTION_BALANCE_RESERVATION_FAILED` (reserva transitoria del gateway; saldo on-chain verificado: 238.62 pUSD libres en la proxy wallet vía eth_call a pUSD 0xC011a7...2DFB → NO es falta de fondos; pérdida $0 porque falló pre-ejecución)
- 8 sept 14:15 — INCIDENTE DUPLICIDAD: pasada del auto_loop + hilo de /start concurrentes → mismo combo ejecutado 2 veces (rfq-0b766b6d cuota 1.75 CONFIRMED + rfq-d2ecb6c9 cuota 1.76 CONFIRMED, 2×$5 al mismo parlay). Sin pérdida extra: es la misma posición duplicada
- 8 sept 14:15:37 — user prueba botones ⏱: `intervalo AUTO -> 30 min` persistido y restaurado tras reinicio ✓
- 8 sept 14:20 — 3er combo CONFIRMED (rfq-04cbbf8a, cuota real 1.83, tx 0x88532a44...); pre-check saldo v11.2 funcionando en log ($238.62 ≥ $5)
- 8 sept 14:23 — v11.3 desplegada (commit 58ef3164, anti-duplicidad)
- 8 sept ~14:27 — 4º combo CONFIRMED (rfq-13208683, cuota 1.62); con el fill de 14:02 (G2-Astralis BO3, $4.87, condition sintético 0x0357…) son 6 fills de combo el 8-sep = MAX_COMBOS_DIA alcanzado
- 8 sept ~15:00 — AUDITORÍA líneas de ayer (petición user): 5/5 GANADAS y redimidas → Cagliari×3 (+1.96/+1.77/+1.77), LoL IG-LGD (+2.83), SMU-FSU (+1.42) = stake $25.16 → payout $34.91 = **+$9.75**. Verificado vía data-api /trades + CLOB /markets (winner=True); los 4 combos reales de hoy siguen ABIERTOS (legs sin resolver)
- 8 sept 15:12 — v11.5 desplegada: sync inicial cerró 15 ops (7🟢/8🔴, PnL -$27.42 — incluye legado copy-era; era-combos sigue verde). El combo #4 (Seville+CS2) se cerró temprano 🔴 al perder un leg (cierre anticipado funcionando). En ABIERTAS quedaron: 4-5 combos reales de hoy + 2 single-legs Seyboth Wild ($5 c/u @1.96) copiados por v10.9 esta mañana ANTES del switch a v11.0 (coinciden con posición on-chain $9.99) + 1 registro basura "🎯 ? $0.00"
- 8 sept 15:26 — v11.6 desplegada y verificada (horario restaurado "próxima pasada en 21 min"; tope diario 6 activo)
- 8 sept 15:36 — v11.7 desplegada y verificada
- 8 sept 15:45 — v11.8 desplegada y verificada; sync inicial cerró 1 op más (-$5, leg perdido)
- 8 sept 16:09 — v11.9 desplegada y verificada (horario restaurado 9 min; sync cerró 1 op más -$5)
- 8 sept 17:03 — v12.0 desplegada y verificada (hash 1632dbd8, horario restaurado 14 min)
- 8 sept ~17:15 — user (con panel de 6 abiertas pegado): quitar duplicados de ABIERTAS (Seyboth ×2 y combo ×2 aparecen dobles), títulos enteros, y añadir por línea precio actual + probabilidad viva + consejo cerrar/mantener → v12.1: agrupar_abiertas + render_grupo + precio_mid (midpoint CLOB) + consejo 💰/🟢/🔴; tests con el escenario exacto del user OK + smoke real
- 8 sept ~17:30 — user confirma despliegue v12.1 (log 171644 'v12.1 iniciado') y pide v12.2: quitar botones stake $1/$2/$5 → stake decidido por el bot ENTRE $5 Y $10 según cuota y cómo vaya la combinada; y botones de MÁXIMO DE OPERACIONES/DÍA 5/10/20/30/50 con CÓDIGO de 4 cifras obligatorio para ≥10 → implementado (stake_para dinámico con reajuste post-quote, PIN persistido en /opt/polymarket/codigo_pin.txt, tope cuenta todas las franjas, títulos enteros 240 + enviar_largo anti-corte de Telegram); tests sandbox exhaustivos OK
- 11 sept 18:40 (Madrid) — **v12.7 (denuncia del user: "las ops de ✅ Cerradas NO son reales; cantidades y resultados no coinciden con Polymarket y hay combos cerrados antes de terminar")** — **CAUSA RAÍZ VERIFICADA**: el catálogo `/v1/rfq/combo-markets` devuelve `position_ids` que **NO son los `token_id` del CLOB** (otro espacio de ids: pares consecutivos …6064/…6065; p.ej. "U.S. invade Iran" catálogo `79855995…6064` vs CLOB `5511507842…`), así que `resolver_operacion` hacía `lg["position_id"] == win_tok` y **nunca** acertaba ⇒ en cuanto una leg cerraba, el combo se archivaba como **PERDIDA (pnl = −stake)** aunque ganara. Segundo bug: un mercado `closed` **sin ganador declarado** (resolución UMA pendiente) también contaba como pérdida ⇒ "cerrados antes de terminar". **DESCUBRIMIENTOS ON-CHAIN**: los tokens de combo viven en el ERC1155 `0x006f54f7f9a22e0000cc2ab60031000000ae9fef` (**NO** en el CTF `0x4D97…6045`, donde `balanceOf` da siempre 0 — por eso las comprobaciones anteriores salían 0), el manager es `0x30000034706c7d8e12009dab006be20000c031a8`, y Polymarket **autocobra** las ganadoras (~1 h) dejando un `REDEEM` en data-api `/activity` con `usdcSize` = $ cobrados (el bot NO hace redeem). Los combos no cotizan en el CLOB: `midpoint`/`price` dan 404 incluso con el mercado vivo (sólo RFQ). **AUDITORÍA REAL** (77 combos, 26-jul→11-sep; cruze de `/trades` + `/activity` + `balanceOf` en el ERC1155 de combos): era bot (61 combos, stake $5-10) → **25 ganadas cobradas +$195.82** · 3 vendidas (cierres manuales de ago.) +$35.97 · 33 aún en cartera ($285.19, de las que 11 son de las últimas 72 h) ⇒ **PnL realizado +$231.79** (tests antiguos $1-2: +$35.66). El bot, en cambio, reportaba "2 cerradas, 0 ganadas, −$18.37". Ejemplo concreto: combo Chelsea+Liverpool 09-09 20:42 → el bot −$9.74; la wallet cobró $12.19 ⇒ **+$2.45**. Los 5 "sin rastro" de ayer se explican: 4 fueron VENTAS y el 5º (BetBoom 13:33) acabó cobrando +$3.73 al aparecer su REDEEM. **FIX v12.6**: ganador por **OUTCOME** (nombre de la cara) o por **índice 0** si la op antigua no lo guarda (verificado: el orden de `outcomes` del catálogo == el de los tokens CLOB en 7 mercados, y en mercado resuelto el `winner=True` cae sobre el nombre del equipo), cerrado-sin-ganador = ⏳ PENDIENTE, y manda la verdad real (`cobros_wallet()` REDEEM + `saldo_combo_token()` on-chain, con caches 10/5 min y 3 RPC de respaldo); las ops nuevas guardan `outcome` por leg. **FIX v12.7 (petición user: "quiero que corra sola")**: **AUTO-CURACIÓN** — `reauditar_estado()` corre SOLA ~25 s tras cada arranque y cada **4 h** (`AUDITORIA_CADA_H`) dentro de `PASADA_LOCK` y sin depender del modo: reabre las mal archivadas, corrige resultado/PnL (guardando `resultado_antes`/`pnl_antes`), cierra las abiertas ya resueltas, **no toca los cierres manuales 🔒** y sólo avisa por Telegram si cambia algo (🩺 AUTO-CURACIÓN). Guardas: sólo ops de los últimos 45 días, y si el CLOB no devuelve datos de alguna leg (caída/429) la op **no se toca** (`sin_datos`, para no reabrir a ciegas); idempotente (2ª pasada = 0 cambios). `/reauditar [seco]` sigue a mano con saldo on-chain y `/status` muestra la última auditoría. **TESTS**: 11/11 del resolver contra mercados reales + end-to-end de la auditoría sobre estado sintético (corrige la cobrada, reabre la pendiente, respeta la manual, confirma la pérdida real, cierra la abierta resuelta, modo seco no escribe, idempotencia, backup previo) + guard sin-datos. Commits: bot **`4731f473`** · scripts `actualizar_v127.sh` (HASH fijado, backup del estado previo, foto antes/después, publica en diag-public) y `diag_estado_v127.sh` (vuelca `combos_estado.json` a diag-public para contrastarlo op a op). **PENDIENTE: push (hace falta el PAT del user) + despliegue en Hetzner.**
- 9 sept 18:45 (Madrid) — user elige (ask_user) **reintentar UNA vez con $5** cuando el RFQ responde `SIZE_TOO_LARGE` → **v12.5 implementada y testeada**: el bloque va en `ejecutar_combo_rfq` justo tras el primer parse de la respuesta (ancla única `crear_rfq(pids, stake, identidad)`), condición `_cod0 == "SIZE_TOO_LARGE" and stake > STAKE_MIN_AUTO + 0.001`; log `⚠️ RFQ SIZE_TOO_LARGE con $9.08 -> reintento único con $5.00 (suelo)` + aviso Telegram 🔁. **NO se reintenta en la rama SELL** (`cerrar_grupo`): vender menos dejaría la posición a medias y el resto sin archivar (comentario añadido en el código). Tests sandbox 7 bloques OK: reintento acaba en fill con `stake_dolares` = `total_req` real ($5, no los $9.08 pedidos), ya- al-mínimo no reintenta, doble fallo libera la huella (combo reintentable), `NO_QUOTES` NO reintenta, flujo normal intacto (1 petición), SELL con SIZE_TOO_LARGE no reintenta y deja la posición abierta, regresión PIN/prob/stake. **CONTEXTO DEL CAMBIO (leído en el log del servidor)**: hoy el RFQ rechazó 3 intentos — `SIZE_TOO_LARGE` 12:02 y 12:22, `NO_QUOTES` 12:12; el bot los registraba, liberaba el combo y pasaba de largo (2 oportunidades perdidas).
- 9 sept 16:21 — **TEST DE SALUD en el servidor** (`salud_combos_20260909_162133.log`, primer uso de `test_salud.sh`): código íntegro (145071 bytes, md5 `bf92fb2f…` idéntico a GitHub, `py_compile` OK, 0 tracebacks), estado `max_ops_dia=10 · prob_min_auto=0.65 · stake=AUTO · intervalo=10 min · chat_id=sí · 18 registros RFQ · 10 fills hoy · próxima pasada 2.1 min`, **proxy OK con IP de salida 85.85.41.76**, APIs ✅, disco 30%, RAM 29%, wallet 40 posiciones ≈$16.78 (la mayoría ajenas al bot de combos). Salió 1 ❌ ("CLOB a través del proxy → 404") que era **falso**: el chequeo usaba `midpoint?token_id=1` (404 seguro) y el midpoint real se omitía porque `/tmp/_pos.json` se descargaba DESPUÉS de extraer el token → corregido en `589ff17` (usa `/ok` + posiciones antes + midpoint por proxy con token real; validado ejecutando el script en el sandbox: bloque 5 todo ✅ salvo los 2 chequeos por proxy, que ahí dan HTTP 000 porque el sandbox no tiene ruta al tailnet).
- 9 sept 16:21 — **v12.4 DESPLEGADA Y VERIFICADA** (commit del bot `ef9d7912`, actualizador `82716622`, log `combos_update_v106_20260909_162114.log`): HASH ef9d7912, 145071 bytes, `POLY COMBOS BOT v12.4`, servicio `active (running)` 16:21:17 UTC (PID 1293951, 20.0 MB), arranque con **`stake=AUTO · max ops/día=10 · prob AUTO ≥65% · PIN ops fijo (4 cifras)`** ← el PIN del user ya activo, `Test proxy: 200`, `v12.4 iniciado`, sin errores. El sync del arranque cerró 2 ops: **0 ganadas, PnL −$18.37**. CONFIG DEL USER (leída del estado): tope **10/día** (por eso los 10 fills de hoy son legítimos) y probabilidad **alta ≥65%** (subió desde la media-alta 60% que dejé por defecto) → ventana AUTO cuota **1.20-1.54**; intervalo 10 min.
- 8 sept 23:23 (Madrid) — **CIERRE DE SESIÓN NOCTURNA (limpieza + backups + test de salud)**: el user se va a descansar. (1) **v12.4 empujada y verificada en GitHub** (`ef9d7912` bot, `82716622` actualizador, raw 200, md5 `bf92fb2f643beea011354edfaf798de0`, SYNTAX_OK) pero **SIN desplegar** — el servidor sigue con **v12.3** (`active` desde 20:37 UTC). (2) **Backup local** en `/home/user/backups/2026-09-08_noche/`: bot v12.2/v12.3/v12.4 + CONTEXTO + actualizar/ver + `backup_completo.py` + `MANIFIESTO.md` (inventario con md5, git, pendientes) + `TEST_SALUD_sandbox.md`. (3) **Limpieza**: borrados los ficheros de trabajo del sandbox (`patch_v124.py`, `servir_v123/`, `__pycache__`, temporales); árbol git limpio; sin procesos en segundo plano. (4) **`test_salud.sh` CREADO y commiteado** (la doc lo citaba pero nunca existió): 9 bloques + publicación en diag-public; corregidos dos falsos positivos descubiertos al validarlo contra las APIs reales (midpoint con token inventado → 404; gateway RFQ sin L2 → 404, no 401) y un bug de `grep -c` (`|| echo 0` producía "0\n0" y rompía la comparación aritmética). (5) **`backup_completo.py` RECUPERADO** a la rama desde el commit histórico `01bcaa8` (estaba perdido: no aparecía en ninguna rama del remoto). (6) **Test de salud desde el sandbox**: integridad del código en GitHub (3 refs → mismo md5), sintaxis OK, APIs públicas OK, wallet 40 posiciones ≈$18 (la mayoría ajenas al bot de combos), sin fills desde ~18:20 UTC (tope diario 8/6), smoke test de v12.4 (PIN fijo, teclado numérico, prob 60%, funciones de cierre, `direction`/`side`) y **fórmula del stake validada con 20.000 casos aleatorios** (20000/20000, invariantes [5,10] y skip con RFQ ≥0,5% peor). ACLARACIÓN: en data-api `size` = SHARES, no dólares (el fill "de $21.93" eran 21,93 sh × 0,2194 = **$4.81**); y `stake_para(cuota_REAL, cuota_EST)` lleva REAL primero — dos aserciones de test mías estaban mal, el código era correcto. PENDIENTE MAÑANA: desplegar v12.4 → `test_salud.sh` en el servidor → `/testcerrar 1` antes del primer cierre real.
- 8 sept 22:47 (Madrid) — user pide **v12.4**: que el código de 4 cifras para cambiar el tope diario (desde 10 ops) sea **el que él elija** y lo introduzca él mismo, y que el bot le saque el **teclado numérico**. Implementado como `PIN_FIJO_OPS` (constante en el código) + `codigo_pin()` sin generación aleatoria ni archivo; teclado numérico y flujo sin cambios respecto a v12.2; PIN fuera de los logs. Testeado en sandbox (botones, texto, PIN malo, ⌫, ❌, persistencia, override env, archivo viejo ignorado). Pendiente de push + despliegue.
- 8 sept 20:37 — **v12.3 DESPLEGADA Y VERIFICADA** en Hetzner (bot `f21c4627`, rama HEAD `a0e4121`, log `combos_update_v106_20260908_203717.log`): HASH f21c4627, 144528 bytes descargados, `POLY COMBOS BOT v12.3`, servicio active (running) 20:37:20 UTC (PID 1212692, 19.6 MB), arranque con `intervalo AUTO restaurado: 30 min` + **`stake=AUTO · max ops/día=6 · prob AUTO ≥60%`** + `v12.3 cargado … prob ≥60%`, `Test proxy: 200`, `v12.3 iniciado`, horario respetado (próxima pasada en 28 min, sin pasada inmediata). Sin traceback. En las pasadas AUTO sigue saliendo `tope diario alcanzado (8/6 ops)` → hoy ya no abrirá nada (el contador se resetea a medianoche UTC).
- 8 sept 20:20-20:33 — **INCIDENTE DE DESPLIEGUE (resuelto)**: di las instrucciones de v12.3 ANTES de que los commits estuvieran en GitHub (el push había fallado). El actualizador paró el bot (Paso 1), descargó una página 404 de 14 bytes y su guarda de tamaño abortó sin reiniciar → bot parado y `/opt/polymarket/poly_combos_bot.py` corrupto. Causa del push fallido: el `.git/config` del sandbox (volátil) apuntaba a `Albina15/bots-backup`, que NO existe (el repo bueno es `lamegawi/bots-backup`), y la copia del PAT venía truncada del resumen de sesión. Se restauró la v12.2 desde `/root/bot_v122.bak.py` (md5 `a61a8517e0d472ba266db50aac89c3ec`, idéntico al de GitHub) y el bot volvió a estar `active` a las 20:29:37 con `v12.2 cargado`. **LECCIÓN: NUNCA dar la Parte 2 sin haber confirmado antes `curl -sI raw.githubusercontent.com/…/<HASH>/…` → 200; y si el actualizador falla a medias, el bot queda PARADO (para antes de descargar) → tener siempre a mano el bloque de rescate (backup + restart).**
- 8 sept ~19:50 — user pide v12.3: botón de cerrar posición REAL; en ABIERTAS un ✅ verde / ❌ rojo A LA DERECHA de cada línea según haya terminado positiva o perdida; y que AUTO solo opere probabilidad alta (si no, descartar y pasar a la siguiente). Aclarado con 3 preguntas: umbral ≥65% de referencia pero filtro en **"media-alta"** (respuesta literal del user), y cierre **solo manual** (AUTO nunca vende solo) → implementado + verificado en sandbox (firma SELL EIP-712 recuperable, body RFQ SELL y HMAC L2 exactos, contabilidad proporcional sin doble conteo, dry_run en simples —bug cazado y corregido—)
- 8 sept 19:40 — **v12.2 DESPLEGADA Y VERIFICADA** en Hetzner (commit `5cbb63c3`, log diag-public `combos_update_v106_20260908_194038.log`): 117778 bytes, `POLY COMBOS BOT v12.2`, servicio active (running) 19:40:40 UTC, `stake=AUTO · max ops/día=6`, horario restaurado (próxima pasada en 15 min, sin pasada inmediata), `Test proxy: 200`, `v12.2 iniciado` 19:40:42. Pendiente de probar por el user: menú 🔢 (fijar tope con PIN) y ver el stake real de los próximos fills
- 8 sept ~16:30 — user: las extendidas NO deben ir en automático (fuera de las 6/día), solo por botón y contabilizar aparte; botones de Trades UNO POR COMBO debajo de cada uno; nuevo botón 💥 SúperCombos (cuota ≥5, máx 10, informativo+ejecutable manual, estadísticas aparte) → v12.0: tres franjas (base auto / extendida manual / súper manual), cmd_trades y cmd_super con enviar_catalogo (1 mensaje+botón por combo), cupos por franja en lanzar_combo_manual, combos_hoy_count solo base, stats por franja; tests 12/12 OK
- 8 sept ~16:00 — user pregunta opinión sobre subir el techo de cuota >2.5 → propuesta franja extendida con condiciones; user elige (ask_user): techo 3.0 / p≥0.75 / 2 por día → corrección matemática comunicada (0.75³→2.37 no cruza 2.5; se usa 0.70) → v11.9 implementada: seleccionar_combo devuelve (sel, extendida), prioridad extendida con cupo, ejecutar_combo_rfq(extendida=) ventana real hasta 3.2, catálogo/botones/paneles con 🚀, historial etiquetado; tests sandbox 7/7 OK (prioridad, cupo, fallida no consume, p<0.70 excluida, cuota real 2.8 aceptada/rechazada según franja, botón manual 🚀)
- 8 sept ~15:45 — user pide probabilidad de acierto por combo + botón para ejecutar el combo elegido → v11.8: texto prob (~% + etiqueta) + inline_keyboard con ▶️ por combo + procesar_callback/lanzar_combo_manual (anti-dup + lock + caché hash8 1h); tests sandbox OK (prob/etiquetas, botón lanza RFQ, duplicado ⛔, caducado alerta)
- 8 sept ~15:40 — user: el TOP-10 de la v11.6 muestra líneas sueltas → v11.7 con combos candidatos reales; tests OK (orden por volumen, triples, mismo evento excluido, filtros, vacío elegante)
- 8 sept ~15:30 — user redefine botones: 📋 Trades = catálogo informativo de combos (1-10 por volumen $, en rango de cuota, SIN operaciones); operaciones solo en 📂/✅ → v11.6 implementada y testeada (orden por volumen desc, filtro cuota, sin sync, basura filtrada en 📂)
- 8 sept ~15:10 — v11.5: panel de operaciones en vivo (ver resumen); tests fixtures (win/loss/abierta/cierre temprano/idempotencia/fallback) + smoke test real Cagliari OK
- 8 sept ~14:45 — v11.4: horario persistente (proximo_paso_ts + chat_id en estado); reinicio respeta la programación (si caducó → now+intervalo, nunca inmediata); dispatch acepta también texto manual "30 minutos"; desplegada tras reporte del usuario (pasada a los ~5 min pese a ⏱30m, causada por los 3 reinicios seguidos de esa tarde)
- 8 sept ~14:35 — v11.2: `saldo_disponible_clob()` (SDK get_balance_allowance COLLATERAL) antes de firmar; si saldo < total_req → skip con aviso 💸; accept con reintento único idempotente (6s) ante 503/SERVICE_UNAVAILABLE/TRADE_SUBMISSION_FAILED/PRE_EXECUTION_BALANCE_RESERVATION_FAILED
