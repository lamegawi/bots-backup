#!/usr/bin/env python3
"""Verificar que el filtro p_lado>10% y cuota<25 está activo en los 3 bots."""
import os
import subprocess
import base64
import urllib.request
import json
from datetime import datetime

def log(s):
    print(s, flush=True)

def leer(path):
    try:
        with open(path) as f: return f.read()
    except: return None

def find_pat():
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"): return t
    return os.environ.get("GH_PAT", "")

def publicar(texto, ruta, pat):
    if not pat: return False, "sin PAT"
    b64 = base64.b64encode(texto.encode()).decode()
    sha = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}?ref=diag-public",
            headers={"Authorization": f"token {pat}", "User-Agent": "diag"})
        with urllib.request.urlopen(req, timeout=15) as r:
            sha = json.loads(r.read()).get("sha")
    except: pass
    payload = {"message": f"filtros3 {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {pat}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return True, r.read().decode()
    except Exception as e:
        return False, str(e)

BOTS = [
    ("Elon 48h",      "poly-elon",      "/opt/polymarket/bot-polymarket-elon/real.json",      "/opt/polymarket/bot-polymarket-elon/senal_vivo.py"),
    ("Zelenskyy sem",  "poly-zelenskyy", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json", "/opt/polymarket/bot-polymarket-zelenskyy/senal_vivo.py"),
    ("Trump mensual",  "poly-trump",     "/opt/polymarket/bot-polymarket-trump/real.json",     "/opt/polymarket/bot-polymarket-trump/senal_vivo.py"),
]

def check_bot(nombre, srv, real, senal):
    log(f"\n--- {nombre} ({srv}) ---")
    r = subprocess.run(["systemctl", "is-active", srv], capture_output=True, text=True, timeout=5)
    activo = r.stdout.strip() == "active"
    log(f"  servicio: {r.stdout.strip()}")
    s = leer(senal)
    if s and "p_lado < 0.10" in s and "cuota_lado and cuota_lado > 25" in s:
        log("  filtro: ✓ activo (p_lado<10% y cuota<25)")
    else:
        log("  filtro: ✗ NO presente (o incompleto)")
    data = leer(real)
    if data:
        try:
            d = json.loads(data)
            act = d.get("activa")
            if act:
                log(f"  activa: SÍ")
                log(f"    slug: {act.get('slug', '?')}")
                log(f"    bin: {act.get('bin_titulo', '?')}")
                log(f"    cuota: {act.get('cuota', 0):.2f}")
                log(f"    p_modelo: {act.get('p_modelo', 0):.0%}")
                log(f"    paso: {act.get('paso', 0)}")
                log(f"    stake: ${act.get('stake', 0):.2f}")
            else:
                log(f"  activa: NO")
        except Exception as e:
            log(f"  ERROR parseando real: {e}")
    # ultimas lineas de log
    r = subprocess.run(["journalctl", "-u", srv, "-n", "15", "--no-pager"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        log("  log (ultimas 15):")
        for ln in r.stdout.strip().split("\n"):
            if "Started" in ln or "Stopping" in ln or "Stopped" in ln or "FILTRO" in ln:
                log(f"    {ln[:170]}")

log("=" * 70)
log(f"VERIFICAR FILTROS 3 BOTS - {datetime.now().isoformat()}")
log("=" * 70)
for b in BOTS: check_bot(*b)
log("")
log("=" * 70)

# Publicar
pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
ok, info = publicar(f"Filtros 3 bots - {ts}", f"diag_hetzner/filtros3_{ts}.txt", pat)
log(f"publicado: {ok}")
if not ok: log(f"  err: {info[:200]}")
