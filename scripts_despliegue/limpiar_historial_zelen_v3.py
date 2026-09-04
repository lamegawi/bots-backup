#!/usr/bin/env python3
"""
Limpia el ghost op de Aug 25 (+$267.80) del real_zelen.json de Zelenskyy.

USO:
  python3 limpiar_historial_zelen_v3.py --dry     # solo muestra qué haría
  python3 limpiar_historial_zelen_v3.py           # aplica (hace backup)
  python3 limpiar_historial_zelen_v3.py --auto    # busca y borra Aug 25

El script:
  1) Lee /opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json
  2) Hace un backup a real_zelen.json.bak.YYYYMMDD_HHMMSS
  3) Busca operaciones del 25 de agosto 2026 con beneficio cercano a $267.80
  4) Lista lo que encontró (dry-run) o lo borra (--apply)
  5) Reescribe el JSON con la operación quitada
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
GHOST_DATE = "2026-08-25"   # fecha del ghost op
GHOST_BENEF = 267.80          # beneficio reportado
TOLERANCIA = 0.05             # ±0.05 USD

def log(s):
    print(s, flush=True)

def es_ghost(op):
    """Detecta si una op es el ghost op del 25/08."""
    # beneficio puede estar en distintos campos según la versión
    benef = op.get("beneficio") or op.get("benef") or op.get("pnl") or 0
    if abs(float(benef) - GHOST_BENEF) > TOLERANCIA:
        return False
    # fecha
    fecha = op.get("fecha") or op.get("ts") or op.get("timestamp") or op.get("created_at") or ""
    fecha = str(fecha)[:10]  # YYYY-MM-DD
    if fecha == GHOST_DATE:
        return True
    # a veces la fecha está en otro formato
    if GHOST_DATE.replace("-", "") in str(fecha).replace("-", "").replace("/", ""):
        return True
    return False

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
    ap.add_argument("--dry", action="store_true", help="solo mostrar, no tocar")
    ap.add_argument("--apply", action="store_true", help="aplicar cambios (hace backup)")
    ap.add_argument("--auto", action="store_true", help="buscar y borrar Aug 25 +$267.80 sin preguntar")
    args = ap.parse_args()
    
    if not os.path.exists(ARCHIVO):
        log(f"ERROR: no existe {ARCHIVO}")
        sys.exit(1)
    
    log("=" * 70)
    log(f"LIMPIAR GHOST OP ZELENSKYY - {datetime.now().isoformat()}")
    log("=" * 70)
    log(f"Archivo: {ARCHIVO}")
    log("")
    
    # leer
    with open(ARCHIVO) as f:
        data = json.load(f)
    
    log(f"Estructura del JSON: {list(data.keys())}")
    log(f"  activa: {bool(data.get('activa'))}")
    
    # buscar operaciones en distintos campos
    ops = data.get("operaciones") or data.get("historial") or data.get("ops") or []
    if not isinstance(ops, list):
        log(f"  operaciones: {type(ops).__name__}, no es lista")
        ops = []
    log(f"  total operaciones: {len(ops)}")
    log("")
    
    # buscar ghost
    ghosts = []
    for i, op in enumerate(ops):
        if es_ghost(op):
            ghosts.append((i, op))
    
    if not ghosts:
        log(f"✗ No se encontró ninguna op que coincida con Aug 25 / +${GHOST_BENEF}")
        log("")
        log("Operaciones de agosto 2026:")
        for i, op in enumerate(ops):
            f = str(op.get("fecha") or op.get("ts") or "")[:10]
            if "2026-08" in f or "2026-09" in f:
                b = op.get("beneficio") or op.get("benef") or op.get("pnl") or 0
                log(f"  [{i}] {f}  ${float(b):.2f}  {op.get('slug', op.get('mercado', '?'))[:50]}")
        log("")
        log("Si ves la ghost op, dímelo y la borramos manualmente.")
        sys.exit(0)
    
    log(f"✓ Ghost op encontrada: {len(ghosts)} coincidencia(s)")
    log("")
    for i, op in ghosts:
        log(f"  [{i}] {op}")
        log("")
    
    if args.dry or not args.apply:
        log("=" * 70)
        log("MODO DRY-RUN: no se ha tocado nada")
        log(f"Para aplicar: {sys.argv[0]} --apply")
        sys.exit(0)
    
    # backup
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{ARCHIVO}.bak.{ts}"
    shutil.copy2(ARCHIVO, backup)
    log(f"✓ Backup: {backup}")
    log("")
    
    # borrar
    indices = {i for i, _ in ghosts}
    nueva_ops = [op for i, op in enumerate(ops) if i not in indices]
    log(f"  antes: {len(ops)} ops")
    log(f"  después: {len(nueva_ops)} ops")
    log(f"  borradas: {len(ops) - len(nueva_ops)}")
    log("")
    
    # recalcular saldo si tiene campo saldo
    if "saldo" in data:
        antiguo = data["saldo"]
        # restar beneficios de los ghosts
        delta = sum(float(op.get("beneficio") or op.get("benef") or op.get("pnl") or 0) for _, op in ghosts)
        data["saldo"] = round(antiguo - delta, 2)
        log(f"  saldo: ${antiguo:.2f} → ${data['saldo']:.2f}  (delta: -${delta:.2f})")
        log("")
    
    # actualizar
    data["operaciones"] = nueva_ops
    if "historial" in data:
        data["historial"] = nueva_ops
    
    # escribir
    with open(ARCHIVO, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    log(f"✓ Escrito {ARCHIVO}")
    log("")
    log("=" * 70)
    
    # publicar
    pat = find_pat()
    if pat:
        texto = f"Limpiar ghost op zelenskyy - {ts}\n\n" + "\n".join([
            f"Borradas {len(ghosts)} ops de Aug 25",
            f"Saldo: ${data.get('saldo', 0):.2f}",
            f"Backup: {backup}",
        ])
        ok = publicar(texto, f"diag_hetzner/ghostzelen3_{ts}.txt", pat)
        log(f"publicado: {ok}")

if __name__ == "__main__":
    main()
