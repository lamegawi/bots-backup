#!/usr/bin/env python3
"""
SINCRONIZAR SALDOS JSON v3
==========================
Los 3 bots comparten la MISMA wallet de Polymarket.
El cash on-chain NO se divide: es el mismo para los 3.
Asignamos el bankroll_inicial de cada bot de forma que cuadre con
su PnL histórico individual y con el cash real compartido.

Logica:
  cash_real = $282.34 (compartido por los 3 bots)
  cada bot i tiene pnl_historico_i
  bankroll_inicial_i = (cash_real / 3) - pnl_historico_i
  
  PERO esto ya estaba mal. Lo que el usuario quiere es:
  "el cash real + posiciones = total real disponible, y es para los 3"
  
  Solución:
  - Para cada bot, calculamos qué fracción del cash le corresponde
    en función de su PnL histórico
  - O simplemente: bankroll_inicial de cada bot = cash_real + pnl_historico_i
  - Así, el saldo del JSON = bankroll_inicial + pnl_historico = cash_real
  - Todos los bots ven cash_real como saldo disponible

USO:
  python3 sincronizar_saldo_json_v3.py --dry
  python3 sincronizar_saldo_json_v3.py --apply
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
    payload = {"message": f"syncjson3 {datetime.now().strftime('%H%M%S')}",
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
    pnl = 0.0
    for op in ops:
        res = op.get("resultado", "")
        if res in ("G", "P"):
            b = float(op.get("beneficio") or op.get("benef") or op.get("pnl") or 0)
            pnl += b
    return pnl

def get_posiciones(wallet):
    url = f"https://data-api.polymarket.com/positions?user={wallet}&limit=500"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            posiciones = json.loads(r.read())
        val_actual = sum(float(p.get("currentValue", 0) or 0) for p in posiciones)
        return val_actual, None
    except Exception as e:
        return 0, str(e)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not args.dry and not args.apply:
        args.dry = True

    log("=" * 70)
    log(f"SINCRONIZAR SALDOS JSON v3 · {datetime.now().isoformat()}")
    log("=" * 70)
    log("")
    log("Los 3 bots comparten la MISMA wallet.")
    log("El cash real + posiciones es para los 3, NO se divide.")
    log("")

    env = cargar_env("/etc/polymarket.env")
    for k, v in env.items(): os.environ[k] = v
    wallet = env.get("POLY_WALLET_ADDRESS", "").strip()
    saldos = saldo_onchain(wallet)
    cash_real = sum(saldos.values())
    val_pos, err = get_posiciones(wallet)
    total_real = cash_real + val_pos
    log(f"Cash on-chain:   ${cash_real:.2f}")
    log(f"Posiciones:      ${val_pos:.2f}")
    log(f"TOTAL REAL:      ${total_real:.2f}")
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
        # bankroll_inicial = total_real - pnl_historico
        # saldo_nuevo = total_real (lo que el bot ve como cash disponible)
        # (porque el bot va a usar el saldo del JSON como su bankroll de operacion)
        bankroll_inicial_real = round(total_real - pnl_historico, 2)
        nuevo_saldo = round(total_real, 2)
        diferencia = nuevo_saldo - saldo_virtual

        log(f"--- {nombre} ({fjson}) ---")
        log(f"  ops: {len(ops)}")
        log(f"  pnl histórico:           ${pnl_historico:+.2f}")
        log(f"  saldo virtual actual:    ${saldo_virtual:.2f}")
        log(f"  bankroll inicial REAL:   ${bankroll_inicial_real:.2f}")
        log(f"  nuevo saldo propuesto:   ${nuevo_saldo:.2f}  (cash+posiciones real)")
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
        log("NOTA: cada bot ahora ve el MISMO saldo (${:.2f})".format(total_real))
        log("porque todos operan sobre la misma wallet. Es lo correcto.")
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
    log("✅ Sincronización completada (v3, cash compartido)")
    log("=" * 70)
    pat = find_pat()
    texto = "Sincronizar JSON v3 - " + ts + "\n" + "\n".join(LOG)
    ok = publicar(texto, f"diag_hetzner/syncjson3_{ts}.txt")
    log(f"publicado: {ok}")

if __name__ == "__main__":
    main()
