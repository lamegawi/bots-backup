#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
volcar_estado_a_csv.py — vuelca el estado_tweets.json al CSV incluyendo
el día en curso (que `actualizar_csv()` descarta por diseño).

Uso:
  python3 volcar_estado_a_csv.py            # vuelca
  python3 volcar_estado_a_csv.py --dry-run  # solo muestra lo que haría
  python3 volcar_estado_a_csv.py --periodo 2026-09-04 2026-09-11  # ventana

Política:
  - Toma `created_at` para posts y reposts con timestamp EXACTO (jina).
  - Para reposts SIN timestamp exacto (espejos Nitter), usa `primera_vista`.
  - Atribuye cada item a su día ET.
  - Sobrescribe el CSV con los conteos recalculados (NO monotónico aquí:
    la fuente es la misma que la original, no es un scrape parcial).
  - Hace backup del CSV previo a `datos_elon.csv.bak`.
"""
import argparse
import csv
import json
import os
import sys
from datetime import datetime, date
from zoneinfo import ZoneInfo

try:
    ET = ZoneInfo("America/New_York")
except Exception:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-4), name="EDT")

CSV = "datos_elon.csv"
ESTADO = "estado_tweets.json"
T_FMT = "%a %b %d %H:%M:%S +0000 %Y"


def cargar():
    if not os.path.exists(ESTADO):
        sys.exit(f"No existe {ESTADO}")
    d = json.load(open(ESTADO, encoding="utf-8"))
    return d.get("tweets", {})


def volcar(tweets, periodo_ini=None, periodo_fin=None, dry=False):
    dias = {}
    for sid, v in tweets.items():
        if v.get("kind") == "repost" and not v.get("exacto"):
            base = v.get("primera_vista", v.get("created_at", ""))
        else:
            base = v.get("created_at", "")
        try:
            f = datetime.strptime(base, T_FMT).astimezone(ET).date()
        except Exception:
            continue
        if periodo_ini and f < periodo_ini:
            continue
        if periodo_fin and f > periodo_fin:
            continue
        dias[f] = dias.get(f, 0) + 1
    filas_viejas = {}
    if os.path.exists(CSV):
        with open(CSV, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                filas_viejas[r["fecha"]] = int(r["tweets"])
    filas_nuevas = dict(filas_viejas)
    for f, n in dias.items():
        filas_nuevas[f.isoformat()] = n
    print(f"Días en estado: {len(dias)}")
    print(f"Días en CSV previo: {len(filas_viejas)}")
    print(f"Días en CSV nuevo:  {len(filas_nuevas)}")
    hoy = datetime.now(ET).date()
    print(f"\nVentana {periodo_ini} → {periodo_fin}:")
    for f in sorted(dias):
        if periodo_ini and f < periodo_ini:
            continue
        if periodo_fin and f > periodo_fin:
            continue
        marca = "  ← HOY (incompleto)" if f == hoy else ""
        viejo = filas_viejas.get(f.isoformat(), "-")
        delta = (f"[{dias[f] - viejo:+d}]" if viejo != "-" else "[nuevo]")
        print(f"  {f}  estado={dias[f]:>3}  csv_previo={viejo:>3}  {delta}{marca}")
    total = sum(dias[f] for f in dias
                if (not periodo_ini or f >= periodo_ini)
                and (not periodo_fin or f <= periodo_fin))
    print(f"\nTOTAL en ventana: {total}")
    if dry:
        print("\n[DRY-RUN] CSV no modificado.")
        return
    if os.path.exists(CSV):
        bak = CSV + ".bak"
        with open(CSV, "rb") as src, open(bak, "wb") as dst:
            dst.write(src.read())
        print(f"\nBackup: {bak}")
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "tweets"])
        for f_ in sorted(filas_nuevas):
            w.writerow([f_, filas_nuevas[f_]])
    print(f"CSV actualizado: {CSV} ({len(filas_nuevas)} filas)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--periodo", nargs=2, metavar=("INI", "FIN"))
    args = ap.parse_args()
    ini = fin = None
    if args.periodo:
        ini = date.fromisoformat(args.periodo[0])
        fin = date.fromisoformat(args.periodo[1])
    tweets = cargar()
    print(f"Estado: {len(tweets)} items\n")
    volcar(tweets, ini, fin, dry=args.dry_run)
