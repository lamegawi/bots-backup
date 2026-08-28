#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Comprueba: (1) ventanas semanales vs seguidas, (2) estado real de cada orden en CLOB."""
import json
import os
import sys

BASE = "/opt/polymarket"

print("=" * 60)
print("1) VENTANAS en mercado_activo.json (todas)")
print("=" * 60)
p = f"{BASE}/bot-polymarket-elon/mercado_activo.json"
d = json.load(open(p, encoding="utf-8"))
mercados = d.get("mercados", [])
print("TOTAL registrados:", len(mercados))
sem = [m for m in mercados if m.get("tipo") == "semanal"]
print("SEMANALES:", len(sem))
for m in sem:
    print("   -", m.get("titulo"), "| cerrado:", m.get("cerrado"),
          "| fin:", (m.get("fin_iso") or "")[:16])
print()
print("TODOS por tipo:")
for m in mercados:
    print("   [%s] %s | cerrado=%s | fin=%s" % (
        m.get("tipo"), m.get("titulo"), m.get("cerrado"),
        (m.get("fin_iso") or "")[:16]))

print()
print("=" * 60)
print("2) ESTADO REAL de cada orden (CLOB) + qué ventana sigue cada bot")
print("=" * 60)

sys.path.insert(0, f"{BASE}/bot-polymarket-elon")
try:
    import operar_real as op
    client = op.get_client()
except Exception as e:
    print("no pude crear cliente CLOB:", e)
    client = None

BOTS = [
    ("48h",        f"{BASE}/bot-polymarket-elon/real.json"),
    ("48h-V2",     f"{BASE}/bot-polymarket-elon-v2/real.json"),
    ("Semanal",    f"{BASE}/bot-polymarket-elon-semanal/real_semanal.json"),
    ("Semanal-V2", f"{BASE}/bot-polymarket-elon-semanal-v2/real_semanal.json"),
    ("Mensual",    f"{BASE}/bot-polymarket-elon-mensual/real_mensual.json"),
    ("Mensual-V2", f"{BASE}/bot-polymarket-elon-mensual-v2/real_mensual.json"),
]

for nombre, path in BOTS:
    try:
        st = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        print(f"\n[{nombre}] sin estado: {e}")
        continue
    act = st.get("activa")
    if not act:
        print(f"\n[{nombre}] sin apuesta activa (historial: {len(st.get('historial', []))})")
        continue
    print(f"\n[{nombre}] {act.get('bin_titulo')} {act.get('lado')} stake ${act.get('stake', 0):.2f}")
    print(f"   slug: {act.get('slug')}")
    print(f"   pendiente flag: {act.get('pendiente')}")
    oid = act.get("order_id")
    print(f"   order_id: {oid}")
    if client and oid:
        try:
            det = client.get_order(oid)
            print(f"   -> status CLOB: {det.get('status')}")
            print(f"   -> size_matched: {det.get('size_matched')}")
            print(f"   -> original_size: {det.get('original_size')}")
        except Exception as e:
            print(f"   -> error consultando orden: {e}")
