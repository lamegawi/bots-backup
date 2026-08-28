#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Busca TODOS los eventos de tweets (más amplio) y el estado de órdenes en CLOB."""
import json
import subprocess
import sys

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return json.loads(r.stdout)

# 1) búsqueda más amplia: "tweets"
print("=" * 70)
print("BÚSQUEDA 'tweets' (amplia)")
print("=" * 70)
for q in ['%22tweets%22', 'elon%20musk%20tweets', '%22elon%20musk%22%20tweets']:
    d = curl(f"https://gamma-api.polymarket.com/public-search?q={q}&limit=100")
    if not d:
        continue
    evs = d.get("events", []) if isinstance(d, dict) else d
    if evs:
        print(f"\nquery={q} -> {len(evs)} eventos:")
        for e in evs:
            print(f"   closed={e.get('closed')} | {e.get('title')} | end={e.get('endDate','')[:16]}")
        break

# 2) estado de órdenes CLOB
print()
print("=" * 70)
print("ESTADO REAL DE ÓRDENES EN CLOB")
print("=" * 70)
sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
import operar_real as op
client = op.get_client()

ordenes = [
    ("48h-V2", "0xb315477a366dbd7fee0661579e0b1217e886703272771fc4187ceb22e5f44e29"),
    ("Semanal", "0xd5d7aade0a9a0f324acf5468febb6057a0db87b5a34dccbd7379f1d89200e1d2"),
    ("Semanal-V2", "0xa1b936cd50c6a94de1c81cd0bf4c510378348a2866519bd5581f299d24ee8462"),
    ("Mensual", "0xd6645d42ae0dcd55d532e357b807a7502522ae5e9cbce13ecbb89f9018794c8e"),
    ("Mensual-V2", "0xea551b0d35d41484f7b6a280ef06c64e2d91e788f596e34ffc5dc0eabf391d66"),
]
for nombre, oid in ordenes:
    try:
        det = client.get_order(oid)
        if det is None:
            print(f"[{nombre}] {oid[:14]}… -> NO EXISTE en CLOB (cancelada/expiró)")
        else:
            st = det.get("status")
            sz = det.get("size_matched")
            print(f"[{nombre}] {oid[:14]}… -> status={st} matched={sz}")
    except Exception as e:
        print(f"[{nombre}] {oid[:14]}… -> error: {e}")
