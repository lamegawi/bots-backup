#!/usr/bin/env python3
"""
TARJETA - 5 puntos de acción con datos REALES
=============================================
Genera un informe con 5 acciones concretas para los próximos 7 días.
Usa el método on-chain (como el bot Telegram) + el JSON de los bots.
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

def publicar(texto, ruta):
    if not PAT: return False
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"tarjeta5 {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {PAT}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return True
    except: return False

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

def saldo_onchain(wallet):
    rpcs = ["https://polygon-rpc.com", "https://1rpc.io/matic",
            "https://polygon.llamarpc.com", "https://rpc.ankr.com/polygon"]
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
                    ["curl", "-s", "--max-time", "10", "-X", "POST", rpc,
                     "-H", "Content-Type: application/json", "-d", body],
                    capture_output=True, text=True, encoding="utf-8", errors="replace",
                    timeout=15).stdout
                r = json.loads(out)
                if "result" in r and r["result"] not in ("0x", "0x0", None):
                    saldos[simbolo] = int(r["result"], 16) / (10 ** dec)
                    break
            except: continue
    return saldos

def get_posiciones(wallet):
    url = f"https://data-api.polymarket.com/positions?user={wallet}&limit=500"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            posiciones = json.loads(r.read())
        val_actual = sum(float(p.get("currentValue", 0) or 0) for p in posiciones)
        val_inicial = sum(float(p.get("initialValue", 0) or 0) for p in posiciones)
        return {"n_pos": len(posiciones), "valor_actual": val_actual,
                "invertido": val_inicial,
                "pnl_no_realizado": val_actual - val_inicial}, None
    except Exception as e: return None, str(e)

# === MAIN ===
log("Generando tarjeta con 5 puntos de acción...")
log("")

env = cargar_env("/etc/polymarket.env")
for k, v in env.items(): os.environ[k] = v
wallet = env.get("POLY_WALLET_ADDRESS", "").strip()

saldos = saldo_onchain(wallet)
cash = sum(saldos.values())
pos, _ = get_posiciones(wallet)
val_pos = pos["valor_actual"] if pos else 0
total = cash + val_pos

# Datos por bot
bots = {}
for nombre, srv, fjson in [
    ("Elon 48h",      "poly-elon",      "/opt/polymarket/bot-polymarket-elon/real.json"),
    ("Zelenskyy sem", "poly-zelenskyy", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
    ("Trump mens",    "poly-trump",     "/opt/polymarket/bot-polymarket-trump/real.json"),
]:
    try:
        with open(fjson) as f: d = json.load(f)
        bots[nombre] = {
            "servicio": srv,
            "json": fjson,
            "saldo_virtual": d.get("saldo", 0),
            "activa": d.get("activa") is not None,
            "ops": d.get("operaciones") or d.get("historial") or [],
        }
    except:
        bots[nombre] = {"servicio": srv, "json": fjson, "saldo_virtual": 0,
                        "activa": False, "ops": []}

# Generar tarjeta
tarjeta = []
tarjeta.append("=" * 78)
tarjeta.append(f"  TARJETA DE ACCIÓN · 5 PUNTOS · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
tarjeta.append("=" * 78)
tarjeta.append("")
tarjeta.append("📊 DIAGNÓSTICO REAL (método del bot Telegram)")
tarjeta.append("-" * 78)
tarjeta.append(f"  Cash on-chain (pUSD + USDC.e + USDC):   ${cash:>9.2f}")
for tok, val in saldos.items():
    tarjeta.append(f"      · {tok:<8}                        ${val:>9.2f}")
tarjeta.append(f"  Posiciones abiertas ({pos['n_pos'] if pos else 0} mercados):    ${val_pos:>9.2f}")
tarjeta.append(f"  ─────────────────────────────────────────")
tarjeta.append(f"  BANKROLL REAL TOTAL:                      ${total:>9.2f}")
tarjeta.append(f"  PnL desde $500 inicial:                   ${total - 500:>+9.2f}  ({(total-500)/500*100:+.1f}%)")
tarjeta.append("")
tarjeta.append("📋 SALDOS VIRTUALES vs REALES (los JSON mienten)")
tarjeta.append("-" * 78)
tarjeta.append(f"  {'Bot':<18} {'Virtual':>12} {'Real (estimado)':>16} {'Activa':>8}")
for n, b in bots.items():
    tarjeta.append(f"  {n:<18} ${b['saldo_virtual']:>10.2f}  ${cash/3:>14.2f}  {'SÍ' if b['activa'] else 'NO':>8}")
tarjeta.append("")
tarjeta.append("=" * 78)
tarjeta.append("🎯 5 ACCIONES CONCRETAS PARA LOS PRÓXIMOS 7 DÍAS")
tarjeta.append("=" * 78)
tarjeta.append("")
tarjeta.append("1️⃣  ACEPTAR LA REALIDAD Y ACTUAR")
tarjeta.append("-" * 78)
tarjeta.append(f"   El bankroll REAL es ${total:.2f} (no $1234 que dicen los JSON).")
tarjeta.append(f"   Has perdido ${abs(total-500):.2f} del capital inicial ({(500-total)/500*100:.0f}%).")
tarjeta.append(f"   Con ${total:.2f} la estrategia debe cambiar: stakes más pequeños,")
tarjeta.append(f"   más selectivo. La paciencia es rentable.")
tarjeta.append("")
tarjeta.append("2️⃣  DEJAR QUE EL FILTRO FUNCIONE (sin tocar nada)")
tarjeta.append("-" * 78)
tarjeta.append(f"   Los 3 bots ya tienen el filtro p_lado<10% y cuota<25 (desde 14:50).")
tarjeta.append(f"   Trump YA bloqueó 2 cuotas absurdas (2000 y 142).")
tarjeta.append(f"   En 7 días comparamos win rate antes/después.")
tarjeta.append(f"   → comando diario: python3 /root/seguimiento_filtros.py")
tarjeta.append("")
tarjeta.append("3️⃣  ARREGLAR EL BUG DEL PnL EN LOS JSON (prioridad alta)")
tarjeta.append("-" * 78)
tarjeta.append(f"   Los JSON reportan saldos falsos (Elon $477, Zelenskyy $756).")
tarjeta.append(f"   Bug en operar_real.py línea 381/128: el benef no cuadra con la wallet.")
tarjeta.append(f"   Solución: recalcular el saldo de cada JSON desde el bankroll real")
tarjeta.append(f"   distribuido proporcionalmente a las ops.")
tarjeta.append(f"   → script: python3 /root/sincronizar_saldo_json.py --apply")
tarjeta.append("")
tarjeta.append("4️⃣  CONSIDERAR PARAR ELON (es el más arriesgado)")
tarjeta.append("-" * 78)
tarjeta.append(f"   Elon: win rate 14%, $10 en <40 con cuota 19.6 (suicida).")
tarjeta.append(f"   Aún con el filtro, Elon apuesta a mercados muy volátiles.")
tarjeta.append(f"   Opción: systemctl stop poly-elon (y dejar Zelenskyy solo).")
tarjeta.append(f"   Mejor opción: reducir su stake máximo a $3-5.")
tarjeta.append("")
tarjeta.append("5️⃣  MONITOREO DIARIO (5 minutos al día)")
tarjeta.append("-" * 78)
tarjeta.append(f"   Todos los días a las 20:00 ejecuta:")
tarjeta.append(f"     python3 /root/saldo_real_total_v2.py    # saldo real")
tarjeta.append(f"     python3 /root/seguimiento_filtros.py    # filtros aplicados")
tarjeta.append(f"   Anota el resultado en un txt local. Si en 7 días:")
tarjeta.append(f"     · bankroll < $250 → PARA los 3 bots")
tarjeta.append(f"     · bankroll > $350 → mantén estrategia")
tarjeta.append(f"     · win rate > 30% → considera subir stakes")
tarjeta.append("")
tarjeta.append("=" * 78)
tarjeta.append("📅 CHECKLIST DIARIO (5 min)")
tarjeta.append("=" * 78)
tarjeta.append("  □ Ejecutar saldo_real_total_v2.py")
tarjeta.append("  □ Ejecutar seguimiento_filtros.py")
tarjeta.append("  □ Anotar el resultado")
tarjeta.append("  □ Si bankroll cae mucho, parar bots")
tarjeta.append("")
tarjeta.append("=" * 78)

texto = "\n".join(tarjeta)
print(texto)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ruta = f"diag_hetzner/tarjeta5_{ts}.txt"
ok = publicar(texto, ruta)
print(f"\npublicado: {ok}")
