#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mercado_ultima_oportunidad.py — busca apuestas en ventanas que están
a punto de cerrar (6-24h restantes).

Concepto: en las últimas horas de una ventana, el TWEET_COUNT está
casiestable. Si nuestro modelo dice P(bin X) ≥ 0.6 y Polymarket da
P(bin X) ≤ 0.35 con cuota ≥ 2.5, hay valor.

USO:
  python3 mercado_ultima_oportunidad.py --user elonmusk
  python3 mercado_ultima_oportunidad.py --user elonmusk --dry-run
  python3 mercado_ultima_oportunidad.py --user realDonaldTrump
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

try:
    ET = ZoneInfo("America/New_York")
except Exception:
    from datetime import timezone, timedelta
    ET = timezone(timedelta(hours=-4), name="EDT")

# reglas (configurables)
VENTANA_MIN_HORAS = 3.0       # mínimo de horas restantes para operar
VENTANA_MAX_HORAS = 24.0      # máximo de horas restantes
EDGE_MIN = 0.20               # diferencia mínima entre modelo y Polymarket
CUOTA_MIN = 2.5               # cuota mínima de Polymarket
P_MODELO_MIN = 0.55           # P(bin) mínima según nuestro modelo
P_POLY_MAX = 0.35             # P(bin) máxima en Polymarket (si es más, no hay valor)
STAKE_PCT_BANKROLL = 0.02     # 2% del bankroll por apuesta
STAKE_MIN = 5.0               # mínimo $5 (apuesta mínima de Polymarket)


def ahora_et():
    return datetime.now(ET)


def parsear_fin_mercado(m):
    """Devuelve la hora de cierre del mercado en ET (datetime) o None."""
    fin = m.get("fin") or m.get("cierre") or m.get("endDate")
    if not fin:
        return None
    if isinstance(fin, str):
        # formatos posibles: ISO 8601
        try:
            if fin.endswith("Z"):
                dt = datetime.fromisoformat(fin.replace("Z", "+00:00"))
            else:
                dt = datetime.fromisoformat(fin)
            return dt.astimezone(ET) if dt.tzinfo else dt.replace(tzinfo=ET)
        except Exception:
            return None
    return fin


def modelos_prediccion(user, tweet_count_actual, avg7, lam48):
    """Distribución Poisson alrededor del TWEET_COUNT actual, con
    incertidumbre por el promedio histórico.

    Para una ventana que está por cerrar (8h restantes), la
    variabilidad de los tweets restantes es baja. Asumimos que
    el TWEET_COUNT final estará en [actual-10, actual+5].
    """
    # distribución uniforme entre [actual-10, actual+5]
    # (Elon puede twittear 0-5 tweets en las próximas 8h)
    lo = max(0, tweet_count_actual - 10)
    hi = tweet_count_actual + 5
    # P(N=k) uniforme discreta
    n_puntos = hi - lo + 1
    p_uniforme = 1.0 / n_puntos if n_puntos > 0 else 0
    return lo, hi, p_uniforme


def p_modelo_para_bin(tweet_count, lo, hi, p_uniforme, bin_lo, bin_hi):
    """P(TWEET_COUNT final ∈ [bin_lo, bin_hi]) según el modelo uniforme."""
    p = 0
    for k in range(lo, hi + 1):
        if bin_lo <= k <= bin_hi:
            p += p_uniforme
    return p


def evaluar_mercado(m, user, polymarket_oficial, avg7, lam48):
    """Evalúa un mercado. Devuelve dict con {apuesta: dict|None, info: dict}."""
    ahora = ahora_et()
    fin = parsear_fin_mercado(m)
    if fin is None:
        return {"info": {"error": "no se pudo parsear cierre"}, "apuesta": None}
    horas_rest = (fin - ahora).total_seconds() / 3600
    if horas_rest < VENTANA_MIN_HORAS or horas_rest > VENTANA_MAX_HORAS:
        return {"info": {"horas_rest": round(horas_rest, 1), "fuera_de_ventana": True}, "apuesta": None}
    titulo = m.get("titulo", "")
    # user puede ser "elonmusk" (sin espacio) y el título es "Elon Musk"
    # buscar tanto el user completo como el "first name" del user
    user_match = user.lower() in titulo.lower() or user.lower().split("@")[0][:5] in titulo.lower()
    if not user_match:
        return {"info": {"no_coincide_user": True, "user": user, "titulo": titulo}, "apuesta": None}
    # buscar TWEET_COUNT oficial de este user
    tc_oficial = polymarket_oficial.get(user, {}).get("tweet_count")
    if not tc_oficial:
        return {"info": {"no_tc_oficial": True}, "apuesta": None}
    # calcular predicción
    lo, hi, p_uniforme = modelos_prediccion(user, tc_oficial, avg7, lam48)
    mejor = None
    for b in m.get("bins", []):
        bin_titulo = b.get("titulo", "")
        bin_lo, bin_hi = parsear_bin(bin_titulo)
        if bin_lo is None:
            continue
        p_poly = b.get("precio_yes", 0)
        if p_poly < 0.005:  # long-shot absoluto
            continue
        if p_poly > P_POLY_MAX:
            continue  # polymarket ya da mucha prob, no hay valor
        cuota = 1 / p_poly if p_poly > 0 else float("inf")
        if cuota < CUOTA_MIN:
            continue
        p_mod = p_modelo_para_bin(tc_oficial, lo, hi, p_uniforme, bin_lo, bin_hi)
        if p_mod < P_MODELO_MIN:
            continue
        edge = p_mod - p_poly
        if edge < EDGE_MIN:
            continue
        ev = p_mod * cuota - 1
        if mejor is None or edge > mejor["edge"]:
            mejor = {
                "bin_titulo": bin_titulo,
                "bin_lo": bin_lo,
                "bin_hi": bin_hi,
                "p_modelo": round(p_mod, 3),
                "p_polymarket": round(p_poly, 3),
                "cuota": round(cuota, 2),
                "edge": round(edge, 3),
                "ev": round(ev, 3),
                "horas_rest": round(horas_rest, 1),
            }
    if mejor is None:
        return {"info": {"horas_rest": round(horas_rest, 1), "tc_oficial": tc_oficial,
                          "lo": lo, "hi": hi, "no_apuesta_valida": True}, "apuesta": None}
    return {"info": {"horas_rest": round(horas_rest, 1), "tc_oficial": tc_oficial,
                     "lo": lo, "hi": hi},
            "apuesta": mejor}


