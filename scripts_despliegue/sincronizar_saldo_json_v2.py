#!/usr/bin/env python3
"""
SINCRONIZAR SALDOS JSON v2
==========================
Arregla el bug de los JSON manteniendo coherencia con el PnL histórico.

Logica nueva:
  bankroll_inicial_real = cash_real + pnl_historico_perdido
  saldo_nuevo = bankroll_inicial_real + pnl_historico_perdido
               = cash_real
  (es decir, el saldo actual del JSON = cash real en wallet, PERO
   queda registro de cuánto se perdió)

Mas simple:
  saldo_nuevo = cash_real  (lo que realmente tienes)
  Anotamos en el JSON cuanto se "perdio" vs lo que el JSON decia
  para mantener trazabilidad.

USO:
  python3 sincronizar_saldo_json_v2.py --dry
  python3 sincronizar_saldo_json_v2.py --apply
"""
import os
import sys
import json
import shutil
import argparse
import subprocess
import base64
import urllib.request
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

def publicar(texto, ruta):
    pat = find_pat()
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
    payload = {"message": f"syncjson2 {datetime.now().strftime('%H%M%S')}",
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

def calcular_pnl_real(ops):
    """PnL real = suma de los beneficios de las ops cerradas."""
    pnl = 0.0
    for op in ops:
        res = op.get("resultado", "")
        if res in ("G", "P"):
            b = float(op.get("beneficio") or op.get("benef") or op.get("pnl") or 0)
            pnl += b
    return pnl

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.dry and not args.apply:
        args.dry = True

    log("=" * 70)
    log(f"SINCRONIZAR SALDOS JSON v2 · {datetime.now().isoformat()}")
    log("=" * 70)
    log("")
    log("Misma distribución 1/3, pero respeta el PnL histórico.")
    log("")

    env = cargar_env("/etc/polymarket.env")
    for k, v in env.items(): os.environ[k] = v
    wallet = env.get("POLY_WALLET_ADDRESS", "").strip()
    saldos = saldo_onchain(wallet)
    cash_real = sum(saldos.values())
    log(f"Cash on-chain REAL: ${cash_real:.2f}")
    log("")

    BOTS = [
        ("Elon 48h",      "/opt/polymarket/bot-polymarket-elon/real.json"),
        ("Zelenskyy sem", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
        ("Trump mens",    "/opt/polymarket/bot-polymarket-trump/real.json"),
    ]

    cambios = []
    for nombre, fjson in BOTS:
        if not os.path.exists(fjson):
            log(f"--- {nombre} --- NO EXISTE {fjson}\n")
            continue
        with open(fjson) as f: data = json.load(f)
        ops = data.get("operaciones") or data.get("historial") or []
        saldo_virtual = data.get("saldo", 0)
        pnl_historico = calcular_pnl_real(ops)
        # Distribucion 1/3
        cash_por_bot = cash_real / 3
        # bankroll_inicial_real = cash_real/3 - pnl_historico (porque si empezo con X
        # y perdio pnl_historico, ahora tiene cash_real/3)
        # O sea: bankroll_inicial_real = cash_por_bot - pnl_historico
        # PERO pnl_historico es negativo (perdida), entonces -pnl = positivo
        # bankroll_inicial_real = cash_por_bot - pnl_historico = 94.11 - (-22.16) = 116.27
        bankroll_inicial_real = round(cash_por_bot - pnl_historico, 2)
        # El saldo virtual deberia ser: bankroll_inicial_real + pnl_historico = cash_por_bot
        # Asi que la verdad es: nuevo_saldo = cash_por_bot
        # Pero queremos anotar que el bot "cree" que perdio mas (o menos)
        # Guardamos el bankroll inicial real para trazabilidad
        nuevo_saldo = round(cash_por_bot, 2)
        diferencia = nuevo_saldo - saldo_virtual

        log(f"--- {nombre} ({fjson}) ---")
        log(f"  ops: {len(ops)}")
        log(f"  pnl histórico:           ${pnl_historico:+.2f}")
        log(f"  saldo virtual actual:    ${saldo_virtual:.2f}")
        log(f"  bankroll inicial REAL:   ${bankroll_inicial_real:.2f}  (lo que tenía al empezar)")
        log(f"  cash real (1/3):         ${cash_por_bot:.2f}")
        log(f"  nuevo saldo propuesto:   ${nuevo_saldo:.2f}")
        log(f"  cambio:                  ${diferencia:+.2f}")
        log("")

        cambios.append({
            "nombre": nombre, "fjson": fjson, "data": data,
            "nuevo_saldo": nuevo_saldo, "bankroll_inicial_real": bankroll_inicial_real,
            "pnl_historico": pnl_historico, "saldo_virtual": saldo_virtual,
        })

    if args.dry:
        log("=" * 70)
        log("MODO DRY-RUN: nada tocado")
        log(f"Para aplicar: {sys.argv[0]} --apply")
        log("")
        log("VENTAJAS de v2 vs v1:")
        log("  · Mantiene coherencia: bankroll_inicial + pnl = cash_real")
        log("  · Trazabilidad: queda registrado cuánto se invirtió al inicio")
        log("  · Si el bot arranca y ve saldo=$94.11, no rompe nada")
        return

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log("Aplicando cambios (con backup)...\n")
    for c in cambios:
        fjson = c["fjson"]
        backup = f"{fjson}.bak.{ts}"
        shutil.copy2(fjson, backup)
        log(f"  backup: {backup}")
        c["data"]["saldo"] = c["nuevo_saldo"]
        c["data"]["_sincronizado_con_real"] = True
        c["data"]["_sincronizado_ts"] = ts
        c["data"]["_bankroll_inicial_real"] = c["bankroll_inicial_real"]
        c["data"]["_pnl_historico_acumulado"] = round(c["pnl_historico"], 2)
        with open(fjson, "w") as f:
            json.dump(c["data"], f, indent=2, ensure_ascii=False)
        log(f"  ✓ {c['nombre']}: saldo=${c['nuevo_saldo']:.2f}, bankroll_inicial=${c['bankroll_inicial_real']:.2f}")
        log("")

    log("=" * 70)
    log("✅ Sincronización completada (v2, con trazabilidad)")
    log("=" * 70)
    pat = find_pat()
    texto = "Sincronizar JSON v2 - " + ts + "\n" + "\n".join(LOG)
    ok = publicar(texto, f"diag_hetzner/syncjson2_{ts}.txt")
    log(f"publicado: {ok}")

if __name__ == "__main__":
    main()
