#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLY COMBOS BOT v5 — Combo simples automáticos
================================================
Estrategia: SIMPLES automáticos (1 evento) con filtro de cuota
  · Cuota objetivo: 1.50 - 2.50 (sweet spot para deportes)
  · Releer precio en tiempo real antes de enviar
  · Si la cuota es peor que el máximo, SALTA el trade
  · Máximo 3 trades simultáneos
  · Stake configurable ($1-$5)
  · Todo automático en modo AUTO (no requiere aprobación)

ARCHIVOS:
  · /root/poly_combos_token.txt       - Token Telegram
  · /opt/polymarket/combos_estado.json - Estado (modo, stake, trades copiados)
  · /etc/polymarket.env               - Credenciales Polymarket (CLOB)

USO:
  python3 /opt/polymarket/poly_combos_bot.py
"""
import os
import sys
import json
import time
import shutil
import base64
import subprocess
import urllib.request
import urllib.parse
import threading
import ssl
from datetime import datetime, timezone

LOG = []
def log(s):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {s}"
    print(line, flush=True)
    LOG.append(line)

# Anti-shadow module (evita problemas con /root/copy.py)
try:
    import importlib.util as _ilu
    _spec = _ilu.find_spec("copy")
except: pass


# ============================================
# CONFIGURACIÓN
# ============================================
TELEGRAM_TOKEN = None
WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"
HOST_CLOB = "https://clob.polymarket.com"

# Proxy en el PC del usuario (Tailscale 100.83.57.99:8888)
# Las operaciones se ejecutan a traves de este proxy para que salgan con
# la IP de tu PC (no la IP de Hetzner, que Polymarket rechaza).
PROXY_URL = "http://100.83.57.99:8888"

ESTADO_FILE = "/opt/polymarket/combos_estado.json"
BACKUP_FILE = "/opt/polymarket/combos_estado.bak.json"
ENV_FILE = "/etc/polymarket.env"

# ============================================
# ESTRATEGIA — Combo simples automáticos
# ============================================
STAKE_POR_TRADE = 2.0            # $ por trade
CUOTA_MIN = 1.20                 # cuota minima (probabilidad alta)
CUOTA_MAX = 2.50                 # cuota maxima (sweet spot para simples)
MAX_TRADES_SIMULTANEOS = 3       # maximo de operaciones a la vez
HORAS_RECIENTE = 6               # ventana de trades (mas corto = mas fresco)
INTERVALO_AUTO_S = 300           # cada cuanto revisa (5 min)
PESO_MIN = 5                     # peso minimo del trader (top 6)

# Estado (modo por defecto AUTO)
MODO_OPERACION = "AUTO"           # AUTO, SEMI, OFF
CHAT_ID = None                    # se detecta al primer mensaje

TOP_TRADERS = [
    ("pleaseplease123",     "0x5e9458202b5817a72cf81105ec8a30e6f3705ba1", 10),
    ("ferrariChampions2026", "0xfe787d2da716d60e8acff57fb87eb13cd4d10319", 8),
    ("balthazar",            "0x5a218c7ad04135830a45c41aaed7294df7809318", 5),
    ("Sassy-Bucket",         "0x4bff30af91642dc7d2b19a8664378fe55c45fc26", 5),
    ("Jsram",                "0x83720820a8aa6c3f20ad71850e7a1a17d16c5223", 5),
    ("Flaznorp",             "0x821dab0565ebf5b327f51db06223fdcfe01acf16", 5),
    ("Talvez10",             "0xa71093cafc0c099b4ccab24c3cb8018d817923c4", 4),
    ("GoalLineGhost",        "0x0346afae2603313d2bbee96b628536c8cbe352a5", 3),
    ("AV23IUa",              "0xdb859a551fcf56e49416160911476bea7307152f", 3),
]

DEPORTES_OK = ["MLB", "UFC", "NFL", "NBA", "tennis", "ATP", "soccer",
               "EPL", "O/U", "Spread", "Moneyline", "Over/Under",
               "Bundesliga", "Serie A", "Ligue 1", "La Liga",
               "NCAAF", "NCAAB", "WNBA", "MMA", "boxing"]
EXCLUIR = ["Trump", "Biden", "Election", "President", "Congress",
           "Bitcoin", "Ethereum", "Crypto", "NFT",
           "Fed", "rate", "inflation", "Russia", "Ukraine", "China",
           "Iran", "Israel", "WHO", "covid", "pandemic"]

TRADES_CACHE = {"ts": 0, "trades": []}
ULTIMO_TRADE_EJECUTADO = 0  # timestamp ultimo trade para evitar duplicados


# ============================================
# TELEGRAM
# ============================================
def cargar_token():
    global TELEGRAM_TOKEN
    paths = ["/root/poly_combos_token.txt", os.path.expanduser("~/poly_combos_token.txt")]
    for p in paths:
        if os.path.exists(p):
            t = open(p).read().strip()
            if ":" in t and len(t) > 20:
                TELEGRAM_TOKEN = t
                return True
    return False

def telegram_api(method, params=None):
    if not TELEGRAM_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        if params:
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(url, data=data)
        else:
            req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        log(f"telegram_api error: {e}")
        return None


# ============================================
# PROXY (Tailscale → PC del usuario)
# ============================================
_proxy_ctx = None
def _proxy_opener():
    global _proxy_ctx
    if _proxy_ctx is None:
        _proxy_ctx = ssl.create_default_context()
        _proxy_ctx.check_hostname = False
        _proxy_ctx.verify_mode = ssl.CERT_NONE
    proxy_handler = urllib.request.ProxyHandler({
        "http": PROXY_URL,
        "https": PROXY_URL,
    })
    https_handler = urllib.request.HTTPSHandler(context=_proxy_ctx)
    return urllib.request.build_opener(proxy_handler, https_handler)

def http_get(url, timeout=20):
    try:
        opener = _proxy_opener()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)


# ============================================
# TECLADO FIJO (siempre visible)
# ============================================
TECLADO_FIJO = {
    "keyboard": [
        [{"text": "📋 Trades"}, {"text": "💰 Saldo"}, {"text": "📂 Abiertas"}],
        [{"text": "✅ Cerradas"}, {"text": "🏆 Top"}, {"text": "📊 Estado"}],
        [{"text": "🟢 AUTO"}, {"text": "🟡 SEMI"}, {"text": "🔴 OFF"}],
        [{"text": "💵 Stake $1"}, {"text": "💵 Stake $2"}, {"text": "💵 Stake $5"}],
    ],
    "resize_keyboard": True,
    "persistent": True,
}

def enviar(chat_id, texto, reply_markup=None):
    params = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    # siempre anade el teclado fijo
    if reply_markup is None:
        params["reply_markup"] = json.dumps(TECLADO_FIJO)
    else:
        params["reply_markup"] = json.dumps(reply_markup)
    return telegram_api("sendMessage", params)


# ============================================
# CREDENCIALES Y CLIENTE CLOB
# ============================================
def cargar_env():
    env = {}
    if not os.path.exists(ENV_FILE):
        return env
    with open(ENV_FILE) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            k, v = linea.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def get_clob_client():
    """Crea el cliente CLOB forzando uso del proxy del PC."""
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds
        from py_clob_client_v2 import SignatureTypeV2
    except ImportError:
        log("ERROR: falta py-clob-client-v2")
        return None
    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    if not signer:
        log("ERROR: falta POLY_PRIVATE_KEY")
        return None
    # Forzar proxy a nivel de entorno
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
    os.environ["ALL_PROXY"] = PROXY_URL
    kwargs = {}
    if env.get("POLY_API_KEY") and env.get("POLY_API_SECRET") and env.get("POLY_API_PASSPHRASE"):
        kwargs["creds"] = ApiCreds(env["POLY_API_KEY"], env["POLY_API_SECRET"],
                                   env["POLY_API_PASSPHRASE"])
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()
    if wallet:
        kwargs["funder"] = wallet
    kwargs["signature_type"] = int(SignatureTypeV2.POLY_PROXY) if wallet else int(SignatureTypeV2.EOA)
    try:
        client = ClobClient(HOST_CLOB, chain_id=137, key=signer, **kwargs)
        try:
            import httpx
            client.client = httpx.Client(
                proxies={"http://": PROXY_URL, "https://": PROXY_URL},
                verify=False, timeout=30)
        except Exception as e:
            log(f"aviso httpx patch: {e}")
        if "creds" not in kwargs:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
            except Exception as e:
                log(f"aviso derive_api_key: {e}")
        return client
    except Exception as e:
        log(f"ERROR creando cliente CLOB: {e}")
        return None


# ============================================
# RE-LECTURA DE CUOTA EN TIEMPO REAL
# ============================================
def get_precio_actual(token_id):
    """Consulta el precio actual de un token (mid o best bid).
    Usa el proxy del PC. Devuelve precio float o None.
    """
    try:
        url = f"{HOST_CLOB}/midpoint?token_id={token_id}"
        status, body = http_get(url, timeout=10)
        if status == 200:
            data = json.loads(body)
            mid = data.get("mid") or data.get("midpoint")
            if mid:
                return float(mid)
        # fallback: book
        url = f"{HOST_CLOB}/book?token_id={token_id}"
        status, body = http_get(url, timeout=10)
        if status == 200:
            data = json.loads(body)
            bids = data.get("bids", [])
            asks = data.get("asks", [])
            if asks:
                return float(asks[0]["price"])  # best ask (precio de compra)
            if bids:
                return float(bids[0]["price"])
    except Exception as e:
        log(f"  get_precio_actual: {e}")
    return None


# ============================================
# DETECCIÓN Y FILTRADO DE TRADES
# ============================================
def detectar_trades():
    """Detecta trades de top traders en las últimas HORAS_RECIENTE horas."""
    ahora = datetime.now().timestamp()
    candidatos = []
    for nombre, wallet, peso in TOP_TRADERS:
        try:
            url = f"https://data-api.polymarket.com/trades?user={wallet}&limit=30"
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as r:
                trades = json.loads(r.read())
            for t in trades:
                if not isinstance(t, dict): continue
                titulo = t.get("title", "") or t.get("question", "")
                if any(ex in titulo for ex in EXCLUIR):
                    continue
                if not any(d.lower() in titulo.lower() for d in DEPORTES_OK):
                    continue
                ts = t.get("timestamp", 0)
                if ahora - ts > HORAS_RECIENTE * 3600:
                    continue
                price = float(t.get("price", 0))
                if price <= 0: continue
                # filtro previo de cuota
                cuota = round(1/price, 2)
                if cuota < CUOTA_MIN or cuota > CUOTA_MAX:
                    continue
                candidatos.append({
                    "trader": nombre, "peso": peso, "titulo": titulo,
                    "side": t.get("side", "?"), "price": price,
                    "size": float(t.get("size", 0)),
                    "asset": t.get("asset", "?"),
                    "timestamp": ts, "cuota": cuota,
                    "stake_sugerido": STAKE_POR_TRADE,
                })
        except Exception as e:
            log(f"error {nombre}: {e}")
    # ordenar por peso del trader
    candidatos.sort(key=lambda x: -x["peso"])
    # dedup por titulo
    vistos = set()
    finales = []
    for c in candidatos:
        key = c["titulo"][:50]
        if key in vistos: continue
        vistos.add(key)
        finales.append(c)
        if len(finales) >= MAX_TRADES_SIMULTANEOS * 2:
            break
    return finales

def trades_refresh():
    ahora = time.time()
    if ahora - TRADES_CACHE["ts"] > 60 or not TRADES_CACHE["trades"]:
        TRADES_CACHE["ts"] = ahora
        TRADES_CACHE["trades"] = detectar_trades()
    return TRADES_CACHE["trades"]


# ============================================
# EJECUCIÓN DE TRADE
# ============================================
def buscar_token_por_titulo(titulo):
    """Busca el token_id de un mercado por coincidencia de titulo.
    Devuelve (token_id, side) o (None, None).
    """
    try:
        url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            markets = json.loads(r.read())
        titulo_lower = titulo.lower()
        # buscar mejor coincidencia
        mejor = None
        mejor_score = 0
        for m in markets:
            q = (m.get("question") or m.get("title") or "").lower()
            if not q: continue
            # score simple: porcentaje de palabras del titulo que aparecen en q
            palabras = set(titulo_lower.replace(":", " ").replace("vs.", " ").split())
            palabras = {p for p in palabras if len(p) > 3}
            if not palabras: continue
            match = sum(1 for p in palabras if p in q)
            score = match / len(palabras)
            if score > mejor_score:
                mejor_score = score
                mejor = m
        if mejor and mejor_score > 0.4:
            tokens_str = mejor.get("clobTokenIds") or "[]"
            try:
                tokens = json.loads(tokens_str)
            except:
                tokens = []
            if tokens:
                # detectar YES/NO
                side = "YES"
                if "no" in titulo_lower and mejor_score < 0.7:
                    side = "NO"
                token_id = tokens[0] if side == "YES" else (tokens[1] if len(tokens) > 1 else tokens[0])
                return token_id, side
    except Exception as e:
        log(f"  buscar_token error: {e}")
    return None, None

def ejecutar_trade(trade, chat_id=None):
    """Ejecuta un trade simple (1 evento) automaticamente.
    1. Re-lee el precio actual del libro
    2. Si la cuota sigue en rango, envía la orden
    3. Notifica a Telegram
    """
    titulo = trade["titulo"]
    log(f"[REAL] {titulo[:50]}")
    # 1. buscar el token del mercado
    token_id, side = buscar_token_por_titulo(titulo)
    if not token_id:
        log(f"  SKIP: no encontre mercado para '{titulo[:40]}'")
        return False, "no_encontrado"
    # 2. re-leer precio en tiempo real
    precio_actual = get_precio_actual(token_id)
    if precio_actual is None:
        log(f"  SKIP: no pude leer precio actual")
        return False, "precio_no_disponible"
    if precio_actual <= 0 or precio_actual >= 1:
        log(f"  SKIP: precio invalido {precio_actual}")
        return False, "precio_invalido"
    cuota_actual = round(1 / precio_actual, 2)
    if cuota_actual < CUOTA_MIN or cuota_actual > CUOTA_MAX:
        log(f"  SKIP: cuota {cuota_actual} fuera de rango [{CUOTA_MIN}-{CUOTA_MAX}]")
        return False, f"cuota_fuera_rango_{cuota_actual}"
    # 3. verificar que no hayamos operado este mismo trade hace poco
    global ULTIMO_TRADE_EJECUTADO
    ahora = time.time()
    if ahora - ULTIMO_TRADE_EJECUTADO < 30:
        log(f"  SKIP: throttling (ultimo trade hace {ahora-ULTIMO_TRADE_EJECUTADO:.0f}s)")
        return False, "throttle"
    # 4. enviar la orden
    client = get_clob_client()
    if not client:
        return False, "cliente_no_disponible"
    try:
        from py_clob_client_v2.clob_types import OrderArgs
        size_shares = round(STAKE_POR_TRADE / precio_actual, 2)
        if size_shares < 5:
            log(f"  SKIP: {size_shares} shares < 5 (minimo)")
            return False, f"size_{size_shares}_muy_pequeno"
        log(f"  BUY {size_shares} shares @ {precio_actual:.3f} (cuota {cuota_actual})")
        resp = client.create_and_post_order(
            OrderArgs(token_id=token_id, price=precio_actual,
                      size=size_shares, side="BUY"))
        oid = resp.get("orderID") or resp.get("order_id") or "?"
        ULTIMO_TRADE_EJECUTADO = ahora
        # guardar en estado
        estado = cargar_estado()
        estado["trades_copiados"].append({
            **trade,
            "copiado_en": datetime.now().isoformat(),
            "precio_ejecutado": precio_actual,
            "cuota_ejecutada": cuota_actual,
            "size_shares": size_shares,
            "order_id": oid,
            "token_id": token_id,
            "side": side,
            "status": "ejecutado",
        })
        guardar_estado(estado)
        if chat_id:
            enviar(chat_id, f"✅ *ORDEN EJECUTADA*\n"
                          f"📌 {titulo[:55]}\n"
                          f"💵 {size_shares} shares @ {precio_actual:.2f} (cuota {cuota_actual})\n"
                          f"💰 Stake: ${size_shares * precio_actual:.2f}\n"
                          f"👤 Trader: `{trade['trader']}`\n"
                          f"🆔 `{str(oid)[:20]}`")
        return True, oid
    except Exception as e:
        err = str(e)[:200]
        log(f"  ERROR: {err}")
        if chat_id:
            enviar(chat_id, f"❌ *ERROR*\n{titulo[:50]}\n`{err}`")
        return False, err


# ============================================
# ESTADO
# ============================================
def cargar_estado():
    if not os.path.exists(ESTADO_FILE):
        return {"modo": MODO_OPERACION, "stake": STAKE_POR_TRADE,
                "trades_copiados": [], "historial": []}
    try:
        with open(ESTADO_FILE) as f:
            d = json.load(f)
        d.setdefault("modo", MODO_OPERACION)
        d.setdefault("stake", STAKE_POR_TRADE)
        d.setdefault("trades_copiados", [])
        d.setdefault("historial", [])
        return d
    except:
        return {"modo": MODO_OPERACION, "stake": STAKE_POR_TRADE,
                "trades_copiados": [], "historial": []}

def guardar_estado(estado):
    if os.path.exists(ESTADO_FILE):
        shutil.copy2(ESTADO_FILE, BACKUP_FILE)
    with open(ESTADO_FILE, "w") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)


# ============================================
# SALDO Y POSICIONES
# ============================================
def saldo_real():
    env = cargar_env()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET)
    rpcs = ["https://polygon-rpc.com", "https://1rpc.io/matic",
            "https://polygon.llamarpc.com"]
    tokens = [
        ("pUSD",   "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB", 6),
        ("USDC.e", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6),
        ("USDC",   "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
    ]
    data = "0x70a08231" + "0" * 24 + wallet.lower()[2:]
    saldos = {}
    for simbolo, contrato, dec in tokens:
        saldos[simbolo] = 0.0
        for rpc in rpcs:
            try:
                body = json.dumps({"jsonrpc": "2.0", "method": "eth_call",
                                   "params": [{"to": contrato, "data": data}, "latest"],
                                   "id": 1})
                out = subprocess.run(
                    ["curl", "-s", "--max-time", "8", "-X", "POST", rpc,
                     "-H", "Content-Type: application/json", "-d", body],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=12).stdout
                r = json.loads(out)
                if "result" in r and r["result"] not in ("0x", "0x0", None):
                    saldos[simbolo] = int(r["result"], 16) / (10 ** dec)
                    break
            except: continue
    return saldos

def get_posiciones_api():
    """Posiciones reales via API (mezcla con otros bots). Solo para enriquecer."""
    try:
        url = f"https://data-api.polymarket.com/positions?user={WALLET}&limit=500"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read())
    except: return []


# ============================================
# COMANDOS
# ============================================
def cmd_start(chat_id):
    estado = cargar_estado()
    texto = (f"🤖 *POLY COMBOS BOT v5*\n\n"
             f"Modo: *{estado.get('modo', MODO_OPERACION)}*\n"
             f"Stake: *${estado.get('stake', STAKE_POR_TRADE):.2f}*\n"
             f"Cuota objetivo: *{CUOTA_MIN:.2f} - {CUOTA_MAX:.2f}*\n"
             f"Máx trades simultáneos: *{MAX_TRADES_SIMULTANEOS}*\n\n"
             f"📌 *Estrategia*: Combo SIMPLES automáticos\n"
             f"   1 evento por trade, cuota 1.20-2.50\n"
             f"   Re-lectura de precio en tiempo real\n"
             f"   Sin aprobación manual (modo AUTO)\n\n"
             f"👇 Usa los botones de abajo.")
    return enviar(chat_id, texto)

def cmd_trades(chat_id):
    trades = trades_refresh()
    if not trades:
        return enviar(chat_id, "❌ No hay trades con cuota 1.20-2.50 ahora mismo.")
    texto = f"*🎯 TRADES DISPONIBLES ({len(trades)})*\n"
    texto += f"_Cuota objetivo: {CUOTA_MIN}-{CUOTA_MAX}_\n\n"
    for i, t in enumerate(trades, 1):
        texto += f"*{i}. {t['titulo'][:55]}*\n"
        texto += f"   {t['trader']} (peso {t['peso']}) | cuota {t['cuota']:.2f}\n"
        texto += f"   Stake sugerido: ${t['stake_sugerido']}\n\n"
    return enviar(chat_id, texto)

def cmd_saldo(chat_id):
    saldos = saldo_real()
    cash = sum(saldos.values())
    pos = get_posiciones_api()
    val_pos = sum(float(p.get("currentValue", 0) or 0) for p in pos)
    total = cash + val_pos
    texto = f"💰 *SALDO*\n\n*Cash on-chain:* ${cash:.2f}\n"
    for tok, val in saldos.items():
        texto += f"   {tok}: ${val:.2f}\n"
    texto += f"\n*Posiciones (total wallet):* ${val_pos:.2f}\n"
    texto += f"*TOTAL:* ${total:.2f}\n"
    texto += f"\n_PnL desde $500: ${total - 500:+.2f} ({(total-500)/500*100:+.1f}%)_"
    return enviar(chat_id, texto)

def _pos_combos():
    """Lee las posiciones que este bot ha operado (estado local)."""
    estado = cargar_estado()
    return estado.get("trades_copiados", []), estado.get("historial", [])

def cmd_abiertas(chat_id):
    copiados, _ = _pos_combos()
    if not copiados:
        return enviar(chat_id,
                      "*📂 POSICIONES ABIERTAS DE COMBOS*\n\n"
                      "_El bot aún no ha abierto ninguna posición._\n"
                      "_Pulsa 🟢 AUTO si quieres que empiece._")
    # contar las ejecutadas
    ejecutadas = [c for c in copiados if c.get("status") == "ejecutado"]
    texto = f"*📂 OPERACIONES DE COMBOS ({len(ejecutadas)})*\n\n"
    for c in ejecutadas[-15:]:
        titulo = (c.get("titulo") or "?")[:55]
        orden = c.get("order_id", "?")[:12]
        precio = c.get("precio_ejecutado", 0)
        cuota = c.get("cuota_ejecutada", 0)
        stake = c.get("size_shares", 0) * precio
        fecha = c.get("copiado_en", "")[:16]
        texto += f"✅ {titulo}\n   ${stake:.2f} @ {precio:.2f} (cuota {cuota:.2f})\n   `{orden}` · {fecha}\n\n"
    texto += f"\n_Usa 📊 Estado para ver el resumen._"
    return enviar(chat_id, texto)

def cmd_cerradas(chat_id):
    _, historial = _pos_combos()
    if not historial:
        return enviar(chat_id, "📭 El bot de Combos aún no tiene cerradas.")
    total = 0
    for h in historial:
        try: total += float(h.get("pnl", 0) or 0)
        except: pass
    texto = f"*✅ CERRADAS DE COMBOS ({len(historial)})*\n_PnL total: ${total:+.2f}_\n\n"
    for h in historial[-20:]:
        titulo = (h.get("titulo") or "?")[:55]
        pnl = float(h.get("pnl", 0) or 0)
        ico = "🟢" if pnl >= 0 else "🔴"
        cerrado = h.get("cerrado_en", h.get("copiado_en", "?"))[:16]
        texto += f"{ico} {titulo} → ${pnl:+.2f} ({cerrado})\n"
    return enviar(chat_id, texto)

def cmd_top(chat_id):
    texto = "*🏆 LEADERBOARD POLYMARKET (mensual)*\n\n"
    for i, (n, _, _) in enumerate(TOP_TRADERS[:10], 1):
        texto += f"{i}. {n}\n"
    return enviar(chat_id, texto)

def cmd_modo(chat_id, modo):
    global MODO_OPERACION
    modo = modo.upper()
    if modo not in ("AUTO", "SEMI", "OFF"):
        return enviar(chat_id, "❌ AUTO, SEMI, OFF")
    MODO_OPERACION = modo
    estado = cargar_estado()
    estado["modo"] = modo
    guardar_estado(estado)
    desc = {"AUTO": "🟢 ejecuta automáticamente",
            "SEMI": "🟡 informa pero no opera",
            "OFF": "🔴 solo informa"}[modo]
    enviar(chat_id, f"*Modo: {modo}*\n_{desc}_")
    if modo == "AUTO":
        threading.Thread(target=lambda: auto_pasada(chat_id), daemon=True).start()
    return True

def cmd_stake(chat_id, valor):
    global STAKE_POR_TRADE
    try:
        stake = float(valor)
        if stake < 0.5 or stake > 50:
            return enviar(chat_id, "❌ Stake entre $0.50 y $50")
        STAKE_POR_TRADE = stake
        estado = cargar_estado()
        estado["stake"] = stake
        guardar_estado(estado)
        return enviar(chat_id, f"*Stake: ${stake:.2f}*")
    except:
        return enviar(chat_id, "❌ /stake 2.5")

def cmd_status(chat_id):
    global CHAT_ID
    CHAT_ID = chat_id
    estado = cargar_estado()
    ejecutadas = [c for c in estado.get("trades_copiados", []) if c.get("status") == "ejecutado"]
    texto = (f"*📊 ESTADO*\n\n"
             f"Modo: *{estado.get('modo', MODO_OPERACION)}*\n"
             f"Stake: *${estado.get('stake', STAKE_POR_TRADE):.2f}*\n"
             f"Cuota: *{CUOTA_MIN}-{CUOTA_MAX}*\n"
             f"Trades ejecutados: *{len(ejecutadas)}*\n"
             f"Wallet: `{WALLET[:10]}…{WALLET[-4:]}`\n"
             f"Proxy: `{PROXY_URL}`\n"
             f"Hora: {datetime.now().strftime('%H:%M:%S')}")
    return enviar(chat_id, texto)


# ============================================
# AUTO LOOP — el corazón del bot
# ============================================
def auto_pasada(chat_id):
    """Una pasada: detecta trades y ejecuta automaticamente los mejores."""
    if MODO_OPERACION != "AUTO":
        return
    log(f"[AUTO] pasada (chat {chat_id})")
    trades = trades_refresh()
    if not trades:
        enviar(chat_id, "🔄 *AUTO:* sin trades con cuota 1.20-2.50 ahora mismo.")
        return
    enviar(chat_id, f"🔄 *AUTO: {len(trades)} candidatos, ejecutando…*")
    ejecutar = 0
    saltados = 0
    for t in trades[:MAX_TRADES_SIMULTANEOS * 2]:
        if ejecutar >= MAX_TRADES_SIMULTANEOS:
            break
        # solo top traders (peso >= PESO_MIN)
        if t["peso"] < PESO_MIN:
            saltados += 1
            continue
        ok, motivo = ejecutar_trade(t, chat_id)
        if ok:
            ejecutar += 1
        else:
            saltados += 1
            log(f"  saltado: {motivo}")
    if ejecutar:
        enviar(chat_id, f"✅ *AUTO: {ejecutar} trade(s) ejecutado(s), {saltados} saltado(s)*")
    else:
        enviar(chat_id, f"⚠️ *AUTO: 0 ejecuciones, {saltados} saltados*\n"
                       f"_Prueba a cambiar a SEMI para ver los detalles._")

def auto_loop():
    """Loop cada INTERVALO_AUTO_S segundos."""
    while True:
        try:
            if MODO_OPERACION == "AUTO" and CHAT_ID:
                auto_pasada(CHAT_ID)
        except Exception as e:
            log(f"auto_loop error: {e}")
        time.sleep(INTERVALO_AUTO_S)


# ============================================
# LOOP PRINCIPAL DE TELEGRAM
# ============================================
def procesar_update(update):
    global MODO_OPERACION, CHAT_ID
    if "message" not in update:
        return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    CHAT_ID = chat_id
    # botones del teclado fijo
    if text == "📋 Trades":
        return cmd_trades(chat_id)
    elif text == "💰 Saldo":
        return cmd_saldo(chat_id)
    elif text == "📂 Abiertas":
        return cmd_abiertas(chat_id)
    elif text == "✅ Cerradas":
        return cmd_cerradas(chat_id)
    elif text == "🏆 Top":
        return cmd_top(chat_id)
    elif text == "📊 Estado":
        return cmd_status(chat_id)
    elif text == "🟢 AUTO":
        return cmd_modo(chat_id, "AUTO")
    elif text == "🟡 SEMI":
        return cmd_modo(chat_id, "SEMI")
    elif text == "🔴 OFF":
        return cmd_modo(chat_id, "OFF")
    elif text.startswith("💵 Stake $"):
        try:
            v = float(text.replace("💵 Stake $", "").strip())
            return cmd_stake(chat_id, str(v))
        except:
            return enviar(chat_id, "❌")
    # comandos
    if text == "/start":
        cmd_start(chat_id)
        if MODO_OPERACION == "AUTO":
            threading.Thread(target=lambda: auto_pasada(chat_id), daemon=True).start()
        return
    elif text == "/trades":
        return cmd_trades(chat_id)
    elif text == "/abiertas":
        return cmd_abiertas(chat_id)
    elif text == "/cerradas":
        return cmd_cerradas(chat_id)
    elif text == "/saldo":
        return cmd_saldo(chat_id)
    elif text == "/top":
        return cmd_top(chat_id)
    elif text.startswith("/auto"):
        parts = text.split()
        return cmd_modo(chat_id, parts[1] if len(parts) > 1 else "AUTO")
    elif text.startswith("/stake"):
        parts = text.split()
        return cmd_stake(chat_id, parts[1] if len(parts) > 1 else "2.0")
    elif text == "/status" or text == "/estado":
        return cmd_status(chat_id)

def bot_loop():
    log("Bot iniciado, esperando mensajes...")
    offset = 0
    while True:
        try:
            params = {"timeout": 30, "offset": offset}
            data = urllib.parse.urlencode(params).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                data=data)
            with urllib.request.urlopen(req, timeout=60) as r:
                result = json.loads(r.read())
            if result.get("ok"):
                for update in result.get("result", []):
                    offset = update["update_id"] + 1
                    try:
                        procesar_update(update)
                    except Exception as e:
                        log(f"error update: {e}")
        except Exception as e:
            log(f"loop error: {e}")
            time.sleep(5)


def main():
    if not cargar_token():
        log("ERROR: no se encontró el token")
        return
    log(f"Token cargado")
    log(f"Wallet: {WALLET}")
    log(f"Modo: {MODO_OPERACION}")
    log(f"Stake: ${STAKE_POR_TRADE}")
    log(f"Cuota objetivo: {CUOTA_MIN}-{CUOTA_MAX}")
    log(f"Proxy PC: {PROXY_URL}")
    # test proxy
    log("Test proxy...")
    status, body = http_get("https://api.telegram.org", timeout=10)
    if status:
        log(f"  Proxy OK (status {status})")
    else:
        log(f"  PROXY FALLO: {body[:100]}")
    # arrancar auto loop
    t = threading.Thread(target=auto_loop, daemon=True)
    t.start()
    bot_loop()

if __name__ == "__main__":
    main()
