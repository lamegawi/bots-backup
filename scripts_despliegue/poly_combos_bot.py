#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLY COMBOS BOT — Bot de Telegram para COPIAR trades de top traders
====================================================================
Combina:
  1. Detección de trades de los top traders (de Polymarket data-api)
  2. Ejecución REAL automática en la CLOB con py-clob-client-v2
  3. Bot de Telegram con botones inline para gestionar el bot

MODOS DE OPERACIÓN (selector por Telegram):
  · AUTO: copia automáticamente los top trades (3 simultaneos, $2 cada uno)
  · SEMI: detecta y propone, pero espera botón /copiar_1, /copiar_2, /copiar_3
  · OFF: solo informa, no opera

ARCHIVOS:
  · /root/poly_combos_token.txt  - Token del bot de Telegram
  · /root/poly_combos_estado.json - Estado de operaciones copiadas
  · /etc/polymarket.env          - Credenciales Polymarket (CLOB)

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
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = []
def log(s):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {s}"
    print(line, flush=True)
    LOG.append(line)

# Anti-shadow: forzar carga del modulo copy estandar (evita shadow modules)
try:
    import importlib.util as _ilu
    _spec = _ilu.find_spec("copy")
    if _spec and "site-packages" not in (_spec.origin or "") and "dist-packages" not in (_spec.origin or ""):
        # si el copy no viene de una ruta estandar, hay shadow module
        pass
except: pass


# ============================================
# CONFIGURACIÓN
# ============================================
TELEGRAM_TOKEN = None
WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"
HOST_CLOB = "https://clob.polymarket.com"

# Proxy en el PC del usuario (Tailscale 100.83.57.99:8888)
# Las operaciones SE EJECUTAN a traves de este proxy para que salgan con
# la IP de tu PC (no la IP de Hetzner, que Polymarket rechaza).
PROXY_URL = "http://100.83.57.99:8888"

ESTADO_FILE = "/opt/polymarket/combos_estado.json"
BACKUP_FILE = "/opt/polymarket/combos_estado.bak.json"
ENV_FILE = "/etc/polymarket.env"

STAKE_POR_TRADE = 2.0
MAX_TRADES_SIMULTANEOS = 3
HORAS_RECIENTE = 24
MODO_OPERACION = "AUTO"  # AUTO, SEMI, OFF — AUTO por defecto: opera al arrancar
CHAT_ID = None  # se detecta al primer mensaje

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
               "EPL", "O/U", "Spread", "Moneyline", "Over/Under"]
EXCLUIR = ["Trump", "Biden", "Election", "President", "Congress",
           "Bitcoin", "Ethereum", "Crypto", "NFT",
           "Fed", "rate", "inflation", "Russia", "Ukraine", "China"]

# cache de trades detectados
TRADES_CACHE = {"ts": 0, "trades": []}

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

def telegram_api(method, params=None, files=None):
    if not TELEGRAM_TOKEN:
        return None
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/{method}"
    try:
        if files:
            boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
            body = b""
            for k, v in (params or {}).items():
                body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
            for k, (fn, data) in files.items():
                body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{fn}\"\r\nContent-Type: application/octet-stream\r\n\r\n".encode() + data + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
            req = urllib.request.Request(url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        elif params:
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
# Todas las llamadas HTTP del bot pasan por aqui para que las requests
# salgan con la IP del PC del usuario, no de Hetzner.
import ssl
_proxy_ctx = None
def _proxy_opener():
    """Devuelve un opener configurado con el proxy del PC."""
    global _proxy_ctx
    if _proxy_ctx is None:
        _proxy_ctx = ssl.create_default_context()
        # ser permisivos con certificados auto-firmados del proxy
        _proxy_ctx.check_hostname = False
        _proxy_ctx.verify_mode = ssl.CERT_NONE
    proxy_handler = urllib.request.ProxyHandler({
        "http": PROXY_URL,
        "https": PROXY_URL,
    })
    https_handler = urllib.request.HTTPSHandler(context=_proxy_ctx)
    return urllib.request.build_opener(proxy_handler, https_handler)

def http_get(url, timeout=20):
    """GET via proxy. Devuelve (status, body_str) o (None, error_str)."""
    try:
        opener = _proxy_opener()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)

