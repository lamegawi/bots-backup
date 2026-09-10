#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper_tweets_pm.py — extrae el conteo OFICIAL de Polymarket
=============================================================
Lee la página de un mercado Polymarket «Elon Musk # tweets» y extrae:
  - TWEET_COUNT: nº de tweets según Polymarket (la fuente de verdad)
  - bins: {rango: precio_YES}
  - cierre: timestamp del cierre del mercado
  - titulo: «X tweets between D and D+1»

Si se le pasa --actualizar-csv, vuelca el TWEET_COUNT al CSV
como día «hoy» (es un proxy de la suma diaria real mientras el
scrapeo jina se queda corto).

USO:
  python3 scraper_tweets_pm.py --slug elon-musk-tweets-september-4-september-11-2026
  python3 scraper_tweets_pm.py --slug <slug> --actualizar-csv
  python3 scraper_tweets_pm.py --auto  # detecta el slug del mercado 48h activo
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

try:
    ET = ZoneInfo("America/New_York")
except Exception:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-4), name="EDT")

JINA_KEY_FILE = "/opt/polymarket/.jina_key"
CSV = "datos_elon.csv"


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


def fetch_pm(slug):
    """Lee la página del mercado vía jina. Devuelve el markdown."""
    url = f"https://r.jina.ai/https://polymarket.com/event/{slug}"
    hdrs = {"Accept": "text/plain", "x-no-cache": "true"}
    tok = jina_token()
    if tok:
        hdrs["Authorization"] = "Bearer " + tok
    md = curl(url, hdrs, timeout=90)
    return md


def parsear(md):
    """Extrae TWEET_COUNT, bins, cierre, titulo."""
    out = {}
    # formato en la página: "TWEET COUNT 150 Time left ..."
    m = re.search(r"TWEET\s*COUNT\s+(\d+)", md)
    if m:
        out["tweet_count"] = int(m.group(1))
    # también aceptar el formato "TWEET_COUNT = 150" por si acaso
    if "tweet_count" not in out:
        m = re.search(r"TWEET_COUNT\s*[=:]\s*(\d+)", md)
        if m:
            out["tweet_count"] = int(m.group(1))
    m = re.search(r"(?:Will|Elon)\s+(?:Musk\s+)?(?:have|post|tweet|write)?\s*([\d,]+)\s*(?:or more)?\s*tweets?", md, re.I)
    if m:
        out["titulo_match"] = m.group(0)
    bins = {}
    for m in re.finditer(r"(\d+)-(\d+)\s+tweets?[^|]*?(?:\|\s*)?\$?([\d.]+)", md):
        lo, hi, price = int(m.group(1)), int(m.group(2)), float(m.group(3))
        bins[f"{lo}-{hi}"] = price
    for m in re.finditer(r"(\d+)\s+tweets?\s+or fewer", md, re.I):
        bins[f"<={m.group(1)}"] = 0.0
    for m in re.finditer(r"(\d+)\+?\s*tweets?[^|]*?(?:\|\s*)?\$?([\d.]+)", md):
        lo = int(m.group(1))
        if f"{lo}-{lo}" in bins:
            continue
    out["bins"] = bins
    m = re.search(r"(closes?|ends?)\s+on\s+([A-Z][a-z]+\s+\d{1,2}(?:,\s*\d{4})?)", md, re.I)
    if m:
        out["cierre"] = m.group(2)
    return out


def detectar_slug_48h():
    """Busca el slug del mercado 48h activo."""
    url = "https://r.jina.ai/https://polymarket.com/search?q=elon+musk+tweets"
    hdrs = {"Accept": "text/plain", "x-no-cache": "true"}
    tok = jina_token()
    if tok:
        hdrs["Authorization"] = "Bearer " + tok
    md = curl(url, hdrs, timeout=60)
    slugs = set()
    for m in re.finditer(r"/event/([a-z0-9\-]*elon[^\"']*tweets?[^\"']*)", md, re.I):
        slugs.add(m.group(1))
    for m in re.finditer(r"/event/([a-z0-9\-]*musk[^\"']*tweet[^\"']*)", md, re.I):
        slugs.add(m.group(1))
    return sorted(slugs)


def actualizar_csv(fecha, n):
    """Escribe fecha=n en el CSV (sobrescribe si existe, no machaca otros)."""
    filas = {}
    if os.path.exists(CSV):
        with open(CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                filas[r["fecha"]] = int(r["tweets"])
    filas[fecha.isoformat()] = n
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "tweets"])
        for f_ in sorted(filas):
            w.writerow([f_, filas[f_]])
    return len(filas)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slug", help="slug del mercado (ej. elon-musk-of-tweets-september-4-september-11-2026)")
    ap.add_argument("--auto", action="store_true", help="detectar el slug del 48h activo")
    ap.add_argument("--actualizar-csv", action="store_true",
                    help="si TWEET_COUNT existe, escribir fecha=hoy con ese valor")
    ap.add_argument("--periodo", nargs=2, metavar=("INI","FIN"),
                    help="volcar TWEET_COUNT como primer día SIN datos del periodo")
    ap.add_argument("--debug-html", action="store_true",
                    help="guardar el HTML crudo recibido a /tmp/pm_debug.html")
    args = ap.parse_args()

    if not args.slug and not args.auto:
        ap.error("especifica --slug o --auto")

    if args.auto:
        slugs = detectar_slug_48h()
        print(f"Slugs encontrados ({len(slugs)}):")
        for s in slugs[:10]:
            print(f"  {s}")
        if not slugs:
            sys.exit("No encontré slugs")
        args.slug = slugs[0]
        print(f"\nUsando: {args.slug}\n")

    print(f"Scrapeando: https://polymarket.com/event/{args.slug}\n")
    md = fetch_pm(args.slug)
    if args.debug_html:
        with open("/tmp/pm_debug.html", "w", encoding="utf-8") as f:
            f.write(md)
        print(f"  HTML crudo guardado en /tmp/pm_debug.html ({len(md)} bytes)")
    if "Just a moment" in md or "404" in md[:200] or "Page Not Found" in md[:200]:
        print("Posible bloqueo o 404. Primeros 500 chars:")
        print(md[:500])
        sys.exit(1)

    out = parsear(md)
    print(json.dumps(out, indent=2, ensure_ascii=False))

    if args.actualizar_csv and "tweet_count" in out:
        # El TWEET_COUNT es el TOTAL del periodo del mercado, NO un día.
        # Por seguridad, NO se vuelca al CSV de días individuales.
        # Se guarda en polymarket_oficial.json para referencia.
        oficial = {
            "slug": args.slug,
            "tweet_count_oficial": out["tweet_count"],
            "scrapeado_en": datetime.now(ET).isoformat(),
            "bins": out.get("bins", {}),
        }
        with open("polymarket_oficial.json", "w", encoding="utf-8") as f:
            json.dump(oficial, f, indent=2, ensure_ascii=False)
        print(f"\n[INFO] TWEET_COUNT={out['tweet_count']} es el TOTAL del mercado, no un día.")
        print(f"[INFO] Guardado en polymarket_oficial.json (NO se vuelca al CSV de días).")
        print(f"[INFO] Para el bot: el AVG7 debe seguir basándose en el CSV diario, no en este total.")
    elif args.actualizar_csv:
        print("\n[AVISO] no se encontró TWEET_COUNT; nada que guardar.")


if __name__ == "__main__":
    main()
