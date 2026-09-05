#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
POLY COMBOS BOT v6 — Simples + Combos automáticos + Estadísticas
==================================================================
Estrategia en 3 niveles:
  · SIMPLE  (1 evento) → cuota 1.40-2.50
  · DOBLE   (2 eventos mismo deporte) → cuota objetivo 1.80-3.50
  · TRIPLE  (3 eventos mismo deporte) → cuota objetivo 2.50-5.00

Sistema de estadísticas:
  · Por tipo (simple/doble/triple)
  · Win rate, PnL total, PnL medio
  · Mejor trade, peor trade
  · Por deporte

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

# Anti-shadow module
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
PROXY_URL = "http://100.83.57.99:8888"

ESTADO_FILE = "/opt/polymarket/combos_estado.json"
BACKUP_FILE = "/opt/polymarket/combos_estado.bak.json"
ENV_FILE = "/etc/polymarket.env"

# ============================================
# ESTRATEGIA — Simples + Combos
# ============================================
STAKE_POR_TRADE = 2.0             # $ por pierna
STAKE_POR_COMBO_DOBLE = 1.0       # $ por pierna (combo 2 = $2 total)
STAKE_POR_COMBO_TRIPLE = 0.70     # $ por pierna (combo 3 = $2.10 total)
CUOTA_MIN_SIMPLE = 1.40
CUOTA_MAX_SIMPLE = 2.50
CUOTA_OBJ_DOBLE = (1.80, 3.50)    # rango objetivo para combos dobles
CUOTA_OBJ_TRIPLE = (2.50, 5.00)
MAX_TRADES_SIMULTANEOS = 3
HORAS_RECIENTE = 6
INTERVALO_AUTO_S = 300
PESO_MIN = 5

MODO_OPERACION = "AUTO"
CHAT_ID = None
ULTIMO_TRADE_TS = 0               # throttle

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

DEPORTES_KEYWORDS = {
    "MLB": ["MLB"],
    "UFC": ["UFC", "MMA", "Fight Night"],
    "NFL": ["NFL", "NCAAF"],
    "NBA": ["NBA", "NCAAB"],
    "Tennis": ["tennis", "ATP", "WTA", "US Open"],
    "Soccer": ["soccer", "EPL", "Bundesliga", "Serie A", "La Liga", "Ligue 1", "World Cup"],
}
EXCLUIR = ["Trump", "Biden", "Election", "President", "Congress",
           "Bitcoin", "Ethereum", "Crypto", "NFT",
           "Fed", "rate", "inflation", "Russia", "Ukraine", "China",
           "Iran", "Israel", "WHO", "covid", "pandemic"]

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
# CREDENCIALES Y CLOB
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
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import ApiCreds
        from py_clob_client_v2 import SignatureTypeV2
    except ImportError:
        return None
    env = cargar_env()
    signer = env.get("POLY_PRIVATE_KEY", "").strip()
    if not signer:
        return None
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
        except: pass
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
# UTILIDADES DE MERCADO
# ============================================
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

def buscar_token_por_titulo(titulo, asset_hint=None):
    """Busca el token_id de un mercado.
    Estrategia:
      1. Si el asset_hint (token_id) viene en el trade, USARLO DIRECTO
      2. Si no, buscar por titulo en gamma-api con score de palabras
    Devuelve (token_id, side, question) o (None, None, None).
    """
    # 1. usar el asset directamente (ES el token_id)
    if asset_hint and str(asset_hint).isdigit() and len(str(asset_hint)) > 20:
        return str(asset_hint), "YES", titulo
    # 2. fallback: buscar por titulo
    try:
        url = "https://gamma-api.polymarket.com/markets?active=true&closed=false&limit=500"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=20) as r:
            markets = json.loads(r.read())
        titulo_lower = titulo.lower()
        mejor = None
        mejor_score = 0
        for m in markets:
            q = (m.get("question") or m.get("title") or "").lower()
            if not q: continue
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
            try: tokens = json.loads(tokens_str)
            except: tokens = []
            if tokens:
                side = "YES"
                if "no" in titulo_lower and mejor_score < 0.7:
                    side = "NO"
                token_id = tokens[0] if side == "YES" else (tokens[1] if len(tokens) > 1 else tokens[0])
                return token_id, side, mejor.get("question", "")
    except Exception as e:
        log(f"  buscar_token error: {e}")
    return None, None, None