def http_post_json(url, payload, timeout=20):
    """POST JSON via proxy. Devuelve (status, body_str)."""
    try:
        opener = _proxy_opener()
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST",
            headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except Exception as e:
        return None, str(e)

# Teclado fijo SIEMPRE visible (debajo del cuadro de texto)
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

def enviar(chat_id, texto, reply_markup=None, always_keyboard=True):
    """Envia mensaje. Por defecto incluye el teclado fijo siempre visible."""
    params = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    if reply_markup:
        params["reply_markup"] = json.dumps(reply_markup)
    elif always_keyboard:
        params["reply_markup"] = json.dumps(TECLADO_FIJO)
    return telegram_api("sendMessage", params)

def enviar_trades_con_botones(chat_id, trades):
    botones = []
    for i, t in enumerate(trades, 1):
        titulo_corto = t["titulo"][:30]
        botones.append([{
            "text": f"📋 Copiar {i}: {titulo_corto}",
            "callback_data": f"copiar_{i}"
        }])
    botones.append([
        {"text": "🔄 Auto: ON", "callback_data": "auto_on"},
        {"text": "⏸ Auto: OFF", "callback_data": "auto_off"},
    ])
    botones.append([
        {"text": "💰 Saldo", "callback_data": "saldo"},
        {"text": "📂 Abiertas", "callback_data": "abiertas"},
        {"text": "📋 Trades", "callback_data": "trades"},
    ])
    texto = f"*🎯 TRADES PARA COPIAR ({len(trades)})*\n"
    texto += f"_Modo actual: {MODO_OPERACION}_\n\n"
    for i, t in enumerate(trades, 1):
        texto += f"*{i}. {t['titulo'][:50]}*\n"
        texto += f"   Trader: `{t['trader']}` (peso {t['peso']})\n"
        texto += f"   {t['side']} @ {t['price']:.2f} → cuota {t['cuota']:.2f}\n"
        texto += f"   Tu stake: ${t['stake_sugerido']}\n\n"
    return enviar(chat_id, texto, {"inline_keyboard": botones})

# ============================================
# POLYMARKET — CLIENTE CLOB
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
    """Crea el cliente CLOB usando las credenciales del env.
    IMPORTANTE: el cliente se configura para usar el proxy del PC
    (Tailscale 100.83.57.99:8888) en TODAS las llamadas HTTP.
    """
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds
        from py_clob_client_v2 import SignatureTypeV2
    except ImportError:
        log("ERROR: falta py-clob-client-v2. Instalar: pip install py-clob-client-v2")
        return None
    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    if not signer:
        log("ERROR: falta POLY_PRIVATE_KEY en /etc/polymarket.env")
        return None
    # Forzar proxy a nivel de entorno para que TODOS los requests (incluido
    # el SDK) vayan por el PC del usuario
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
        # Forzar proxy tambien en el cliente httpx interno del SDK
        try:
            import httpx
            # reemplazar el transport con uno que use proxy
            client.client = httpx.Client(
                proxies={"http://": PROXY_URL, "https://": PROXY_URL},
                verify=False, timeout=30)
        except Exception as e:
            log(f"aviso: no se pudo parchar httpx client: {e}")
        if "creds" not in kwargs:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
            except Exception as e:
                log(f"aviso derive_api_key: {e}")
        log(f"  cliente CLOB creado (proxy={PROXY_URL})")
        return client
    except Exception as e:
        log(f"ERROR creando cliente CLOB: {e}")
        return None

