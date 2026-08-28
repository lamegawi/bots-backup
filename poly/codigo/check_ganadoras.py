#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operaciones cerradas en positivo + fechas, para saber cuáles hizo el bot."""
import json
import subprocess
import sys

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(r.stdout) if r.stdout.strip() else None

funder = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
pos = curl(f"https://data-api.polymarket.com/positions?user={funder}") or []

ganadoras = [p for p in pos if float(p.get("cashPnl", 0) or 0) > 0]
print("OPERACIONES CERRADAS EN POSITIVO:", len(ganadoras))
print()

sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
import operar_real as op
client = op.get_client()

for p in sorted(ganadoras, key=lambda x: -float(x.get("cashPnl", 0))):
    cid = p.get("conditionId")
    q = cid[:14]
    end = ""
    try:
        m = client.get_market(cid)
        if m and m.get("question"):
            q = m["question"]
        if m and m.get("end_date_iso"):
            end = m["end_date_iso"][:10]
    except Exception:
        pass
    pnl = float(p.get("cashPnl", 0) or 0)
    init = float(p.get("initialValue", 0) or 0)
    avg = float(p.get("avgPrice", 0) or 0)
    print(f"  +${pnl:+.2f}  (invertido ${init:.2f} @ {avg:.4f})  fin={end}")
    print(f"      {q}")
    print()
