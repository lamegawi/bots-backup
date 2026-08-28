#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Posiciones abiertas reales con mapeo por conditionId via gamma API."""
import json
import subprocess

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)

funder = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"

# cache de mercados por conditionId
cache = {}

def info_mercado(cid):
    if cid in cache:
        return cache[cid]
    m = curl(f"https://gamma-api.polymarket.com/markets/{cid}")
    if not m:
        cache[cid] = None
        return None
    # m es un objeto market con clobTokenIds, outcomes, groupItemTitle, y el evento padre
    ev = m.get("events", [{}])
    evento = ev[0] if isinstance(ev, list) and ev else m
    title = evento.get("title") or m.get("eventTitle") or ""
    slug = evento.get("slug") or m.get("eventSlug") or ""
    out = {
        "title": title,
        "slug": slug,
        "bin": m.get("groupItemTitle") or "",
        "outcomes": m.get("outcomes") or [],
        "tokens": m.get("clobTokenIds") or [],
        "end": evento.get("endDate") or m.get("endDate") or "",
    }
    cache[cid] = out
    return out

pos = curl(f"https://data-api.polymarket.com/positions?user={funder}") or []
abiertas = [p for p in pos if float(p.get("size", 0) or 0) > 0
            and float(p.get("currentValue", 0) or 0) > 0.001]
print("posiciones con valor > 0:", len(abiertas), "\n")

total = 0
for p in sorted(abiertas, key=lambda x: -(float(x.get("currentValue", 0) or 0))):
    cid = p.get("conditionId", "")
    info = info_mercado(cid) if cid else None
    asset = str(p.get("asset"))
    size = float(p.get("size", 0))
    avg = float(p.get("avgPrice", 0))
    cur_val = float(p.get("currentValue", 0) or 0)
    init_val = float(p.get("initialValue", 0) or 0)
    pnl = cur_val - init_val
    total += cur_val
    ventana = (info.get("title") if info else cid[:12]).replace("Elon Musk # tweets ", "").replace("?", "")
    # lado: asset coincide con tokens[0]=YES o tokens[1]=NO
    lado = "?"
    if info and info.get("tokens"):
        if asset == str(info["tokens"][0]):
            lado = "YES"
        elif len(info["tokens"]) > 1 and asset == str(info["tokens"][1]):
            lado = "NO"
    bin_t = info.get("bin") if info else "?"
    fin = (info.get("end") or "")[:16] if info else ""
    print(f"* {ventana}")
    print(f"    bin {bin_t} {lado} · {size:.1f} shares @ {avg:.4f}")
    print(f"    invertido ${init_val:.2f} -> ahora ${cur_val:.2f} -> ${pnl:+.2f}")
    print(f"    fin {fin}")
    print()

print(f"VALOR TOTAL posiciones: ${total:.2f}")