def parsear_bin(titulo):
    """Extrae (lo, hi) de un título tipo '40-64' o '<20' o '500+'."""
    import re
    if "<" in titulo:
        m = re.search(r"<(\d+)", titulo)
        if m:
            return 0, int(m.group(1))
    if "+" in titulo:
        m = re.search(r"(\d+)\+", titulo)
        if m:
            return int(m.group(1)), 9999
    m = re.match(r"(\d+)-(\d+)", titulo)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


def cargar_polymarket_oficial():
    """Carga tweet_count de polymarket_oficial.json o .disabled."""
    for fname in ("polymarket_oficial.json", "polymarket_oficial.json.disabled"):
        if os.path.exists(fname):
            try:
                d = json.load(open(fname))
                return {d.get("user", "elonmusk"): d}
            except Exception:
                pass
    return {}


def cargar_mercados(user):
    """Carga mercados de Elon del mercado_activo.json."""
    if not os.path.exists("mercado_activo.json"):
        return []
    try:
        d = json.load(open("mercado_activo.json"))
        ms = d.get("mercados", [])
        # user "elonmusk" debe matchear con "Elon Musk" en el título
        user_first = user.lower().split("@")[0][:5]  # "elonm"
        out = []
        for m in ms:
            if m.get("cerrado"):
                continue
            titulo_low = m.get("titulo", "").lower()
            if user.lower() in titulo_low or user_first in titulo_low:
                out.append(m)
        return out
    except Exception:
        return []


def cargar_metricas_csv():
    """Lee el CSV y calcula AVG7, V2, lam48."""
    import csv
    if not os.path.exists("datos_elon.csv"):
        return None
    with open("datos_elon.csv") as f:
        filas = [(r["fecha"], int(r["tweets"])) for r in csv.DictReader(f)]
    if len(filas) < 9:
        return None
    ult7 = [n for _, n in filas[-7:]]
    ult2 = [n for _, n in filas[-2:]]
    avg7 = sum(ult7) / 7
    v2 = sum(ult2)
    r = v2 / (2 * avg7)
    aj = min(1.5, max(0.5, 1 + 0.5 * (r - 1)))
    lam = 2 * avg7 * aj
    return {"avg7": avg7, "v2": v2, "r": r, "ajuste": aj, "lam48": lam}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="elonmusk")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--bankroll", type=float, default=500.0)
    args = ap.parse_args()

    mercados = cargar_mercados(args.user)
    oficial = cargar_polymarket_oficial()
    metricas = cargar_metricas_csv()
    if metricas is None:
        print("[ERROR] no se pudo cargar métricas del CSV")
        return 1

    print(f"=== MERCADO ÚLTIMAS OPORTUNIDADES — {args.user} ===")
    print(f"  AVG7={metricas['avg7']:.2f}  V2={metricas['v2']}  λ48={metricas['lam48']:.1f}")
    print(f"  TWEET_COUNT oficial: {oficial.get(args.user, {}).get('tweet_count', 'N/A')}")
    print(f"  Mercados activos de {args.user}: {len(mercados)}")
    print()
    for m in mercados:
        titulo = m.get("titulo", "")
        r = evaluar_mercado(m, args.user, oficial, metricas["avg7"], metricas["lam48"])
        info = r["info"]
        horas = info.get("horas_rest", "?")
        if info.get("fuera_de_ventana"):
            print(f"  [FUERA] {titulo[:60]} (rest: {horas}h)")
            continue
        if info.get("no_tc_oficial"):
            print(f"  [NO TC] {titulo[:60]}")
            continue
        if info.get("no_apuesta_valida"):
            print(f"  [N/A]  {titulo[:60]} (rest: {horas}h, tc: {info.get('tc_oficial')}, lo-hi: {info.get('lo')}-{info.get('hi')})")
            continue
        a = r["apuesta"]
        if a is None:
            print(f"  [-]    {titulo[:60]}")
            continue
        stake = max(STAKE_MIN, args.bankroll * STAKE_PCT_BANKROLL)
        ev_dolares = stake * a["ev"]
        print(f"  [VAL]  {titulo[:60]}")
        print(f"        bin: {a['bin_titulo']} ({a['bin_lo']}-{a['bin_hi']})")
        print(f"        P_modelo={a['p_modelo']:.2f}  P_poly={a['p_polymarket']:.3f}  cuota={a['cuota']}")
        print(f"        edge={a['edge']:.2f}  EV={a['ev']:.2f}")
        print(f"        stake=${stake:.2f}  EV_$={ev_dolares:+.2f}")
        if not args.dry_run:
            print(f"        >>> LLAMAR A operar_real.pasada_real() CON:")
            print(f"            bin='{a['bin_titulo']}'  lado='YES'  stake=${stake:.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
