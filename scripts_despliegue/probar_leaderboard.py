#!/usr/bin/env python3
"""
PROBAR LEADERBOARD POLYMARKET
=============================
Prueba varios endpoints para encontrar la tabla de clasificacion.

USO: python3 probar_leaderboard.py
"""
import os
import json
import urllib.request
import base64
from datetime import datetime

LOG = []
def log(s):
    line = str(s)
    print(line[:500], flush=True)
    LOG.append(line)

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
    payload = {"message": f"leader {datetime.now().strftime('%H%M%S')}",
               "content": b64, "branch": "diag-public"}
    if sha: payload["sha"] = sha
    req = urllib.request.Request(
        f"https://api.github.com/repos/lamegawi/bots-backup/contents/{ruta}",
        data=json.dumps(payload).encode(), method="PUT",
        headers={"Authorization": f"token {pat}", "Content-Type": "application/json",
                 "User-Agent": "diag"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r: return True
    except: return False

log("=" * 70)
log(f"PROBAR LEADERBOARD · {datetime.now().isoformat()}")
log("=" * 70)

# Posibles endpoints de leaderboard
endpoints = [
    ("leaderboard_v1", "https://data-api.polymarket.com/leaderboard?limit=50"),
    ("leaderboard_v2", "https://data-api.polymarket.com/leaderboard?category=combo&limit=50"),
    ("leaderboard_v3", "https://gamma-api.polymarket.com/leaderboard?limit=50"),
    ("leaderboard_v4", "https://data-api.polymarket.com/leaderboard/combo?limit=50"),
    ("leaderboard_v5", "https://data-api.polymarket.com/leaderboard?timePeriod=all&limit=50"),
    ("users_top", "https://data-api.polymarket.com/users/top?limit=50"),
    ("traders", "https://data-api.polymarket.com/traders?limit=50"),
    ("combo_events", "https://gamma-api.polymarket.com/events?tag_slug=combos&limit=50"),
    ("combo_markets", "https://gamma-api.polymarket.com/markets?tag_slug=combos&limit=50"),
]

resultados = {}
for nombre, url in endpoints:
    log(f"\n[{nombre}] {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            if isinstance(data, list):
                count = len(data)
                log(f"  ✓ {count} items (lista)")
                resultados[nombre] = {"url": url, "count": count, "data": data[:30]}
            elif isinstance(data, dict):
                log(f"  ✓ dict con keys: {list(data.keys())[:10]}")
                resultados[nombre] = {"url": url, "data": data}
            else:
                log(f"  ? tipo: {type(data).__name__}")
                resultados[nombre] = {"url": url, "data": data}
    except Exception as e:
        log(f"  ✗ {type(e).__name__}: {str(e)[:200]}")
        resultados[nombre] = {"error": str(e)}

log("")
log("=" * 70)
log("Publicando respuesta cruda...")

pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = json.dumps(resultados, indent=2, ensure_ascii=False, default=str)
ruta = f"diag_hetzner/leaderboard_{ts}.txt"
ok = publicar(texto, ruta, pat)
log(f"publicado: {ok}")
log(f"tamaño: {len(texto)} bytes")
