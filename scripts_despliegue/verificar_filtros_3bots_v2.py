#!/usr/bin/env python3
"""v2: forzar flush y publish con captura completa."""
import os
import sys
import subprocess
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
    payload = {"message": f"filtros3v2 {datetime.now().strftime('%H%M%S')}",
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

def leer(path):
    try:
        with open(path) as f: return f.read()
    except Exception as e:
        return f"<<error: {e}>>"

def check(nombre, srv, real, senal):
    log("")
    log(f"--- {nombre} ({srv}) ---")
    r = subprocess.run(["systemctl", "is-active", srv], capture_output=True, text=True, timeout=5)
    log(f"  servicio: {r.stdout.strip()}")
    s = leer(senal)
    if isinstance(s, str) and "p_lado < 0.10" in s and "cuota_lado > 25" in s:
        log("  filtro local: ✓ presente (p_lado<10% y cuota<25)")
    else:
        log(f"  filtro local: ✗ NO presente (o archivo: {s[:80] if isinstance(s,str) else 'N/A'})")
    d = leer(real)
    if isinstance(d, str):
        try:
            dj = json.loads(d)
            act = dj.get("activa")
            if act:
                log(f"  activa: SÍ")
                log(f"    slug: {act.get('slug', '?')}")
                log(f"    bin: {act.get('bin_titulo', '?')}")
                log(f"    cuota: {act.get('cuota', 0):.2f}")
                log(f"    p_modelo: {act.get('p_modelo', 0):.0%}")
                log(f"    paso: {act.get('paso', 0)}")
                log(f"    stake: ${act.get('stake', 0):.2f}")
            else:
                log("  activa: NO (sin operaciones en curso)")
            # contador
            ops = dj.get("operaciones", [])
            log(f"  ops totales: {len(ops)}")
        except Exception as e:
            log(f"  ERROR parseando: {e}")
    # log systemd
    r = subprocess.run(["journalctl", "-u", srv, "-n", "30", "--no-pager"],
                       capture_output=True, text=True, timeout=10)
    if r.returncode == 0:
        log("  journalctl (ultimas 30):")
        for ln in r.stdout.strip().split("\n"):
            if "Started" in ln or "Stopping" in ln or "Stopped" in ln or "FILTRO" in ln or "activ" in ln.lower() or "ERROR" in ln or "error" in ln:
                log(f"    {ln[:170]}")
    sys.stdout.flush()

BOTS = [
    ("Elon 48h",      "poly-elon",      "/opt/polymarket/bot-polymarket-elon/real.json",            "/opt/polymarket/bot-polymarket-elon/senal_vivo.py"),
    ("Zelenskyy sem", "poly-zelenskyy", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json",  "/opt/polymarket/bot-polymarket-zelenskyy/senal_vivo.py"),
    ("Trump mensual", "poly-trump",     "/opt/polymarket/bot-polymarket-trump/real.json",           "/opt/polymarket/bot-polymarket-trump/senal_vivo.py"),
]

log("=" * 70)
log(f"VERIFICAR FILTROS 3 BOTS (v2) - {datetime.now().isoformat()}")
log("=" * 70)
for b in BOTS: check(*b)
log("")
log("=" * 70)

# Publicar
pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = "Filtros 3 bots v2 - " + ts + "\n\n" + "\n".join(OUT)
ok = publicar(texto, f"diag_hetzner/filtros3v2_{ts}.txt", pat)
log(f"publicado: {ok}")
sys.stdout.flush()