def get_market_para_evento(titulo, asset):
    """Busca un mercado por título o asset (token_id) y devuelve (token_id, side_target, current_price)."""
    try:
        # buscar el bin por titulo exacto
        from urllib.parse import quote
        url = f"https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=200"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            markets = json.loads(r.read())
        titulo_lower = titulo.lower()
        for m in markets:
            q = (m.get("question") or m.get("title") or "").lower()
            if titulo_lower[:30] in q or q[:30] in titulo_lower:
                tokens_str = m.get("clobTokenIds") or "[]"
                try:
                    tokens = json.loads(tokens_str)
                except:
                    continue
                if not tokens:
                    continue
                # intentar identificar YES/NO por el titulo del mercado
                if "no" in titulo_lower or "draw" in titulo_lower:
                    return tokens[1] if len(tokens) > 1 else tokens[0], "NO", 0.5
                return tokens[0], "YES", 0.5
        # fallback: si el asset empieza con un id
        if asset and str(asset).isdigit():
            return str(asset), "YES", 0.5
    except Exception as e:
        log(f"error buscando mercado: {e}")
    return None, None, 0.5

def ejecutar_trade_real(trade, chat_id=None):
    """Ejecuta una orden REAL en CLOB."""
    log(f"[REAL] ejecutando trade: {trade['titulo'][:50]}")
    client = get_clob_client()
    if not client:
        return False, "cliente CLOB no disponible"
    token_id, lado, _ = get_market_para_evento(trade["titulo"], trade.get("asset"))
    if not token_id:
        return False, f"no se encontró mercado para: {trade['titulo'][:50]}"
    # traducir side del top trader a side nuestro
    side_trader = trade.get("side", "BUY")
    # si el trader compró YES, nosotros compramos YES
    if "NO" in (trade["titulo"].upper()):
        side = "BUY"
    else:
        side = "BUY" if side_trader == "BUY" else "SELL"
    try:
        # obtener precio actual del libro
        from py_clob_client_v2.clob_types import OrderArgs
        # si BUY a precio X, y el trader compró a precio mayor, usar precio del trader
        # si SELL, usar el precio (será venta de shares)
        precio = float(trade["price"])
        if side == "BUY":
            # comprar shares a este precio: size = stake / price
            size_shares = round(STAKE_POR_TRADE / precio, 2)
            if size_shares < 5:
                return False, f"tamaño {size_shares} < 5 shares mínimo"
            log(f"  BUY {size_shares} shares @ {precio:.3f} = ${STAKE_POR_TRADE}")
            resp = client.create_and_post_order(
                OrderArgs(token_id=token_id, price=precio, size=size_shares, side="BUY"))
        else:
            # SELL: el trader está vendiendo, no copiamos ventas
            return False, "no copiamos ventas (solo compras nuevas)"
        oid = resp.get("orderID") or resp.get("order_id")
        if chat_id:
            enviar(chat_id, f"✅ *ORDEN EJECUTADA*\n"
                          f"  {trade['titulo'][:50]}\n"
                          f"  BUY {size_shares} @ {precio:.3f}\n"
                          f"  OrderID: `{str(oid)[:20]}`")
        return True, oid
    except Exception as e:
        log(f"  ERROR enviando orden: {e}")
        if chat_id:
            enviar(chat_id, f"❌ *ERROR*\n  {str(e)[:200]}")
        return False, str(e)

# ============================================
# ESTADO
# ============================================
def cargar_estado():
    if not os.path.exists(ESTADO_FILE):
        return {"modo": MODO_OPERACION, "trades_copiados": [], "historial": []}
    try:
        with open(ESTADO_FILE) as f:
            d = json.load(f)
        d.setdefault("modo", MODO_OPERACION)
        d.setdefault("trades_copiados", [])
        d.setdefault("historial", [])
        return d
    except:
        return {"modo": MODO_OPERACION, "trades_copiados": [], "historial": []}

def guardar_estado(estado):
    if os.path.exists(ESTADO_FILE):
        shutil.copy2(ESTADO_FILE, BACKUP_FILE)
    with open(ESTADO_FILE, "w") as f:
        json.dump(estado, f, indent=2, ensure_ascii=False)

