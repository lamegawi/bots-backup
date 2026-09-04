#!/usr/bin/env python3
"""
SALDO REAL TOTAL v2
===================
Usa el MISMO método que el bot de Telegram:
  1) Lee on-chain via eth_call directo a Polygon (pUSD + USDC.e + USDC)
  2) Lee CLOB SDK (get_balance_allowance) por si acaso
  3) Lee data-api posiciones
Suma TODO: eso es el bankroll real.

El bot Telegram dice $292.34, asi que este script debería decir lo mismo.
"""
import os
import sys
import json
import subprocess
import urllib.request
import base64
from datetime import datetime

LOG = []
def log(s):
    s = str(s)
    print(s, flush=True)
    LOG.append(s)

def find_pat():
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"): return t
    return os.environ.get("GH_PAT", "")

PAT = find_pat()
REPO = "lamegawi/bots-backup"

def publicar(texto, ruta):
    if not PAT: return False
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"saldoreal2 {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {PAT}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return True
    except Exception as e: return False

def cargar_env(ruta):
    env = {}
    if not os.path.exists(ruta): return env
    with open(ruta) as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith('#'): continue
            if '=' in linea:
                k, v = linea.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env

# === Método on-chain (el bueno) ===
def saldo_onchain(wallet):
    """Lee pUSD + USDC.e + USDC directo de Polygon via eth_call."""
    rpcs = [
        "https://polygon-rpc.com",
        "https://1rpc.io/matic",
        "https://polygon.llamarpc.com",
        "https://rpc.ankr.com/polygon",
    ]
    tokens = [
        ("pUSD",   "0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB", 6),
        ("USDC.e", "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174", 6),
        ("USDC",   "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359", 6),
    ]
    data = "0x70a08231" + "0" * 24 + wallet.lower()[2:]
    saldos = {}
    for simbolo, contrato, dec in tokens:
        body = json.dumps({"jsonrpc": "2.0", "method": "eth_call",
                           "params": [{"to": contrato, "data": data}, "latest"], "id": 1})
        saldos[simbolo] = 0.0
        for rpc in rpcs:
            try:
                out = subprocess.run(
                    ["curl", "-s", "--max-time", "10", "-X", "POST", rpc,
                     "-H", "Content-Type: application/json", "-d", body],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=15).stdout
                r = json.loads(out)
                if "result" in r and r["result"] not in ("0x", "0x0", None):
                    saldos[simbolo] = int(r["result"], 16) / (10 ** dec)
                    log(f"  {simbolo}: ${saldos[simbolo]:.2f}  (vía {rpc})")
                    break
            except Exception as e:
                log(f"  {simbolo} via {rpc}: {e}")
                continue
    return saldos

# === Método CLOB SDK (complemento) ===
def saldo_clob(env):
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    except ImportError as e:
        return None, f"py_clob_client_v2 no instalado: {e}"
    pk = env.get("POLY_PRIVATE_KEY", "").strip()
    if not pk: return None, "sin private key"
    try:
        client = ClobClient("https://clob.polymarket.com", key=pk, chain_id=137, signature_type=2)
        api_creds = client.create_or_derive_api_key()
        client.set_api_creds(api_creds)
        r = client.get_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        return (float(r.get("balance", 0)) / 1e6, float(r.get("allowance", 0)) / 1e6), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"

# === data-api posiciones ===
def get_posiciones(wallet):
    url = f"https://data-api.polymarket.com/positions?user={wallet}&limit=500"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            posiciones = json.loads(r.read())
        val_actual = sum(float(p.get("currentValue", 0) or 0) for p in posiciones)
        val_inicial = sum(float(p.get("initialValue", 0) or 0) for p in posiciones)
        return {
            "n_pos": len(posiciones),
            "valor_actual": val_actual,
            "invertido": val_inicial,
            "pnl_no_realizado": val_actual - val_inicial,
            "raw": posiciones,
        }, None
    except Exception as e:
        return None, str(e)

# === MAIN ===
log("=" * 70)
log(f"SALDO REAL TOTAL v2 (método del bot Telegram) · {datetime.now().isoformat()}")
log("=" * 70)
log("")
log("Lee el saldo EXACTAMENTE como lo hace el bot de Telegram:")
log("  eth_call directo a Polygon → pUSD + USDC.e + USDC")
log("")

env = cargar_env("/etc/polymarket.env")
if not env:
    log("✗ no se pudo cargar /etc/polymarket.env"); sys.exit(1)
