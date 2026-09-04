#!/usr/bin/env python3
"""
SALDO REAL TOTAL v1
===================
Calcula el bankroll REAL combinando:
  - Saldo CLOB (USDC en el exchange, via SDK v2)
  - Valor de posiciones abiertas (data-api Polymarket)
NO usa los saldos virtuales de los JSON (están mal).

USO: python3 saldo_real_total.py
"""
import os
import sys
import json
import traceback
import urllib.request
import urllib.error
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
    payload = {"message": f"saldoreal {datetime.now().strftime('%H%M%S')}",
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

def get_balance_clob(env):
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
log(f"SALDO REAL TOTAL · {datetime.now().isoformat()}")
log("=" * 70)
log("")
log("⚠️  ESTE ES EL SALDO REAL DE TU WALLET POLYMARKET")
log("   NO usa los saldos virtuales de los JSON (que están mal)")
log("")

env = cargar_env("/etc/polymarket.env")
if not env:
    log("✗ no se pudo cargar /etc/polymarket.env"); sys.exit(1)
for k, v in env.items(): os.environ[k] = v
wallet = env.get("POLY_WALLET_ADDRESS", "").strip()
log(f"Wallet: {wallet}")
log("")

# 1) CLOB
log("[1/2] Consultando saldo CLOB (SDK)...")
clob, err_c = get_balance_clob(env)
if err_c:
    log(f"  ✗ {err_c}")
    clob = None
else:
    bal, allow = clob
    log(f"  ✓ Balance CLOB:   ${bal:.2f}")
    log(f"  ✓ Allowance:      ${allow:.2f}")
log("")

# 2) Posiciones
log("[2/2] Consultando posiciones abiertas (data-api)...")
pos, err_p = get_posiciones(wallet)
if err_p:
    log(f"  ✗ {err_p}")
    pos = None
else:
    log(f"  ✓ {pos['n_pos']} posiciones abiertas")
    log(f"  ✓ Valor actual:   ${pos['valor_actual']:.2f}")
    log(f"  ✓ Invertido:      ${pos['invertido']:.2f}")
    log(f"  ✓ PnL no realizado: ${pos['pnl_no_realizado']:+.2f}")
log("")

# 3) Calcular total REAL
log("=" * 70)
log("💰 BANKROLL REAL TOTAL")
log("=" * 70)
if clob and pos:
    bal, _ = clob
    total = bal + pos['valor_actual']
    log(f"  CLOB libre:        ${bal:.2f}")
    log(f"  Posiciones:        ${pos['valor_actual']:.2f}")
    log(f"  ─────────────────────────")
    log(f"  TOTAL REAL:        ${total:.2f}")
    log("")
    log(f"  PnL desde $500 inicial: ${total - 500:+.2f}")
    log("")
    log("  Desglose por bot (estimado, no exacto):")
    # Distribución naive: si los bots comparten wallet, no se puede separar
    # pero podemos listar las posiciones
    log(f"  (todos los bots usan la misma wallet 0x...{wallet[-4:]})")
elif clob:
    bal, _ = clob
    log(f"  CLOB libre:        ${bal:.2f}")
    log(f"  TOTAL REAL:        ${bal:.2f}")
elif pos:
    log(f"  Posiciones:        ${pos['valor_actual']:.2f}")
    log(f"  TOTAL REAL:        ${pos['valor_actual']:.2f}")
else:
    log("  ✗ No se pudo obtener saldo real")
log("")
log("=" * 70)
log("")
log("📊 PARA COMPARAR CON LOS JSON VIRTUALES (que están MAL):")
for nombre, fjson in [("Elon 48h", "/opt/polymarket/bot-polymarket-elon/real.json"),
                       ("Zelenskyy sem", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
                       ("Trump mens", "/opt/polymarket/bot-polymarket-trump/real.json")]:
    try:
        with open(fjson) as f: d = json.load(f)
        s = d.get("saldo", "?")
        log(f"  {nombre}: ${s} (virtual, NO real)")
    except Exception as e:
        log(f"  {nombre}: no se pudo leer")
log("")
log("=" * 70)

# Publicar
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = f"diag_hetzner/saldoreal_{ts}.txt"
inf = ["=" * 78,
       f"SALDO REAL TOTAL - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, ""]
inf.append(f"Wallet: {wallet}")
inf.append("")
inf.append("--- COMPONENTES ---")
if clob:
    bal, allow = clob
    inf.append(f"  CLOB balance:  ${bal:.2f}")
    inf.append(f"  CLOB allow:    ${allow:.2f}")
if pos:
    inf.append(f"  Posiciones:    {pos['n_pos']}")
    inf.append(f"  Valor actual:  ${pos['valor_actual']:.2f}")
    inf.append(f"  Invertido:     ${pos['invertido']:.2f}")
    inf.append(f"  PnL no realiz: ${pos['pnl_no_realizado']:+.2f}")
inf.append("")
if clob and pos:
    bal, _ = clob
    total = bal + pos['valor_actual']
    inf.append("=" * 78)
    inf.append(f"==> BANKROLL REAL TOTAL: ${total:.2f}")
    inf.append(f"   (${bal:.2f} CLOB + ${pos['valor_actual']:.2f} posiciones)")
    inf.append(f"==> PnL desde $500 inicial: ${total - 500:+.2f}")
    inf.append("=" * 78)
inf.append("")
inf.append("--- JSON VIRTUALES (MAL, no usar) ---")
for nombre, fjson in [("Elon 48h", "/opt/polymarket/bot-polymarket-elon/real.json"),
                       ("Zelenskyy sem", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
                       ("Trump mens", "/opt/polymarket/bot-polymarket-trump/real.json")]:
    try:
        with open(fjson) as f: d = json.load(f)
        inf.append(f"  {nombre}: ${d.get('saldo', '?')} (virtual)")
    except: pass
inf.append("")
inf.append("--- LOG COMPLETO ---")
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ok = publicar(texto, ruta)
log(f"publicado: {ok}")