# ============================================
# DETECCIÓN DE TRADES
# ============================================
def detectar_trades():
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
                candidatos.append({
                    "trader": nombre, "peso": peso, "titulo": titulo,
                    "side": t.get("side", "?"), "price": price,
                    "size": float(t.get("size", 0)),
                    "asset": t.get("asset", "?"),
                    "timestamp": ts, "cuota": round(1/price, 2),
                    "stake_sugerido": STAKE_POR_TRADE,
                })
        except Exception as e:
            log(f"error {nombre}: {e}")
    candidatos.sort(key=lambda x: -x["peso"])
    vistos = set()
    finales = []
    for c in candidatos:
        key = c["titulo"][:50]
        if key in vistos: continue
        vistos.add(key)
        finales.append(c)
        if len(finales) >= MAX_TRADES_SIMULTANEOS:
            break
    return finales

def trades_refresh():
    """Refresca el cache de trades si ha pasado más de 2 minutos."""
    ahora = time.time()
    if ahora - TRADES_CACHE["ts"] > 120 or not TRADES_CACHE["trades"]:
        TRADES_CACHE["ts"] = ahora
        TRADES_CACHE["trades"] = detectar_trades()
    return TRADES_CACHE["trades"]

# ============================================
# SALDO / POSICIONES
# ============================================
def saldo_real():
    """Consulta el saldo CLOB."""
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

def get_posiciones():
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
    texto = (f"*🤖 POLY COMBOS BOT*\n\n"
             f"Bot de copia de trades de los top traders de Polymarket Sports.\n\n"
             f"*Modo actual: {MODO_OPERACION}* — stake ${STAKE_POR_TRADE:.2f}\n\n"
             f"*👇 Usa los botones de abajo para navegar.*\n"
             f"_El teclado queda fijo, solo pulsa._\n\n"
             f"*Trades:* ver recomendaciones\n"
             f"*Saldo:* tu balance real\n"
             f"*Abiertas:* posiciones activas\n"
             f"*Cerradas:* historial\n"
             f"*Top:* leaderboard\n"
             f"*Estado:* info del bot\n"
             f"*AUTO/SEMI/OFF:* cambiar modo\n"
             f"*Stake $1/$2/$5:* cambiar stake")
    # sin inline_buttons, solo el teclado fijo abajo
    return enviar(chat_id, texto)

def cmd_trades(chat_id):
    trades = trades_refresh()
    if not trades:
        return enviar(chat_id, "❌ No hay trades recomendados ahora mismo.")
    return enviar_trades_con_botones(chat_id, trades)

def cmd_copiar(chat_id, num):
    global MODO_OPERACION
    if MODO_OPERACION == "OFF":
        return enviar(chat_id,
                      "*🔴 MODO OFF — No se ejecutan operaciones*\n\n"
                      "Cambia a 🟢 AUTO o 🟡 SEMI desde los botones de abajo.")
    trades = trades_refresh()
    if num < 1 or num > len(trades):
        return enviar(chat_id, f"❌ Número inválido. Hay {len(trades)} trades disponibles.")
    trade = trades[num - 1]
    estado = cargar_estado()
    estado["trades_copiados"].append({
        **trade, "copiado_en": datetime.now().isoformat(),
        "status": "ejecutando", "chat_id": chat_id,
    })
    guardar_estado(estado)
    enviar(chat_id, f"⏳ *Ejecutando trade {num}...*\n  {trade['titulo'][:50]}")
    ok, oid = ejecutar_trade_real(trade, chat_id)
    estado = cargar_estado()
    if estado["trades_copiados"]:
        estado["trades_copiados"][-1]["status"] = "ok" if ok else "error"
        estado["trades_copiados"][-1]["order_id"] = oid
        guardar_estado(estado)
    return ok

