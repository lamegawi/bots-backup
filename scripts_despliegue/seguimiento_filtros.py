#!/usr/bin/env python3
"""Cuenta cuántas apuestas ha descartado el filtro en cada bot desde el último reinicio."""
import os
import sys
import subprocess
import re
import base64
import urllib.request
import json
from datetime import datetime

OUT = []
def log(s):
    line = str(s)
    print(line, flush=True)
    OUT.append(line)

def find_pat():
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"): return t
    return os.environ.get("GH_PAT", "")

def publicar(texto, ruta, pat):
    if not pat:
        log("  [publish] sin PAT, no se publica")
        return False
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {pat}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"segfiltros {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {pat}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True
    except Exception as e:
        log(f"  [publish] err: {e}")
        return False

def contar_filtros(srv):
    """Cuenta lineas [FILTRO] en el log del servicio desde el último reinicio."""
    r = subprocess.run(
        ["journalctl", "-u", srv, "--since", "today", "--no-pager"],
        capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return None, None, []
    lineas = r.stdout.split("\n")
    descartes_p = sum(1 for ln in lineas if "[FILTRO]" in ln and "p_lado" in ln)
    descartes_c = sum(1 for ln in lineas if "[FILTRO]" in ln and "cuota" in ln and ">25" in ln)
    ejemplos = []
    for ln in lineas:
        if "[FILTRO]" in ln and len(ejemplos) < 5:
            ejemplos.append(ln[:180])
    return descartes_p, descartes_c, ejemplos

BOTS = [
    ("Elon 48h",      "poly-elon"),
    ("Zelenskyy sem", "poly-zelenskyy"),
    ("Trump mensual", "poly-trump"),
]

log("=" * 70)
log(f"SEGUIMIENTO FILTROS - {datetime.now().isoformat()}")
log("=" * 70)
log("")
log("Cuenta de apuestas DESCARTADAS por el filtro desde hoy:")
log("")

total_p = 0
total_c = 0
for nombre, srv in BOTS:
    r = subprocess.run(["systemctl", "is-active", srv], capture_output=True, text=True, timeout=5)
    activo = r.stdout.strip() == "active"
    dp, dc, ejs = contar_filtros(srv) if activo else (None, None, [])
    log(f"--- {nombre} ({srv}) ---")
    log(f"  estado: {r.stdout.strip()}")
    if dp is None:
        log("  (no se pudo leer log)")
    else:
        log(f"  descartes por p_lado<10%: {dp}")
        log(f"  descartes por cuota>25:    {dc}")
        log(f"  TOTAL descartes:          {dp+dc}")
        if ejs:
            log("  ejemplos:")
            for e in ejs:
                log(f"    {e}")
        total_p += dp
        total_c += dc
    log("")

log(f"=== TOTAL 3 BOTS ===")
log(f"  descartes por p_lado<10%: {total_p}")
log(f"  descartes por cuota>25:    {total_c}")
log(f"  TOTAL:                     {total_p+total_c}")
log("")
log("=" * 70)

# Publicar
pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = f"Seguimiento filtros - {ts}\n\n" + "\n".join(OUT)
ok = publicar(texto, f"diag_hetzner/segfiltros_{ts}.txt", pat)
log(f"publicado: {ok}")
sys.stdout.flush()
