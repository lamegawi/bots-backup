#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SEÑAL EN VIVO — integra los datos de tweets + los precios de Polymarket
=======================================================================
Flujo completo y automático:
  1) (opcional) refresca los datos de tweets (recoger_tweets.py --fuente jina)
  2) calcula AVG7 / V2 / R / λ48 desde datos_elon.csv (o usa overrides)
  3) descarga (o carga) los mercados activos de Polymarket y sus bins
  4) calcula p_modelo (Poisson) para cada bin, aplica las reglas R1-R7
     y da el veredicto: APOSTAR YES / APOSTAR NO / PASAR + stake del ciclo

USO:
  python3 senal_vivo.py                     # señal con datos actuales
  python3 senal_vivo.py --actualizar        # + refrescar precios Polymarket
  python3 senal_vivo.py --recoger           # + refrescar tweets
  python3 senal_vivo.py --paso 2            # paso actual del ciclo (stake)
  python3 senal_vivo.py --avg7 27 --v2 50   # override (pruebas / datos de
                                            # referencia de la semana resuelta)
"""
import argparse
import json
import math
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import senal
import mercado_polymarket as mp


# ============================================================
# MOTOR DE TRADING (versión) — tamaño por ventaja (escalones + tope)
# ============================================================
MOTOR_ACTUAL = "motor_v2_ev_escalones_tope10"
EV_MIN_ENTRADA = 1.8   # EV mínimo para entrar (filtro extra en semanal/mensual)
EV_MAX_TOPE = 10.0     # tope duro de stake por apuesta (€)


def stake_motor_v2(stake_base, p_lado, cuota):
    """Tamaño según la ventaja. Devuelve None si no se debe entrar.

    EV = p_lado × cuota (probabilidad del lado elegido × su cuota).
      EV < 1.8        -> no entrar
      1.8 ≤ EV < 2.5  -> stake base (×1)
      2.5 ≤ EV < 4.0  -> ×1.5
      EV ≥ 4.0        -> ×2.0
    Siempre limitado a EV_MAX_TOPE €."""
    if not cuota or cuota <= 0:
        return None
    ev = p_lado * cuota
    EPS = 1e-9  # tolerancia de coma flotante (0.6×3.0 = 1.7999…)
    if ev < EV_MIN_ENTRADA - EPS:
        return None
    if ev >= 4.0 - EPS:
        mult = 2.0
    elif ev >= 2.5 - EPS:
        mult = 1.5
    else:
        mult = 1.0
    return round(min(stake_base * mult, EV_MAX_TOPE), 2)

try:
    ET = ZoneInfo("America/New_York")
except Exception:
    # Windows sin tzdata: fallback a hora fija de verano (UTC-4)
    from datetime import timedelta
    from datetime import timezone as _tz
    ET = _tz(timedelta(hours=-4), name="EDT")
T_FMT = "%a %b %d %H:%M:%S +0000 %Y"

# Entrada solo al INICIO de cada ventana (evita bins ya casi decididos y
# minimiza el error de t0 cuando ya hay muchos tweets publicados).
ENTRADA_MAX_H = {"48h": 12.0, "semanal": 24.0, "mensual": 72.0}


def conteo_ventana(inicio_utc, ahora_utc):
    """T0 = tweets dentro de la ventana del mercado (posts + reposts + quotes).

    Estrategia robusta:
      · días COMPLETOS estrictamente dentro de la ventana → datos_elon.csv
        (el CSV solo guarda días terminados)
      · día de inicio y día actual (parciales) → estado_tweets.json con
        timestamps exactos, SIN saltar reposts (la regla del mercado cuenta
        posts + quote posts + reposts).
    Devuelve (n, total_estado)."""
    try:
        estado = json.load(open("estado_tweets.json", encoding="utf-8")).get("tweets", {})
    except Exception:
        estado = {}
    total = len(estado)
    ahora_et = ahora_utc.astimezone(ET)
    inicio_et = inicio_utc.astimezone(ET)
    hoy = ahora_et.date()
    d_inicio = inicio_et.date()
    incluye_dia_inicio = (inicio_et.hour == 0 and inicio_et.minute == 0)
    n = 0
    # ---- días completos dentro de la ventana (datos_elon.csv) ----
    try:
        import csv as _csv
        with open("datos_elon.csv", newline="", encoding="utf-8") as f:
            for fila in _csv.DictReader(f):
                try:
                    d = datetime.strptime(fila["fecha"].strip(), "%Y-%m-%d").date()
                except Exception:
                    continue
                if d >= hoy:
                    continue
                if d > d_inicio or (incluye_dia_inicio and d == d_inicio):
                    try:
                        n += int(float(fila["tweets"]))
                    except Exception:
                        pass
    except Exception:
        pass
    # ---- día de inicio y día actual (parciales), contando TODOS los tipos ----
    for v in estado.values():
        try:
            ts = datetime.strptime(v["created_at"], T_FMT).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        d_ts = ts.astimezone(ET).date()
        if d_ts not in (d_inicio, hoy):
            continue
        if d_ts == d_inicio and incluye_dia_inicio:
            continue  # ese día ya se contó completo vía CSV
        if inicio_utc <= ts <= ahora_utc:
            n += 1
    return n, total


def evaluar(avg7, v2, ajuste, lam48, mercados, paso, t0_override=-1, ahora=None):
    """Evalúa todos los mercados abiertos y devuelve (evaluados, candidatas).
    - evaluados: lista de dicts {titulo, tipo, inicio, fin, horas_rest,
      lam_rest, t0, bins:[{titulo, lo, hi, precio_yes, cuota_yes, cuota_no,
      p_modelo, veredicto}]}
    - candidatas: lista de dicts {mercado, bin, lado, precio, cuota, p_modelo}
      que cumplen las reglas R3+R4 (para abrir apuesta de papel)."""
    ahora = ahora or datetime.now(timezone.utc)
    tabla = senal.tabla_apuestas()
    _, stake_base, _, _ = tabla[paso - 1] if 1 <= paso <= len(tabla) else tabla[0]
    evaluados, candidatas = [], []
    for mk in mercados:
        if mk["cerrado"] or not mk.get("inicio_iso"):
            continue
        inicio = datetime.fromisoformat(mk["inicio_iso"]).astimezone(timezone.utc)
        fin = datetime.fromisoformat(mk["fin_iso"]).astimezone(timezone.utc)
        if ahora < inicio or ahora > fin:
            continue
        horas_rest = (fin - ahora).total_seconds() / 3600
        horas_elapsed = (ahora - inicio).total_seconds() / 3600
        if horas_elapsed > ENTRADA_MAX_H.get(mk["tipo"], 12.0):
            continue  # entrada solo al inicio de la ventana
        if mk["tipo"] == "48h":
            lam_rest = lam48 * max(0.0, horas_rest) / 48.0
        elif mk["tipo"] == "semanal":
            lam_rest = 7 * avg7 * ajuste * max(0.0, horas_rest) / 168.0
        else:
            lam_rest = lam48 * max(0.0, horas_rest) / 48.0
        t0_auto, total_estado = conteo_ventana(inicio, ahora)
        t0 = t0_override if t0_override >= 0 else t0_auto
        bins = []
        for b in mk["bins"]:
            hi = b["hi"] if b["hi"] != float("inf") else math.inf
            # Guarda: bin ya decidido por los tweets publicados (t0).
            #   hi finito y t0 > hi  -> [lo,hi] superado: YES imposible, NO ya decidido
            #   hi = inf  y t0 >= lo -> "≥ lo" ya cumplido: YES ya decidido
            decidido = (t0 > hi) if hi != math.inf else (t0 >= b["lo"])
            if decidido:
                p = 1.0 if hi == math.inf else 0.0
                bins.append({"titulo": b["titulo"], "lo": b["lo"], "hi": b["hi"],
                             "precio_yes": b["precio_yes"], "cuota_yes": b["cuota_yes"],
                             "cuota_no": b["cuota_no"], "p_modelo": p,
                             "veredicto": "PASAR"})
                continue
            p = senal.p_bin(b["lo"] - t0, (hi - t0) if hi != math.inf else math.inf, lam_rest)
            cy, cn = b["cuota_yes"], b["cuota_no"]
            veredicto, lado = "PASAR", None
            if p >= senal.P_MIN_YES and cy and cy >= senal.CUOTA_MINIMA:
                veredicto, lado = "APOSTAR YES", "YES"
            elif p <= senal.P_MAX_NO and cn and cn >= senal.CUOTA_MINIMA:
                veredicto, lado = "APOSTAR NO", "NO"
            bins.append({"titulo": b["titulo"], "lo": b["lo"], "hi": b["hi"],
                         "precio_yes": b["precio_yes"], "cuota_yes": cy,
                         "cuota_no": cn, "p_modelo": p, "veredicto": veredicto})
            if lado:
                cuota_lado = (cy if lado == "YES" else cn)
                p_lado = p if lado == "YES" else (1.0 - p)
                ev = round(p_lado * (cuota_lado or 0), 3)
                stake = stake_motor_v2(stake_base, p_lado, cuota_lado)
                if stake is None:
                    continue  # EV por debajo del mínimo: no entrar
                # Filtro de seguridad (arena 2026-09-04): no apostar si la
                # probabilidad efectiva del lado es < 10% (caso típico: bot
                # cree p=77% en bin "<40" pero mercado cuota 19.6 = 5% real).
                # Sin este filtro, el bot mete apuestas "suicidas" con EV
                # inflado por p_modelo descalibrado.
                if p_lado < 0.10:
                    log(f"  · [FILTRO] descartado {b.get('titulo', '?')} {lado} "
                        f"p_lado={p_lado:.0%} (cuota {cuota_lado:.2f})")
                    continue
                # Filtro de cuota máxima: no apostar en mercados con
                # cuota > 25 (improbables de ganar aunque el bot crea).
                if cuota_lado and cuota_lado > 25:
                    log(f"  · [FILTRO] descartado {b.get('titulo', '?')} {lado} "
                        f"cuota={cuota_lado:.2f} (>25, demasiado improbable)")
                    continue
                candidatas.append({"mercado": mk["titulo"], "slug": mk["slug"],
                                   "ventana": (inicio, fin), "tipo": mk["tipo"],
                                   "bin_titulo": b["titulo"], "lo": b["lo"], "hi": b["hi"],
                                   "lado": lado, "precio": (b["precio_yes"] if lado == "YES" else 1 - b["precio_yes"]),
                                   "cuota": cuota_lado, "p_modelo": p,
                                   "stake": stake, "ev": ev, "motor": MOTOR_ACTUAL})
        evaluados.append({"titulo": mk["titulo"], "slug": mk.get("slug", ""), "tipo": mk["tipo"],
                          "inicio": inicio, "fin": fin, "horas_rest": horas_rest,
                          "lam_rest": lam_rest, "t0": t0, "bins": bins})
    return evaluados, candidatas


def main():
    ap = argparse.ArgumentParser(description="Señal en vivo Polymarket · @elonmusk")
    ap.add_argument("--csv", default="datos_elon.csv", help="CSV de tweets (por defecto datos_elon.csv)")
    ap.add_argument("--actualizar", action="store_true", help="refrescar precios de Polymarket")
    ap.add_argument("--recoger", action="store_true", help="refrescar datos de tweets primero")
    ap.add_argument("--paso", type=int, default=1, help="paso actual del ciclo (1-7)")
    ap.add_argument("--avg7", type=float, default=None, help="override AVG7 (pruebas)")
    ap.add_argument("--v2", type=float, default=None, help="override V2 (pruebas)")
    ap.add_argument("--t0", type=int, default=-1, help="override tweets ya publicados en la ventana (-1 = automático)")
    ap.add_argument("--sin-reposts", action="store_true", help="excluir reposts")
    args = ap.parse_args()

    # ---------------------------------------------------------- 1) tweets
    if args.recoger:
        print("[1/4] Refrescando datos de tweets…")
        subprocess.run([sys.executable, "recoger_tweets.py", "--fuente", "jina"], check=False)

    # ---------------------------------------------------------- 2) métricas
    print("[2/4] Métricas de actividad…")
    if args.avg7 is not None and args.v2 is not None:
        avg7, v2 = args.avg7, args.v2
        r = v2 / (2 * avg7) if avg7 > 0 else float("nan")
        ajuste = senal.clamp(1 + 0.5 * (r - 1), 0.5, 1.5)
        lam48 = 2 * avg7 * ajuste
        origen = f"OVERRIDE (--avg7 {avg7} --v2 {v2})"
    else:
        try:
            datos = senal.cargar_csv(args.csv)
        except SystemExit as e:
            print(f"  ERROR: {e}")
            print("  Usa --avg7 X --v2 Y con datos de referencia (p. ej. del último")
            print("  mercado semanal resuelto) o espera a tener ≥ 9 días de datos.")
            return
        m = senal.metricas(datos)
        avg7, v2, r, ajuste, lam48 = m["avg7"], m["v2"], m["r"], m["ajuste"], m["lam48"]
        origen = f"datos propios ({len(datos)} días)"
    print(f"  AVG7 = {avg7:.2f} · V2 = {v2} · R = {r:.3f} · ajuste = {ajuste:.3f} · "
          f"λ48 = {lam48:.1f}   [{origen}]")

    # ---------------------------------------------------------- 3) mercado
    print("[3/4] Mercados Polymarket…")
    if args.actualizar:
        try:
            mp.actualizar_mercado()
            print("  precios actualizados ✓")
        except Exception as e:
            print(f"  [ERROR] no se pudo actualizar: {e}")
    try:
        mercados = json.load(open(mp.SALIDA, encoding="utf-8"))["mercados"]
    except Exception:
        print("  No hay mercado_activo.json. Ejecuta: python3 mercado_polymarket.py")
        return

    ahora = datetime.now(timezone.utc)
    tabla = senal.tabla_apuestas()
    _, stake, perd_acum, _ = tabla[args.paso - 1] if 1 <= args.paso <= len(tabla) else tabla[0]

    # ---------------------------------------------------------- 4) señal
    print("[4/4] Evaluación por bin…\n")
    evaluados, candidatas = evaluar(avg7, v2, ajuste, lam48, mercados, args.paso,
                                    t0_override=args.t0)
    for ev in evaluados:
        print(f"■ {ev['titulo']}  [{ev['tipo']}]")
        print(f"  ventana: {ev['inicio'].astimezone(ET).strftime('%m-%d %H:%M %Z')} → "
              f"{ev['fin'].astimezone(ET).strftime('%m-%d %H:%M %Z')}  ·  "
              f"ahora: {ahora.astimezone(ET).strftime('%m-%d %H:%M %Z')}")
        etiq = f"λ48={lam48:.1f}" if ev['tipo'] == "48h" else f"λ7={7*avg7*ajuste:.1f}"
        print(f"  {etiq} → λ restante={ev['lam_rest']:.1f} · horas restantes: {ev['horas_rest']:.1f} "
              f"· tweets ya en ventana (T0): {ev['t0']}")
        print(f"  {'bin':<10}{'p_modelo':>10}{'precio':>9}{'cuotaY':>8}{'cuotaN':>8}   veredicto")
        for b in ev["bins"]:
            cy = ("{:.2f}".format(b['cuota_yes']) if b['cuota_yes'] else '—')
            cn = ("{:.2f}".format(b['cuota_no']) if b['cuota_no'] else '—')
            print("  {:<10}{:>10.1%}{:>9.3f}{:>8}{:>8}   {}".format(
                b['titulo'], b['p_modelo'], b['precio_yes'], cy, cn, b['veredicto']))
        print()
    if not candidatas:
        print("► VEREDICTO GLOBAL: PASAR — ningún bin cumple (p_modelo ≥ 60% o ≤ 30%) "
              "con cuota ≥ 3.00.")
        print("  La regla es no apostar: la paciencia es parte de la estrategia.")
    else:
        print("► VEREDICTO GLOBAL: hay apuesta candidata (ver tabla). Recuerda:")
        print("  - una sola apuesta activa (espera a que la anterior se resuelva)")
        print(f"  - paso {args.paso} → stake ${stake:.2f} (pérdida acumulada si falla: ${perd_acum:.2f})")
        print("  - registra la operación en el Excel (hoja Registro)")


if __name__ == "__main__":
    main()
