#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Posiciones ABIERTAS (size>0) del funder, cruzadas con las ventanas de mercado_activo.json."""
import json
import subprocess

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)

funder = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"

# 1) mercado_activo.json -> mapeo token_id -> (ventana, bin, lado)
import os
BASE = "/opt/polymarket/bot-polymarket-elon"
d = json.load(open(f"{BASE}/mercado_activo.json", encoding="utf-8"))
mapa = {}   # token_id -> dict
for m in d.get("mercados", []):
    for b in m.get("bins", []):
        for campo, lado in (("token_id", "YES"), ("token_id_no", "NO")):
            tid = b.get(campo)
            if tid:
                mapa[str(tid)] = {
                    "ventana": m.get("titulo", m.get("slug")),
                    "slug": m.get("slug"),
                    "bin": b.get("titulo"),
                    "lado": lado,
                    "fin": m.get("fin_iso"),
                    "tipo": m.get("tipo"),
                }

print("bins mapeados en mercado_activo.json:", len(mapa))

# 2) posiciones del funder
pos = curl(f"https://data-api.polymarket.com/positions?user={funder}") or []
print("total posiciones:", len(pos))

abiertas = [p for p in pos if float(p.get("size", 0) or 0) > 0]
print("ABIERTAS (size>0):", len(abiertas))
print()

for p in sorted(abiertas, key=lambda x: -(float(x.get("currentValue", 0) or 0))):
    asset = str(p.get("asset"))
    info = mapa.get(asset, {})
    size = float(p.get("size", 0))
    avg = float(p.get("avgPrice", 0))
    cur_val = float(p.get("currentValue", 0) or 0)
    init_val = float(p.get("initialValue", 0) or 0)
    pnl = cur_val - init_val
    ventana = (info.get("ventana") or "?").replace("Elon Musk # tweets ", "").replace("?", "")
    print(f"· {ventana} [{info.get('tipo','?')}]")
    print(f"    bin {info.get('bin','?')} {info.get('lado','?')} · {size:.1f} shares @ {avg:.4f}")
    print(f"    invertido ${init_val:.2f} → ahora ${cur_val:.2f} → {'🟢 +' if pnl>=0 else '🔴 '}${pnl:+.2f}")
    print(f"    fin: {(info.get('fin') or '')[:16]}")
    print()
