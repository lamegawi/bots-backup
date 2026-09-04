#!/usr/bin/env python3
"""
SNAPSHOT JSONS - backup completo de los JSON de los bots
========================================================
Copia los 3 JSON a un lugar seguro con timestamp, publica el
contenido en diag-public y devuelve SHA256 de cada uno.

USO: python3 snapshot_jsons.py
"""
import os
import json
import shutil
import hashlib
import base64
import urllib.request
from datetime import datetime

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
    payload = {"message": f"snapshot {datetime.now().strftime('%H%M%S')}",
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

JS = [
    ("Elon 48h",      "/opt/polymarket/bot-polymarket-elon/real.json"),
    ("Zelenskyy sem", "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"),
    ("Trump mens",    "/opt/polymarket/bot-polymarket-trump/real.json"),
]

ts = datetime.now().strftime("%Y%m%d_%H%M%S")
out = []
out.append("=" * 70)
out.append(f"SNAPSHOT JSONS · {datetime.now().isoformat()}")
out.append("=" * 70)
out.append("")

snapshots = {}
for nombre, fp in JS:
    out.append(f"--- {nombre} ({fp}) ---")
    if not os.path.exists(fp):
        out.append("  (no existe)")
        out.append("")
        continue
    with open(fp, "rb") as f:
        raw = f.read()
    sha = hashlib.sha256(raw).hexdigest()
    out.append(f"  tamaño:  {len(raw)} bytes")
    out.append(f"  sha256:  {sha}")
    try:
        d = json.loads(raw)
        out.append(f"  saldo:   ${d.get('saldo', '?')}")
        out.append(f"  paso:    {d.get('paso', '?')}")
        out.append(f"  activa:  {bool(d.get('activa'))}")
        ops = d.get("operaciones") or d.get("historial") or []
        out.append(f"  ops:     {len(ops)}")
        if d.get("_sincronizado_con_real"):
            out.append(f"  _sincronizado_ts: {d.get('_sincronizado_ts', '?')}")
            out.append(f"  _bankroll_inicial_real: ${d.get('_bankroll_inicial_real', '?')}")
    except Exception as e:
        out.append(f"  ERROR parseando: {e}")
    snapshots[nombre] = raw
    out.append("")

# publicar
pat = find_pat()
texto = "\n".join(out)
ruta = f"diag_hetzner/snapshot_{ts}.txt"
ok = publicar(texto, ruta, pat)
out.append(f"publicado: {ok}")
print("\n".join(out))
