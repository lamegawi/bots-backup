#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
verificar_tweets_ventana.py — compara los tweets que Polymarket/xtracker ve
con los que el bot tiene en estado_tweets.json.

USO:
  python3 verificar_tweets_ventana.py
  python3 verificar_tweets_ventana.py --user elonmusk
  python3 verificar_tweets_ventana.py --user realDonaldTrump
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    ET = ZoneInfo("America/New_York")
except Exception:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-4), name="EDT")

T_FMT = "%a %b %d %H:%M:%S +0000 %Y"


def curl(url, headers=None, timeout=20):
    cmd = ["curl", "-s", "--max-time", str(timeout), "-L", "-A",
           "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
           url]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"curl falló ({r.returncode})")
    return r.stdout


def fetch_xtracker(user):
    return curl(f"https://xtracker.polymarket.com/user/{user}", timeout=20)


def fetch_xtracker_json(user):
    """xtracker expone un endpoint JSON /api/users/{user}/posts?days=N.
    Si existe, devuelve los tweets con su timestamp real."""
    # probar endpoints comunes
    for url in [
        f"https://xtracker.polymarket.com/api/users/{user}/posts",
        f"https://xtracker.polymarket.com/api/posts?user={user}",
        f"https://xtracker.polymarket.com/user/{user}.json",
    ]:
        try:
            txt = curl(url, {"Accept": "application/json"}, timeout=10)
            if txt and txt.startswith("["):
                return json.loads(txt)
            if txt and txt.startswith("{"):
                return json.loads(txt)
        except Exception:
            pass
    return None


def parsear_xtracker_tweets(html, user):
    """Extrae los últimos tweets del HTML de xtracker (parseo básico)."""
    # Buscar IDs de tweets de X.com en el HTML
    ids = re.findall(r'(?:twitter\.com|x\.com)/' + re.escape(user) + r'/status/(\d+)', html)
    # también buscar fechas tipo "Sep 10" o "2026-09-10"
    fechas = re.findall(r'(?:Sep|Oct|Nov|Dec)\s+(\d{1,2})', html)
    return list(dict.fromkeys(ids))[:20], fechas


def cargar_estado():
    if not os.path.exists("estado_tweets.json"):
        return {}
    try:
        return json.load(open("estado_tweets.json", encoding="utf-8")).get("tweets", {})
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="elonmusk")
    args = ap.parse_args()

    print(f"=== VERIFICACIÓN DE TWEETS — {args.user} ===")
    print(f"Fecha UTC: {datetime.utcnow().isoformat()}")
    print(f"Fecha ET:  {datetime.now(ET).isoformat()}")
    print()

    # 1) estado del bot
    estado = cargar_estado()
    print(f"== ESTADO GUARDADO DEL BOT ==")
    print(f"  Items totales: {len(estado)}")
    posts = sum(1 for v in estado.values() if v.get("kind") == "post")
    reps = sum(1 for v in estado.values() if v.get("kind") == "repost")
    print(f"  Posts: {posts}  Reposts: {reps}")
    if estado:
        # últimos 10 por created_at
        items = []
        for sid, v in estado.items():
            try:
                dt = datetime.strptime(v.get("created_at", ""), T_FMT)
            except Exception:
                continue
            items.append((dt, sid, v.get("kind"), v.get("created_at")))
        items.sort()
        print(f"\n  Últimos 10 items por timestamp (created_at):")
        print(f"  {'FECHA UTC':<22} {'KIND':<8} {'ID':<22} {'PRIMERA_VISTA'}")
        for dt, sid, kind, ts in items[-10:]:
            pv = estado[sid].get("primera_vista", "?")
            print(f"  {ts:<22} {kind:<8} {sid:<22} {pv}")

    # 2) xtracker (vista)
    print(f"\n== XTRACKER (vista oficial Polymarket) ==")
    try:
        html = fetch_xtracker(args.user)
        ids, fechas = parsear_xtracker_tweets(html, args.user)
        print(f"  Tamaño HTML: {len(html)} bytes")
        print(f"  IDs de tweets encontrados en HTML: {len(ids)}")
        for i, sid in enumerate(ids[:10]):
            en_estado = "✓" if sid in estado else "✗"
            print(f"    {i+1}. {sid}  en_estado={en_estado}")
    except Exception as e:
        print(f"  [ERROR] {e}")

    # 3) intersección
    if estado and ids:
        en_comun = set(estado.keys()) & set(ids)
        solo_bot = set(estado.keys()) - set(ids)
        solo_xtracker = set(ids) - set(estado.keys())
        print(f"\n== INTERSECCIÓN ==")
        print(f"  Tweets en ambos: {len(en_comun)}")
        print(f"  Solo en bot: {len(solo_bot)} (no están en el primer fold de xtracker)")
        print(f"  Solo en xtracker (primer fold): {len(solo_xtracker)}")
        if solo_xtracker:
            print(f"\n  ⚠ Tweets que el BOT NO TIENE (vistos en xtracker):")
            for sid in list(solo_xtracker)[:5]:
                print(f"    {sid}")


if __name__ == "__main__":
    main()
