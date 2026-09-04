#!/usr/bin/env python3
"""
DIAG V5 - saldo real via Polygon RPC + clasificación fina de posiciones
=====================================================================
MEJORAS vs v4:
- Lee wallet de /root/wallet_address.txt (si existe) o la deriva de private key
- Consulta saldo REAL via JSON-RPC a Polygon (sin depender de los bots)
- Clasifica posiciones: bot Zelenskyy vs manual vs fantasma
- Identifica mercados ya cerrados/resueltos (donde el precio es 0 o 1)
"""
import json
import os
import sys
import time
import traceback
import urllib.request
import urllib.error
import base64
from datetime import datetime

FUNDER_DEFAULT = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
DATA_API = "https://data-api.polymarket.com/positions"
RAMA_DIAG = "diag-public"
REPO = "lamegawi/bots-backup"

# Polygon JSON-RPC público
POLYGON_RPCS = [
    "https://polygon-rpc.com",
    "https://rpc.ankr.com/polygon",
    "https://polygon.llamarpc.com",
]

# Tokens de Polymarket en Polygon
POLYMARKET_TOKENS = {
    "pUSD":   "0xA04BC50F8A8B8d3D3E1E5E0B6f3E0C0E0E0E0E0E0",  # placeholder
    "USDC":   "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",  # USDC nativo en Polygon
    "USDC.e": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",  # USDC bridged
}

LOG = []
def log(s):
    s = str(s)
    print(s, flush=True)
    LOG.append(s)

