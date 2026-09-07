#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLY COMBOS BOT v11.0 — COMBOS REALES (parlays multi-leg) via RFQ
=====================================================
Estrategia nueva (vs v7):
  1. Lee COMBOS ACTIVOS del endpoint publico: /v1/rfq/combo-markets
  2. Cada combo = 2-10 legs, paga si TODOS aciertan
  3. Cuota objetivo 1.20-2.50 (multiplicacion de legs)
  4. v11.0: /v1/rfq/combo-markets es un CATALOGO DE LEGS (no combos formados).
     Los combos reales se crean por la Requester API (RFQ):
       POST combos-rfq-gateway-requester-api /v1/requester/rfq/requests
       con 2-50 leg_position_ids → quote de market makers → firmar orden
       Exchange v3 (EIP-712) → accept (<5s) → poll hasta FILLED (tx_hash)
     Docs: https://docs.polymarket.com/trading/combos/requesters

FIX v10.9 (el SDK usa HTTPX, no requests):
  · inyectar_proxy_sdk() reemplaza helpers._http_client del SDK por un
    httpx.Client con proxy → TODAS las llamadas del SDK salen por el PC
  · enviar_orden() usa create_and_post_order() NATIVO del SDK (patrón
    bot de Elon): el SDK construye el envelope v2 {"order":..,"owner":..,
    "orderType":..} y firma headers L2 (POLY_SIGNATURE HMAC con creds
    derivadas). El POST manual v10.6-10.8 enviaba cuerpo+headers mal.

ARCHIVOS:
  · /root/poly_combos_token.txt       - Token Telegram
  · /opt/polymarket/combos_estado.json - Estado + historial
  · /etc/polymarket.env               - Credenciales Polymarket
