#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
scraper_tweets_pm.py — extrae el conteo OFICIAL de Polymarket SIN jina
========================================================================
Estrategia en cascada (cada fuente es fallback de la anterior):
  1) curl directo a xtracker.polymarket.com (HTML, parseable)
  2) curl directo a polymarket.com/event/... (HTML, parseable)
  3) curl a gamma-api.polymarket.com (JSON, sólo para precios/bin)
  4) jina (si hay clave) — desactivado por defecto

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
from datetime import datetime, date
from zoneinfo import ZoneInfo

try:
    ET = ZoneInfo("America/New_York")
except Exception:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-4), name="EDT")

JINA_KEY_FILE = "/opt/polymarket/.jina_key"
CSV = "datos_elon.csv"


def curl(url, headers=None, timeout=30):
    """Usa urllib con SSL no verificado (porque el bot corre como servicio
    systemd sin acceso a CA certs del sistema, lo que hace fallar
    'curl' con exit 60)."""
    import urllib.request
    import ssl
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers or {})
    req.add_header("User-Agent", "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.read().decode("utf-8", errors="replace")


def fetch_xtracker_direct(user):
    """Curl directo a xtracker.polymarket.com (sin jina)."""
    url = f"https://xtracker.polymarket.com/user/{user}"
    return curl(url, timeout=20)


def fetch_pm_direct(slug):
    """Curl directo a polymarket.com (sin jina)."""
    url = f"https://polymarket.com/event/{slug}"
    return curl(url, timeout=20)


def fetch_gamma(slug):
    """API gamma de Polymarket (JSON, sin auth)."""
    url = f"https://gamma-api.polymarket.com/events?slug={slug}"
    return curl(url, {"Accept": "application/json"}, timeout=20)


def parsear_xtracker(html, user):
    """Extrae tweet_count del HTML de xtracker."""
    out = {"user": user, "fuente": "xtracker.polymarket.com"}
    # el patrón en la primera vista: "Sep 4 – Sep 11 150" (con guion largo –)
    m = re.search(r"Sep\s*4\s*[–\-—]\s*Sep\s*11\s+(\d+)", html)
    if m:
        out["tweet_count"] = int(m.group(1))
        return out
    # fallback: en página de detalle, "Sep 4, 2026 → Sep 11, 2026" seguido de "150"
    m = re.search(r"Sep\s*4,\s*2026\s*[→\->]+\s*Sep\s*11,\s*2026.*?(\d+)\s*posts", html, re.S | re.I)
    if m:
        out["tweet_count"] = int(m.group(1))
        return out
    # fallback genérico: buscar "September 4 - September 11, 2026" y un número cercano
    idx = html.find("September 4 - September 11, 2026")
    if idx >= 0:
        fragmento = html[idx:idx+500]
        m = re.search(r"(\d{2,4})", fragmento)
        if m:
            n = int(m.group(1))
            if 50 < n < 500:  # rango plausible
                out["tweet_count"] = n
                return out
    return out


def parsear_pm(html, user):
    """Extrae tweet_count de la página del mercado en polymarket.com.

    Estructura HTML observada:
      <span>TWEET COUNT</span>...<span class="text-2xl">152</span>
    Donde "TWEET COUNT" y el número están en <span> separados.
    """
    out = {"user": user, "fuente": "polymarket.com"}
    # buscar la posición de "TWEET COUNT" y leer el primer número cercano
    idx = html.find("TWEET COUNT")
    if idx < 0:
        idx = html.find("TWEET_COUNT")
    if idx < 0:
        return out
    # leer 800 chars después para encontrar el número
    fragmento = html[idx:idx+800]
    # buscar el primer número plausible (entre 50 y 500) en un span
    m = re.search(r">(\d{2,4})<", fragmento)
    if m:
        n = int(m.group(1))
        if 50 < n < 500:
            out["tweet_count"] = n
            return out
    return out


def parsear_gamma(json_str, user):
    """Extrae precios/bin de la API gamma. No tiene TWEET_COUNT."""
    out = {"user": user, "fuente": "gamma-api.polymarket.com"}
    try:
        d = json.loads(json_str)
    except Exception as e:
        out["error"] = f"JSON parse falló: {e}"
        return out
    if not d:
        out["error"] = "API devolvió []"
        return out
    bins = {}
    for m in d[0].get("markets", []):
        m_sl = m.get("slug", "")
        m_match = re.search(r"-(\d+)-(\d+)$", m_sl)
        if not m_match:
            m_match = re.search(r"-(\d+)$", m_sl)
        if not m_match:
            continue
        lo, hi = int(m_match.group(1)), int(m_match.group(2)) if m_match.lastindex == 2 else int(m_match.group(1))
        prices = m.get("outcomePrices", "[]")
        if isinstance(prices, str):
            try:
                prices = json.loads(prices)
            except Exception:
                continue
        if not prices:
            continue
        bins[f"{lo}-{hi}" if m_match.lastindex == 2 else f"{lo}+"] = float(prices[0])
    out["bins"] = bins
    return out


def guardar_csv_y_oficial(out, hoy):
    """Si hay tweet_count, actualiza CSV (día=hoy) y polymarket_oficial.json."""
    if "tweet_count" not in out:
        print("[AVISO] no hay tweet_count, no se actualiza CSV")
        return
    filas = {}
    if os.path.exists(CSV):
        with open(CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                filas[r["fecha"]] = int(r["tweets"])
    filas[hoy.isoformat()] = out["tweet_count"]
    if os.path.exists(CSV):
        with open(CSV, "rb") as src, open(CSV + ".bak", "wb") as dst:
            dst.write(src.read())
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "tweets"])
        for f_ in sorted(filas):
            w.writerow([f_, filas[f_]])
    oficial = {
        "fuente": out.get("fuente"),
        "user": out.get("user"),
        "tweet_count_oficial": out["tweet_count"],
        "scrapeado_en": datetime.now(ET).isoformat(),
    }
    if "bins" in out:
        oficial["bins"] = out["bins"]
    with open("polymarket_oficial.json", "w", encoding="utf-8") as f:
        json.dump(oficial, f, indent=2, ensure_ascii=False)
    print(f"[OK] CSV: {hoy} = {out['tweet_count']} tweets")
    print(f"[OK] polymarket_oficial.json guardado ({out.get('fuente')})")


