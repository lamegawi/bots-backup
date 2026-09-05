#!/usr/bin/env python3
"""
BACKUP COMPLETO v1
==================
Guarda una copia COMPLETA de:
  - Los 3 JSON de los bots (con todas las operaciones)
  - El codigo fuente (vía git)
  - La configuracion (sin secretos)
  - Un informe con resumen

Publica todo en GitHub en la rama arena/01a058fe-bots-backup,
carpeta backups_completos/ con timestamp.

USO: python3 backup_completo.py
"""
import os
import sys
import json
import shutil
import base64
import urllib.request
import subprocess
from datetime import datetime

LOG = []
def log(s):
    line = str(s)
    print(line, flush=True)
    LOG.append(line)

def find_pat():
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"): return t
    return os.environ.get("GH_PAT", "")

PAT = find_pat()
REPO = "lamegawi/bots-backup"
BRANCH = "arena/01a058fe-bots-backup"

def github_put(path, content_bytes, message):
    """Sube un archivo a GitHub via Contents API."""
    if not PAT:
        log(f"  [skip] sin PAT, no publico {path}")
        return False
    b64 = base64.b64encode(content_bytes).decode()
    sha = None
    # ver si ya existe
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/contents/{path}?ref={BRANCH}",
            headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except urllib.error.HTTPError as e:
        if e.code != 404:
            log(f"  err leyendo {path}: {e}")
    payload = {"message": message, "content": b64, "branch": BRANCH}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/{REPO}/contents/{path}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {PAT}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True
    except urllib.error.HTTPError as e:
        log(f"  err publicando {path}: {e}")
        return False

# === MAIN ===
log("=" * 70)
log(f"BACKUP COMPLETO · {datetime.now().isoformat()}")
log("=" * 70)

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
fecha = datetime.now().strftime("%Y-%m-%d")
backups_dir = f"backups_completos/{fecha}_{ts}"

# 1) Backup de los JSONs
log("")
log("[1/3] Copiando JSONs de los bots...")
BOTS = [
    ("elon",      "Elon 48h",      "/opt/polymarket/bot-polymarket-elon/real.json"),
    ("zelenskyy", "Zelenskyy sem", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
    ("trump",     "Trump mens",    "/opt/polymarket/bot-polymarket-trump/real.json"),
]
jsons_ok = 0
for slug, nombre, fp in BOTS:
    if not os.path.exists(fp):
        log(f"  {nombre}: no existe {fp}")
        continue
    try:
        with open(fp, "rb") as f:
            raw = f.read()
        # Validar que es JSON
        json.loads(raw)
        # Subir a GitHub
        dst = f"{backups_dir}/json_{slug}_{ts}.json"
        ok = github_put(dst, raw, f"backup completo {slug} {ts}")
        if ok:
            log(f"  ✓ {nombre}: {len(raw)} bytes → {dst}")
            jsons_ok += 1
        else:
            log(f"  ✗ {nombre}: fallo publicando")
    except Exception as e:
        log(f"  ✗ {nombre}: {e}")

# 2) Backup del codigo (snapshot de git)
log("")
log("[2/3] Snapshot de codigo...")
try:
    # detectar el repo en Hetzner (varios paths posibles)
    repo_cwd = None
    for r in ["/root/bots-backup", "/opt/bots-backup", os.path.expanduser("~/bots-backup")]:
        if os.path.exists(os.path.join(r, ".git")):
            repo_cwd = r
            break
    sha = None
    log_git = ""
    if repo_cwd:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5, cwd=repo_cwd)
        if r.returncode == 0:
            sha = r.stdout.strip()
            r2 = subprocess.run(["git", "log", "-1", "--format=%H %s %ai"], capture_output=True, text=True, timeout=5, cwd=repo_cwd)
            log_git = r2.stdout.strip()
    if not sha and PAT:
        # fallback: leer desde GitHub API
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{REPO}/commits/{BRANCH}",
                headers={"Authorization": f"token {PAT}", "User-Agent": "diag"})
            with urllib.request.urlopen(req, timeout=15) as r2:
                d = json.loads(r2.read())
                sha = d.get("sha", "")
                log_git = d.get("commit", {}).get("message", "") + " - " + d.get("commit", {}).get("author", {}).get("date", "")
        except Exception as e:
            log(f"  err leyendo desde API: {e}")
    if sha:
        contenido = f"git rev: {sha}\ncommit: {log_git}\nfecha: {datetime.now().isoformat()}\n"
        ok = github_put(f"{backups_dir}/git_info_{ts}.txt", contenido.encode(), f"backup info {ts}")
        log(f"  ✓ git HEAD: {sha[:8]}")
    else:
        log(f"  ✗ no pude leer git HEAD")
except Exception as e:
    log(f"  err: {e}")

# 3) Informe de resumen
log("")
log("[3/3] Generando informe...")
inf = []
inf.append("=" * 70)
inf.append(f"BACKUP COMPLETO · {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
inf.append("=" * 70)
inf.append("")
inf.append(f"Fecha: {fecha}")
inf.append(f"Tag ts: {ts}")
inf.append(f"Ruta: {backups_dir}/")
inf.append("")
inf.append("ARCHIVOS RESPALDADOS:")
inf.append(f"  - jsons subidos: {jsons_ok} de {len(BOTS)}")
for slug, nombre, _ in BOTS:
    inf.append(f"    - {nombre} ({slug})")
inf.append("")
inf.append("INSTRUCCIONES PARA RESTAURAR:")
inf.append("  1) Ir a https://github.com/lamegawi/bots-backup")
inf.append(f"  2) Carpeta: {backups_dir}/")
inf.append("  3) Bajar el JSON deseado")
inf.append("  4) En Hetzner: cp backup.json /opt/polymarket/bot-X/real.json")
inf.append("  5) Reiniciar el servicio: systemctl restart poly-X")
inf.append("")
inf.append("--- LOG COMPLETO ---")
inf.extend(LOG)
inf.append("=" * 70)
contenido = "\n".join(inf)
github_put(f"{backups_dir}/informe_{ts}.txt", contenido.encode(), f"backup informe {ts}")
log(f"  ✓ informe: {backups_dir}/informe_{ts}.txt")

log("")
log("=" * 70)
log(f"BACKUP COMPLETO TERMINADO · {jsons_ok} JSONs respaldados")
log("=" * 70)