"""
import os
import sys
import json
import time
import shutil
import base64
import random
import hashlib
import re as _re
import itertools
import subprocess
import urllib.request
import urllib.parse
import threading
import ssl
from datetime import datetime, timezone
from collections import defaultdict

LOG = []
def log(s):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {s}"
    print(line, flush=True)
    LOG.append(line)

# Anti-shadow
try:
    import importlib.util as _ilu
    _ilu.find_spec("copy")
except: pass


# ============================================
# CONFIGURACIÓN
# ============================================
TELEGRAM_TOKEN = None
WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"
HOST_CLOB = "https://clob.polymarket.com"
COMBOS_API = "https://combos-rfq-api.polymarket.com"
PROXY_URL = "http://100.83.57.99:8888"

ESTADO_FILE = "/opt/polymarket/combos_estado.json"
BACKUP_FILE = "/opt/polymarket/combos_estado.bak.json"
ENV_FILE = "/etc/polymarket.env"

# ============================================
# ESTRATEGIA v7 — Mercados activos
# ============================================
STAKE_POR_TRADE = 5.0
MIN_SHARES = 5.0  # CLOB pide minimo 5 shares por orden
CUOTA_MIN = 1.20
CUOTA_MAX = 2.50

# ---- v11.0: combos reales via RFQ (Requester API) ----
RFQ_GATEWAY = "https://combos-rfq-gateway-requester-api.polymarket.com"
RFQ_BASE = "/v1/requester/rfq"
EXCHANGE_V3 = "0xe3333700cA9d93003F00f0F71f8515005F6c00Aa"
DATA_API = "https://data-api.polymarket.com"
LEGS_POR_COMBO = (2, 3)    # combinar 2 legs (preferido) o 3
LEG_PRICE_MIN = 0.60       # yes_price mínimo por leg
LEG_PRICE_MAX = 0.96       # yes_price máximo por leg
LEG_VOL_MIN = 20000        # volumen mínimo ($) por leg
POOL_TOP_N = 30            # considerar top-N legs por volumen
MAX_COMBOS_DIA = 6         # tope de combos por día UTC
COOLDOWN_LEG_H = 6.0       # horas sin reutilizar un leg ya operado
RFQ_TIMEOUT_FILL_S = 45    # espera de FILLED tras aceptar
MAX_TRADES_SIMULTANEOS = 3
INTERVALO_AUTO_S = 300
PESO_MIN = 5
MAX_MERCADOS_A_REVISAR = 100  # limita para no saturar

MODO_OPERACION = "AUTO"
CHAT_ID = None
ULTIMO_TRADE_TS = 0

# Categorias de mercados que nos interesan (deportes)
DEPORTES_KEYWORDS = {
    # Deportes con sus titulos comunes
    "MLB": ["mlb", "yankees", "dodgers", "astros", "mets", "giants",
            "nationals", "cardinals", "padres", "braves", "cubs",
            "red sox", "rangers", "tigers", "guardians", "royals",
            "mariners", "angels", "athletics", "orioles", "rays",
            "blue jays", "twins", "white sox", "brewers", "reds",
            "pirates", "rockies", "diamondbacks", "marlins", "phillies"],
    "UFC": ["ufc", "mma", "fight night", "knockout", "submission",
            "featherweight", "lightweight", "heavyweight", "middleweight",
            "welterweight", "bantamweight", "flyweight"],
    "NFL": ["nfl", "quarterback", "touchdown", "super bowl", "chiefs",
            "cowboys", "eagles", "packers", "ravens", "bills",
            "49ers", "lions", "dolphins", "jets", "texans", "colts",
            "jaguars", "titans", "broncos", "raiders", "chargers",
            "browns", "bengals", "steelers", "saints", "falcons",
            "panthers", "bears", "vikings", "cardinals", "buccaneers",
            "rams", "seahawks", "commanders"],
    "NBA": ["nba", "lakers", "celtics", "warriors", "bulls", "heat",
            "knicks", "nets", "bucks", "76ers", "raptors", "nuggets",
            "suns", "mavericks", "clippers", "rockets", "spurs",
            "thunder", "trail blazers", "jazz", "kings", "pacers",
            "hawks", "hornets", "pistons", "magic", "cavaliers",
            "timberwolves", "grizzlies", "pelicans"],
    "Tennis": ["tennis", "atp", "wta", "us open", "wimbledon",
               "french open", "australian open", "roland garros",
               "djokovic", "alcaraz", "sinner", "medvedev", "zverev",
               "swiatek", "sabalenka", "rybakina", "gael monfils",
               "federer", "nadal"],
    "Soccer": ["soccer", "epl", "premier league", "la liga", "bundesliga",
               "serie a", "ligue 1", "champions league", "europa league",
               "world cup", "uefa", "real madrid", "barcelona", "atletico",
               "manchester", "liverpool", "chelsea", "arsenal", "tottenham",
               "bayern", "dortmund", "psg", "juventus", "milan", "inter",
               "napoli", "roma", "ajax"],
    "NCAAF": ["ncaaf", "college football", "alabama", "georgia", "lsu",
              "michigan", "ohio state", "texas", "oklahoma", "notre dame",
              "usc", "oregon"],
    "NCAAB": ["ncaab", "march madness", "kansas", "duke", "kentucky",
              "north carolina", "villanova", "uconn"],
}

EXCLUIR_KEYWORDS = ["xi jinping", "trump", "biden", "election", "president",
                    "congress", "senate", "democratic", "republican", "governor",
                    "bitcoin", "ethereum", "crypto", "nft", "fed",
                    "russia", "ukraine", "china", "iran", "israel", "who",
                    "nobel", "oscar", "grammy", "emmy", "box office",
                    "movie", "film", "album", "song", "taylor swift", "kanye"]


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
# PROXY
# ============================================
_proxy_ctx = None
def _proxy_opener():
    global _proxy_ctx
    if _proxy_ctx is None:
        _proxy_ctx = ssl.create_default_context()
        _proxy_ctx.check_hostname = False
        _proxy_ctx.verify_mode = ssl.CERT_NONE
    proxy_handler = urllib.request.ProxyHandler({
        "http": PROXY_URL, "https": PROXY_URL,
    })
    https_handler = urllib.request.HTTPSHandler(context=_proxy_ctx)
    return urllib.request.build_opener(proxy_handler, https_handler)

def http_get(url, timeout=20, headers=None):
    try:
        opener = _proxy_opener()
        hdrs = {"User-Agent": "Mozilla/5.0"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, headers=hdrs)
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        try:
            return e.code, e.read().decode('utf-8', errors='replace')
        except Exception:
            return e.code, str(e)
    except Exception as e:
        return None, str(e)

def http_post(url, data, headers=None, timeout=30):
    """POST con proxy. data es string (JSON ya serializado)."""
    try:
        opener = _proxy_opener()
        hdrs = {"User-Agent": "Mozilla/5.0"}
        if headers:
            hdrs.update(headers)
        req = urllib.request.Request(url, data=data.encode() if isinstance(data, str) else data,
                                     headers=hdrs, method="POST")
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace") if hasattr(e, "read") else str(e)
    except Exception as e:
        return None, str(e)


# ============================================
# TECLADO FIJO
# ============================================
TECLADO_FIJO = {
    "keyboard": [
        [{"text": "📋 Trades"}, {"text": "💰 Saldo"}, {"text": "📂 Abiertas"}],
        [{"text": "✅ Cerradas"}, {"text": "📊 Stats"}, {"text": "🏆 Top"}],
        [{"text": "🟢 AUTO"}, {"text": "🟡 SEMI"}, {"text": "🔴 OFF"}],
        [{"text": "💵 Stake $1"}, {"text": "💵 Stake $2"}, {"text": "💵 Stake $5"}],
    ],
    "resize_keyboard": True,
    "persistent": True,
}

def enviar(chat_id, texto, reply_markup=None):
    params = {"chat_id": chat_id, "text": texto, "parse_mode": "Markdown"}
    if reply_markup is None:
        params["reply_markup"] = json.dumps(TECLADO_FIJO)
    else:
        params["reply_markup"] = json.dumps(reply_markup)
    return telegram_api("sendMessage", params)


# ============================================
# CREDENCIALES
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
    """Replica el patrón del bot de Elon: crea el cliente simple
    con las env vars de proxy. Confia en que py_clob_client_v2
    respeta HTTP_PROXY/HTTPS_PROXY."""
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds
        from py_clob_client_v2 import SignatureTypeV2
    except ImportError:
        log("  py_clob_client_v2 no instalado")
        return None
    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    if not signer:
        log("  sin POLY_PRIVATE_KEY")
        return None
    # v10.9: inyectar proxy en el cliente httpx del SDK (no basta el env)
    inyectar_proxy_sdk()

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
        if "creds" not in kwargs:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
            except: pass
        return client
    except Exception as e:
        log(f"cliente error: {e}")
        return None


def inyectar_proxy_sdk(proxy_url=None):
    """v10.9: fuerza que py_clob_client_v2 salga por el proxy del PC.

    CLAVE: el SDK usa HTTPX (no requests). Su cliente se crea A NIVEL DE
    MODULO al importar:  helpers._http_client = httpx.Client(http2=True)
    → setear env vars despues de importar NO afecta al cliente ya creado,
    y los monkey-patch de v10.2-10.4 parcheaban requests (libreria que el
    SDK no usa). Aqui reemplazamos _http_client EXPLICITAMENTE por uno con
    proxy, cubriendo varias versiones de httpx. Devuelve True si OK."""
    proxy_url = proxy_url or PROXY_URL
    if not proxy_url:
        return False
    # env vars tambien (por si algo re-importa/crea clientes nuevos)
    for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
              "http_proxy", "https_proxy", "all_proxy"):
        os.environ[k] = proxy_url
    try:
        import httpx
        from py_clob_client_v2.http_helpers import helpers as _hh
        ultimo_err = None
        for kwargs in (
            {"http2": True, "proxy": proxy_url},                   # httpx >= 0.26
            {"http2": True, "proxies": {"all://": proxy_url}},     # httpx 0.23-0.25
            {"http2": True, "proxies": proxy_url},                 # httpx antiguos
            {"proxy": proxy_url},                                  # sin paquete h2
            {"proxies": {"all://": proxy_url}},
        ):
            try:
                _hh._http_client = httpx.Client(**kwargs)
                return True
            except (TypeError, ImportError) as e:
                ultimo_err = e
                continue
        log(f"  · aviso: proxy SDK no inyectado ({str(ultimo_err)[:80]})")
        return False
    except Exception as e:
        log(f"  · aviso: proxy SDK fallo ({str(e)[:80]})")
        return False


# ============================================
# v11.0 — COMBOS REALES via RFQ (Requester API)
# ============================================
# Flujo oficial (docs.polymarket.com/trading/combos/requesters):
#   1. POST {gateway}/v1/requester/rfq/requests   (leg_position_ids + notional)
#      → subasta entre market makers (400ms) → mejor quote (blended_price_e6)
#   2. Firmar orden Exchange v3 (EIP-712, contrato 0xe333...00Aa,
#      tokenId = yes_position_id del combo, maker = proxy wallet, signer = EOA,
#      signatureType=1 POLY_PROXY, builder/metadata = bytes32 cero)
#   3. POST .../requests/{rfq_id}/accept  (ventana ~5s desde el quote)
#   4. GET  .../requests/{rfq_id}  → poll hasta FILLED (tx_hash) / FAILED
# Headers L2 en cada petición: POLY_ADDRESS (EOA signer), POLY_API_KEY,
# POLY_PASSPHRASE, POLY_TIMESTAMP, POLY_SIGNATURE (HMAC-SHA256 del secret
# derivado sobre ts+METHOD+path+body_exacto, base64url).
_IDENTIDAD_RFQ = None

def obtener_identidad_rfq(forzar=False):
    """(creds CLOB derivadas, direccion EOA signer, proxy wallet, private key).
    Cacheado por proceso. Todo via proxy (httpx del SDK inyectado)."""
    global _IDENTIDAD_RFQ
    if _IDENTIDAD_RFQ is not None and not forzar:
        return _IDENTIDAD_RFQ
    env = cargar_env()
    pk = env.get("POLY_PRIVATE_KEY", "").strip()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()
    if not pk:
        log("  RFQ: sin POLY_PRIVATE_KEY")
        return None
    if not inyectar_proxy_sdk():
        log("  RFQ: aviso, proxy SDK no inyectado")
    from py_clob_client_v2.client import ClobClient
    from py_clob_client_v2 import SignatureTypeV2
    from eth_account import Account
    client = ClobClient(host=HOST_CLOB, chain_id=137, key=pk, funder=wallet,
                        signature_type=int(SignatureTypeV2.POLY_PROXY))
    creds = client.derive_api_key()
    signer_addr = Account.from_key(pk).address
    _IDENTIDAD_RFQ = (creds, signer_addr, wallet, pk)
    log(f"  RFQ: identidad lista (signer {signer_addr[:10]}... maker {wallet[:10]}...)")
    return _IDENTIDAD_RFQ


def l2_headers_rfq(method, path, body_str, creds, signer_addr):
    """Headers L2 para el gateway RFQ (mismo esquema HMAC que el CLOB)."""
    from py_clob_client_v2.signing.hmac import build_hmac_signature
    ts = str(int(time.time()))
    sig = build_hmac_signature(creds.api_secret, ts, method.upper(), path, body_str)
    return {
        "Content-Type": "application/json",
        "POLY_ADDRESS": signer_addr,
        "POLY_SIGNATURE": sig,
        "POLY_TIMESTAMP": ts,
        "POLY_API_KEY": creds.api_key,
        "POLY_PASSPHRASE": creds.api_passphrase,
    }


def crear_rfq(leg_position_ids, notional_usd, identidad):
    creds, signer_addr, wallet, pk = identidad
    body = {
        "signer_address": signer_addr,
        "maker_address": wallet,
        "signature_type": 1,
        "leg_position_ids": [str(x) for x in leg_position_ids],
        "direction": "BUY",
        "side": "YES",
        "requested_size": {"unit": "notional",
                           "value_e6": str(int(round(notional_usd * 1000000)))},
    }
    body_str = json.dumps(body, separators=(",", ":"))
    path = f"{RFQ_BASE}/requests"
    headers = l2_headers_rfq("POST", path, body_str, creds, signer_addr)
    return http_post(RFQ_GATEWAY + path, body_str, headers, timeout=20)


def firmar_orden_v3(req, quote, identidad):
    """Firma EIP-712 de la orden Exchange v3 para aceptar el quote."""
    creds, signer_addr, wallet, pk = identidad
    from eth_account import Account
    from eth_account.messages import encode_typed_data
    msg = {
        "salt": str(random.randint(1, 2**249)),
        "maker": wallet,
        "signer": signer_addr,
        "tokenId": str(req.get("yes_position_id")),
        "makerAmount": str(quote.get("maker_amount_e6")),
        "takerAmount": str(quote.get("taker_amount_e6")),
        "side": 0,
        "signatureType": 1,
        "timestamp": str(int(time.time())),
        "metadata": "0x" + "00" * 32,
        "builder": "0x" + "00" * 32,
    }
    typed = {
        "domain": {"name": "Polymarket CTF Exchange", "version": "3",
                   "chainId": 137, "verifyingContract": EXCHANGE_V3},
        "types": {
            "EIP712Domain": [
                {"name": "name", "type": "string"},
                {"name": "version", "type": "string"},
                {"name": "chainId", "type": "uint256"},
                {"name": "verifyingContract", "type": "address"},
            ],
            "Order": [
                {"name": "salt", "type": "uint256"},
                {"name": "maker", "type": "address"},
                {"name": "signer", "type": "address"},
                {"name": "tokenId", "type": "uint256"},
                {"name": "makerAmount", "type": "uint256"},
                {"name": "takerAmount", "type": "uint256"},
                {"name": "side", "type": "uint8"},
                {"name": "signatureType", "type": "uint8"},
                {"name": "timestamp", "type": "uint256"},
                {"name": "metadata", "type": "bytes32"},
                {"name": "builder", "type": "bytes32"},
            ],
        },
        "primaryType": "Order",
        "message": {**msg,
                    "salt": int(msg["salt"]),
                    "tokenId": int(msg["tokenId"]),
                    "makerAmount": int(msg["makerAmount"]),
                    "takerAmount": int(msg["takerAmount"]),
                    "timestamp": int(msg["timestamp"])},
    }
    acct = Account.from_key(pk)
    firmado = acct.sign_message(encode_typed_data(full_message=typed))
    sig = bytes(firmado.signature)
    if sig[64] in (0, 1):           # normalizar v a 27/28
        sig = sig[:64] + bytes([sig[64] + 27])
    msg["signature"] = "0x" + sig.hex()
    return msg


def aceptar_rfq(rfq_id, quote_id, signed_order, identidad):
    creds, signer_addr, wallet, pk = identidad
    body = {"quote_id": str(quote_id), "signed_order": signed_order}
    body_str = json.dumps(body, separators=(",", ":"))
    path = f"{RFQ_BASE}/requests/{rfq_id}/accept"
    headers = l2_headers_rfq("POST", path, body_str, creds, signer_addr)
    return http_post(RFQ_GATEWAY + path, body_str, headers, timeout=20)


def consultar_rfq(rfq_id, identidad):
    creds, signer_addr, wallet, pk = identidad
    path = f"{RFQ_BASE}/requests/{rfq_id}"
    headers = l2_headers_rfq("GET", path, None, creds, signer_addr)
    return http_get(RFQ_GATEWAY + path, timeout=15, headers=headers)


def esperar_fill(rfq_id, identidad, timeout_s=RFQ_TIMEOUT_FILL_S):
    """Poll del estado del RFQ. FILLED/CONFIRMED = éxito; FAILED/EXPIRED/
    CANCELED = terminal; timeout local NO es fallo (seguir consultando luego)."""
    fin = time.time() + timeout_s
    ultimo = {}
    while time.time() < fin:
        status, resp = consultar_rfq(rfq_id, identidad)
        try:
            ultimo = json.loads(resp)
        except Exception:
            ultimo = {"status": f"http_{status}"}
        st = ultimo.get("status", "")
        if st in ("FILLED", "CONFIRMED"):
            return st, ultimo
        if st in ("FAILED", "EXPIRED", "CANCELED"):
            return st, ultimo
        time.sleep(3)
    return ultimo.get("status") or "TIMEOUT_LOCAL", ultimo


# ---- seleccion de legs y deduplicacion ----

def evento_de(slug):
    """Clave de evento: slug hasta la fecha incluida (mlb-laa-bos-2026-09-07-total-8pt5
    y mlb-laa-bos-2026-09-07 son el MISMO evento → no combinar, correlacionados)."""
    m = _re.match(r"^(.*?\d{4}-\d{2}-\d{2})", slug or "")
    if m:
        return m.group(1)
    partes = (slug or "").split("-")
    return "-".join(partes[:-1]) if len(partes) > 1 else (slug or "")


def fecha_slug_ok(slug):
    """Descarta legs con fecha pasada en el slug (partidos ya jugados)."""
    m = _re.search(r"(\d{4}-\d{2}-\d{2})", slug or "")
    if not m:
        return True
    try:
        d = datetime.strptime(m.group(1), "%Y-%m-%d").date()
    except Exception:
        return True
    return d >= datetime.now(timezone.utc).date()


def huella_combo(pids):
    return hashlib.sha1("|".join(sorted(str(x) for x in pids)).encode()).hexdigest()[:16]


def leg_reciente(estado, pid):
    ts = estado.get("combos_rfq", {}).get("legs", {}).get(str(pid))
    if not ts:
        return False
    try:
        t = datetime.fromisoformat(ts)
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
    except Exception:
        return False
    return (datetime.now(timezone.utc) - t).total_seconds() / 3600.0 < COOLDOWN_LEG_H


def combos_hoy_count(estado):
    hoy = datetime.now(timezone.utc).date().isoformat()
    return sum(1 for r in estado.get("combos_rfq", {}).get("historial", [])
               if str(r.get("fecha", "")).startswith(hoy))


def seleccionar_combo(legs, estado):
    """Elige la mejor combinación de 2-3 legs (eventos distintos, cuota estimada
    en rango, sin legs en cooldown, combo no repetido). Top por volumen."""
    if combos_hoy_count(estado) >= MAX_COMBOS_DIA:
        log(f"  tope diario alcanzado ({MAX_COMBOS_DIA} combos)")
        return None
    pool = []
    for c in legs:
        p = c.get("yes_price") or 0
        if not (LEG_PRICE_MIN <= p <= LEG_PRICE_MAX):
            continue
        if (c.get("volumen") or 0) < LEG_VOL_MIN:
            continue
        if c.get("pending"):
            continue
        if not fecha_slug_ok(c.get("slug")):
            continue
        if not c.get("yes_token"):
            continue
        if leg_reciente(estado, c.get("yes_token")):
            continue
        pool.append(c)
    pool.sort(key=lambda x: -(x.get("volumen") or 0))
    pool = pool[:POOL_TOP_N]
    huellas = estado.get("combos_rfq", {}).get("huellas", {})
    candidatos = []
    for n in range(LEGS_POR_COMBO[0], LEGS_POR_COMBO[1] + 1):
        if n > len(pool):
            break
        for sel in itertools.combinations(pool, n):
            eventos = {evento_de(c.get("slug")) for c in sel}
            if len(eventos) != n:
                continue
            pids = [str(c["yes_token"]) for c in sel]
            if huella_combo(pids) in huellas:
                continue
            prod = 1.0
            for c in sel:
                prod *= c.get("yes_price") or 0
            cuota = round(1 / prod, 2) if prod > 0 else 0
            if not (CUOTA_MIN <= cuota <= CUOTA_MAX):
                continue
            vol_min = min(c.get("volumen") or 0 for c in sel)
            candidatos.append((vol_min, cuota, list(sel)))
        if candidatos:
            break  # preferir combos de 2 legs
    if not candidatos:
        return None
    candidatos.sort(key=lambda x: -x[0])
    return candidatos[0][2]


def ejecutar_combo_rfq(sel, chat_id=None, dry_run=False):
    """Flujo RFQ completo: crear → validar cuota real → firmar v3 → aceptar
    → esperar FILLED → registrar + notificar. dry_run=True NO acepta (gratis)."""
    pids = [str(c["yes_token"]) for c in sel]
    titulo = " + ".join((c.get("question") or "")[:38] for c in sel)
    prod = 1.0
    for c in sel:
        prod *= c.get("yes_price") or 0
    cuota_est = round(1 / prod, 2) if prod > 0 else 0
    log(f"[COMBO] {len(sel)} legs · cuota est. {cuota_est} · stake ${STAKE_POR_TRADE}")
    for c in sel:
        log(f"  · {(c.get('question') or '')[:56]} (p={c.get('yes_price'):.2f} vol=${(c.get('volumen') or 0)/1000:.0f}k)")
    if chat_id:
        enviar(chat_id, f"🎰 *COMBO {len(sel)} LEGS* (cuota est. ~{cuota_est})\n" +
               "\n".join(f"· {(c.get('question') or '')[:55]} (p={c.get('yes_price'):.2f})" for c in sel))
    identidad = obtener_identidad_rfq()
    if not identidad:
        return False, "sin_identidad"
    status, resp = crear_rfq(pids, STAKE_POR_TRADE, identidad)
    log(f"  RFQ create -> {status} {str(resp)[:160]}")
    try:
        d = json.loads(resp)
    except Exception:
        d = {}
    if status != 200 or not isinstance(d, dict) or not d:
        return False, f"rfq_http_{status}:{str(resp)[:150]}"
    err = d.get("error")
    if d.get("status") == "FAILED" or err:
        code = err.get("code") if isinstance(err, dict) else str(err)
        return False, f"rfq_{code or 'failed'}"
    quote = d.get("quote") or {}
    req = d.get("request") or {}
    rfq_id = d.get("rfq_id")
    quote_id = quote.get("quote_id")
    try:
        blended = int(quote.get("blended_price_e6", 0)) / 1e6
        shares = int(quote.get("net_receive_e6", 0)) / 1e6
        total_req = int(quote.get("total_required_e6", 0)) / 1e6
    except Exception:
        return False, f"quote_ilegible:{str(quote)[:120]}"
    cuota_real = round(1 / blended, 2) if blended > 0 else 0
    log(f"  quote: cuota={cuota_real} blended={blended:.3f} shares={shares:.2f} total=${total_req:.2f}")
    if dry_run:
        log("  dry-run: quote OK, NO se acepta (expira solo, coste 0)")
        if chat_id:
            enviar(chat_id, f"🧪 *TEST COMBO OK*\n💱 Cuota real: *{cuota_real}* · {shares:.2f} shares · ${total_req:.2f}\nNo aceptado (coste $0). rfq_id `{str(rfq_id)[:18]}`")
        return True, {"dry_run": True, "cuota": cuota_real, "rfq_id": rfq_id}
    if not (CUOTA_MIN <= cuota_real <= CUOTA_MAX):
        log(f"  NO acepto: cuota real {cuota_real} fuera de [{CUOTA_MIN}-{CUOTA_MAX}]")
        if chat_id:
            enviar(chat_id, f"⚠️ Cuota real {cuota_real} fuera de rango — quote NO aceptado ($0)")
        return False, f"cuota_real_{cuota_real}_fuera"
    # firmar + aceptar RÁPIDO (ventana ~5s)
    try:
        signed = firmar_orden_v3(req, quote, identidad)
    except Exception as e:
        log(f"  firma v3 error: {e}")
        return False, f"firma_v3:{str(e)[:150]}"
    status, resp = aceptar_rfq(rfq_id, quote_id, signed, identidad)
    log(f"  RFQ accept -> {status} {str(resp)[:160]}")
    if status != 200:
        return False, f"accept_http_{status}:{str(resp)[:150]}"
    try:
        da = json.loads(resp)
    except Exception:
        da = {}
    if isinstance(da, dict) and da.get("status") == "FAILED":
        err = da.get("error") or {}
        return False, f"accept_{err.get('code') if isinstance(err, dict) else err}"
    st, ultimo = esperar_fill(rfq_id, identidad)
    tx = ultimo.get("tx_hash", "") if isinstance(ultimo, dict) else ""
    log(f"  RFQ status final: {st} tx={str(tx)[:26]}")
    ok = st in ("FILLED", "CONFIRMED")
    pendiente = st in ("EXECUTING", "MINED", "RETRYING", "AWAITING_MAKER_CONFIRMATION", "TIMEOUT_LOCAL")
    registro = {
        "tipo": "combo_rfq",
        "copiado_en": datetime.now(timezone.utc).isoformat(),
        "question": titulo,
        "n_legs": len(sel),
        "legs": [{"question": c.get("question"), "slug": c.get("slug"),
                  "yes_price": c.get("yes_price"), "position_id": str(c.get("yes_token")),
                  "condition_id": c.get("condition_id")} for c in sel],
        "rfq_id": rfq_id,
        "quote_id": quote_id,
        "combo_condition_id": req.get("condition_id"),
        "combo_yes_position_id": req.get("yes_position_id"),
        "precio_ejecutado": blended,
        "cuota_ejecutada": cuota_real,
        "cuota_estimada": cuota_est,
        "size_shares": round(shares, 2),
        "stake_dolares": round(total_req, 2),
        "order_id": rfq_id,
        "tx_hash": tx,
        "status": "filled" if ok else ("pendiente" if pendiente else "fallido"),
        "estado_rfq": st,
        "slug": "", "market_id": "", "condition_id": req.get("condition_id", ""),
        "real_token": req.get("yes_position_id"),
        "volumen": min((c.get("volumen") or 0) for c in sel),
        "tags": ["combo-rfq"],
    }
    estado = cargar_estado()
    rfq = estado.setdefault("combos_rfq", {"huellas": {}, "legs": {}, "historial": []})
    rfq.setdefault("huellas", {})
    rfq.setdefault("legs", {})
    rfq.setdefault("historial", [])
    ahora_iso = datetime.now(timezone.utc).isoformat()
    rfq["huellas"][huella_combo(pids)] = ahora_iso
    for pid in pids:
        rfq["legs"][pid] = ahora_iso
    rfq["historial"].append({"fecha": ahora_iso, "rfq_id": rfq_id, "status": registro["status"],
                             "cuota": cuota_real, "stake": registro["stake_dolares"],
                             "legs": titulo})
    estado.setdefault("trades_copiados", []).append(registro)
    guardar_estado(estado)
    if chat_id:
        if ok:
            enviar(chat_id, f"✅ *COMBO REAL LLENADO* 🎉\n📌 {titulo[:80]}\n"
                            f"💵 {shares:.2f} shares @ {blended:.3f} (cuota {cuota_real})\n"
                            f"💰 ${total_req:.2f}\n🔗 tx `{str(tx)[:24]}`")
        elif pendiente:
            enviar(chat_id, f"⏳ *COMBO ACEPTADO, esperando fill* ({st})\n📌 {titulo[:70]}\n"
                            f"Consulta /fills para confirmar (timeout local ≠ fallo)")
        else:
            enviar(chat_id, f"❌ *COMBO {st}*\n📌 {titulo[:70]}\nrfq `{str(rfq_id)[:18]}`")
    return ok, {"oid": rfq_id, "status": st, "cuota": cuota_real}


def cmd_testcombo(chat_id):
    """🧪 RFQ completo SIN aceptar: valida el pipeline a coste cero."""
    def _run():
        try:
            legs = listar_combos()
            if not legs:
                return enviar(chat_id, "🧪 Sin legs disponibles ahora")
            sel = seleccionar_combo(legs, cargar_estado())
            if not sel:
                return enviar(chat_id, "🧪 No hay combos viables ahora (cuota/cooldown/tope diario/eventos)")
            ejecutar_combo_rfq(sel, chat_id, dry_run=True)
        except Exception as e:
            log(f"testcombo error: {e}")
            enviar(chat_id, f"🧪 Error: {str(e)[:150]}")
    threading.Thread(target=_run, daemon=True).start()
    return enviar(chat_id, "🧪 Pidiendo quote de un combo real (sin aceptar, $0)...")


def cmd_fills(chat_id):
    """🔎 Rellena estados pendientes de RFQ + reconcilia fills con data-api."""
    def _run():
        try:
            lineas = []
            estado = cargar_estado()
            cambiados = 0
            identidad = None
            for r in estado.get("trades_copiados", []):
                if r.get("tipo") == "combo_rfq" and r.get("status") == "pendiente" and r.get("rfq_id"):
                    if identidad is None:
                        identidad = obtener_identidad_rfq()
                    if not identidad:
                        break
                    st, ult = esperar_fill(r["rfq_id"], identidad, timeout_s=6)
                    if st in ("FILLED", "CONFIRMED", "FAILED", "EXPIRED", "CANCELED"):
                        r["status"] = "filled" if st in ("FILLED", "CONFIRMED") else "fallido"
                        r["estado_rfq"] = st
                        r["tx_hash"] = ult.get("tx_hash", r.get("tx_hash", ""))
                        cambiados += 1
            if cambiados:
                guardar_estado(estado)
                lineas.append(f"♻️ {cambiados} combo(s) pendiente(s) actualizado(s)")
            url = f"{DATA_API}/trades?user={WALLET}&limit=40"
            status, body = http_get(url, timeout=20)
            try:
                trades = json.loads(body) if status == 200 else []
            except Exception:
                trades = []
            grupos = {}
            for t in trades:
                ts = t.get("timestamp") or 0
                try:
                    dia = datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat()
                except Exception:
                    dia = "?"
                k = (dia, (t.get("title") or "?")[:42])
                g = grupos.setdefault(k, {"n": 0, "usd": 0.0, "sh": 0.0})
                g["n"] += 1
                g["usd"] += float(t.get("size") or 0) * float(t.get("price") or 0)
                g["sh"] += float(t.get("size") or 0)
            ultimos = sorted(grupos.items(), key=lambda kv: kv[0][0], reverse=True)[:10]
            if ultimos:
                lineas.append("🔎 *Fills en la wallet (data-api)*")
                for (dia, tit), g in ultimos:
                    lineas.append(f"`{dia[5:]}` {tit} — {g['n']}x {g['sh']:.1f}sh ≈ ${g['usd']:.2f}")
            hoy = datetime.now(timezone.utc).date().isoformat()
            combos_h = [r for r in estado.get("combos_rfq", {}).get("historial", [])
                        if str(r.get("fecha", "")).startswith(hoy)]
            if combos_h:
                lineas.append(f"\n🎰 *Combos RFQ hoy*: {len(combos_h)}")
                for c in combos_h[-5:]:
                    lineas.append(f"· {c.get('status')} cuota {c.get('cuota')} ${c.get('stake')}")
            if not lineas:
                lineas = ["Sin fills encontrados"]
            enviar(chat_id, "\n".join(lineas))
        except Exception as e:
            log(f"fills error: {e}")
            enviar(chat_id, f"🔎 Error: {str(e)[:150]}")
    threading.Thread(target=_run, daemon=True).start()
    return enviar(chat_id, "🔎 Consultando fills...")


# ============================================
# MERCADOS ACTIVOS EN TIEMPO REAL
# ============================================
def detectar_deporte_por_titulo(titulo):
    """Detecta el deporte a partir del titulo del mercado."""
    t = titulo.lower()
    for deporte, kws in DEPORTES_KEYWORDS.items():
        if any(k in t for k in kws):
            return deporte
    return None

def listar_combos():
    """v11: el endpoint /v1/rfq/combo-markets devuelve el CATALOGO DE LEGS
    (mercados simples 'combinables'), NO combos formados. Cada entrada es una
    posible pata; los combos reales se construyen por RFQ (seccion v11)."""
    combos = []
    cursor = ""
    paginas = 0
    while paginas < 5:  # hasta 5 paginas
        url = f"{COMBOS_API}/v1/rfq/combo-markets?limit=50"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"
        status, body = http_get(url, timeout=15)
        if status != 200:
            log(f"  combo-markets status {status}")
            break
        try:
            data = json.loads(body)
        except:
            break
        batch = data.get("markets", [])
        if not batch:
            break
        for m in batch:
            titulo = m.get("title") or m.get("question") or ""
            tags = m.get("tags") or []
            slug = m.get("slug", "")
            # tags son listas: ["sports", "soccer", "games"]
            # Filtrar solo deportes
            tags_str = " ".join(tags).lower() if isinstance(tags, list) else str(tags).lower()
            es_deporte = any(t in tags_str for t in ["sport", "soccer", "football", "basketball",
                                                      "baseball", "tennis", "mma", "ufc",
                                                      "cricket", "esports", "nfl", "nba", "mlb",
                                                      "ncaaf", "ncaab", "wnba", "nhl", "fight"])
            if not es_deporte:
                continue
            # outcome_prices = [precio_yes, precio_no]
            try:
                prices = m.get("outcome_prices", [])
                if isinstance(prices, str):
                    prices = json.loads(prices)
            except:
                prices = []
            if not prices:
                continue
            try:
                yes_price = float(prices[0])
            except:
                continue
            if not (0.02 <= yes_price <= 0.97):
                continue
            # position_ids = [token_yes, token_no]
            try:
                tokens = m.get("position_ids", [])
                if isinstance(tokens, str):
                    tokens = json.loads(tokens)
            except:
                tokens = []
            if not tokens or len(tokens) < 1:
                continue
            vol = float(m.get("volume") or 0)
            market_id = m.get("id", "")
            condition_id = m.get("condition_id", "")
            combos.append({
                "market_id": market_id,
                "condition_id": condition_id,
                "question": titulo,
                "slug": slug,
                "yes_token": str(tokens[0]),  # position_id del endpoint combos (NO tradable)
                "no_token": str(tokens[1]) if len(tokens) > 1 else str(tokens[0]),
                "yes_price": yes_price,
                "cuota": round(1/yes_price, 2) if yes_price > 0 else 0,
                "volumen": vol,
                "pending": bool(m.get("pending")),
                "tags": tags,
                # Estos se llenan despues via /markets/{condition_id}
                "real_token": None,
            })
        log(f"  pagina {paginas + 1}: +{len(batch)} mercados, {len(combos)} legs de deportes")
        # siguiente pagina
        cursor = data.get("next_cursor", "")
        if not cursor:
            break
        paginas += 1
    combos.sort(key=lambda x: -x["volumen"])
    return combos


def listar_mercados_deportes():
    """[LEGACY v7] Lee mercados individuales. Mantenido como fallback."""
    return listar_combos()  # en v9 todo es combos

def get_precio_actual(token_id):
    try:
        url = f"{HOST_CLOB}/midpoint?token_id={token_id}"
        status, body = http_get(url, timeout=10)
        if status == 200:
            data = json.loads(body)
            mid = data.get("mid") or data.get("midpoint")
            if mid:
                return float(mid)
        url = f"{HOST_CLOB}/book?token_id={token_id}"
        status, body = http_get(url, timeout=10)
        if status == 200:
            data = json.loads(body)
            if data.get("asks"):
                return float(data["asks"][0]["price"])
            if data.get("bids"):
                return float(data["bids"][0]["price"])
    except: pass
    return None


def resolver_token_real(condition_id):
    """v10: dado el condition_id de un combo, devuelve el token_id real
    tradable en el CLOB. None si falla."""
    try:
        url = f"{HOST_CLOB}/markets/{condition_id}"
        status, body = http_get(url, timeout=10)
        if status != 200:
            return None
        data = json.loads(body)
        if not data.get("accepting_orders") or data.get("closed"):
            return None
        tokens = data.get("tokens", [])
        if not tokens:
            return None
        # tokens[0] = YES, tokens[1] = NO
        yes = tokens[0]
        return yes.get("token_id")
    except Exception as e:
        log(f"  resolver_token_real err: {e}")
        return None


# ============================================
# EJECUCIÓN DE TRADES
# ============================================
def enviar_orden(token_id, precio, stake_dolares):
    """v10.9: create_and_post_order() NATIVO del SDK (patrón bot de Elon)
    con el cliente httpx del SDK forzado a salir por el proxy del PC."""
    global ULTIMO_TRADE_TS
    ahora = time.time()
    if ahora - ULTIMO_TRADE_TS < 10:
        return False, "throttle"
    size_shares = round(stake_dolares / precio, 2)
    if size_shares < MIN_SHARES:
        stake_necesario = MIN_SHARES * precio * 1.01
        return False, f"size_{size_shares}_necesita_stake_${stake_necesario:.2f}"

    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    api_key = env.get("POLY_API_KEY", "").strip()
    api_secret = env.get("POLY_API_SECRET", "").strip()
    api_passphrase = env.get("POLY_API_PASSPHRASE", "").strip()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET).strip()
    if not signer:
        return False, "sin_credenciales"

    # 1) v10.9: cliente SDK con proxy INYECTADO en httpx + envío NATIVO.
    #    El POST manual de v10.6-10.8 estaba doblemente roto:
    #      a) el cuerpo no es el signed order crudo: la API v2 espera el
    #         envelope {"order":{...},"owner":...,"orderType":...} que
    #         construye order_to_json_v2() del SDK
    #      b) los headers L2 iban vacíos (api_key/passphrase del env no
    #         existen) y faltaba POLY_SIGNATURE (HMAC con el secret
    #         derivado, calculado sobre el cuerpo EXACTO serializado)
    #    Con create_and_post_order() el SDK hace todo eso solo; nosotros
    #    solo garantizamos que su httpx salga por el proxy del PC.
    try:
        proxy_ok = inyectar_proxy_sdk()
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, OrderArgs
        from py_clob_client_v2 import SignatureTypeV2
        # Igual que el bot de Elon: si no hay creds, las derivamos de la private key
        kwargs_client = {
            "key": signer,
            "funder": wallet,
            "signature_type": int(SignatureTypeV2.POLY_PROXY) if wallet else int(SignatureTypeV2.EOA),
        }
        if api_key and api_secret and api_passphrase:
            kwargs_client["creds"] = ApiCreds(api_key, api_secret, api_passphrase)
        client = ClobClient(host=HOST_CLOB, chain_id=137, **kwargs_client)
        if "creds" not in kwargs_client:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
                log(f"  · Creds derivadas automaticamente (proxy_sdk={'OK' if proxy_ok else 'FALLO'})")
            except Exception as e:
                return False, f"derive_error:{str(e)[:200]}"

        order_args = OrderArgs(token_id=token_id, price=precio,
                                size=size_shares, side="BUY")

        # 2) v10.9: POST nativo del SDK (patrón exacto del bot de Elon)
        log(f"  enviando orden via SDK (httpx+proxy)...")
        resp = client.create_and_post_order(order_args)
        if isinstance(resp, str):
            try:
                resp = json.loads(resp)
            except Exception:
                pass
        log(f"  SDK resp: {json.dumps(resp, default=str)[:220] if isinstance(resp, (dict, list)) else str(resp)[:220]}")
        if isinstance(resp, dict):
            if resp.get("success") is True or resp.get("orderID") or resp.get("orderId"):
                oid = resp.get("orderID") or resp.get("orderId") or resp.get("id") or "?"
                ULTIMO_TRADE_TS = ahora
                return True, {"oid": oid, "size": size_shares, "precio": precio,
                              "status": resp.get("status", "?")}
            err = resp.get("errorMsg") or resp.get("error") or str(resp)[:150]
            return False, f"api_rechazo:{str(err)[:200]}"
        return False, f"resp_desconocida:{str(resp)[:150]}"
    except Exception as e:
        # PolyApiException trae status_code y error_msg reales de la API
        status = getattr(e, "status_code", None)
        errmsg = getattr(e, "error_msg", None)
        if status is not None or errmsg is not None:
            return False, f"PolyApi[{status}]:{str(errmsg)[:200]}"
        return False, f"sdk_error:{str(e)[:200]}"

def ejecutar_trade(mercado, chat_id=None):
    """Ejecuta un trade en un mercado activo (v10: combo con token real)."""
    titulo = mercado["question"]
    log(f"[TRADE] {titulo[:60]}")
    # v10: resolver token real desde condition_id
    real_token = mercado.get("real_token")
    if not real_token:
        condition_id = mercado.get("condition_id", "")
        if not condition_id:
            log(f"  SKIP: no condition_id")
            return False, "no_condition_id"
        real_token = resolver_token_real(condition_id)
        if not real_token:
            log(f"  SKIP: no pude resolver token real de {condition_id[:10]}...")
            return False, "token_real_no_resuelto"
        mercado["real_token"] = real_token
        log(f"  token real resuelto: {real_token[:18]}...")
    # re-leer precio actual con el token real
    precio = get_precio_actual(real_token)
    if not precio or precio <= 0 or precio >= 1:
        log(f"  SKIP: precio no disponible")
        return False, "precio_no_disponible"
    if not (0.02 <= precio <= 0.95):
        log(f"  SKIP: precio {precio} fuera de mercado activo")
        return False, "mercado_inactivo"
    cuota = round(1/precio, 2)
    if not (CUOTA_MIN <= cuota <= CUOTA_MAX):
        log(f"  SKIP: cuota {cuota} fuera de [{CUOTA_MIN}-{CUOTA_MAX}]")
        return False, f"cuota_{cuota}_fuera"
    # enviar
    log(f"  precio={precio:.3f} cuota={cuota:.2f} stake=${STAKE_POR_TRADE}")
    ok, resultado = enviar_orden(real_token, precio, STAKE_POR_TRADE)
    if not ok:
        log(f"  ERROR: {resultado}")
        return False, resultado
    # guardar
    registro = {
        "tipo": "combo",
        "copiado_en": datetime.now().isoformat(),
        "question": titulo,
        "slug": mercado.get("slug"),
        "market_id": mercado.get("market_id", ""),
        "condition_id": mercado.get("condition_id", ""),
        "real_token": real_token,
        "precio_ejecutado": precio,
        "cuota_ejecutada": cuota,
        "size_shares": resultado["size"],
        "stake_dolares": STAKE_POR_TRADE,
        "order_id": resultado["oid"],
        "volumen": mercado.get("volumen", 0),
        "tags": mercado.get("tags", []),
        "status": "ejecutado",
    }
    estado = cargar_estado()
    estado["trades_copiados"].append(registro)
    guardar_estado(estado)
    if chat_id:
        tags_str = ", ".join(mercado.get("tags", [])[:3])
        enviar(chat_id, f"✅ *COMBO EJECUTADO*\n"
                      f"📌 {titulo[:60]}\n"
                      f"💵 {resultado['size']} shares @ {precio:.2f} (cuota {cuota:.2f})\n"
                      f"💰 Stake: ${STAKE_POR_TRADE}\n"
                      f"🏷 {tags_str}\n"
                      f"📊 Vol: ${mercado.get('volumen', 0):.0f}\n"
                      f"🆔 `{str(resultado['oid'])[:18]}`")
    return True, "ok"


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
# ESTADÍSTICAS
# ============================================
def calcular_stats():
    estado = cargar_estado()
    copiados = estado.get("trades_copiados", [])
    historial = estado.get("historial", [])
    s = {
        "total": len(copiados), "wins": 0, "losses": 0,
        "pnl": 0.0, "stake": 0.0, "mejor": None, "peor": None,
    }
    for op in copiados + historial:
        pnl = op.get("pnl")
        stake = op.get("stake_dolares") or op.get("stake_total") or 0
        if pnl is not None:
            s["pnl"] += pnl
            s["stake"] += stake
            if pnl > 0: s["wins"] += 1
            else: s["losses"] += 1
            if s["mejor"] is None or pnl > s["mejor"].get("pnl", -9999):
                s["mejor"] = op
            if s["peor"] is None or pnl < s["peor"].get("pnl", 9999):
                s["peor"] = op
    return s


# ============================================
# COMANDOS
# ============================================
def cmd_start(chat_id):
    texto = (f"🤖 *POLY COMBOS BOT v11.0*\n\n"
             f"Modo: *{MODO_OPERACION}*\n"
             f"Stake: *${STAKE_POR_TRADE}*\n"
             f"Cuota: *{CUOTA_MIN}-{CUOTA_MAX}*\n\n"
             f"📌 *Estrategia v11* (COMBOS REALES):\n"
             f"   · Construye parlays de 2-3 legs deportivos\n"
             f"   · Pide quote a market makers (RFQ oficial)\n"
             f"   · Solo acepta si la cuota real entra en rango\n"
             f"   · Fill confirmado con tx_hash (FILLED)\n"
             f"   · Sin repetir legs (cooldown {COOLDOWN_LEG_H:.0f}h) · max {MAX_COMBOS_DIA}/dia\n\n"
             f"🧪 /testcombo — prueba gratis (quote sin aceptar)\n"
             f"🔎 /fills — fills reales de la wallet\n"
             f"📊 /stats — estadisticas")
    return enviar(chat_id, texto)

def cmd_trades(chat_id):
    combos = listar_combos()
    if not combos:
        return enviar(chat_id, "❌ No hay combos activos ahora mismo.")
    # filtrar por cuota
    filtrados = [m for m in combos if CUOTA_MIN <= m["cuota"] <= CUOTA_MAX]
    if not filtrados:
        texto = f"📋 *COMBOS ACTIVOS ({len(combos)})*\n_Ninguno en cuota {CUOTA_MIN}-{CUOTA_MAX}_\n\n"
        for m in combos[:8]:
            tags_str = ", ".join(m.get("tags", [])[:3])
            texto += f"· {m['question'][:50]} (cuota {m['cuota']:.2f}) [{tags_str}]\n"
        return enviar(chat_id, texto)
    texto = f"📋 *COMBOS EN RANGO ({len(filtrados)})*\n"
    for i, m in enumerate(filtrados[:10], 1):
        tags_str = ", ".join(m.get("tags", [])[:3])
        texto += f"{i}. {m['question'][:50]}\n   cuota {m['cuota']:.2f} · vol ${m['volumen']:.0f} · {tags_str}\n\n"
    return enviar(chat_id, texto)

def cmd_saldo(chat_id):
    env = cargar_env()
    wallet = env.get("POLY_WALLET_ADDRESS", WALLET)
    rpcs = ["https://polygon-rpc.com", "https://1rpc.io/matic"]
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
                                   "params": [{"to": contrato, "data": data}, "latest"], "id": 1})
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
    cash = sum(saldos.values())
    texto = f"💰 *SALDO*\n\n*Cash:* ${cash:.2f}\n"
    for tok, val in saldos.items():
        texto += f"   {tok}: ${val:.2f}\n"
    return enviar(chat_id, texto)

def cmd_stats(chat_id):
    s = calcular_stats()
    total = s["wins"] + s["losses"]
    wr = (s["wins"]/total*100) if total > 0 else 0
    roi = (s["pnl"]/s["stake"]*100) if s["stake"] > 0 else 0
    texto = f"📊 *ESTADÍSTICAS*\n\n"
    texto += f"Operaciones: {s['total']}\n"
    if total > 0:
        texto += f"Cerradas: {total} (✅{s['wins']} ❌{s['losses']})\n"
        texto += f"Win rate: *{wr:.1f}%*\n"
        texto += f"PnL: *${s['pnl']:+.2f}*\n"
        texto += f"Stake: ${s['stake']:.2f}\n"
        texto += f"ROI: *{roi:+.1f}%*\n"
    if s["mejor"]:
        m = s["mejor"]
        texto += f"\n🏆 Mejor: {m.get('question','?')[:40]} → ${m.get('pnl',0):+.2f}\n"
    if s["peor"]:
        m = s["peor"]
        texto += f"💀 Peor: {m.get('question','?')[:40]} → ${m.get('pnl',0):+.2f}\n"
    if s["total"] == 0:
        texto += "\n_Aún no hay operaciones. Espera la próxima pasada AUTO._"
    return enviar(chat_id, texto)

def cmd_abiertas(chat_id):
    estado = cargar_estado()
    ejecutadas = [c for c in estado.get("trades_copiados", []) if c.get("status") == "ejecutado"]
    if not ejecutadas:
        return enviar(chat_id, "📭 Sin operaciones aún.")
    texto = f"📂 *COMBOS ABIERTOS ({len(ejecutadas)})*\n\n"
    for op in ejecutadas[-10:]:
        titulo = op.get("question", "?")[:50]
        oid = str(op.get("order_id", ""))[:10]
        precio = op.get("precio_ejecutado", 0)
        stake = op.get("stake_dolares", 0)
        tipo = op.get("tipo", "combo")
        texto += f"✅ {titulo}\n   ${stake:.2f} @ {precio:.2f} ({tipo}) `{oid}`\n\n"
    return enviar(chat_id, texto)

def cmd_cerradas(chat_id):
    estado = cargar_estado()
    historial = estado.get("historial", [])
    if not historial:
        return enviar(chat_id, "📭 Sin cerradas.")
    total = sum(float(h.get("pnl", 0) or 0) for h in historial)
    texto = f"✅ *CERRADAS ({len(historial)})*\n_PnL: ${total:+.2f}_\n\n"
    for h in historial[-15:]:
        titulo = h.get("question", "?")[:50]
        pnl = float(h.get("pnl", 0) or 0)
        ico = "🟢" if pnl >= 0 else "🔴"
        texto += f"{ico} {titulo} → ${pnl:+.2f}\n"
    return enviar(chat_id, texto)

def cmd_top(chat_id):
    texto = ("*🏆 TOP TRADERS POLYMARKET*\n\n"
             "1. pleaseplease123 +$1.0M\n"
             "2. ferrariChampions2026 +$791K\n"
             "3. balthazar +$534K\n"
             "4. 0xd9670... +$466K\n"
             "5. Talvez10 +$339K\n"
             "6. AV23IUa +$311K\n"
             "7. 11vsldfdsgfkjgos +$272K\n"
             "8. Flaznorp +$265K\n"
             "9. sainttroplay +$207K\n"
             "10. ExplosiveNinja +$189K")
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
    enviar(chat_id, f"*Modo: {modo}*")
    if modo == "AUTO":
        threading.Thread(target=lambda: auto_pasada(chat_id), daemon=True).start()

def cmd_stake(chat_id, valor):
    global STAKE_POR_TRADE
    try:
        stake = float(valor)
        if stake < 0.5 or stake > 50:
            return enviar(chat_id, "❌ $0.50-$50")
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
    s = calcular_stats()
    texto = (f"📊 *ESTADO v10 (Combos)*\n\n"
             f"Modo: *{MODO_OPERACION}*\n"
             f"Stake: *${STAKE_POR_TRADE}*\n"
             f"Cuota: *{CUOTA_MIN}-{CUOTA_MAX}*\n"
             f"Trades: *{s['total']}*\n"
             f"PnL: *${s['pnl']:+.2f}*\n"
             f"Proxy: `{PROXY_URL}`\n"
             f"Hora: {datetime.now().strftime('%H:%M:%S')}")
    return enviar(chat_id, texto)


# ============================================
# AUTO LOOP
# ============================================
def auto_pasada(chat_id):
    """v11: lee el CATALOGO DE LEGS, construye un combo real (2-3 piernas,
    eventos distintos, cuota en rango, sin repetir legs recientes) y lo
    ejecuta via RFQ (quote → firma Exchange v3 → accept → FILLED).
    Max 1 combo por pasada + tope diario. La via CLOB de legs sueltos
    (ejecutar_trade) queda DESACTIVADA en AUTO: no eran combos reales."""
    if MODO_OPERACION != "AUTO":
        return
    log("[AUTO] pasada (combos RFQ v11)")
    try:
        legs = listar_combos()
    except Exception as e:
        log(f"  listar error: {e}")
        return
    if not legs:
        log("  sin legs disponibles")
        return
    estado = cargar_estado()
    sel = seleccionar_combo(legs, estado)
    if not sel:
        log("  sin combos viables esta pasada (eventos distintos, cuota, cooldown, tope)")
        return
    ok, res = ejecutar_combo_rfq(sel, chat_id)
    if ok:
        log(f"  ✅ combo OK: {str(res)[:110]}")
    else:
        log(f"  ❌ combo: {str(res)[:130]}")

def auto_loop():
    while True:
        try:
            if MODO_OPERACION == "AUTO" and CHAT_ID:
                auto_pasada(CHAT_ID)
        except Exception as e:
            log(f"auto_loop error: {e}")
        time.sleep(INTERVALO_AUTO_S)


# ============================================
# LOOP TELEGRAM
# ============================================
def procesar_update(update):
    global CHAT_ID
    if "message" not in update:
        return
    msg = update["message"]
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "").strip()
    CHAT_ID = chat_id
    if text == "📋 Trades":
        return cmd_trades(chat_id)
    elif text == "💰 Saldo":
        return cmd_saldo(chat_id)
    elif text == "📂 Abiertas":
        return cmd_abiertas(chat_id)
    elif text == "✅ Cerradas":
        return cmd_cerradas(chat_id)
    elif text == "📊 Stats":
        return cmd_stats(chat_id)
    elif text == "🏆 Top":
        return cmd_top(chat_id)
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
    if text == "/testcombo":
        return cmd_testcombo(chat_id)
    elif text == "/fills":
        return cmd_fills(chat_id)
    if text == "/start":
        cmd_start(chat_id)
        if MODO_OPERACION == "AUTO":
            threading.Thread(target=lambda: auto_pasada(chat_id), daemon=True).start()
        return
    elif text == "/trades":
        return cmd_trades(chat_id)
    elif text == "/stats":
        return cmd_stats(chat_id)
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
    elif text in ("/status", "/estado"):
        return cmd_status(chat_id)

def bot_loop():
    log("v11.0 iniciado")
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
                    try: procesar_update(update)
                    except Exception as e: log(f"update err: {e}")
        except Exception as e:
            log(f"loop err: {e}")
            time.sleep(5)

def main():
    if not cargar_token():
        log("ERROR: no se encontró el token")
        return
    log(f"v11.0 cargado · modo={MODO_OPERACION} · stake=${STAKE_POR_TRADE}")
    log(f"Proxy: {PROXY_URL}")
    status, body = http_get("https://api.telegram.org", timeout=10)
    log(f"Test proxy: {status if status else 'FALLO'}")
    t = threading.Thread(target=auto_loop, daemon=True)
    t.start()
    bot_loop()

if __name__ == "__main__":
    main()