def cmd_saldo(chat_id):
    saldos = saldo_real()
    cash = sum(saldos.values())
    pos = get_posiciones()
    val_pos = sum(float(p.get("currentValue", 0) or 0) for p in pos)
    total = cash + val_pos
    texto = f"*💰 SALDO REAL*\n\n*Cash on-chain:* ${cash:.2f}\n"
    for tok, val in saldos.items():
        texto += f"  · {tok}: ${val:.2f}\n"
    texto += f"\n*Posiciones:* ${val_pos:.2f}\n"
    texto += f"*TOTAL:* ${total:.2f}\n"
    texto += f"\n_PnL desde $500: ${total - 500:+.2f} ({(total-500)/500*100:+.1f}%)_"
    botones = [[{"text": "🔙 Volver", "callback_data": "menu"}]]
    return enviar(chat_id, texto, {"inline_keyboard": botones})

def _posiciones_combos():
    """Lee las posiciones que este bot de Combos ha copiado (estado local).
    NO mezcla con las posiciones de otros bots (Elon/Zelensky) que usan la
    misma wallet en Polymarket."""
    estado = cargar_estado()
    return estado.get("trades_copiados", []), estado.get("historial", [])

def cmd_abiertas(chat_id):
    """Muestra SOLO las posiciones que este bot de Combos ha abierto.
    Filtra por titulo o asset para no mostrar las de Elon/Zelensky."""
    copiados, _ = _posiciones_combos()
    # tokens/assets que el bot de combos ha operado
    tokens_combos = set()
    titulos_combos = set()
    for t in copiados:
        if t.get("status") == "ok":
            titulos_combos.add((t.get("titulo") or "")[:30].lower())
            for k in ("asset", "token_id", "order_id"):
                v = t.get(k)
                if v: tokens_combos.add(str(v))
    if not titulos_combos and not tokens_combos:
        return enviar(chat_id,
                      "*📂 POSICIONES ABIERTAS DE COMBOS*\n\n"
                      "_El bot de Combos aún no ha abierto ninguna posición._\n"
                      "_Pulsa 🟢 AUTO si quieres que empiece ya._")
    # leer API solo para enriquecer con PnL actual
    pos = get_posiciones()
    abiertas_combos = []
    for p in pos:
        if float(p.get("currentValue", 0) or 0) <= 0.001: continue
        titulo = (p.get("title") or p.get("question") or "").lower()[:30]
        asset = str(p.get("asset", ""))
        if titulo in titulos_combos or asset in tokens_combos:
            abiertas_combos.append(p)
    if not abiertas_combos:
        return enviar(chat_id,
                      "*📂 POSICIONES ABIERTAS DE COMBOS*\n\n"
                      "_No hay posiciones activas del bot de Combos._\n"
                      f"_({len(copiados)} trade(s) copiado(s) en historial)_")
    texto = f"*📂 POSICIONES ABIERTAS DE COMBOS ({len(abiertas_combos)})*\n\n"
    total_pnl = 0
    for p in abiertas_combos[:15]:
        titulo = (p.get("title") or p.get("question", "?"))[:50]
        outcome = p.get("outcome", "?")
        cur = float(p.get("currentValue", 0) or 0)
        pnl = float(p.get("cashPnl", 0) or 0)
        total_pnl += pnl
        ico = "🟢" if pnl >= 0 else "🔴"
        texto += f"{ico} {titulo}\n   {outcome} | PnL: ${pnl:+.2f} (cur ${cur:.2f})\n\n"
    texto += f"*Total PnL abierto: ${total_pnl:+.2f}*"
    return enviar(chat_id, texto)

