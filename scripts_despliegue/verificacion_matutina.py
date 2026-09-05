#!/usr/bin/env python3
"""Verificacion rapida: estado de los 3 bots + saldo + filtros."""
import os
import sys
import json
import subprocess
import base64
import urllib.request
from datetime import datetime

LOG = []
def log(s):
    print(s, flush=True)
    LOG.append(str(s))

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
    payload = {"message": f"matutina {datetime.now().strftime('%H%M%S')}",
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

BOTS = [
    ("Elon 48h",      "poly-elon",      "/opt/polymarket/bot-polymarket-elon/real.json"),
    ("Zelenskyy sem", "poly-zelenskyy", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
    ("Trump mens",    "poly-trump",     "/opt/polymarket/bot-polymarket-trump/real.json"),
]

log("=" * 70)
log(f"VERIFICACION MATUTINA · {datetime.now().isoformat()}")
log("=" * 70)

# 1) Estado servicios
log("")
log("[1/3] Servicios:")
for n, srv, _ in BOTS:
    r = subprocess.run(["systemctl", "is-active", srv], capture_output=True, text=True, timeout=5)
    log(f"  {n}: {r.stdout.strip()}")

# 2) Operaciones activas
log("")
log("[2/3] Operaciones activas:")
for n, _, fp in BOTS:
    if not os.path.exists(fp):
        log(f"  {n}: sin JSON")
        continue
    try:
        with open(fp) as f: d = json.load(f)
        a = d.get("activa")
        if a:
            log(f"  {n}: ACTIVA - bin {a.get('bin_titulo','?')} cuota {a.get('cuota',0):.2f} paso {a.get('paso',0)} stake ${a.get('stake',0):.2f}")
        else:
            log(f"  {n}: sin operacion activa")
        log(f"     saldo JSON: ${d.get('saldo',0):.2f}  ops: {len(d.get('operaciones',[]) or d.get('historial',[]) or [])}")
    except Exception as e:
        log(f"  {n}: error: {e}")

# 3) Filtros aplicados desde ayer
log("")
log("[3/3] Filtros descartados (ultimas 24h):")
for n, srv, _ in BOTS:
    r = subprocess.run(["journalctl", "-u", srv, "--since", "24 hours ago", "--no-pager"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        descartes = sum(1 for ln in r.stdout.split("\n") if "[FILTRO]" in ln)
        log(f"  {n}: {descartes} apuestas descartadas")

log("")
log("=" * 70)

# Publicar
pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = "Verificacion matutina - " + ts + "\n" + "\n".join(LOG)
ok = publicar(texto, f"diag_hetzner/matutina_{ts}.txt", pat)
log(f"publicado: {ok}")
