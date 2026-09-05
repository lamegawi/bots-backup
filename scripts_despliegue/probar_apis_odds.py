#!/usr/bin/env python3
"""
PROBAR APIS DE ODDS EXTERNAS
=============================
Prueba varias APIs publicas de odds (sin autenticacion) para encontrar
partidos de deportes con cuotas.

USO: python3 probar_apis_odds.py
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
    payload = {"message": f"odds {datetime.now().strftime('%H%M%S')}",
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
log(f"PROBAR APIS DE ODDS · {datetime.now().isoformat()}")
log("=" * 70)

# APIs publicas (sin auth o con auth opcional)
apis = [
    # The Odds API (free tier, sin auth 500 requests/mes)
    ("the_odds_api_nba", "https://api.the-odds-api.com/v4/sports/basketball_nba/odds/?regions=us&markets=h2h&oddsFormat=decimal&dateFormat=iso"),
    ("the_odds_api_nfl", "https://api.the-odds-api.com/v4/sports/americanfootball_nfl/odds/?regions=us&markets=h2h&oddsFormat=decimal&dateFormat=iso"),
    ("the_odds_api_epl", "https://api.the-odds-api.com/v4/sports/soccer_epl/odds/?regions=eu&markets=h2h&oddsFormat=decimal&dateFormat=iso"),
    # ESPN (sin auth)
    ("espn_nba_scoreboard", "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"),
    ("espn_nfl_scoreboard", "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"),
    ("espn_soccer_scoreboard", "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard"),
    # API-Football (necesita key, gratis 100 req/dia)
    # Football-Data.org (gratis, sin auth)
    ("football_data_epl", "https://api.football-data.org/v4/competitions/PL/matches?status=SCHEDULED"),
    # OpenLigaDB (gratis, sin auth, soccer)
    ("openligadb_bundesliga", "https://api.openligadb.de/getmatchdata/bl1/2026"),
    # NCAA API (sin auth, americana)
    ("espn_ncaab", "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/scoreboard"),
]

resultados = {}
for nombre, url in apis:
    log(f"\n[{nombre}]")
    log(f"  URL: {url[:80]}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())
            if isinstance(data, list):
                count = len(data)
                log(f"  ✓ {count} items (lista)")
                resultados[nombre] = {"url": url, "count": count, "data": data[:20]}
            elif isinstance(data, dict):
                keys = list(data.keys())[:5]
                log(f"  ✓ dict, keys: {keys}")
                resultados[nombre] = {"url": url, "data": data}
    except Exception as e:
        log(f"  ✗ {type(e).__name__}: {str(e)[:200]}")
        resultados[nombre] = {"error": str(e)}

log("")
log("=" * 70)

# publicar
pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = json.dumps(resultados, indent=2, ensure_ascii=False, default=str)
ruta = f"diag_hetzner/odds_{ts}.txt"
ok = publicar(texto, ruta, pat)
log(f"publicado: {ok}")
log(f"tamaño: {len(texto)} bytes")