def actualizar_csv_desde_fuente(user="elonmusk", slug="elon-musk-of-tweets-september-4-september-11-2026", verbose=True):
    """Función 'main' simplificada que devuelve el tweet_count y actualiza
    el CSV. Usada por bot.py (in-process, evita subprocess + curl -k).

    Returns: int o None
    """
    out = None
    # 1) xtracker
    try:
        html = fetch_xtracker_direct(user)
        if "September 4" in html and "September 11" in html:
            out = parsear_xtracker(html, user)
            if verbose and "tweet_count" in out:
                print(f"  [OK] xtracker: tweet_count = {out['tweet_count']}")
    except Exception as e:
        if verbose:
            print(f"  [ERROR] xtracker: {e}")
    # 2) polymarket.com
    if not out or "tweet_count" not in out:
        try:
            html = fetch_pm_direct(slug)
            if "TWEET COUNT" in html or "TWEET_COUNT" in html:
                out2 = parsear_pm(html, user)
                if "tweet_count" in out2:
                    if out is None:
                        out = out2
                    else:
                        out.update(out2)
                    if verbose:
                        print(f"  [OK] polymarket.com: tweet_count = {out2['tweet_count']}")
        except Exception as e:
            if verbose:
                print(f"  [ERROR] polymarket.com: {e}")
    # 3) gamma (bins, no tweet_count)
    if out is None:
        out = {}
    try:
        js = fetch_gamma(slug)
        out3 = parsear_gamma(js, user)
        if "bins" in out3 and out3["bins"]:
            out["bins"] = out3["bins"]
    except Exception:
        pass
    if "tweet_count" not in out:
        return None
    # SIEMPRE guardar oficial.json (incluso si no se actualiza CSV)
    oficial = {
        "fuente": out.get("fuente"),
        "user": out.get("user"),
        "tweet_count_oficial": out["tweet_count"],
        "scrapeado_en": datetime.now(ET).isoformat(),
    }
    if "bins" in out:
        oficial["bins"] = out["bins"]
    try:
        with open("polymarket_oficial.json", "w", encoding="utf-8") as f:
            json.dump(oficial, f, indent=2, ensure_ascii=False)
        print(f"  [OK] polymarket_oficial.json guardado ({out.get('fuente')})")
    except Exception as e:
        print(f"  [ERROR] no se pudo guardar oficial.json: {e}")
    hoy = datetime.now(ET).date()
    guardar_csv_y_oficial(out, hoy)
    return out["tweet_count"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="elonmusk")
    ap.add_argument("--slug", default="elon-musk-of-tweets-september-4-september-11-2026")
    ap.add_argument("--actualizar-csv", action="store_true")
    ap.add_argument("--debug-html", action="store_true")
    ap.add_argument("--silent", action="store_true",
                    help="modo silencioso: solo imprime TWEET_COUNT=N (para bot.py)")
    args = ap.parse_args()

    out = None

    # 1) xtracker directo
    print("[1/3] Probando xtracker.polymarket.com directo...")
    try:
        html = fetch_xtracker_direct(args.user)
        if args.debug_html:
            with open("/tmp/pm_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            print(f"  HTML guardado: {len(html)} bytes")
        if "September 4" in html and "September 11" in html:
            out = parsear_xtracker(html, args.user)
            if "tweet_count" in out:
                print(f"  [OK] xtracker: tweet_count = {out['tweet_count']}")
    except Exception as e:
        print(f"  [ERROR] xtracker: {e}")

    # 2) polymarket.com directo (si xtracker no dio tweet_count)
    if not out or "tweet_count" not in out:
        print("[2/3] Probando polymarket.com directo...")
        try:
            html = fetch_pm_direct(args.slug)
            if args.debug_html:
                with open("/tmp/pm_debug.html", "w", encoding="utf-8") as f:
                    f.write(html)
                print(f"  HTML guardado: {len(html)} bytes")
            if "TWEET COUNT" in html or "TWEET_COUNT" in html:
                out2 = parsear_pm(html, args.user)
                if "tweet_count" in out2:
                    if out is None:
                        out = out2
                    else:
                        out.update(out2)
                    print(f"  [OK] polymarket.com: tweet_count = {out2['tweet_count']}")
        except Exception as e:
            print(f"  [ERROR] polymarket.com: {e}")

    # 3) gamma API (siempre, para bins)
    print("[3/3] Probando gamma-api.polymarket.com...")
    try:
        js = fetch_gamma(args.slug)
        out3 = parsear_gamma(js, args.user)
        if "bins" in out3 and out3["bins"]:
            if out is None:
                out = out3
            else:
                out["bins"] = out3["bins"]
            print(f"  [OK] gamma: {len(out3['bins'])} bins")
        elif "error" in out3:
            print(f"  [INFO] gamma: {out3['error']}")
    except Exception as e:
        print(f"  [ERROR] gamma: {e}")

    if out is None:
        out = {}
    # modo --silent-para-bot: solo imprime el TWEET_COUNT (sin logs ni JSON)
    if args.silent:
        if "tweet_count" in out:
            print(f"TWEET_COUNT={out['tweet_count']}")
        else:
            print("TWEET_COUNT=NONE")
        return
    print("\n=== RESULTADO ===")
    print(json.dumps(out, indent=2, ensure_ascii=False))

    if args.actualizar_csv:
        hoy = datetime.now(ET).date()
        guardar_csv_y_oficial(out, hoy)


if __name__ == "__main__":
    main()