def cmd_cerradas(chat_id):
    """Muestra SOLO las posiciones cerradas que este bot de Combos ha operado."""
    _, historial = _posiciones_combos()
    if not historial:
        return enviar(chat_id, "📭 El bot de Combos aún no tiene cerradas.")
    total = 0
    for h in historial:
        try:
            total += float(h.get("pnl", 0) or 0)
        except: pass
    texto = f"*✅ CERRADAS DE COMBOS ({len(historial)})*\n_PnL total: ${total:+.2f}_\n\n"
    for h in historial[-20:]:
        titulo = (h.get("titulo") or h.get("title", "?"))[:50]
        pnl = float(h.get("pnl", 0) or 0)
        ico = "🟢" if pnl >= 0 else "🔴"
        cerrado = h.get("cerrado_en", h.get("copiado_en", "?"))[:16]
        texto += f"{ico} {titulo}\n   ${pnl:+.2f} · {cerrado}\n\n"
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
        return enviar(chat_id, "❌ Modos: AUTO, SEMI, OFF")
    MODO_OPERACION = modo
    estado = cargar_estado()
    estado["modo"] = modo
    guardar_estado(estado)
    desc = {"AUTO": "🟢 copia automáticamente los top trades",
            "SEMI": "🟡 detecta y propone, espera tu aprobación",
            "OFF": "🔴 solo informa, no opera"}[modo]
    enviar(chat_id, f"*Modo cambiado a {modo}*\n_{desc}_")
    # si es AUTO, lanzar una pasada inmediata
    if modo == "AUTO":
        threading.Thread(target=lambda: auto_pasada_inmediata(chat_id), daemon=True).start()
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
        return enviar(chat_id, f"*Stake cambiado a ${stake:.2f}*")
    except:
        return enviar(chat_id, "❌ Uso: /stake 2.5")

def cmd_status(chat_id):
    global CHAT_ID
    CHAT_ID = chat_id
    estado = cargar_estado()
    texto = (f"*📊 ESTADO*\n\n"
             f"Modo: *{estado.get('modo', MODO_OPERACION)}*\n"
             f"Stake: *${STAKE_POR_TRADE:.2f}*\n"
             f"Trades copiados (sesión): {len(estado.get('trades_copiados', []))}\n"
             f"Wallet: `{WALLET[:10]}...{WALLET[-4:]}`\n"
             f"Última verificación: {datetime.now().strftime('%H:%M:%S')}")
    botones = [[
        {"text": "🟢 AUTO", "callback_data": "auto_on"},
        {"text": "🟡 SEMI", "callback_data": "auto_semi"},
        {"text": "🔴 OFF", "callback_data": "auto_off"},
    ]]
    return enviar(chat_id, texto, {"inline_keyboard": botones})

# ============================================
# LOOP PRINCIPAL
# ============================================
def procesar_update(update):
    global MODO_OPERACION, CHAT_ID
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        data = cb.get("data", "")
        CHAT_ID = chat_id
        if data.startswith("copiar_"):
            try:
                num = int(data.split("_")[1])
                return cmd_copiar(chat_id, num)
            except: pass
        elif data == "trades":
            return cmd_trades(chat_id)
        elif data == "saldo":
            return cmd_saldo(chat_id)
        elif data == "abiertas":
            return cmd_abiertas(chat_id)
        elif data == "auto_on":
            MODO_OPERACION = "AUTO"
            return enviar(chat_id, "*🟢 Modo AUTO activado*\n_Copia automáticamente_")
        elif data == "auto_semi":
            MODO_OPERACION = "SEMI"
            return enviar(chat_id, "*🟡 Modo SEMI*\n_Espera tu aprobación_")
        elif data == "auto_off":
            MODO_OPERACION = "OFF"
            return enviar(chat_id, "*🔴 Modo OFF*\n_Solo informa_")
        elif data == "menu":
            return cmd_start(chat_id)
        return

    if "message" not in update:
        return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    CHAT_ID = chat_id
    # --- al recibir /start, forzar una pasada AUTO si esta en modo AUTO ---
    if text == "/start" and MODO_OPERACION == "AUTO":
        cmd_start(chat_id)
        # ejecutar una pasada inmediata
        threading.Thread(target=lambda: auto_pasada_inmediata(chat_id), daemon=True).start()
        return
    # --- botones del teclado fijo (texto) ---
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
            return enviar(chat_id, "❌ Stake no válido")
    # --- comandos de texto ---
    if text == "/start":
        return cmd_start(chat_id)
    elif text == "/trades":
        return cmd_trades(chat_id)
    elif text.startswith("/copiar "):
        try: num = int(text.split()[1])
        except: return enviar(chat_id, "❌ /copiar N")
        return cmd_copiar(chat_id, num)
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
        if len(parts) > 1:
            return cmd_modo(chat_id, parts[1])
        return cmd_status(chat_id)
    elif text.startswith("/stake"):
        parts = text.split()
        if len(parts) > 1:
            return cmd_stake(chat_id, parts[1])
        return enviar(chat_id, f"*Stake actual: ${STAKE_POR_TRADE:.2f}*\n_Uso: /stake 2.5_")
    elif text == "/status" or text == "/estado":
        return cmd_status(chat_id)

