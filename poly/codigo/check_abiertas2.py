#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Posiciones abiertas REALES cruzadas con gamma API (clobTokenIds)."""
import json
import subprocess

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)

funder = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
BASE = "/opt/polymarket/bot-polymarket-elon"
d = json.load(open(f"{BASE}/mercado_activo.json", encoding="utf-8"))

# 1) construir mapa token_id -> (ventana, bin, lado) via gamma API
mapa = {}
for m in d.get("mercados", []):
    slug = m.get("slug")
    ev = curl(f"https://gamma-api.polymarket.com/events?slug={slug}")
    if not ev:
        continue
    evs = ev if isinstance(ev, list) else ev.get("events", [])
    for e in evs:
        if e.get("slug") != slug:
            continue
        title = e.get("title", slug)
        for mk in e.get("markets", []):
            bin_t = mk.get("groupItemTitle") or ""
            toks = mk.get("clobTokenIds") or []
            outcomes = mk.get("outcomes") or ["Yes", "No"]
            if len(toks) >= 2:
                mapa[str(toks[0])] = {"ventana": title, "slug": slug,
                                      "bin": bin_t, "lado": "YES",
                                      "fin": e.get("endDate")}
                mapa[str(toks[1])] = {"ventana": title, "slug": slug,
                                      "bin": bin_t, "lado": "NO",
                                      "fin": e.get("endDate")}
print("tokens mapeados:", len(mapa))

# 2) posiciones del funder
pos = curl(f"https://data-api.polymarket.com/positions?user={funder}") or []
abiertas = [p for p in pos if float(p.get("size", 0) or 0) > 0
            and float(p.get("currentValue", 0) or 0) > 0.001]
print("posiciones con valor > 0:", len(abiertas))
print()
total_val = 0
for p in sorted(abiertas, key=lambda x: -(float(x.get("currentValue", 0) or 0))):
    asset = str(p.get("asset"))
    info = mapa.get(asset, {})
    size = float(p.get("size", 0))
    avg = float(p.get("avgPrice", 0))
    cur_val = float(p.get("currentValue", 0) or 0)
    init_val = float(p.get("initialValue", 0) or 0)
    pnl = cur_val - init_val
    total_val += cur_val
    ventana = (info.get("ventana") or p.get("conditionId", "?")[:12]).replace("Elon Musk # tweets ", "").replace("?", "")
    print(f"* {ventana}")
    print(f"    bin {info.get('bin','?')} {info.get('lado','?')} · {size:.1f} shares @ {avg:.4f}")
    print(f"    invertido ${init_val:.2f} → ahora ${cur_val:.2f} → {'+' if pnl>=0 else ''}${pnl:+.2f}")
    print(f"    fin {(info.get('fin') or '')[:16]}")
    print()
print(f"VALOR TOTAL de posiciones: ${total_val:.2f}")