def detectar_deporte(titulo):
    """Detecta el deporte principal de un titulo."""
    t = titulo.lower()
    for deporte, kws in DEPORTES_KEYWORDS.items():
        if any(k.lower() in t for k in kws):
            return deporte
    return "Other"


# ============================================
# DETECCIÓN DE TRADES
# ============================================
def detectar_trades():
    """Detecta trades de top traders. Devuelve lista con todos los candidatos."""
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
                deporte = detectar_deporte(titulo)
                if deporte == "Other":
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
                    "timestamp": ts,
                    "cuota": round(1/price, 2),
                    "deporte": deporte,
                })
        except Exception as e:
            log(f"error {nombre}: {e}")
    candidatos.sort(key=lambda x: -x["peso"])
    return candidatos

def trades_refresh():
    ahora = time.time()
    if ahora - TRADES_CACHE["ts"] > 60 or not TRADES_CACHE["trades"]:
        TRADES_CACHE["ts"] = ahora
        TRADES_CACHE["trades"] = detectar_trades()
    return TRADES_CACHE["trades"]


# ============================================
# DETECCIÓN DE COMBOS
# ============================================
def agrupar_por_deporte(trades):
    """Agrupa trades por deporte. Solo incluye los del mismo deporte."""
    grupos = defaultdict(list)
    for t in trades:
        grupos[t["deporte"]].append(t)
    return grupos

def detectar_combos(trades):
    """Detecta posibles combos (2-3 trades del mismo deporte)."""
    grupos = agrupar_por_deporte(trades)
    combos = []
    for deporte, lista in grupos.items():
        # ordenar por cuota (menor primero, para encontrar el doble optimo)
        lista.sort(key=lambda x: x["cuota"])
        # dobles: 2 trades con cuota 1.20-1.40 cada uno
        if len(lista) >= 2:
            c1, c2 = lista[0], lista[1]
            cuota_combo = round(c1["cuota"] * c2["cuota"], 2)
            if CUOTA_OBJ_DOBLE[0] <= cuota_combo <= CUOTA_OBJ_DOBLE[1] * 1.5:
                combos.append({
                    "tipo": "doble",
                    "deporte": deporte,
                    "trades": [c1, c2],
                    "cuota_combo": cuota_combo,
                    "stake_por_pierna": STAKE_POR_COMBO_DOBLE,
                    "stake_total": STAKE_POR_COMBO_DOBLE * 2,
                })
        # triples: 3 trades
        if len(lista) >= 3:
            c1, c2, c3 = lista[0], lista[1], lista[2]
            cuota_combo = round(c1["cuota"] * c2["cuota"] * c3["cuota"], 2)
            if CUOTA_OBJ_TRIPLE[0] <= cuota_combo <= CUOTA_OBJ_TRIPLE[1] * 1.5:
                combos.append({
                    "tipo": "triple",
                    "deporte": deporte,
                    "trades": [c1, c2, c3],
                    "cuota_combo": cuota_combo,
                    "stake_por_pierna": STAKE_POR_COMBO_TRIPLE,
                    "stake_total": STAKE_POR_COMBO_TRIPLE * 3,
                })
    return combos

def detectar_simples(trades):
    """Trades con cuota individual buena (>= 1.40) que no entran en combo."""
    combos = detectar_combos(trades)
    # titulos que ya estan en combos
    titulos_en_combos = set()
    for c in combos:
        for t in c["trades"]:
            titulos_en_combos.add(t["titulo"][:50])
    simples = []
    for t in trades:
        if t["titulo"][:50] in titulos_en_combos:
            continue
        if CUOTA_MIN_SIMPLE <= t["cuota"] <= CUOTA_MAX_SIMPLE:
            if t["peso"] >= PESO_MIN:
                simples.append(t)
    return simples[:MAX_TRADES_SIMULTANEOS]


