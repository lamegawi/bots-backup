#!/usr/bin/env python3
"""
DETECTAR TRADES PARA COPIAR
============================
Detecta los trades mas recientes de los top traders
y los publica como recomendaciones (con stake sugerido $2-3).

USO: python3 detectar_trades_copy.py
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
    paths = ["/root/diag_token.txt", os.path.expanduser("~/diag_token.txt"), "/tmp/diag_token.txt"]
    for r in paths:
        if os.path.exists(r):
            t = open(r).read().strip()
            if t.startswith("ghp_"):
                return t
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
    payload = {"message": f"copytrades {datetime.now().strftime('%H%M%S')}",
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

# Traders y sus pesos (los que mas ganan primero)
TOP_TRADERS = [
    ("pleaseplease123",     "0x5e9458202b5817a72cf81105ec8a30e6f3705ba1", 10),
    ("ferrariChampions2026", "0xfe787d2da716d60e8acff57fb87eb13cd4d10319", 8),
    ("balthazar",            "0x5a218c7ad04135830a45c41aaed7294df7809318", 5),
    ("Sassy-Bucket",         "0x4bff30af91642dc7d2b19a8664378fe55c45fc26", 5),
    ("Jsram",                "0x83720820a8aa6c3f20ad71850e7a1a17d16c5223", 5),
    ("Flaznorp",             "0x821dab0565ebf5b327f51db06223fdcfe01acf16", 5),
    ("Talvez10",             "0xa71093cafc0c099b4ccab24c3cb8018d817923c4", 4),
    ("GoalLineGhost",        "0x0346afae2603313d2bbee96b628536c8cbe352a5", 3),
    ("AV23IUa",              "0xdb859a551fcf56e49416160911476bea7307152f", 3),
]

# Deportes permitidos (filtrar solo estos)
DEPORTES_OK = [
    "MLB", "UFC", "NFL", "NBA", "NHL", "tennis", "ATP", "WTA",
    "soccer", "EPL", "La Liga", "Bundesliga", "Serie A", "Ligue 1",
    "World Cup", "Champions League", "Europa League",
    "O/U", "Spread", "Moneyline", "Over/Under",
]

# Excluir politicos/crypto/series
EXCLUIR = [
    "Trump", "Biden", "Election", "President", "Congress",
    "Bitcoin", "Ethereum", "Crypto", "NFT",
    "Fed", "rate", "inflation", "economy",
    "Russia", "Ukraine", "China", "NATO", "Iran", "Israel",
    "WHO", "covid", "pandemic",
]

STAKE_POR_TRADE = 2.0  # dolares por trade
MAX_TRADES_SIMULTANEOS = 3  # maximo de operaciones a la vez
HORAS_RECIENTE = 24  # considerar trades de las ultimas 24h

log("=" * 70)
log(f"DETECTAR TRADES PARA COPIAR · {datetime.now().isoformat()}")
log("=" * 70)
log(f"Stake por trade: ${STAKE_POR_TRADE}")
log(f"Max trades simultaneos: {MAX_TRADES_SIMULTANEOS}")
log(f"Ventana: ultimas {HORAS_RECIENTE} horas")
log("")

candidatos = []

for nombre, wallet, peso in TOP_TRADERS:
    log(f"\n[{nombre}] peso={peso}")
    try:
        url = f"https://data-api.polymarket.com/trades?user={wallet}&limit=30"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            trades = json.loads(r.read())
        log(f"  {len(trades)} trades")
        for t in trades:
            if not isinstance(t, dict): continue
            titulo = t.get('title', '') or t.get('question', '')
            # filtrar deportes
            if any(ex in titulo for ex in EXCLUIR):
                continue
            # detectar si es deporte
            if not any(d.lower() in titulo.lower() for d in DEPORTES_OK):
                continue
            # verificar timestamp
            ts = t.get('timestamp', 0)
            ahora = datetime.now().timestamp()
            if ahora - ts > HORAS_RECIENTE * 3600:
                continue
            side = t.get('side', '?')
            price = float(t.get('price', 0))
            size = float(t.get('size', 0))
            asset = t.get('asset', '?')[:20]
            log(f"  · {datetime.fromtimestamp(ts).strftime('%H:%M')} | {titulo[:50]} | {side} @ {price:.2f}")
            candidatos.append({
                "trader": nombre,
                "peso": peso,
                "titulo": titulo,
                "side": side,
                "price": price,
                "size": size,
                "asset": asset,
                "timestamp": ts,
                "cuota": round(1/price, 2) if price > 0 else 0,
                "stake_sugerido": STAKE_POR_TRADE,
            })
    except Exception as e:
        log(f"  ERROR: {e}")

# ordenar por peso del trader (los mas exitosos primero)
candidatos.sort(key=lambda x: -x["peso"])

# deduplicar por mercado (no copiar el mismo mercado 2 veces)
vistos = set()
finales = []
for c in candidatos:
    key = c["titulo"][:50]
    if key in vistos:
        continue
    vistos.add(key)
    finales.append(c)
    if len(finales) >= MAX_TRADES_SIMULTANEOS:
        break

log("")
log("=" * 70)
log(f"RECOMENDACIONES PARA COPIAR ({len(finales)} trades)")
log("=" * 70)
log("")
for i, c in enumerate(finales, 1):
    log(f"{i}. {c['titulo'][:60]}")
    log(f"   Trader: {c['trader']} (peso {c['peso']})")
    log(f"   Lado: {c['side']} @ {c['price']:.3f} (cuota {c['cuota']:.2f})")
    log(f"   Stake del trader: {c['size']:.0f} | TU stake: ${c['stake_sugerido']}")
    log(f"   Cuando: {datetime.fromtimestamp(c['timestamp']).strftime('%Y-%m-%d %H:%M')}")
    log("")

log("=" * 70)

# publicar
pat = find_pat()
ts = datetime.now().strftime("%Y%m%d_%H%M%S")
texto = "TRADES PARA COPIAR - " + ts + "\n\n" + "\n".join(LOG) + "\n\nJSON:\n" + json.dumps(finales, indent=2, ensure_ascii=False)
ruta = f"diag_hetzner/copytrades_{ts}.txt"
ok = publicar(texto, ruta, pat)
log(f"publicado: {ok}")
