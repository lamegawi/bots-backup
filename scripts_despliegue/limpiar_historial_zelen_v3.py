#!/usr/bin/env python3
"""
Limpia la ghost op de Aug 25 (+$3.62) del real_zelen.json de Zelenskyy.

Ghost op detectada: [1] 2026-08-25, mercado zelenskyy-of-tweets-august-25-september-1-2026
Beneficio: +$3.62  (era 0.00, fue "inventada" y reventó el saldo)

USO:
  python3 limpiar_historial_zelen_v3.py --dry    # muestra qué haría
  python3 limpiar_historial_zelen_v3.py --apply  # borra (con backup)
"""
import os
import sys
import json
import shutil
import argparse
import base64
import urllib.request
from datetime import datetime

ARCHIVO = "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"
GHOST_DATE = "2026-08-25"
GHOST_BENEF = 3.62
TOLERANCIA = 0.02

def log(s): print(s, flush=True)

def es_ghost(op):
    benef = op.get("beneficio") or op.get("benef") or op.get("pnl") or 0
    if abs(float(benef) - GHOST_BENEF) > TOLERANCIA:
        return False
    fecha = str(op.get("fecha") or op.get("ts") or op.get("timestamp") or "")[:10]
    return fecha == GHOST_DATE

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
    payload = {"message": f"ghostzelen3 {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {pat}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r: return True
    except Exception as e: return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if not os.path.exists(ARCHIVO):
        log(f"ERROR: no existe {ARCHIVO}"); sys.exit(1)
    log("=" * 70)
    log(f"LIMPIAR GHOST OP ZELENSKYY - {datetime.now().isoformat()}")
    log("=" * 70)
    with open(ARCHIVO) as f: data = json.load(f)
    log(f"Estructura: {list(data.keys())}")
    log(f"  activa: {bool(data.get('activa'))}")
    ops = data.get("operaciones") or data.get("historial") or data.get("ops") or []
    log(f"  total ops: {len(ops)}")
    log("")
    ghosts = []
    for i, op in enumerate(ops):
        if es_ghost(op): ghosts.append((i, op))
    if not ghosts:
        log("✗ No se encontró ghost op")
        log("Ops de agosto:")
        for i, op in enumerate(ops):
            f_ = str(op.get("fecha") or op.get("ts") or "")[:10]
            if "2026-08" in f_ or "2026-09" in f_:
                b = op.get("beneficio") or op.get("benef") or op.get("pnl") or 0
                log(f"  [{i}] {f_}  ${float(b):.2f}  {op.get('slug', op.get('mercado', '?'))[:60]}")
        sys.exit(0)
    log(f"✓ Ghost op encontrada: {len(ghosts)}")
    for i, op in ghosts:
        log(f"  [{i}] {op}")
        log("")
    if args.dry or not args.apply:
        log("=" * 70)
        log("MODO DRY-RUN: nada tocado")
        log(f"Para aplicar: {sys.argv[0]} --apply")
        sys.exit(0)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{ARCHIVO}.bak.{ts}"
    shutil.copy2(ARCHIVO, backup)
    log(f"✓ Backup: {backup}")
    log("")
    indices = {i for i, _ in ghosts}
    nueva_ops = [op for i, op in enumerate(ops) if i not in indices]
    log(f"  antes: {len(ops)} ops")
    log(f"  después: {len(nueva_ops)} ops")
    log(f"  borradas: {len(ops) - len(nueva_ops)}")
    log("")
    if "saldo" in data:
        antiguo = data["saldo"]
        delta = sum(float(op.get("beneficio") or op.get("benef") or op.get("pnl") or 0) for _, op in ghosts)
        data["saldo"] = round(antiguo - delta, 2)
        log(f"  saldo: ${antiguo:.2f} → ${data['saldo']:.2f}  (delta: -${delta:.2f})")
        log("")
    data["operaciones"] = nueva_ops
    if "historial" in data: data["historial"] = nueva_ops
    with open(ARCHIVO, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log(f"✓ Escrito {ARCHIVO}")
    log("")
    log("=" * 70)
    pat = find_pat()
    if pat:
        texto = f"Ghost zelen borrada - {ts}\nBorradas {len(ghosts)} ops\nSaldo: ${data.get('saldo',0):.2f}\nBackup: {backup}"
        ok = publicar(texto, f"diag_hetzner/ghostzelen3_{ts}.txt", pat)
        log(f"publicado: {ok}")

if __name__ == "__main__": main()