def cargar_pat():
    for r in ["/root/diag_token.txt", "/opt/polymarket/diag_token.txt",
              os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            with open(r) as f:
                t = f.read().strip()
                if t.startswith("ghp_") or t.startswith("github_pat_"):
                    log(f"PAT de {r}")
                    return t
    return os.environ.get("GH_PAT", "")

PAT = cargar_pat()

def publicar(texto, ruta):
    if not PAT:
        return False, "Sin PAT"
    texto_bytes = texto.encode("utf-8")
    log(f"  publicar(): {len(texto_bytes)} bytes → {ruta}")
    b64 = base64.b64encode(texto_bytes).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/contents/{ruta}?ref={RAMA_DIAG}",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError:
        pass
    payload = {"message": f"diag {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": RAMA_DIAG}
    if sha:
        payload["sha"] = sha
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{ruta}",
        data=body, method="PUT",
        headers={"Authorization": f"token {PAT}", "Content-Type": "application/json",
                 "Accept": "application/vnd.github+json", "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            url = resp.get("content", {}).get("html_url", "")
            log(f"  ✓ HTTP {r.status} publicado: {url}")
            return True, url
    except urllib.error.HTTPError as e:
        body_err = e.read().decode("utf-8", errors="replace")[:500]
        log(f"  ✗ HTTP {e.code}: {body_err}")
        return False, f"HTTP {e.code}: {body_err}"
    except Exception as e:
        log(f"  ✗ Error: {type(e).__name__}: {e}")
        return False, f"{type(e).__name__}: {e}"

# === WALLET: múltiples fuentes ===
def obtener_wallet():
    """Busca la wallet_address en este orden:
    1) /root/wallet_address.txt (creado por el usuario)
    2) Variable de entorno WALLET_ADDRESS
    3) config.json de los bots (campo wallet_address)
    4) config.json de los bots (derivar de wallet_private_key)
    """
    # 1) Archivo explícito
    for r in ["/root/wallet_address.txt", "/opt/polymarket/wallet_address.txt",
              os.path.expanduser("~/wallet_address.txt"), "/tmp/wallet_address.txt"]:
        if os.path.exists(r):
            with open(r) as f:
                w = f.read().strip()
                if w.startswith("0x") and len(w) == 42:
                    log(f"  ✓ wallet de {r}: {w[:10]}...{w[-6:]}")
                    return w, f"archivo {r}"
            log(f"  {r} existe pero no contiene una dirección válida")

    # 2) Env
    w = os.environ.get("WALLET_ADDRESS", "").strip()
    if w.startswith("0x") and len(w) == 42:
        log(f"  ✓ wallet de env WALLET_ADDRESS")
        return w, "variable de entorno"

    # 3) config.json
    bots_dirs = [
        "/opt/polymarket/bot-polymarket-elon",
        "/opt/polymarket/bot-polymarket-elon-semanal",
        "/opt/polymarket/bot-polymarket-elon-mensual",
        "/opt/polymarket/bot-polymarket-zelenskyy",
        "/opt/polymarket/bot-polymarket-trump",
    ]
    for d in bots_dirs:
        if not os.path.isdir(d):
            continue
        cfg_path = os.path.join(d, "config.json")
        if not os.path.exists(cfg_path):
            continue
        try:
            with open(cfg_path) as f:
                cfg = json.load(f)
            w = (cfg.get("wallet_address") or "").strip()
            if w.startswith("0x") and len(w) == 42:
                log(f"  ✓ wallet de {d}/config.json")
                return w, f"{d}/config.json"
            pk = (cfg.get("wallet_private_key") or "").strip()
            if pk:
                try:
                    from eth_account import Account
                    acct = Account.from_key(pk)
                    log(f"  ✓ wallet derivada de {d}/config.json:wallet_private_key")
                    return acct.address, f"{d}/config.json:wallet_private_key (derivada)"
                except ImportError:
                    log(f"  {d}: tiene private_key pero eth_account no instalado")
                except Exception as e:
                    log(f"  {d}: error derivando: {e}")
        except Exception as e:
            log(f"  error leyendo {cfg_path}: {e}")

    return None, None

# === SALDO via Polygon RPC ===
def polygon_rpc(method, params):
    """Llama al JSON-RPC de Polygon."""
    payload = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}
    last_err = None
    for rpc in POLYGON_RPCS:
        try:
            req = urllib.request.Request(
                rpc, data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
                if "result" in data:
                    return data["result"]
                last_err = data.get("message", "?")
        except Exception as e:
            last_err = str(e)
            continue
    raise Exception(f"todos los RPC fallaron: {last_err}")

def leer_balance_token(wallet, token_address, decimales=6):
    """Lee el balance de un token ERC-20 via eth_call.
    Function signature: balanceOf(address) -> uint256
    Selector: 0x70a08231
    """
    # Quitar 0x y rellenar a 32 bytes
    wallet_clean = wallet.lower().replace("0x", "").zfill(64)
    data = "0x70a08231" + wallet_clean
    result = polygon_rpc("eth_call", [{"to": token_address, "data": data}, "latest"])
    return int(result, 16) / (10 ** decimales)

def consultar_saldo_v5(wallet):
    """Lee USDC nativo y USDC.e (los dos principales en Polygon)."""
    saldos = {}
    try:
        usdc = leer_balance_token(wallet, POLYMARKET_TOKENS["USDC"], 6)
        saldos["USDC"] = usdc
        log(f"  USDC nativo: ${usdc:.2f}")
    except Exception as e:
        log(f"  Error leyendo USDC: {e}")
        saldos["USDC"] = 0
    try:
        usdce = leer_balance_token(wallet, POLYMARKET_TOKENS["USDC.e"], 6)
        saldos["USDC.e"] = usdce
        log(f"  USDC.e: ${usdce:.2f}")
    except Exception as e:
        log(f"  Error leyendo USDC.e: {e}")
        saldos["USDC.e"] = 0
    # pUSD es más complejo, lo dejamos para v6
    saldos["pUSD"] = 0
    saldos["total"] = saldos["USDC"] + saldos["USDC.e"]
    return saldos

# === POSICIONES: clasificación fina ===
def clasificar_posicion(p, wallet):
    """Determina si una posición es del bot Zelenskyy, manual, o fantasma."""
    title = (p.get("title") or "").lower()
    slug = (p.get("slug") or "").lower()
    cur = float(p.get("currentValue", 0) or 0)
    init = float(p.get("initialValue", 0) or 0)
    pnl = cur - init

    # Categoría
    categoria = "OTRO"
    if "zelenskyy" in title or "zelensky" in title or "zelen" in slug:
        categoria = "ZELENSKYY_BOT"
    elif "elon" in title or "musk" in title:
        categoria = "ELON_BOT"
    elif "trump" in title:
        categoria = "TRUMP_BOT"
    elif "balance of power" in title or "d senate" in title or "d house" in title:
        categoria = "MANUAL_POLITICA"
    elif "romeu zema" in title or "brazil" in title:
        categoria = "MANUAL_BRASIL"
    else:
        categoria = "OTRO"

    # Estado
    if cur <= 0.001 and pnl < 0:
        estado = "FANTASMA"  # mercado cerrado, vale $0
    elif cur <= 0.001 and pnl == 0:
        estado = "VACIA"
    elif pnl > 0:
        estado = "EN_PROFIT"
    else:
        estado = "EN_PERDIDA"

    return categoria, estado

def analizar_posiciones_v5(wallet):
    url = f"{DATA_API}?user={wallet}&limit=200"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        posiciones = json.loads(r.read().decode())

    # Clasificar
    por_categoria = {}
    por_estado = {"FANTASMA": [], "EN_PROFIT": [], "EN_PERDIDA": [], "VACIA": []}
    total_cur = total_init = 0.0
    items = []
    for p in posiciones:
        try:
            size = float(p.get("size", 0) or 0)
            cur = float(p.get("currentValue", 0) or 0)
            init = float(p.get("initialValue", 0) or 0)
            title = (p.get("title") or "")[:70]
            outcome = p.get("outcome", "?")
            asset = p.get("asset", "")
            slug = p.get("slug", "")
            pnl = cur - init
            categoria, estado = clasificar_posicion(p, wallet)
            total_cur += cur
            total_init += init
            item = {"title": title, "outcome": outcome, "size": size,
                    "cur": cur, "init": init, "pnl": pnl, "asset": asset,
                    "slug": slug, "categoria": categoria, "estado": estado}
            items.append(item)
            por_categoria.setdefault(categoria, []).append(item)
            por_estado[estado].append(item)
        except Exception as e:
            log(f"  error parseando: {e}")
            continue
    return posiciones, items, por_categoria, por_estado, total_cur, total_init

# === MAIN ===
log("=" * 70)
log(f"DIAG V5 · {datetime.now().isoformat()}")
log("=" * 70)
log("")

errores = []
wallet = None
fuente = None
saldos = {}
items = por_categoria = por_estado = []
total_cur = total_init = 0.0
n_pos = 0

# 1) Wallet
log("[1/4] Buscando wallet address...")
wallet, fuente = obtener_wallet()
if not wallet:
    log("  ✗ NO se encontró wallet en ningún sitio")
    errores.append("wallet no encontrada")
else:
    log(f"  wallet: {wallet}")
    log(f"  fuente: {fuente}")

log("")

# 2) Saldo
log("[2/4] Consultando saldo on-chain via Polygon RPC...")
if wallet:
    try:
        saldos = consultar_saldo_v5(wallet)
        log(f"  TOTAL: ${saldos.get('total', 0):.2f}")
    except Exception as e:
        log(f"  ERROR consultando saldo: {e}")
        log(traceback.format_exc())
        errores.append(f"saldo: {e}")
else:
    errores.append("sin wallet")

log("")

# 3) Posiciones
log("[3/4] Analizando posiciones...")
if wallet:
    try:
        posiciones, items, por_categoria, por_estado, total_cur, total_init = analizar_posiciones_v5(wallet)
        n_pos = len(posiciones)
        log(f"  {n_pos} posiciones leídas")
        log(f"  Total: ${total_cur:.2f} valor, ${total_init:.2f} invertido, PnL ${total_cur - total_init:+.2f}")
        log(f"  Por estado:")
        for est, lista in por_estado.items():
            log(f"    {est}: {len(lista)}")
        log(f"  Por categoría:")
        for cat, lista in por_categoria.items():
            n = len(lista)
            v = sum(i["cur"] for i in lista)
            i = sum(i["init"] for i in lista)
            log(f"    {cat}: {n} (valor ${v:.2f}, invertido ${i:.2f})")
    except Exception as e:
        log(f"  ERROR: {e}")
        log(traceback.format_exc())
        errores.append(f"posiciones: {e}")
else:
    errores.append("sin wallet para posiciones")

log("")

# 4) Publicar
log("[4/4] Publicando informe...")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = f"diag_hetzner/diag_{ts}.txt"
inf = []
inf.append("=" * 78)
inf.append(f"DIAGNOSTICO V5 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
inf.append("=" * 78)
if errores:
    inf.append(f"ERRORES: {'; '.join(errores)}")
    inf.append("")
if wallet:
    inf.append(f"--- WALLET ---")
    inf.append(f"  {wallet}  (de {fuente})")
    inf.append("")
inf.append(f"--- SALDO ON-CHAIN (Polygon RPC directo) ---")
inf.append(f"  USDC nativo: ${saldos.get('USDC', 0):.2f}")
inf.append(f"  USDC.e:      ${saldos.get('USDC.e', 0):.2f}")
inf.append(f"  pUSD:        ${saldos.get('pUSD', 0):.2f} (no consultado en v5)")
inf.append(f"  TOTAL:       ${saldos.get('total', 0):.2f}")
inf.append("")
inf.append(f"--- POSICIONES ({n_pos}) ---")
inf.append(f"  Total invertido:  ${total_init:.2f}")
inf.append(f"  Valor actual:     ${total_cur:.2f}")
inf.append(f"  PnL no realizado: ${total_cur - total_init:+.2f}")
inf.append("")
# Por estado
inf.append(f"--- POR ESTADO ---")
for est in ["EN_PROFIT", "EN_PERDIDA", "FANTASMA", "VACIA"]:
    lista = por_estado.get(est, [])
    if not lista:
        continue
    v = sum(i["cur"] for i in lista)
    i = sum(i["init"] for i in lista)
    inf.append(f"  {est}: {len(lista)} posiciones (valor ${v:.2f}, invertido ${i:.2f})")
inf.append("")
# Por categoría
inf.append(f"--- POR CATEGORÍA ---")
for cat, lista in sorted(por_categoria.items()):
    v = sum(i["cur"] for i in lista)
    i = sum(i["init"] for i in lista)
    inf.append(f"  {cat}: {len(lista)} (valor ${v:.2f}, invertido ${i:.2f}, PnL ${v-i:+.2f})")
inf.append("")
# Detalle de las importantes
inf.append(f"--- DETALLE: EN_PROFIT ({len(por_estado.get('EN_PROFIT', []))}) ---")
for item in por_estado.get("EN_PROFIT", []):
    inf.append(f"  [{item['categoria']}] {item['title']}")
    inf.append(f"    {item['outcome']} size={item['size']:.2f}  cur=${item['cur']:.2f}  "
               f"init=${item['init']:.2f}  PnL=${item['pnl']:+.2f}")
inf.append("")
inf.append(f"--- DETALLE: FANTASMA (top 20 de {len(por_estado.get('FANTASMA', []))}) ---")
fantasmas = por_estado.get("FANTASMA", [])
# Ordenar por init desc (las que más dinero tenían)
fantasmas.sort(key=lambda x: -x["init"])
for item in fantasmas[:20]:
    inf.append(f"  [{item['categoria']}] {item['title']}")
    inf.append(f"    {item['outcome']} size={item['size']:.2f}  init=${item['init']:.2f}  → vale $0")
if len(fantasmas) > 20:
    inf.append(f"  ... y {len(fantasmas) - 20} más")
inf.append("")
inf.append(f"--- DETALLE: EN_PERDIDA (top 20) ---")
en_perdida = por_estado.get("EN_PERDIDA", [])
en_perdida.sort(key=lambda x: x["pnl"])
for item in en_perdida[:20]:
    inf.append(f"  [{item['categoria']}] {item['title']}")
    inf.append(f"    {item['outcome']} size={item['size']:.2f}  cur=${item['cur']:.2f}  "
               f"init=${item['init']:.2f}  PnL=${item['pnl']:+.2f}")
if len(en_perdida) > 20:
    inf.append(f"  ... y {len(en_perdida) - 20} más")
inf.append("")
inf.append("--- LOG COMPLETO ---")
inf.extend(LOG)
inf.append("=" * 78)

texto = "\n".join(inf)
ok, info = publicar(texto, ruta)
if ok:
    log(f"\n✓ URL: {info}")
else:
    log(f"\n✗ Error: {info}")
    log("")
    log("=== INFORME COMPLETO (publicación falló) ===")
    log(texto)