# ============================================
# EJECUCIÓN DE TRADES
# ============================================
def enviar_orden(token_id, precio, stake_dolares, chat_id=None):
    """Envía una orden BUY a CLOB. Devuelve (ok, oid_o_error)."""
    global ULTIMO_TRADE_TS
    ahora = time.time()
    if ahora - ULTIMO_TRADE_TS < 10:
        return False, "throttle"
    client = get_clob_client()
    if not client:
        return False, "cliente_no_disponible"
    try:
        from py_clob_client_v2.clob_types import OrderArgs
        size_shares = round(stake_dolares / precio, 2)
        if size_shares < 5:
            return False, f"size_{size_shares}_muy_pequeno"
        resp = client.create_and_post_order(
            OrderArgs(token_id=token_id, price=precio,
                      size=size_shares, side="BUY"))
        oid = resp.get("orderID") or resp.get("order_id") or "?"
        ULTIMO_TRADE_TS = ahora
        return True, {"oid": oid, "size": size_shares, "precio": precio}
    except Exception as e:
        return False, str(e)[:200]

def ejecutar_simple(trade, chat_id=None):
    """Ejecuta un trade simple (1 evento)."""
    log(f"[SIMPLE] {trade['titulo'][:50]}")
    # buscar mercado (usando el asset del trade directamente)
    token_id, side, q = buscar_token_por_titulo(trade["titulo"], asset_hint=trade.get("asset"))
    if not token_id:
        log(f"  SKIP: no encontre mercado (asset={str(trade.get('asset'))[:20]})")
        return False, "no_encontrado", None
    log(f"  token_id={token_id[:20]}... side={side}")
    # re-leer precio
    precio = get_precio_actual(token_id)
    if not precio or precio <= 0 or precio >= 1:
        log(f"  SKIP: no pude leer precio actual")
        return False, "precio_no_disponible", None
    log(f"  precio actual={precio:.3f} (cuota {1/precio:.2f})")
    cuota = round(1/precio, 2)
    if not (CUOTA_MIN_SIMPLE <= cuota <= CUOTA_MAX_SIMPLE):
        log(f"  SKIP: cuota {cuota} fuera de rango [{CUOTA_MIN_SIMPLE}-{CUOTA_MAX_SIMPLE}]")
        return False, f"cuota_{cuota}_fuera_rango", None
    # enviar
    log(f"  enviando orden...")
    ok, resultado = enviar_orden(token_id, precio, STAKE_POR_TRADE, chat_id)
    if not ok:
        log(f"  ERROR: {resultado}")
        return False, resultado, None
    log(f"  OK orden={str(resultado.get('oid', '?'))[:18]}")
    # re-leer precio
    precio = get_precio_actual(token_id)
    if not precio or precio <= 0 or precio >= 1:
        return False, "precio_no_disponible", None
    cuota = round(1/precio, 2)
    if not (CUOTA_MIN_SIMPLE <= cuota <= CUOTA_MAX_SIMPLE):
        return False, f"cuota_{cuota}_fuera_rango", None
    # enviar
    ok, resultado = enviar_orden(token_id, precio, STAKE_POR_TRADE, chat_id)
    if not ok:
        return False, resultado, None
    # guardar en estado
    registro = {
        **trade,
        "tipo": "simple",
        "copiado_en": datetime.now().isoformat(),
        "precio_ejecutado": precio,
        "cuota_ejecutada": cuota,
        "size_shares": resultado["size"],
        "stake_dolares": STAKE_POR_TRADE,
        "order_id": resultado["oid"],
        "token_id": token_id,
        "status": "ejecutado",
    }
    estado = cargar_estado()
    estado["trades_copiados"].append(registro)
    guardar_estado(estado)
    if chat_id:
        enviar(chat_id, f"✅ *SIMPLE ejecutado*\n"
                      f"📌 {trade['titulo'][:55]}\n"
                      f"💵 {resultado['size']} shares @ {precio:.2f} (cuota {cuota:.2f})\n"
                      f"💰 Stake: ${STAKE_POR_TRADE:.2f}\n"
                      f"🆔 `{str(resultado['oid'])[:18]}`")
    return True, "ok", registro

