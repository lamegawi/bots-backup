#!/usr/bin/env python3
"""
CONSULTAR SALDO CLOB - v7
=========================
ARREGLADO: set_api_creds con los nombres correctos (apiKey/secret/passphrase)
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

def cargar_pat():
    for r in ["/root/diag_token.txt", "/opt/polymarket/diag_token.txt",
              os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            with open(r) as f:
                t = f.read().strip()
                if t.startswith("ghp_") or t.startswith("github_pat_"):
                    return t
    return os.environ.get("GH_PAT", "")

PAT = cargar_pat()
REPO = "lamegawi/bots-backup"
RAMA_DIAG = "diag-public"

def publicar(texto, ruta):
    if not PAT:
        return False, "Sin PAT"
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/contents/{ruta}?ref={RAMA_DIAG}",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError:
        pass
    payload = {"message": f"saldo {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": RAMA_DIAG}
    if sha:
        payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {PAT}", "Content-Type": "application/json",
                 "Accept": "application/vnd.github+json", "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            return True, resp.get("content", {}).get("html_url", "")
    except Exception as e:
        return False, str(e)

def cargar_env(ruta):
    env = {}
    if not os.path.exists(ruta):
        return env
    try:
        with open(ruta) as f:
            for linea in f:
                linea = linea.strip()
                if not linea or linea.startswith('#'):
                    continue
                if '=' in linea:
                    k, v = linea.split('=', 1)
                    env[k.strip()] = v.strip().strip('"').strip("'")
    except Exception as e:
        log(f"  error leyendo {ruta}: {e}")
    return env

def consultar_saldo_sdk_v2_v7(env):
    """v7: usa los nombres correctos de campos."""
    try:
        from py_clob_client_v2.client import ClobClient
        from py_clob_client_v2.clob_types import BalanceAllowanceParams, AssetType
    except ImportError as e:
        return None, f"py_clob_client_v2 no instalado: {e}"
    pk = env.get("POLY_PRIVATE_KEY", "").strip()
    if not pk:
        return None, "sin private key"
    try:
        HOST = "https://clob.polymarket.com"
        CHAIN_ID = 137
        client = ClobClient(HOST, key=pk, chain_id=CHAIN_ID, signature_type=2)
        # 1) Derivar la API key
        api_creds = client.create_or_derive_api_key()
        log(f"  api_key derivada: {api_creds.api_key[:8] if hasattr(api_creds, 'api_key') else str(api_creds)[:8]}")
        # 2) Setear credenciales — los nombres son apiKey, secret, passphrase
        # Mirar el código fuente para ver qué espera
        log(f"  tipo de api_creds: {type(api_creds)}")
        log(f"  contenido: {api_creds if not hasattr(api_creds, '__dict__') else api_creds.__dict__}")
        # Probar varias formas
        for intento in [
            api_creds,  # el objeto tal cual
            {"apiKey": api_creds.api_key, "secret": api_creds.api_secret, "passphrase": api_creds.api_passphrase},
            {"api_key": api_creds.api_key, "api_secret": api_creds.api_secret, "api_passphrase": api_creds.api_passphrase},
        ]:
            try:
                client.set_api_creds(intento)
                log(f"  ✓ credenciales seteadas (intento: {type(intento).__name__})")
                break
            except Exception as e:
                log(f"  intento {type(intento).__name__}: {e}")
                continue
        else:
            return None, "todos los intentos de set_api_creds fallaron"
        # 3) Consultar
        r = client.get_balance_allowance(
            BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))
        balance = float(r.get("balance", 0)) / 1e6
        allowance = float(r.get("allowance", 0)) / 1e6
        return (balance, allowance), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}\n{traceback.format_exc()}"

def consultar_saldo_via_positions(wallet):
    url = f"https://data-api.polymarket.com/positions?user={wallet}&limit=200"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            posiciones = json.loads(r.read())
        total_value = sum(float(p.get("currentValue", 0) or 0) for p in posiciones)
        total_init = sum(float(p.get("initialValue", 0) or 0) for p in posiciones)
        return {
            "n_pos": len(posiciones),
            "valor_actual": total_value,
            "invertido": total_init,
            "pnl": total_value - total_init,
        }, None
    except Exception as e:
        return None, str(e)

# === MAIN ===
log("=" * 70)
log(f"CONSULTA SALDO CLOB v7 · {datetime.now().isoformat()}")
log("=" * 70)
log("")

env = cargar_env("/etc/polymarket.env")
if not env:
    log("  ✗ no se pudo cargar env")
    sys.exit(1)
for k, v in env.items():
    os.environ[k] = v
wallet = env.get("POLY_WALLET_ADDRESS", "").strip()
log(f"  wallet: {wallet}")
log("")

log("[1/3] SDK v2 con set_api_creds fixeado...")
saldo, err = consultar_saldo_sdk_v2_v7(env)
if err:
    log(f"  ✗ {err}")
else:
    bal, allow = saldo
    log(f"  ✓ Balance CLOB: ${bal:.2f}")
    log(f"  ✓ Allowance:    ${allow:.2f}")

log("")

log("[2/3] Portfolio (data-api)...")
portfolio, err_p = consultar_saldo_via_positions(wallet)
if err_p:
    log(f"  ✗ {err_p}")
else:
    log(f"  ✓ {portfolio['n_pos']} posiciones, valor ${portfolio['valor_actual']:.2f}")

log("")

log("[3/3] Publicando informe...")
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = f"diag_hetzner/saldo_{ts}.txt"
inf = []
inf.append("=" * 78)
inf.append(f"CONSULTA SALDO CLOB v7 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
inf.append("=" * 78)
inf.append(f"Wallet: {wallet}")
inf.append("")
inf.append("--- SALDO CLOB (SDK v2) ---")
if saldo:
    bal, allow = saldo
    inf.append(f"  Balance:   ${bal:.2f}")
    inf.append(f"  Allowance: ${allow:.2f}")
else:
    inf.append(f"  ERROR: {err}")
inf.append("")
inf.append("--- PORTFOLIO (data-api) ---")
if portfolio:
    inf.append(f"  Posiciones:    {portfolio['n_pos']}")
    inf.append(f"  Valor actual:  ${portfolio['valor_actual']:.2f}")
    inf.append(f"  Invertido:     ${portfolio['invertido']:.2f}")
    inf.append(f"  PnL no realizado: ${portfolio['pnl']:+.2f}")
inf.append("")
if saldo and portfolio:
    bal, _ = saldo
    total = bal + portfolio['valor_actual']
    inf.append("=" * 78)
    inf.append(f"==> BANKROLL TOTAL: ${total:.2f}")
    inf.append(f"   = ${bal:.2f} (CLOB) + ${portfolio['valor_actual']:.2f} (posiciones)")
    inf.append(f"==> PnL desde $500 inicial: ${total - 500:+.2f}")
    inf.append("=" * 78)
inf.append("")
inf.append("--- LOG COMPLETO ---")
inf.extend(LOG)
inf.append("=" * 78)

texto = "\n".join(inf)
ok, info = publicar(texto, ruta)
if ok:
    log(f"  ✓ Publicado: {info}")
else:
    log(f"  ✗ Error: {info}")
    log("")
    log("=== INFORME COMPLETO ===")
    log(texto)