for k, v in env.items(): os.environ[k] = v
wallet = env.get("POLY_WALLET_ADDRESS", "").strip()
log(f"Wallet: {wallet}")
log("")

# 1) on-chain (este es el bueno)
log("[1/3] Saldo on-chain (Polygon eth_call)...")
log("      tokens: pUSD + USDC.e + USDC")
saldos = saldo_onchain(wallet)
total_onchain = sum(saldos.values())
log(f"  subtotal on-chain: ${total_onchain:.2f}")
log("")

# 2) CLOB
log("[2/3] Saldo CLOB (SDK)...")
clob, err_c = saldo_clob(env)
if err_c:
    log(f"  ✗ {err_c}")
    clob = None
else:
    bal, allow = clob
    log(f"  ✓ CLOB balance:  ${bal:.2f}")
    log(f"  ✓ CLOB allowance: ${allow:.2f}")
log("")

# 3) data-api
log("[3/3] Posiciones abiertas (data-api)...")
pos, err_p = get_posiciones(wallet)
if err_p:
    log(f"  ✗ {err_p}")
    pos = None
else:
    log(f"  ✓ {pos['n_pos']} posiciones")
    log(f"  ✓ valor actual:  ${pos['valor_actual']:.2f}")
log("")

# 4) TOTAL REAL
log("=" * 70)
log("💰 BANKROLL REAL TOTAL (mismo método que el bot Telegram)")
log("=" * 70)
total = total_onchain
if clob: total += clob[0]
if pos: total += pos['valor_actual']
log(f"  on-chain Polygon:    ${total_onchain:>9.2f}  ← este es el que ve el bot")
if clob: log(f"  + CLOB balance:      ${clob[0]:>9.2f}")
if pos: log(f"  + posiciones value:  ${pos['valor_actual']:>9.2f}")
log(f"  ─────────────────────────────────────────")
log(f"  TOTAL:               ${total:>9.2f}")
log("")
log(f"  PnL desde $500 inicial: ${total - 500:+.2f}")
log("=" * 70)
log("")
log("📊 SALDOS VIRTUALES (JSON, MAL):")
for nombre, fjson in [("Elon 48h",      "/opt/polymarket/bot-polymarket-elon/real.json"),
                       ("Zelenskyy sem", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
                       ("Trump mens",    "/opt/polymarket/bot-polymarket-trump/real.json")]:
    try:
        with open(fjson) as f: d = json.load(f)
        s = d.get("saldo", "?")
        log(f"  {nombre}: ${s} (virtual)")
    except: log(f"  {nombre}: (no existe)")
log("")
log("=" * 70)

# Publicar
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = f"diag_hetzner/saldoreal2_{ts}.txt"
inf = ["=" * 78,
       f"SALDO REAL TOTAL v2 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, "",
       f"Wallet: {wallet}", "",
       "--- ON-CHAIN (Polygon eth_call, método del bot Telegram) ---"]
for k, v in saldos.items(): inf.append(f"  {k}: ${v:.2f}")
inf.append(f"  SUBTOTAL: ${total_onchain:.2f}")
inf.append("")
inf.append("--- CLOB SDK ---")
if clob: inf.append(f"  Balance: ${clob[0]:.2f}, Allowance: ${clob[1]:.2f}")
else: inf.append("  (no leido)")
inf.append("")
inf.append("--- DATA-API posiciones ---")
if pos:
    inf.append(f"  {pos['n_pos']} posiciones, valor ${pos['valor_actual']:.2f}")
inf.append("")
inf.append("=" * 78)
inf.append(f"BANKROLL REAL TOTAL: ${total:.2f}")
inf.append(f"PnL desde $500 inicial: ${total - 500:+.2f}")
inf.append("=" * 78)
inf.append("")
inf.append("--- JSON VIRTUALES (no usar) ---")
for nombre, fjson in [("Elon 48h",      "/opt/polymarket/bot-polymarket-elon/real.json"),
                       ("Zelenskyy sem", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
                       ("Trump mens",    "/opt/polymarket/bot-polymarket-trump/real.json")]:
    try:
        with open(fjson) as f: d = json.load(f)
        inf.append(f"  {nombre}: ${d.get('saldo', '?')} (virtual)")
    except: inf.append(f"  {nombre}: (no existe)")
inf.append("")
inf.append("--- LOG COMPLETO ---")
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ok = publicar(texto, ruta)
log(f"publicado: {ok}")
