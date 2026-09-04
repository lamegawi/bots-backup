#!/usr/bin/env python3
"""
VER SALUD DE TRUMP
==================
Comprueba si el bot de Trump tiene:
- Servicio de salud diario
- Chequeo integral diario
- Comprobación de fantasmas
- Reportes
"""
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

def cargar_pat():
    for r in ["/root/diag_token.txt", "/opt/polymarket/diag_token.txt",
              os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            try:
                with open(r) as f:
                    t = f.read().strip()
                    if t.startswith("ghp_") or t.startswith("github_pat_"):
                        return t
            except: pass
    return os.environ.get("GH_PAT", "")

PAT = cargar_pat()

def publicar(texto, ruta):
    if not PAT:
        return False, "Sin PAT"
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"salud {datetime.now().strftime('%H%M%S')}",
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
log(f"VERIFICACION SALUD TRUMP · {datetime.now().isoformat()}")
log("=" * 70)
log("")

# 1) Listar servicios trump
log("[1] Servicios trump (todos):")
r = subprocess.run(["systemctl", "list-units", "--type=service", "--all", "--no-pager"],
                   capture_output=True, text=True, timeout=10)
trump_services = []
for linea in r.stdout.split('\n'):
    if 'trump' in linea.lower():
        log(f"  {linea.strip()}")
        parts = linea.split()
        if parts:
            name = parts[0]
            if name.startswith("poly-"):
                trump_services.append(name)

log("")
log("[2] Servicios esperados vs reales:")
esperados = [
    "poly-trump.service",              # bot principal
    "poly-telegram-trump.service",     # bot telegram (a crear)
    "poly-salud-trump.service",        # salud diario
    "poly-test-diario-trump.service",  # test diario
    "poly-fantasmas-trump.service",    # fantasmas
    "poly-backup-cruzado.service",     # backup cruzado
]
for e in esperados:
    status = "✓" if e in trump_services else "✗ FALTA"
    log(f"  {status} {e}")

log("")
log("[3] Contenido de servicios de salud de Trump (si existen):")
servicios_salud = [s for s in trump_services if 'salud' in s or 'test' in s or 'fantasma' in s]
for s in servicios_salud:
    log(f"\n--- {s} ---")
    r = subprocess.run(["systemctl", "cat", s, "--no-pager"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        for linea in r.stdout.split('\n')[:30]:
            if linea.strip() and not linea.strip().startswith('#'):
                log(f"  {linea}")

log("")
log("[4] Comprobar si existen los check_salud.py y check_integral.py con soporte para Trump:")
archivos_check = [
    "/opt/polymarket/check_salud.py",
    "/opt/polymarket/check_integral.py",
]
for fp in archivos_check:
    log(f"\n  {fp}: {'EXISTE' if os.path.exists(fp) else 'NO EXISTE'}")
    if os.path.exists(fp):
        with open(fp) as f:
            contenido = f.read()
        # Buscar si tiene soporte para trump
        tiene_trump = "trump" in contenido.lower()
        log(f"    ¿menciona 'trump'? {tiene_trump}")
        # Buscar las líneas con --trump
        for linea in contenido.split('\n'):
            if 'trump' in linea.lower() and ('--' in linea or 'argparse' in linea.lower()):
                log(f"    > {linea.strip()[:120]}")

log("")
log("[5] Ver los timers (programación diaria) de Trump:")
r = subprocess.run(["systemctl", "list-timers", "--all", "--no-pager"],
                   capture_output=True, text=True, timeout=10)
for linea in r.stdout.split('\n'):
    if 'trump' in linea.lower() or 'poly' in linea.lower():
        log(f"  {linea.strip()}")

log("")
log("[6] Ver últimas ejecuciones de servicios de salud Trump:")
for s in servicios_salud:
    log(f"\n  {s}:")
    r = subprocess.run(["systemctl", "status", s, "--no-pager", "-n", "5"],
                       capture_output=True, text=True, timeout=10)
    for linea in r.stdout.split('\n')[:15]:
        log(f"    {linea.strip()}")

# Publicar
inf = ["=" * 78,
       f"VERIFICACION SALUD TRUMP - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
       "=" * 78, ""]
inf.extend(LOG)
inf.append("=" * 78)
texto = "\n".join(inf)
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(texto, f"diag_hetzner/salud_trump_{ts}.txt")
if ok:
    log(f"\n\n✓ Publicado: https://github.com/lamegawi/bots-backup/blob/diag-public/diag_hetzner/salud_trump_{ts}.txt")
else:
    log(f"\n\n✗ Error: {info}")
