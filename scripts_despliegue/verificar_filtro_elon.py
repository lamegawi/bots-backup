#!/usr/bin/env python3
import os
import subprocess
import base64
import urllib.request
import json
from datetime import datetime

LOG = []
def log(s):
    s = str(s)
    print(s, flush=True)
    LOG.append(s)

# Buscar PAT
PAT = None
for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
    if os.path.exists(r):
        try:
            PAT = open(r).read().strip()
            if PAT.startswith("ghp_"):
                break
        except: pass
if not PAT:
    PAT = os.environ.get("GH_PAT", "")

def publicar(texto, ruta):
    if not PAT: return False, "Sin PAT"
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"verfiltro {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {PAT}", "Content-Type": "application/json",
                 "Accept": "application/vnd.github+json", "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True, r.read().decode()
    except Exception as e:
        return False, str(e)

log("=" * 70)
log(f"VERIFICAR FILTRO ELON · {datetime.now().isoformat()}")
log("=" * 70)
log("")

# 1) Ver que el archivo local tiene el filtro
fp = "/opt/polymarket/bot-polymarket-elon/senal_vivo.py"
log(f"[1] Verificar que {fp} tiene el filtro:")
try:
    with open(fp) as f:
        contenido = f.read()
    if "FILTRO" in contenido and "p_lado < 0.10" in contenido:
        log("  ✓ El archivo local tiene el filtro")
    else:
        log("  ✗ El archivo local NO tiene el filtro")
        log("  (es la versión vieja, necesitas bajarla de nuevo)")
except Exception as e:
    log(f"  ERROR: {e}")

log("")

# 2) Estado del servicio
log("[2] Estado del servicio poly-elon:")
r = subprocess.run(["systemctl", "is-active", "poly-elon"],
                   capture_output=True, text=True, timeout=5)
log(f"  {r.stdout.strip()}")

log("")

# 3) Ver las últimas líneas del log
log("[3] Últimas 50 líneas del log de poly-elon:")
r = subprocess.run(["journalctl", "-u", "poly-elon", "-n", "50", "--no-pager"],
                   capture_output=True, text=True, timeout=10)
if r.returncode == 0:
    for linea in r.stdout.split('\n')[-50:]:
        if linea.strip():
            log(f"  {linea[:160]}")

log("")

# 4) Ver el estado actual del bot
log("[4] Estado actual del bot:")
fp = "/opt/polymarket/bot-polymarket-elon/real.json"
if os.path.exists(fp):
    with open(fp) as f:
        data = json.load(f)
    activa = data.get("activa")
    log(f"  activa: {bool(activa)}")
    if activa:
        log(f"    slug: {activa.get('slug', '?')}")
        log(f"    bin: {activa.get('bin_titulo', '?')}")
        log(f"    cuota: {activa.get('cuota', 0):.2f}")
        log(f"    p_modelo: {activa.get('p_modelo', 0):.0%}")
        log(f"    paso: {activa.get('paso', 0)}")
        log(f"    stake: ${activa.get('stake', 0):.2f}")

# Publicar
inf = ["=" * 78,
       f"VERIFICAR FILTRO ELON - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, ""]
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(texto, f"diag_hetzner/verfiltro_{ts}.txt")
if ok:
    log(f"\n✓ Publicado")
else:
    log(f"\n✗ Error: {info}")