def ejecutar_combo(combo, chat_id=None):
    """Ejecuta un combo (2 o 3 piernas)."""
    log(f"[COMBO-{combo['tipo'].upper()}] {combo['deporte']} cuota objetivo {combo['cuota_combo']}")
    piernas = []
    for trade in combo["trades"]:
        token_id, side, q = buscar_token_por_titulo(trade["titulo"], asset_hint=trade.get("asset"))
        if not token_id:
            log(f"  skip pierna: {trade['titulo'][:30]} - no encontrado")
            return False, "pierna_no_encontrada", None
        precio = get_precio_actual(token_id)
        if not precio or precio <= 0 or precio >= 1:
            return False, f"precio_no_disponible_{trade['titulo'][:20]}", None
        ok, resultado = enviar_orden(token_id, precio, combo["stake_por_pierna"], chat_id)
        if not ok:
            return False, f"error_{trade['titulo'][:20]}:{resultado}", None
        piernas.append({
            "trade": trade,
            "token_id": token_id,
            "precio": precio,
            "cuota": round(1/precio, 2),
            "order_id": resultado["oid"],
            "size_shares": resultado["size"],
            "stake": combo["stake_por_pierna"],
        })
        # throttle entre piernas
        time.sleep(3)
    # todas las piernas ejecutadas
    cuota_real = 1.0
    for p in piernas:
        cuota_real *= p["cuota"]
    cuota_real = round(cuota_real, 2)
    combo_id = f"combo_{datetime.now().strftime('%Y%m%d%H%M%S')}_{combo['deporte']}"
    registro = {
        "tipo": combo["tipo"],
        "deporte": combo["deporte"],
        "combo_id": combo_id,
        "copiado_en": datetime.now().isoformat(),
        "piernas": piernas,
        "cuota_objetivo": combo["cuota_combo"],
        "cuota_real": cuota_real,
        "stake_total": combo["stake_total"],
        "stake_por_pierna": combo["stake_por_pierna"],
        "status": "ejecutado",
    }
    estado = cargar_estado()
    estado["trades_copiados"].append(registro)
    guardar_estado(estado)
    if chat_id:
        texto = f"✅ *COMBO {combo['tipo'].upper()} ({combo['deporte']})*\n"
        texto += f"💰 Stake total: ${combo['stake_total']:.2f}\n"
        texto += f"📈 Cuota real: *{cuota_real:.2f}*\n\n"
        for i, p in enumerate(piernas, 1):
            texto += f"  {i}. {p['trade']['titulo'][:40]}\n"
            texto += f"     {p['size_shares']} @ {p['precio']:.2f} (cuota {p['cuota']:.2f})\n"
        texto += f"\n_Retorno si todos ganan: ${combo['stake_total'] * cuota_real:.2f}_"
        enviar(chat_id, texto)
    return True, "ok", registro


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
    """Calcula estadísticas detalladas por tipo, deporte, etc."""
    estado = cargar_estado()
    copiados = estado.get("trades_copiados", [])
    historial = estado.get("historial", [])
    stats = {
        "total_operaciones": len(copiados),
        "simples": 0, "dobles": 0, "triples": 0,
        "stake_total": 0.0,
        "ganancias": 0.0,  # suma de PnL positivos
        "perdidas": 0.0,   # suma de PnL negativos
        "pnl_total": 0.0,
        "wins": 0, "losses": 0,
        "por_tipo": {"simple": {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
                     "doble": {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0},
                     "triple": {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0}},
        "por_deporte": defaultdict(lambda: {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0}),
        "mejor_trade": None,
        "peor_trade": None,
    }
    # analizar trades
    for op in copiados + historial:
        tipo = op.get("tipo", "simple")
        if tipo not in ("simple", "doble", "triple"):
            tipo = "simple"
        stats["por_tipo"][tipo]["count"] += 1
        # deporte
        deporte = op.get("deporte", "Other")
        if tipo == "simple":
            deporte = deporte or detectar_deporte(op.get("titulo", ""))
        stats["por_deporte"][deporte]["count"] += 1
        # pnl (si está cerrado)
        pnl = op.get("pnl")
        stake = op.get("stake_dolares") or op.get("stake_total") or 0
        if pnl is not None:
            stats["pnl_total"] += pnl
            stats["stake_total"] += stake
            if pnl > 0:
                stats["wins"] += 1
                stats["ganancias"] += pnl
                stats["por_tipo"][tipo]["wins"] += 1
                stats["por_deporte"][deporte]["wins"] += 1
            else:
                stats["losses"] += 1
                stats["perdidas"] += pnl
                stats["por_tipo"][tipo]["losses"] += 1
                stats["por_deporte"][deporte]["losses"] += 1
            stats["por_tipo"][tipo]["pnl"] += pnl
            stats["por_deporte"][deporte]["pnl"] += pnl
            # mejor / peor
            if stats["mejor_trade"] is None or pnl > stats["mejor_trade"].get("pnl", -9999):
                stats["mejor_trade"] = op
            if stats["peor_trade"] is None or pnl < stats["peor_trade"].get("pnl", 9999):
                stats["peor_trade"] = op
    stats["simples"] = stats["por_tipo"]["simple"]["count"]
    stats["dobles"] = stats["por_tipo"]["doble"]["count"]
    stats["triples"] = stats["por_tipo"]["triple"]["count"]
    return stats


# ============================================
# COMANDOS
# ============================================
def cmd_start(chat_id):
    estado = cargar_estado()
    texto = (f"🤖 *POLY COMBOS BOT v6*\n\n"
             f"Modo: *{estado.get('modo', MODO_OPERACION)}*\n"
             f"Stake simple: *${STAKE_POR_TRADE}* | doble: ${STAKE_POR_COMBO_DOBLE}/pierna | triple: ${STAKE_POR_COMBO_TRIPLE}/pierna\n"
             f"Cuota simple: *{CUOTA_MIN_SIMPLE}-{CUOTA_MAX_SIMPLE}*\n\n"
             f"📌 *Estrategia*:\n"
             f"   · Si cuota individual ≥ 1.40 → *simple*\n"
             f"   · Si 2 trades del mismo deporte con cuota baja → *combo doble*\n"
             f"   · Si 3 trades del mismo deporte con cuota baja → *combo triple*\n\n"
             f"📊 Pulsa *Stats* para ver estadísticas detalladas")
    return enviar(chat_id, texto)

def cmd_trades(chat_id):
    trades = trades_refresh()
    simples = detectar_simples(trades)
    combos = detectar_combos(trades)
    if not simples and not combos:
        return enviar(chat_id, "❌ No hay trades con cuota 1.40-2.50 ahora mismo.")
    texto = f"*🎯 OPORTUNIDADES*\n"
    if simples:
        texto += f"\n*🟢 SIMPLES ({len(simples)}):*\n"
        for i, t in enumerate(simples, 1):
            texto += f"{i}. {t['titulo'][:50]}\n   {t['trader']} | cuota {t['cuota']:.2f} | ${STAKE_POR_TRADE}\n\n"
    if combos:
        texto += f"\n*🟡 COMBOS ({len(combos)}):*\n"
        for i, c in enumerate(combos, 1):
            texto += f"{i}. {c['tipo'].upper()} {c['deporte']} → cuota {c['cuota_combo']:.2f}\n"
            for t in c["trades"]:
                texto += f"   · {t['titulo'][:40]} (cuota {t['cuota']:.2f})\n"
            texto += f"   Stake: ${c['stake_total']:.2f}\n\n"
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
    """Muestra estadísticas detalladas."""
    s = calcular_stats()
    total = s["wins"] + s["losses"]
    winrate = (s["wins"]/total*100) if total > 0 else 0
    roi = (s["pnl_total"]/s["stake_total"]*100) if s["stake_total"] > 0 else 0
    texto = f"📊 *ESTADÍSTICAS*\n\n"
    texto += f"*Operaciones totales:* {s['total_operaciones']}\n"
    texto += f"   · Simples: {s['simples']}\n"
    texto += f"   · Dobles: {s['dobles']}\n"
    texto += f"   · Triples: {s['triples']}\n\n"
    if total > 0:
        texto += f"*Resultados cerrados:* {total}\n"
        texto += f"   · ✅ Wins: {s['wins']}\n"
        texto += f"   · ❌ Losses: {s['losses']}\n"
        texto += f"   · 📈 Win rate: *{winrate:.1f}%*\n\n"
        texto += f"*PnL total:* ${s['pnl_total']:+.2f}\n"
        texto += f"   · Ganancias: ${s['ganancias']:+.2f}\n"
        texto += f"   · Pérdidas: ${s['perdidas']:+.2f}\n"
        texto += f"   · Stake total: ${s['stake_total']:.2f}\n"
        texto += f"   · ROI: *{roi:+.1f}%*\n\n"
    # por tipo
    texto += "*Por tipo:*\n"
    for tipo in ("simple", "doble", "triple"):
        t = s["por_tipo"][tipo]
        if t["count"] == 0: continue
        cerrado = t["wins"] + t["losses"]
        wr = (t["wins"]/cerrado*100) if cerrado > 0 else 0
        texto += f"   {tipo}: {t['count']} ops, {cerrado} cerrados, WR {wr:.0f}%, PnL ${t['pnl']:+.2f}\n"
    texto += "\n"
    # por deporte
    if s["por_deporte"]:
        texto += "*Por deporte:*\n"
        for dep, d in sorted(s["por_deporte"].items(), key=lambda x: -x[1]["count"]):
            if d["count"] == 0: continue
            cerrado = d["wins"] + d["losses"]
            wr = (d["wins"]/cerrado*100) if cerrado > 0 else 0
            texto += f"   {dep}: {d['count']} ops, WR {wr:.0f}%, PnL ${d['pnl']:+.2f}\n"
    # mejor y peor
    if s["mejor_trade"]:
        t = s["mejor_trade"]
        titulo = t.get("titulo") or "combo " + t.get("deporte", "?")
        texto += f"\n🏆 *Mejor:* {titulo[:40]} → ${t.get('pnl', 0):+.2f}\n"
    if s["peor_trade"]:
        t = s["peor_trade"]
        titulo = t.get("titulo") or "combo " + t.get("deporte", "?")
        texto += f"\n💀 *Peor:* {titulo[:40]} → ${t.get('pnl', 0):+.2f}\n"
    return enviar(chat_id, texto)

def cmd_abiertas(chat_id):
    estado = cargar_estado()
    copiados = estado.get("trades_copiados", [])
    if not copiados:
        return enviar(chat_id, "📭 Sin operaciones del bot de Combos aún.")
    texto = f"*📂 OPERACIONES ({len(copiados)})*\n\n"
    for op in copiados[-15:]:
        if op.get("tipo") == "simple":
            titulo = op.get("titulo", "?")[:50]
            precio = op.get("precio_ejecutado", 0)
            oid = str(op.get("order_id", ""))[:10]
            texto += f"🟢 {titulo}\n   ${op.get('stake_dolares',0):.2f} @ {precio:.2f} `{oid}`\n\n"
        else:
            texto += f"🟡 COMBO {op.get('tipo')} {op.get('deporte','')}\n"
            texto += f"   Cuota real {op.get('cuota_real',0):.2f}, stake ${op.get('stake_total',0):.2f}\n\n"
    return enviar(chat_id, texto)

def cmd_cerradas(chat_id):
    estado = cargar_estado()
    historial = estado.get("historial", [])
    if not historial:
        return enviar(chat_id, "📭 Aún no hay cerradas.")
    total = sum(float(h.get("pnl", 0) or 0) for h in historial)
    texto = f"*✅ CERRADAS ({len(historial)})*\n_PnL: ${total:+.2f}_\n\n"
    for h in historial[-20:]:
        titulo = (h.get("titulo") or "combo " + h.get("deporte",""))[:50]
        pnl = float(h.get("pnl", 0) or 0)
        ico = "🟢" if pnl >= 0 else "🔴"
        fecha = h.get("cerrado_en", h.get("copiado_en", ""))[:16]
        texto += f"{ico} {titulo} → ${pnl:+.2f} ({fecha})\n"
    return enviar(chat_id, texto)

def cmd_top(chat_id):
    texto = "*🏆 LEADERBOARD POLYMARKET*\n\n"
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
    desc = {"AUTO": "🟢 ejecuta automáticamente", "SEMI": "🟡 informa pero no opera",
            "OFF": "🔴 solo informa"}[modo]
    enviar(chat_id, f"*Modo: {modo}*\n_{desc}_")
    if modo == "AUTO":
        threading.Thread(target=lambda: auto_pasada(chat_id), daemon=True).start()

def cmd_stake(chat_id, valor):
    global STAKE_POR_TRADE, STAKE_POR_COMBO_DOBLE, STAKE_POR_COMBO_TRIPLE
    try:
        stake = float(valor)
        if stake < 0.5 or stake > 50:
            return enviar(chat_id, "❌ Entre $0.50 y $50")
        STAKE_POR_TRADE = stake
        STAKE_POR_COMBO_DOBLE = stake / 2
        STAKE_POR_COMBO_TRIPLE = stake / 3
        estado = cargar_estado()
        estado["stake"] = stake
        guardar_estado(estado)
        return enviar(chat_id, f"*Stake simple: ${stake:.2f}*\n"
                              f"_Doble: ${STAKE_POR_COMBO_DOBLE:.2f}/pierna_\n"
                              f"_Triple: ${STAKE_POR_COMBO_TRIPLE:.2f}/pierna_")
    except:
        return enviar(chat_id, "❌ /stake 2.5")

def cmd_status(chat_id):
    global CHAT_ID
    CHAT_ID = chat_id
    estado = cargar_estado()
    s = calcular_stats()
    texto = (f"*📊 ESTADO*\n\n"
             f"Modo: *{estado.get('modo', MODO_OPERACION)}*\n"
             f"Stake simple: *${STAKE_POR_TRADE}*\n"
             f"Cuota simple: *{CUOTA_MIN_SIMPLE}-{CUOTA_MAX_SIMPLE}*\n"
             f"Trades ejecutados: *{s['total_operaciones']}* "
             f"(🟢{s['simples']} 🟡{s['dobles']} 🔴{s['triples']})\n"
             f"PnL: *${s['pnl_total']:+.2f}* | "
             f"WR: *{(s['wins']/(s['wins']+s['losses'])*100) if (s['wins']+s['losses'])>0 else 0:.0f}%*\n"
             f"Proxy: `{PROXY_URL}`\n"
             f"Hora: {datetime.now().strftime('%H:%M:%S')}")
    return enviar(chat_id, texto)


# ============================================
# AUTO LOOP
# ============================================
def auto_pasada(chat_id):
    """Una pasada: detecta oportunidades y ejecuta."""
    if MODO_OPERACION != "AUTO":
        return
    log(f"[AUTO] pasada")
    trades = trades_refresh()
    simples = detectar_simples(trades)
    combos = detectar_combos(trades)
    if not simples and not combos:
        enviar(chat_id, "🔄 *AUTO:* sin oportunidades ahora mismo.")
        return
    ejecutar = 0
    # ejecutar primero los combos (mayor valor)
    for combo in combos[:1]:  # max 1 combo por pasada para no saturar
        ok, motivo, reg = ejecutar_combo(combo, chat_id)
        if ok: ejecutar += 1
        time.sleep(5)
    # luego simples
    budget = MAX_TRADES_SIMULTANEOS - ejecutar
    for t in simples[:budget]:
        ok, motivo, reg = ejecutar_simple(t, chat_id)
        if ok: ejecutar += 1
        time.sleep(2)
    enviar(chat_id, f"✅ *AUTO: {ejecutar} operación(es) ejecutada(s)*")

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
    log("Bot iniciado")
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
    log(f"v6 cargado · modo={MODO_OPERACION} · stake=${STAKE_POR_TRADE}")
    log(f"Proxy: {PROXY_URL}")
    status, body = http_get("https://api.telegram.org", timeout=10)
    log(f"Test proxy: {status if status else 'FALLO'}")
    t = threading.Thread(target=auto_loop, daemon=True)
    t.start()
    bot_loop()

if __name__ == "__main__":
    main()
