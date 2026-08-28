#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consulta las operaciones reales del usuario en Polymarket."""
import json
import subprocess
import sys

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return r.stdout

sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
import operar_real as op
client = op.get_client()

funder = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
signer = "0x8a22F798C20B0f542c38ABD697a29E4BE7C3bae6"

print("=" * 70)
print("1) BALANCE (CLOB get_balance_allowance)")
print("=" * 70)
try:
    r = client.get_balance_allowance(params={"asset_type": "COLLATERAL",
                                             "token_id": "71321045679252212594626385532706912750332728571942532289631379312455583992563"})
    print("   pUSD:", json.dumps(r, indent=2)[:400])
except Exception as e:
    print("   error:", e)

print()
print("=" * 70)
print("2) ÓRDENES ABIERTAS (get_open_orders)")
print("=" * 70)
try:
    oo = client.get_open_orders()
    print("   tipo:", type(oo).__name__)
    if isinstance(oo, dict):
        print(json.dumps(oo, indent=2)[:2000])
    elif isinstance(oo, list):
        print(f"   {len(oo)} órdenes abiertas")
        for o in oo[:20]:
            print("   -", json.dumps(o)[:300])
except Exception as e:
    print("   error:", e)

print()
print("=" * 70)
print("3) TRADES (get_trades) del signer")
print("=" * 70)
try:
    tr = client.get_trades()
    if isinstance(tr, dict):
        print(json.dumps(tr, indent=2)[:2500])
    elif isinstance(tr, list):
        print(f"   {len(tr)} trades")
        for t in tr[:20]:
            print("   -", json.dumps(t)[:300])
except Exception as e:
    print("   error:", e)

print()
print("=" * 70)
print("4) DATA-API posiciones (funder)")
print("=" * 70)
for url in [
    f"https://data-api.polymarket.com/positions?user={funder}",
    f"https://data-api.polymarket.com/positions?user={signer}",
]:
    d = curl(url)
    print(f"   {url}")
    if d is None:
        print("      (sin respuesta)")
    elif isinstance(d, list):
        print(f"      {len(d)} posiciones")
        for p in d[:20]:
            print("      -", json.dumps(p)[:400])
    else:
        print("      ", json.dumps(d)[:500])
    print()
