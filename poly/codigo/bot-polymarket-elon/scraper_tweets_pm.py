#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper_tweets_pm.py — extrae el conteo OFICIAL de xtracker.polymarket.com
=============================================================================
xtracker es la fuente de verdad que Polymarket usa para resolver
(https://xtracker.polymarket.com/). Esta página es ligera (texto plano)
y NO tiene Cloudflare, así que funciona con jina SIN clave o incluso
sin jina (vía allorigins.win o similar).

USO:
  python3 scraper_tweets_pm.py --user elonmusk
  python3 scraper_tweets_pm.py --user elonmusk --actualizar-csv
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

try:
    ET = ZoneInfo("America/New_York")
except Exception:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-4), name="EDT")

JINA_KEY_FILE = "/opt/polymarket/.jina_key"
CSV = "datos_elon.csv"
XTRACKER = "https://xtracker.polymarket.com"


def curl(url, headers=None, timeout=60):
    cmd = ["curl", "-s", "--max-time", str(timeout), "-L", url]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"curl falló ({r.returncode})")
    return r.stdout


def jina_token():
    try:
        t = open(JINA_KEY_FILE, encoding="utf-8").read().strip()
        if t:
            return t
    except Exception:
        pass
    return os.environ.get("JINA_API_KEY", "").strip()


def fetch_xtracker(user, debug=False):
    """Lee la página de usuario vía jina. Sin clave si no hay saldo."""
    url = f"https://{XTRACKER.split('//')[1]}/user/{user}"
    hdrs = {"Accept": "text/plain"}
    tok = jina_token()
    if tok:
        hdrs["Authorization"] = "Bearer " + tok
    hdrs["x-no-cache"] = "true"
    md = curl(f"https://r.jina.ai/{url}", hdrs, timeout=90)
    if debug:
        with open("/tmp/pm_debug.html", "w", encoding="utf-8") as f:
            f.write(md)
    return md


def parsear(md, user):
    """Extrae TWEET_COUNT para el periodo Sep 4 - Sep 11, 2026."""
    out = {"user": user}
    # el patrón en xtracker es: "Sep 4 – Sep 11 150" (con guion largo)
    # seguido de "Sep 4, 2026 → Sep 11, 2026" en la página de detalle
    # buscar en la línea que menciona "September 4 - September 11, 2026"
    lineas = md.split("\n")
    target = None
    for i, ln in enumerate(lineas):
        if "September 4 - September 11, 2026" in ln:
            target = i
            break
    if target is None:
        # fallback: buscar "Sep 4 – Sep 11" en la primera vista
        m = re.search(r"Sep\s*4\s*[–-]\s*Sep\s*11\s+(\d+)", md)
        if m:
            out["tweet_count"] = int(m.group(1))
        return out
    # buscar el número después de la línea objetivo
    # puede estar en la misma línea o en las siguientes (hasta 3 líneas)
    for j in range(target, min(target + 4, len(lineas))):
        m = re.search(r"^\s*(\d+)\s*$", lineas[j])
        if m:
            out["tweet_count"] = int(m.group(1))
            out["linea"] = j
            return out
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="elonmusk", help="usuario de X (sin @)")
    ap.add_argument("--actualizar-csv", action="store_true",
                    help="si tweet_count existe, escribir como fecha de HOY en el CSV")
    ap.add_argument("--debug-html", action="store_true",
                    help="guardar el HTML crudo recibido a /tmp/pm_debug.html")
    args = ap.parse_args()

    md = fetch_xtracker(args.user, debug=args.debug_html)
    if args.debug_html:
        print(f"  HTML crudo: {len(md)} bytes -> /tmp/pm_debug.html")

    if "Account balance not enough" in md or len(md) < 200:
        print("[ERROR] jina sin saldo o respuesta muy pequeña. Primeros 500 chars:")
        print(md[:500])
        sys.exit(1)

    out = parsear(md, args.user)
    print(json.dumps(out, indent=2, ensure_ascii=False))

    if args.actualizar_csv and "tweet_count" in out:
        hoy = datetime.now(ET).date()
        # escribir como día en curso (overrides el conteo diario del CSV)
        filas = {}
        if os.path.exists(CSV):
            with open(CSV, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    filas[r["fecha"]] = int(r["tweets"])
        filas[hoy.isoformat()] = out["tweet_count"]
        # guardar backup
        if os.path.exists(CSV):
            with open(CSV, "rb") as src, open(CSV + ".bak", "wb") as dst:
                dst.write(src.read())
        with open(CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["fecha", "tweets"])
            for f_ in sorted(filas):
                w.writerow([f_, filas[f_]])
        # guardar también en JSON oficial
        oficial = {
            "fuente": "xtracker.polymarket.com",
            "user": args.user,
            "tweet_count_oficial": out["tweet_count"],
            "scrapeado_en": datetime.now(ET).isoformat(),
        }
        with open("polymarket_oficial.json", "w", encoding="utf-8") as f:
            json.dump(oficial, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] CSV actualizado: {hoy} = {out['tweet_count']} tweets")
        print(f"[OK] polymarket_oficial.json guardado")
    elif args.actualizar_csv:
        print("\n[AVISO] no se encontró tweet_count; nada que guardar.")


if __name__ == "__main__":
    main()
