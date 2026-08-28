#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Compara ventanas que ve el bot vs ventanas reales en Polymarket."""
import json
import subprocess

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    return json.loads(r.stdout) if r.stdout.strip() else None

print("=" * 70)
print("1) LO QUE VE EL BOT (mercado_activo.json)")
print("=" * 70)
d = json.load(open("/opt/polymarket/bot-polymarket-elon/mercado_activo.json", encoding="utf-8"))
for m in d["mercados"]:
    print("  [%s] cerrado=%s | %s | fin=%s" % (
        m.get("tipo"), m.get("cerrado"), m.get("titulo"), (m.get("fin_iso") or "")[:16]))

print()
print("=" * 70)
print("2) REAL EN POLYMARKET (búsquedas)")
print("=" * 70)
seen = {}
for q in ["%22elon%20musk%22", "tweets"]:
    dd = curl("https://gamma-api.polymarket.com/public-search?q=%s&limit=100" % q)
    if not dd:
        continue
    evs = dd.get("events", []) if isinstance(dd, dict) else dd
    for e in evs:
        t = (e.get("title") or "").lower()
        if "elon" in t or "tweet" in t:
            slug = e.get("slug", "")
            if slug not in seen:
                seen[slug] = e

print("Ventanas únicas encontradas:", len(seen))
for slug, e in sorted(seen.items(), key=lambda x: x[1].get("endDate") or ""):
    print("  %s | %s | end=%s" % (
        "ABIERTA" if not e.get("closed") else "cerrado",
        e.get("title"), (e.get("endDate") or "")[:16]))
