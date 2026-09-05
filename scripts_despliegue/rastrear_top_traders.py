#!/usr/bin/env python3
"""
RASTREAR TOP TRADERS POLYMARKET
================================
Busca los trades recientes de los traders top de la leaderboard
para detectar cuando abren posiciones nuevas.

USO: python3 rastrear_top_traders.py
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
    for r in ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"):
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
    payload = {"message": f"toptraders {datetime.now().strftime('%H%M%S')}",
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

# Top traders de la leaderboard (wallets)
TOP_TRADERS = [
    ("pleaseplease123",     "0x5e9458202b5817a72cf81105ec8a30e6f3705ba1"),
    ("ferrariChampions2026", "0xfe787d2da716d60e8acff57fb87eb13cd4d10319"),
    ("balthazar",            "0x5a218c7ad04135830a45c41aaed7294df7809318"),
    ("Sassy-Bucket",         "0x4bff30af91642dc7d2b19a8664378fe55c45fc26"),
    ("Jsram",                "0x83720820a8aa6c3f20ad71850e7a1a17d16c5223"),
    ("Flaznorp",             "0x821dab0565ebf5b327f51db06223fdcfe01acf16"),
    ("Talvez10",             "0xa71093cafc0c099b4ccab24c3cb8018d817923c4"),
    ("GoalLineGhost",        "0x0346afae2603313d2bbee96b628536c8cbe352a5"),
    ("AV23IUa",              "0xdb859a551fcf56e49416160911476bea7307152f"),
]

log("=" * 70)
log(f"RASTREAR TOP TRADERS · {datetime.now().isoformat()}")
log("=" * 70)

resultados = {}

for nombre, wallet in TOP_TRADERS:
    log(f"\n[{nombre}] {wallet[:10]}...")
    # varios endpoints para probar
    endpoints = [
        ("trades", f"https://data-api.polymarket.com/trades?user={wallet}&limit=20"),
        ("positions", f"https://data-api.polymarket.com/positions?user={wallet}&limit=20"),
        ("activity", f"https://data-api.polymarket.com/activity?user={wallet}&limit=20"),
        ("value", f"https://data-api.polymarket.com/value?user={wallet}"),
    ]
    resultados[nombre] = {"wallet": wallet, "endpoints": {}}
    for ep_name, url in endpoints:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
                if isinstance(data, list):
                    resultados[nombre]["endpoints"][ep_name] = {"count": len(data), "sample": data[:3]}
                    log(f"  ✓ {ep_name}: {len(data)} items")
                else:
                    resultados[nombre]["endpoints"][ep_name] = data
                    log(f"  ✓ {ep_name}: dict")
        except Exception as e:
            log(f"  ✗ {ep_name}: {type(e).__name__}: {str(e)[:100]}")

log("")
log("=" * 70)
log("Publicando...")

pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = json.dumps(resultados, indent=2, ensure_ascii=False, default=str)
ruta = f"diag_hetzner/toptraders_{ts}.txt"
ok = publicar(texto, ruta, pat)
log(f"publicado: {ok}")
log(f"tamaño: {len(texto)} bytes")
