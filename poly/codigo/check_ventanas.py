#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consulta directa a gamma API para ver todas las ventanas de Elon Musk."""
import json
import subprocess

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("curl falló")
    return json.loads(r.stdout)

print("=" * 60)
print("EVENTOS 'tweets' en gamma API (todos, sin filtrar)")
print("=" * 60)
d = curl("https://gamma-api.polymarket.com/events?slug=elon-musk-of-tweets&limit=100&active=true")
evs = d.get("events", []) if isinstance(d, dict) else d
print("activos:", len(evs))

# también sin active (incluye cerrados)
d2 = curl("https://gamma-api.polymarket.com/events?slug=elon-musk-of-tweets&limit=100")
evs2 = d2.get("events", []) if isinstance(d2, dict) else d2
print("totales (incl. cerrados):", len(evs2))

for e in evs2:
    title = e.get("title", e.get("slug", "?"))
    active = e.get("active")
    closed = e.get("closed")
    end = e.get("endDate", "")[:16]
    # tipo: inferir por duración del título
    print(f"   active={active} closed={closed} | {title} | end={end}")
