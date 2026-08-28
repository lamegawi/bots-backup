#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consulta directa a gamma API: búsqueda pública 'elon musk' para ver TODAS las ventanas."""
import json
import subprocess
from datetime import datetime, timezone

def curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        raise RuntimeError("curl falló")
    return json.loads(r.stdout)

# 1) búsqueda pública (como hace el bot)
print("=" * 70)
print("BÚSQUEDA PÚBLICA 'elon musk' (todas las ventanas)")
print("=" * 70)
d = curl('https://gamma-api.polymarket.com/public-search?q=%22elon%20musk%22&limit=100')
evs = d.get("events", []) if isinstance(d, dict) else d
print("eventos encontrados:", len(evs))
print()

# 2) filtrar solo los de tweets
tweets_events = [e for e in evs if "tweets" in (e.get("title") or "").lower()]
print("eventos con 'tweets':", len(tweets_events))
for e in sorted(tweets_events, key=lambda x: x.get("endDate") or ""):
    title = e.get("title", "?")
    closed = e.get("closed")
    end = (e.get("endDate") or "")[:16]
    vol = e.get("volumeNum") or e.get("volume") or "?"
    print(f"   closed={closed} | {title} | end={end} | vol={vol}")
