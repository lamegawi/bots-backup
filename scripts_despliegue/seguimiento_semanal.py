#!/usr/bin/env python3
"""
SEGUIMIENTO SEMANAL · analisis completo de los 3 bots
=====================================================
Compara el rendimiento desde el ultimo reset (1 semana) e incluye:
  - Saldo real actual (on-chain via eth_call)
  - Posiciones abiertas
  - Filtros aplicados en la semana
  - Win rate por bot
  - PnL real vs virtual
  - Proyeccion a 30 dias

USO: python3 seguimiento_semanal.py
     # automatico, lo puedes poner en cron lunes 09:00
"""
import os
import sys
import json
import subprocess
import base64
import urllib.request
from datetime import datetime, timedelta

LOG = []
OUT = []
def log(s):
    line = str(s)
    print(line, flush=True)
    LOG.append(line)
    OUT.append(line)

def find_pat():
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"): return t
    return os.environ.get("GH_PAT", "")

def publicar(texto, ruta, pat):
    if not pat: return False
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {pat}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"semanal {datetime.now().strftime('%Y%m%d_%H%M')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {pat}", "Content-Type": "application/json",
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

def get_filtros_semana(srv):
    """Cuenta los filtros aplicados esta semana."""
    hace_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    r = subprocess.run(
        ["journalctl", "-u", srv, f"--since={hace_7d}", "--no-pager"],
        capture_output=True, text=True, timeout=15)
    if r.returncode != 0: return 0, 0
    lineas = r.stdout.split("\n")
    p_lado = sum(1 for ln in lineas if "[FILTRO]" in ln and "p_lado" in ln)
    cuota = sum(1 for ln in lineas if "[FILTRO]" in ln and "cuota" in ln and ">25" in ln)
    return p_lado, cuota

def analizar_bot(nombre, srv, fjson):
    """Analiza un bot: estado, ops de la semana, win rate."""
    log(f"\n--- {nombre} ({srv}) ---")
    # servicio
    r = subprocess.run(["systemctl", "is-active", srv], capture_output=True, text=True, timeout=5)
    activo = r.stdout.strip() == "active"
    log(f"  servicio: {r.stdout.strip()}")
    if not activo:
        log(f"  ⚠️  SERVICIO NO ACTIVO")
        return None
    # json
    if not os.path.exists(fjson):
        log(f"  sin JSON ({fjson})")
        return None
    with open(fjson) as f: d = json.load(f)
    saldo = d.get("saldo", 0)
    ops = d.get("operaciones") or d.get("historial") or []
    activa = d.get("activa")
    log(f"  saldo: ${saldo:.2f}")
    log(f"  ops totales: {len(ops)}")
    log(f"  activa: {'SÍ' if activa else 'NO'}")
    # ops de la semana
    hace_7d = datetime.now() - timedelta(days=7)
    ops_semana = []
    for op in ops:
        f_op = op.get("fecha") or op.get("ts") or ""
        try:
            fdt = datetime.fromisoformat(str(f_op).replace("Z", "+00:00").split("T")[0])
            if fdt >= hace_7d:
                ops_semana.append(op)
        except: continue
    # win rate
    cerradas = [o for o in ops if o.get("resultado") in ("G", "P")]
    if cerradas:
        wins = sum(1 for o in cerradas if o.get("resultado") == "G")
        wr = wins / len(cerradas) * 100
        pnl = sum(float(o.get("beneficio") or o.get("benef") or o.get("pnl") or 0) for o in cerradas)
        log(f"  cerradas: {len(cerradas)}, G: {wins}, P: {len(cerradas)-wins}")
        log(f"  win rate: {wr:.1f}%")
        log(f"  PnL cerrado: ${pnl:+.2f}")
    else:
        wr = 0
        pnl = 0
        log(f"  sin ops cerradas")
    # filtros de la semana
    fp, fc = get_filtros_semana(srv)
    log(f"  filtros descartados (semana): p_lado<10%={fp}, cuota>25={fc}")
    log(f"  TOTAL descartes: {fp+fc}")
    return {
        "nombre": nombre, "servicio": srv, "saldo": saldo,
        "ops_totales": len(ops), "ops_cerradas": len(cerradas),
        "wins": sum(1 for o in cerradas if o.get("resultado") == "G"),
        "win_rate": wr, "pnl_cerrado": pnl,
        "filtros_p_lado": fp, "filtros_cuota": fc,
        "activa": activa,
    }