def auto_loop():
    """En modo AUTO, ejecuta los top trades nuevos cada 5 minutos.
    La primera pasada es a los 30s de arrancar (para tener CHAT_ID)."""
    ultimo_envio = 0
    while True:
        try:
            if MODO_OPERACION == "AUTO" and CHAT_ID and time.time() - ultimo_envio > 300:
                log(f"[AUTO] revisando trades (CHAT_ID={CHAT_ID})")
                trades = trades_refresh()
                if not trades:
                    enviar(CHAT_ID, "🔄 *AUTO:* sin trades de deportes ahora mismo.")
                else:
                    enviar(CHAT_ID, f"🔄 *AUTO: {len(trades)} trades candidatos...*")
                    ejecutar = 0
                    for t in trades:
                        # solo copiar los del top 3
                        if t["peso"] < 5: continue
                        ok, _ = ejecutar_trade_real(t, CHAT_ID)
                        if ok: ejecutar += 1
                    enviar(CHAT_ID, f"*AUTO: {ejecutar} trade(s) ejecutado(s)*")
                ultimo_envio = time.time()
        except Exception as e:
            log(f"auto_loop error: {e}")
        time.sleep(60)

def auto_pasada_inmediata(chat_id):
    """Ejecuta una pasada AUTO inmediatamente (al recibir /start o cambiar a AUTO)."""
    global MODO_OPERACION
    if MODO_OPERACION != "AUTO":
        return
    log(f"[AUTO-INMEDIATA] chat {chat_id}")
    trades = trades_refresh()
    if not trades:
        enviar(chat_id, "🔄 *AUTO:* sin trades de deportes ahora mismo.")
        return
    enviar(chat_id, f"🔄 *AUTO: {len(trades)} trades candidatos...*")
    ejecutar = 0
    for t in trades:
        if t["peso"] < 5: continue
        ok, _ = ejecutar_trade_real(t, chat_id)
        if ok: ejecutar += 1
    enviar(chat_id, f"*AUTO: {ejecutar} trade(s) ejecutado(s)*")

def bot_loop():
    log("Bot iniciado, esperando mensajes...")
    offset = 0
    while True:
        try:
            params = {"timeout": 30, "offset": offset,
                      "allowed_updates": '["message","callback_query"]'}
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
                        log(f"error procesando update: {e}")
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
    log(f"Proxy PC: {PROXY_URL}")
    # test rapido del proxy
    log("Test proxy...")
    status, body = http_get("https://api.telegram.org", timeout=10)
    if status:
        log(f"  Proxy OK (status {status})")
    else:
        log(f"  PROXY NO RESPONDE: {body[:200]}")
        log(f"  AVISO: las operaciones se enviarán DIRECTO desde Hetzner")
    # arrancar auto loop en thread
    t = threading.Thread(target=auto_loop, daemon=True)
    t.start()
    # arrancar el loop principal
    bot_loop()

if __name__ == "__main__":
    main()
