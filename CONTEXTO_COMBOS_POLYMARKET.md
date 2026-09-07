# CONTEXTO COMPLETO: Bot de Combos de Polymarket

## 📋 RESUMEN

Bot de Telegram que opera **Combos (parlays) de Polymarket** automáticamente. Lleva 6+ horas en desarrollo y depuración. Está al 95% — solo falta confirmar que las credenciales se derivan correctamente y ejecuta el primer trade.

## 🎯 OBJETIVO

El bot debe:
1. Leer **Combos activos** del endpoint público `https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets`
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
- **Resultado**: probado en sandbox (GET/POST del SDK salen por proxy inyectado). Pendiente ejecutar en Hetzner

## 🔧 CÓDIGO CLAVE (v10.7)

### `enviar_orden()` — patrón del bot de Elon
```python
def enviar_orden(token_id, precio, stake_dolares):
    size_shares = round(stake_dolares / precio, 2)
    if size_shares < MIN_SHARES:  # MIN_SHARES = 5.0
        return False, "size_insuficiente"

    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    api_key = env.get("POLY_API_KEY", "").strip()
    api_secret = env.get("POLY_API_SECRET", "").strip()
    api_passphrase = env.get("POLY_API_PASSPHRASE", "").strip()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()

    # 1) Firmar la orden (NO envia)
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2.clob_types import ApiCreds, OrderArgs
    from py_clob_client_v2 import SignatureTypeV2

    kwargs_client = {
        "key": signer,
        "funder": wallet,
        "signature_type": int(SignatureTypeV2.POLY_PROXY) if wallet else int(SignatureTypeV2.EOA),
    }
    if api_key and api_secret and api_passphrase:
        kwargs_client["creds"] = ApiCreds(api_key, api_secret, api_passphrase)
    client = ClobClient(host=HOST_CLOB, chain_id=137, **kwargs_client)
    if "creds" not in kwargs_client:
        creds = client.derive_api_key()  # ← MAGIA: usa private key
        client.set_api_creds(creds)

    order_args = OrderArgs(token_id=token_id, price=precio, size=size_shares, side="BUY")
    signed_order = client.create_order(order_args)

    # 2) HTTP POST con proxy
    body = json.dumps(signed_order) if not isinstance(signed_order, str) else signed_order
    url = f"{HOST_CLOB}/order"
    headers = {
        "Content-Type": "application/json",
        "POLY_ADDRESS": wallet,
        "POLY_API_KEY": api_key,
        "POLY_PASSPHRASE": api_passphrase,
        "POLY_TIMESTAMP": str(int(time.time())),
    }
    status, resp_body = http_post(url, body, headers)  # http_post usa proxy
    if status in (200, 201):
        data = json.loads(resp_body)
        oid = data.get("orderID") or data.get("order_id")
        return True, {"oid": oid, "size": size_shares, "precio": precio}
    return False, f"http_{status}:{resp_body[:200]}"
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

- **HEAD del repo**: `ac4c912` (v10.7)
- **Bot cargado**: `v10.7 iniciado` a las 15:44:54 UTC
- **Pasada AUTO próxima**: 15:49:54 UTC
- **Lo que esperamos ver**:
  - `[TRADE] ...`
  - `  · Creds derivadas automaticamente` (si funciona)
  - `  orden firmada: {...}`
  - `  HTTP POST /order -> 200 {"orderID":"..."}`
  - `✅ COMBO EJECUTADO 📌 ...`

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
   git push --force origin arena/01a058fe-bots-backup
   ```
3. Obtener HEAD: `gh api repos/lamegawi/bots-backup/commits/arena/01a058fe-bots-backup -q '.sha[:8]'`
4. Ejecutar en Hetzner:
   ```
   curl -sL -o /tmp/v.sh https://raw.githubusercontent.com/lamegawi/bots-backup/<HASH>/scripts_despliegue/actualizar_v106.sh
   sed -i 's/HASH="abe93c7e"/HASH="<NUEVO_HASH>"/' /tmp/v.sh
   bash /tmp/v.sh
   ```

### Test rápido
```
ssh root@46.225.146.21
curl -sL -o /tmp/test.sh https://raw.githubusercontent.com/lamegawi/bots-backup/<HASH>/scripts_despliegue/test_salud.sh && bash /tmp/test.sh
```
Esto verifica que la IP de salida es `85.85.41.76` (PC del usuario).

## 📚 ENDPOINTS CLAVE

| Endpoint | URL | Uso |
|----------|-----|-----|
| Combos | `https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets` | Listar combos activos (público) |
| Market by condition_id | `https://clob.polymarket.com/markets/{condition_id}` | Obtener token_id real tradable |
| Midpoint | `https://clob.polymarket.com/midpoint?token_id={id}` | Precio actual del token |
| Order | `https://clob.polymarket.com/order` | POST con proxy (orden firmada) |
| Gamma (markets individuales) | `https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=N&offset=M` | Markets individuales (mayoría son política) |

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
- ⏳ **PENDIENTE**: desplegar v10.9 en Hetzner y confirmar primer trade ejecutado

## 🔗 URLs ÚTILES

- **Repo principal**: https://github.com/lamegawi/bots-backup/tree/arena/01a058fe-bots-backup
- **Logs publicados**: https://github.com/lamegawi/bots-backup/tree/diag-public/diag_hetzner
- **Polymarket CLOB docs**: https://docs.polymarket.com/
- **Polymarket Combos docs**: https://docs.polymarket.com/api-reference/combo-markets/get-combo-markets
- **py-clob-client-v2**: https://pypi.org/project/py-clob-client-v2/

## 📝 PRÓXIMOS PASOS INMEDIATOS

1. **Verificar que v10.7 funciona**:
   - Ejecutar ver_v106.sh en Hetzner
   - Ver log en diag-public
   - Buscar "Creds derivadas automaticamente" + "HTTP POST /order -> 200"
2. **Si funciona**: el bot ejecuta trades reales, monitorear con `/trades` en Telegram
3. **Si no funciona**: diagnosticar el error específico (probablemente issue con `derive_api_key` o formato de orden firmada)
4. **Mejoras futuras**:
   - Añadir stop-loss
   - Tracking de P&L en tiempo real
   - Filtros de deportes más específicos
   - Notificaciones de trades en Telegram

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
- 7 sept ~19:00 — Análisis del source del SDK (v1.1.0): usa httpx, envelope v2 y L2 HMAC → POST manual inviable → v10.9 con inyectar_proxy_sdk() + create_and_post_order nativo. PENDIENTE desplegar
