#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLY COMBOS BOT v10.6 — Combos (parlays) en tiempo real
=====================================================
Estrategia nueva (vs v7):
  1. Lee COMBOS ACTIVOS del endpoint publico: /v1/rfq/combo-markets
  2. Cada combo = 2-10 legs, paga si TODOS aciertan
  3. Cuota objetivo 1.20-2.50 (multiplicacion de legs)
  4. Ejecuta automaticamente via CLOB

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

def http_get(url, timeout=20):
    try:
        opener = _proxy_opener()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with opener.open(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
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
    # Setear env vars (el SDK las respeta)
    os.environ["HTTP_PROXY"] = PROXY_URL
    os.environ["HTTPS_PROXY"] = PROXY_URL
    os.environ["http_proxy"] = PROXY_URL
    os.environ["https_proxy"] = PROXY_URL
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
        if "creds" not in kwargs:
            try:
                creds = client.derive_api_key()
                client.set_api_creds(creds)
            except: pass
        return client
    except Exception as e:
        log(f"cliente error: {e}")
        return None


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
    """Lee COMBOS ACTIVOS de Polymarket (endpoint publico RFQ).
    Cada combo = 2-10 legs, paga si todos aciertan.
    Cuota = multiplicacion de las probs de cada leg."""
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
            if not (0.02 <= yes_price <= 0.95):
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
                "tags": tags,
                # Estos se llenan despues via /markets/{condition_id}
                "real_token": None,
            })
        log(f"  pagina {paginas + 1}: +{len(batch)} mercados, {len(combos)} combos de deportes")
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
    """v10.6: Firma la orden con ClobClient, luego envia via HTTP directo
    con proxy (como hace el bot de Elon con curl)."""
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
    if not signer or not api_key:
        return False, "sin_credenciales"

    # 1) Crear cliente SOLO para firmar (no envia)
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds, OrderArgs
        from py_clob_client_v2 import SignatureTypeV2
        client = ClobClient(
            host=HOST_CLOB,
            chain_id=137,
            key=signer,
            creds=ApiCreds(api_key, api_secret, api_passphrase),
            funder=wallet,
            signature_type=int(SignatureTypeV2.POLY_PROXY) if wallet else int(SignatureTypeV2.EOA),
        )
        # Crear la orden firmada (NO la posteamos)
        order_args = OrderArgs(token_id=token_id, price=precio,
                                size=size_shares, side="BUY")
        signed_order = client.create_order(order_args)
        log(f"  orden firmada: {str(signed_order)[:120]}")
    except Exception as e:
        return False, f"firma_error:{str(e)[:200]}"

    # 2) Enviar la orden firmada via HTTP POST directo CON PROXY
    try:
        body = json.dumps(signed_order) if not isinstance(signed_order, str) else signed_order
        url = f"{HOST_CLOB}/order"
        timestamp = str(int(time.time()))
        # Headers L2 auth requeridos por Polymarket CLOB
        headers = {
            "Content-Type": "application/json",
            "POLY_ADDRESS": wallet,
            "POLY_API_KEY": api_key,
            "POLY_PASSPHRASE": api_passphrase,
            "POLY_TIMESTAMP": timestamp,
        }
        status, resp_body = http_post(url, body, headers)
        log(f"  HTTP POST /order -> {status} {resp_body[:200]}")
        if status in (200, 201):
            try:
                data = json.loads(resp_body)
            except:
                data = {"raw": resp_body[:200]}
            oid = data.get("orderID") or data.get("order_id") or data.get("id") or "?"
            ULTIMO_TRADE_TS = ahora
            return True, {"oid": oid, "size": size_shares, "precio": precio}
        return False, f"http_{status}:{resp_body[:200]}"
    except Exception as e:
        return False, f"http_error:{str(e)[:200]}"

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
    texto = (f"🤖 *POLY COMBOS BOT v10.6*\n\n"
             f"Modo: *{MODO_OPERACION}*\n"
             f"Stake: *${STAKE_POR_TRADE}*\n"
             f"Cuota: *{CUOTA_MIN}-{CUOTA_MAX}*\n\n"
             f"📌 *Estrategia v10* (COMBOS):\n"
             f"   · Lee COMBOS activos de Polymarket\n"
             f"   · Resuelve token_id real via /markets/<condition_id>\n"
             f"   · Solo deportes: fútbol, MLB, NBA, UFC, etc.\n"
             f"   · Cuota 1.20-2.50\n"
             f"   · Automático cada 5 min\n\n"
             f"📊 *Stats* para ver estadísticas")
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
    """Lee combos activos, filtra por cuota, ejecuta automaticamente."""
    if MODO_OPERACION != "AUTO":
        return
    log(f"[AUTO] pasada")
    combos = listar_combos()
    if not combos:
        enviar(chat_id, "🔄 *AUTO:* sin combos activos ahora.")
        return
    # filtrar por cuota objetivo
    candidatos = [m for m in combos if CUOTA_MIN <= m["cuota"] <= CUOTA_MAX]
    # ordenar por volumen
    candidatos.sort(key=lambda x: -x["volumen"])
    if not candidatos:
        enviar(chat_id, f"🔄 *AUTO:* {len(combos)} combos activos pero ninguno en cuota {CUOTA_MIN}-{CUOTA_MAX}.")
        return
    enviar(chat_id, f"🔄 *AUTO: {len(candidatos)} combos en rango. Ejecutando...*")
    ejecutar = 0
    for m in candidatos[:MAX_TRADES_SIMULTANEOS]:
        ok, motivo = ejecutar_trade(m, chat_id)
        if ok:
            ejecutar += 1
        time.sleep(3)
    if ejecutar:
        enviar(chat_id, f"✅ *AUTO: {ejecutar} combo(s) ejecutado(s)*")
    else:
        enviar(chat_id, f"⚠️ *AUTO: 0 ejecuciones*")

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
    log("v10.6 iniciado")
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
    log(f"v10.6 cargado · modo={MODO_OPERACION} · stake=${STAKE_POR_TRADE}")
    log(f"Proxy: {PROXY_URL}")
    status, body = http_get("https://api.telegram.org", timeout=10)
    log(f"Test proxy: {status if status else 'FALLO'}")
    t = threading.Thread(target=auto_loop, daemon=True)
    t.start()
    bot_loop()

if __name__ == "__main__":
    main()
