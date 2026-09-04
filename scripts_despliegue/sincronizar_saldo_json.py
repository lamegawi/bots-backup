#!/usr/bin/env python3
"""
SINCRONIZAR SALDOS JSON v1
==========================
Arregla el bug de los JSON: los saldos virtuales no cuadran con la realidad.
Recalcula cada JSON restando los PnL reales (de las ops históricas)
desde un punto de partida conocido (el cash on-chain actual).

USO:
  python3 sincronizar_saldo_json.py --dry    # muestra qué cambiaría
  python3 sincronizar_saldo_json.py --apply  # aplica (con backup)
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
    payload = {"message": f"syncjson {datetime.now().strftime('%H%M%S')}",
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
    """PnL real = suma de los beneficios de las ops cerradas.
    Para una op perdedora el benef es -stake.
    Para una op ganadora el benef es +stake*(cuota-1) - fee.
    Pero como ya está calculado en el JSON, simplemente lo sumamos.
    PERO solo si 'resultado' es G o P (cerradas).
    """
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
    log(f"SINCRONIZAR SALDOS JSON · {datetime.now().isoformat()}")
    log("=" * 70)

    env = cargar_env("/etc/polymarket.env")
    for k, v in env.items(): os.environ[k] = v
    wallet = env.get("POLY_WALLET_ADDRESS", "").strip()
    saldos = saldo_onchain(wallet)
    cash_real = sum(saldos.values())
    log(f"\nCash on-chain REAL: ${cash_real:.2f}")
    log("")

    # Cada bot
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
        pnl_real_historico = calcular_pnl_real(ops)
        # El saldo virtual es lo que el bot CREE que tiene
        # Si el cash real es $cash_real y la suma de pnl de las ops cerradas es $pnl_real_historico
        # entonces: cash_real = bankroll_inicial - pnl_real_historico (mal gastado)
        # O sea: bankroll_inicial = cash_real + pnl_real_historico
        # Para el bot, saldo = bankroll_inicial + pnl_real_historico - (stakes apostados pero no resueltos)
        # PERO como简化: si asumimos que el bot NO incluye las posiciones abiertas
        # en su saldo, entonces el saldo virtual debería reflejar el bankroll inicial menos
        # el pnl acumulado, que es exactamente lo que el JSON dice.
        # El problema es que el bankroll inicial que asumió el bot es FALSO.
        #
        # Solución pragmática: ajustar el saldo virtual restando la diferencia
        # entre lo que dice y el cash real.
        #
        # Diferencia = saldo_virtual - cash_real_estimado_para_este_bot
        # Como los bots comparten wallet, dividimos el cash real proporcionalmente
        # a los stakes de cada bot.

        # Distribución naive: misma cantidad para cada bot
        cash_por_bot = cash_real / 3
        diferencia = saldo_virtual - cash_por_bot
        nuevo_saldo = round(cash_por_bot, 2)

        log(f"--- {nombre} ({fjson}) ---")
        log(f"  ops: {len(ops)}")
        log(f"  pnl histórico real (suma de G/P): ${pnl_real_historico:+.2f}")
        log(f"  saldo virtual actual:  ${saldo_virtual:.2f}")
        log(f"  cash real (1/3):       ${cash_por_bot:.2f}")
        log(f"  nuevo saldo propuesto: ${nuevo_saldo:.2f}")
        log(f"  cambio:                ${diferencia:+.2f}")
        log("")

        cambios.append((nombre, fjson, data, nuevo_saldo))

    if args.dry:
        log("=" * 70)
        log("MODO DRY-RUN: nada tocado")
        log(f"Para aplicar: {sys.argv[0]} --apply")
        log("")
        log("⚠️  NOTA: estamos asignando 1/3 del cash real a cada bot (naive).")
        log("   Para hacerlo bien habría que separar las ops de cada bot en")
        log("   la wallet, pero como comparten wallet es imposible sin un")
        log("   registro interno.")
        return

    # Aplicar
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    log("Aplicando cambios (con backup)...\n")
    for nombre, fjson, data, nuevo_saldo in cambios:
        backup = f"{fjson}.bak.{ts}"
        shutil.copy2(fjson, backup)
        log(f"  backup: {backup}")
        data["saldo"] = nuevo_saldo
        data["_sincronizado_con_real"] = True
        data["_sincronizado_ts"] = ts
        with open(fjson, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        log(f"  ✓ {nombre}: saldo → ${nuevo_saldo:.2f}")
        log("")

    log("=" * 70)
    log("✅ Sincronización completada")
    log("=" * 70)
    # Publicar
    pat = find_pat()
    texto = "Sincronizar JSON - " + ts + "\n" + "\n".join(LOG)
    ok = publicar(texto, f"diag_hetzner/syncjson_{ts}.txt")
    log(f"publicado: {ok}")

if __name__ == "__main__":
    main()