# === MAIN ===
log("=" * 70)
log(f"SEGUIMIENTO SEMANAL · {datetime.now().isoformat()}")
log("=" * 70)
log("")

# 1) Saldo real
log("[1] Saldo real (on-chain + posiciones)")
env = cargar_env("/etc/polymarket.env")
for k, v in env.items(): os.environ[k] = v
wallet = env.get("POLY_WALLET_ADDRESS", "").strip()
log(f"  wallet: {wallet}")
saldos = saldo_onchain(wallet)
cash = sum(saldos.values())
pos, _ = get_posiciones(wallet)
val_pos = pos["valor_actual"] if pos else 0
total_real = cash + val_pos
log(f"  cash on-chain:  ${cash:.2f}")
log(f"  posiciones:     ${val_pos:.2f}  ({pos['n_pos'] if pos else 0} mercados)")
log(f"  TOTAL REAL:     ${total_real:.2f}")
log(f"  PnL desde $500: ${total_real - 500:+.2f} ({(total_real-500)/500*100:+.1f}%)")
log("")

# 2) Cada bot
log("[2] Analisis por bot")
BOTS = [
    ("Elon 48h",      "poly-elon",      "/opt/polymarket/bot-polymarket-elon/real.json"),
    ("Zelenskyy sem", "poly-zelenskyy", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
    ("Trump mens",    "poly-trump",     "/opt/polymarket/bot-polymarket-trump/real.json"),
]
resultados = []
for n, s, fp in BOTS:
    r = analizar_bot(n, s, fp)
    if r: resultados.append(r)

# 3) Resumen
log("")
log("=" * 70)
log("RESUMEN SEMANAL")
log("=" * 70)
log(f"{'Bot':<18} {'WinRate':>10} {'PnL':>10} {'Filtros':>10} {'Saldo':>10}")
log("-" * 60)
for r in resultados:
    log(f"{r['nombre']:<18} {r['win_rate']:>9.1f}% ${r['pnl_cerrado']:>+8.2f} {r['filtros_p_lado']+r['filtros_cuota']:>10} ${r['saldo']:>8.2f}")

# 4) Proyeccion
log("")
log("PROYECCION (asumiendo mismas condiciones):")
for r in resultados:
    pnl_dia = r['pnl_cerrado'] / 7
    pnl_30d = pnl_dia * 30
    log(f"  {r['nombre']}: ${pnl_30d:+.2f}/mes (${pnl_dia:+.2f}/dia)")

log("")
log("RECOMENDACIONES:")
trump = next((r for r in resultados if "Trump" in r['nombre']), None)
if trump and trump['filtros_p_lado']+trump['filtros_cuota'] > 50:
    log(f"  ✓ Trump: {trump['filtros_p_lado']+trump['filtros_cuota']} filtros salvaron la semana")
elon = next((r for r in resultados if "Elon" in r['nombre']), None)
if elon:
    if elon['win_rate'] < 30:
        log(f"  ⚠️  Elon: win rate {elon['win_rate']:.1f}% — considera reducir stake")
    else:
        log(f"  ✓ Elon: win rate {elon['win_rate']:.1f}% — funcionando bien")

if total_real < 250:
    log(f"  🚨 BANKROLL BAJO: ${total_real:.2f} < $250 — PARA los bots")
elif total_real > 350:
    log(f"  ✓ Bankroll saludable: ${total_real:.2f} > $350")

log("")
log("=" * 70)

# Publicar
pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = "Seguimiento semanal - " + ts + "\n\n" + "\n".join(OUT)
ruta = f"diag_hetzner/semanal_{ts}.txt"
ok = publicar(texto, ruta, pat)
log(f"publicado: {ok}")
