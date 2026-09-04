#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOTOR DE SEÑAL — ventana SEMANAL «Trump # tweets <inicio> - <fin>?»
======================================================================
Reglas R1–R7 adaptadas a la ventana SEMANAL (7 días, bins de 20
en 20, cuotas altas en el centro). Metodología PROPIA de la ventana
mensual: tabla de apuestas suave (2.00 × 1.35, máx. 5 pasos) y regla
de VENTAJA RELATIVA (p_modelo ≥ precio + 12pp) porque las p_modelo
realistas en los bins centrales son 25-50% con cuotas 4-18 (la regla
absoluta p ≥ 60% de las ventanas de 48 h nunca dispararía aquí).

  R7  Progresión 3.00 × 1.40^(paso−1), reinicio a 3.00 tras ganar,
      máx. 6 pasos (pérdida máx. de ciclo ≈ $48.99).
"""
import argparse
import csv
import math
import sys
from datetime import date, datetime, timedelta

# ----------------------------------------------------------------------------
# Parámetros fijos de la estrategia (tabla PROPIA de la ventana mensual)
# ----------------------------------------------------------------------------
VENTANA        = "semanal"     # 48h | semanal | mensual
STAKE_INICIAL  = 3.00          # $, primera apuesta de cada ciclo
FACTOR         = 1.40          # multiplicador tras cada fallo
CUOTA_MINIMA   = 2.80          # cuota mínima aceptada
P_MIN_YES      = 0.60          # (solo regla ABSOLUTA; en ventaja no se usa)
P_MAX_NO       = 0.30          # (solo regla ABSOLUTA; en ventaja no se usa)
PASOS_MAX      = 6             # stop-loss del ciclo (paso máximo)
REGLA          = "ventaja"     # "absoluta" (48h) | "ventaja" (semanal/mensual)
EDGE_MIN       = 0.12          # ventaja mínima p_modelo − precio (12 pp)
P_FLOOR        = 0.15          # p mínimo para entrar en un bin (evita colas)
AVG7_MIN       = 5.0           # AVG7 mínimo para operar
VOL_MIN        = 5_000         # $ volumen mínimo del mercado
LIQ_MIN        = 1_000         # $ liquidez mínima del mercado
BETA           = 0.5           # coeficiente de momentum del ajuste
AJUSTE_MIN, AJUSTE_MAX = 0.5, 1.5
# ----------------------------------------------------------------------------


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def poisson_cdf(k, lam):
    """P(X ≤ k) con X ~ Poisson(lam). Estable para lam hasta ~700;
    aproximación normal (corrección de continuidad) para lam mayor."""
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    if lam > 700:
        z = (k + 0.5 - lam) / math.sqrt(lam)
        return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    s, term = 0.0, math.exp(-lam)
    kmax = max(0, int(k))
    for i in range(0, kmax + 1):
        s += term
        term *= lam / (i + 1)
    return min(1.0, max(0.0, s))


def p_bin(lo, hi, lam):
    """P(lo ≤ X ≤ hi) con X ~ Poisson(lam). hi puede ser inf."""
    if hi == math.inf:
        return 1.0 - poisson_cdf(lo - 1, lam)
    return poisson_cdf(hi, lam) - poisson_cdf(lo - 1, lam)


def tabla_apuestas(stake_inicial=STAKE_INICIAL, factor=FACTOR, pasos=PASOS_MAX):
    """Genera la tabla de apuestas (stake, pérdida acumulada, beneficio neto)."""
    filas = []
    perdida_prev = 0.0
    for i in range(1, pasos + 1):
        stake = math.ceil(stake_inicial * factor ** (i - 1) * 100) / 100  # redondeo al alza
        perdida_acum = perdida_prev + stake
        # beneficio neto si acierta a la cuota mínima (pago = stake × cuota):
        benef = round(stake * (CUOTA_MINIMA - 1) - perdida_prev, 2)
        filas.append((i, stake, perdida_acum, benef))
        perdida_prev = perdida_acum
    return filas


def cargar_csv(path):
    """Devuelve lista ordenada de (fecha, tweets)."""
    datos = []
    with open(path, newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            fecha = datetime.strptime(fila["fecha"].strip(), "%Y-%m-%d").date()
            tweets = int(float(fila["tweets"].strip()))
            datos.append((fecha, tweets))
    datos.sort(key=lambda x: x[0])
    if len(datos) < 9:
        sys.exit("ERROR: se necesitan al menos 9 días de datos completos (7 para AVG7 + 2 para V2).")
    return datos


def metricas(datos):
    """AVG7, V2, R, ajuste, λ48 a partir de los 7/2 últimos días COMPLETOS."""
    ult7 = [t for _, t in datos[-7:]]
    ult2 = [t for _, t in datos[-2:]]
    avg7 = sum(ult7) / 7.0
    v2 = sum(ult2)
    r = v2 / (2.0 * avg7) if avg7 > 0 else float("nan")
    ajuste = clamp(1.0 + BETA * (r - 1.0), AJUSTE_MIN, AJUSTE_MAX) if not math.isnan(r) else 1.0
    lam48 = 2.0 * avg7 * ajuste
    return dict(avg7=avg7, v2=v2, r=r, ajuste=ajuste, lam48=lam48,
                ult7=ult7, ult2=ult2, fecha_base=datos[-1][0])


def decidir_bin(p, precio_yes, cuota_yes, cuota_no):
    """Reglas de entrada según REGLA de esta ventana.
    Devuelve (veredicto, lado, razon).
    - REGLA "absoluta" (48h): p_modelo ≥ 60% (YES) o ≤ 30% (NO) + cuota mín.
    - REGLA "ventaja" (semanal/mensual): p_modelo ≥ precio + EDGE_MIN (o
      p_modelo(NO) ≥ precio(NO) + EDGE_MIN) + cuota mín. + piso P_FLOOR."""
    precio_no = 1.0 - precio_yes
    if REGLA == "absoluta":
        if p >= P_MIN_YES and cuota_yes and cuota_yes >= CUOTA_MINIMA:
            return "APOSTAR YES", "YES", f"p_modelo {p:.1%} ≥ {P_MIN_YES:.0%} y cuota {cuota_yes:.2f} ≥ {CUOTA_MINIMA:.2f}"
        if p <= P_MAX_NO and cuota_no and cuota_no >= CUOTA_MINIMA:
            return "APOSTAR NO", "NO", f"p_modelo {p:.1%} ≤ {P_MAX_NO:.0%} y cuota NO {cuota_no:.2f} ≥ {CUOTA_MINIMA:.2f}"
        if p >= P_MIN_YES:
            return "PASAR", None, f"p_modelo {p:.1%} alta pero cuota {cuota_yes:.2f} < {CUOTA_MINIMA:.2f}"
        if p <= P_MAX_NO:
            return "PASAR", None, f"p_modelo {p:.1%} baja pero cuota NO {cuota_no:.2f} < {CUOTA_MINIMA:.2f}"
        return "PASAR", None, f"p_modelo {p:.1%} sin ventaja (0.30 < p < 0.60)"
    # ---------------- REGLA VENTAJA (semanal / mensual) ----------------
    vy = p - precio_yes                      # ventaja YES (p_modelo vs mercado)
    vn = (1.0 - p) - precio_no               # ventaja NO
    if p >= P_FLOOR and vy >= EDGE_MIN and cuota_yes and cuota_yes >= CUOTA_MINIMA:
        return ("APOSTAR YES", "YES",
                f"p {p:.1%} ≥ precio {precio_yes:.1%} + {EDGE_MIN:.0%}pp "
                f"(ventaja {vy:.0%}pp) y cuota {cuota_yes:.2f} ≥ {CUOTA_MINIMA:.2f}")
    if (1.0 - p) >= P_FLOOR and vn >= EDGE_MIN and cuota_no and cuota_no >= CUOTA_MINIMA:
        return ("APOSTAR NO", "NO",
                f"p(NO) {1-p:.1%} ≥ precio NO {precio_no:.1%} + {EDGE_MIN:.0%}pp "
                f"(ventaja {vn:.0%}pp) y cuota {cuota_no:.2f} ≥ {CUOTA_MINIMA:.2f}")
    return "PASAR", None, (f"sin ventaja ≥ {EDGE_MIN:.0%}pp (YES {vy:+.0%}pp, "
                           f"NO {vn:+.0%}pp) o cuota < {CUOTA_MINIMA:.2f}")


def decision(m, lo, hi, precio_yes, ya_publicados=0, horas=0):
    """Aplica las reglas R1–R5 y devuelve (p_modelo, cuota_yes, cuota_no,
    veredicto, razon)."""
    if math.isnan(m["r"]):
        return None, None, None, "PASAR", "AVG7 = 0: sin actividad base"
    lam_rest = m["lam48"] * max(0.0, (48.0 - horas)) / 48.0
    p = p_bin(lo - ya_publicados, (hi - ya_publicados) if hi != math.inf else math.inf, lam_rest)
    cuota_yes = 1.0 / precio_yes if precio_yes > 0 else float("inf")
    precio_no = 1.0 - precio_yes
    cuota_no = 1.0 / precio_no if precio_no > 0 else float("inf")

    if m["avg7"] < AVG7_MIN:
        return p, cuota_yes, cuota_no, "PASAR", f"AVG7 = {m['avg7']:.1f} < {AVG7_MIN} (base insuficiente)"
    veredicto, lado, razon = decidir_bin(p, precio_yes, cuota_yes, cuota_no)
    return p, cuota_yes, cuota_no, veredicto, razon


def formatear_senal(m, lo, hi, precio_yes, ya_publicados, horas, paso=None):
    p, c_yes, c_no, veredicto, razon = decision(m, lo, hi, precio_yes, ya_publicados, horas)
    print("=" * 72)
    print(f"SEÑAL  ·  fecha de datos: {m['fecha_base']}  ·  bin [{lo}, {hi if hi != math.inf else '∞'}]  ·  precio YES {precio_yes:.3f}")
    print("=" * 72)
    print(f"  Últimos 7 días        : {m['ult7']}")
    print(f"  Últimos 2 días        : {m['ult2']}")
    print(f"  AVG7 (media 7 días)   : {m['avg7']:.2f} tweets/día")
    print(f"  V2   (últimos 2 días) : {m['v2']} tweets")
    print(f"  R    = V2/(2·AVG7)    : {m['r']:.3f}   ({'bajo → posible recuperación' if m['r'] < 1 else 'alto → momentum'})")
    print(f"  ajuste(R)             : {m['ajuste']:.3f}")
    print(f"  λ48 (esperado 48 h)   : {m['lam48']:.1f} tweets")
    if horas > 0:
        print(f"  ya publicados         : {ya_publicados}  ·  horas transcurridas: {horas}")
    print(f"  p_modelo = P({lo} ≤ X ≤ {hi if hi != math.inf else '∞'}) : {p:.1%}" if p is not None else "  p_modelo = n/d")
    if c_yes is not None:
        print(f"  cuota YES = {c_yes:.2f}  ·  cuota NO = {c_no:.2f}")
    print(f"  ► VEREDICTO: {veredicto}")
    print(f"    Razón: {razon}")
    if veredicto.startswith("APOSTAR") and paso is not None:
        fila = tabla_apuestas()[paso - 1]
        print(f"    Paso {paso} del ciclo → stake ${fila[1]:.2f}  (pérdida acumulada si falla: ${fila[2]:.2f})")
    print()


def backtest(datos, lo, hi, precio_yes):
    """Simula la estrategia completa (reglas R1–R7) sobre el histórico.
    Supuestos documentados: entrada al inicio del día t (mercado de 48 h que
    cubre t+1 y t+2), precio de entrada FIJO = precio_yes (sin slippage),
    sin comisiones. El resultado real se calcula con los tweets observados."""
    apuestas = tabla_apuestas()
    ciclo = 0            # paso actual del ciclo (0 = sin ciclo abierto)
    pendiente_hasta = -1 # índice hasta el que hay una apuesta sin resolver
    saldo = 0.0
    max_exp = 0.0
    wins = losses = 0
    racha_p = racha_p_max = 0
    saldo_min = 0.0
    registro = []

    for t in range(9, len(datos) - 2):
        if t < pendiente_hasta:
            continue
        hist = datos[:t]                      # solo días ya completos
        m = metricas(hist)
        p, c_yes, c_no, veredicto, razon = decision(m, lo, hi, precio_yes)
        if not veredicto.startswith("APOSTAR"):
            continue
        if ciclo == 0:
            ciclo = 1
        paso = ciclo
        _, stake, perd_acum, benef = apuestas[paso - 1]
        max_exp = max(max_exp, perd_acum)
        real = datos[t + 1][1] + datos[t + 2][1]
        ok = (lo <= real <= hi) if hi != math.inf else real >= lo
        if ok:
            saldo += stake * (1 / precio_yes - 1)
            wins += 1
            racha_p = 0
            registro.append((datos[t][0], paso, stake, real, "G", round(saldo, 2)))
            ciclo = 0                          # reinicio del ciclo
        else:
            saldo -= stake
            losses += 1
            racha_p += 1
            racha_p_max = max(racha_p_max, racha_p)
            registro.append((datos[t][0], paso, stake, real, "P", round(saldo, 2)))
            if paso >= PASOS_MAX:
                ciclo = 0                      # stop-loss del ciclo
            else:
                ciclo = paso + 1
        saldo_min = min(saldo_min, saldo)
        pendiente_hasta = t + 3                # resuelve al final de t+2

    total = wins + losses
    print("=" * 72)
    print("BACKTEST (datos históricos)  ·  bin [%s, %s]  ·  precio YES fijo %.2f" %
          (lo, hi if hi != math.inf else "∞", precio_yes))
    print("=" * 72)
    print(f"  Apuestas totales      : {total}   (ganadas {wins}, perdidas {losses})")
    print(f"  Win rate              : {wins / total:.1%}" if total else "  Win rate: n/d")
    print(f"  Beneficio neto        : ${saldo:+.2f}")
    print(f"  Racha máx de pérdidas : {racha_p_max}")
    print(f"  Exposición máx. ciclo : ${max_exp:.2f}  (máx. teórica paso {PASOS_MAX}: ${apuestas[-1][2]:.2f})")
    print(f"  Peor saldo            : ${saldo_min:.2f}")
    print("\n  Paso a paso (fecha | paso | stake | tweets reales | resultado | saldo):")
    for fecha, paso, stake, real, res, sal in registro:
        print(f"    {fecha}  paso {paso}  ${stake:>7.2f}  real={real:>4}  {res}  saldo ${sal:>9.2f}")
    return registro


def main():
    ap = argparse.ArgumentParser(description="Motor de señal — mercado mensual Polymarket de tweets de Trump")
    ap.add_argument("--csv", required=True, help="CSV con columnas fecha,tweets (días completos, hora ET)")
    ap.add_argument("--bin", nargs=2, type=int, metavar=("A", "B"), default=[1, 9999],
                    help="Bin del mercado [A, B]; B=9999 significa '≥ A'")
    ap.add_argument("--precio", type=float, default=0.33, help="Precio actual del YES (0-1)")
    ap.add_argument("--ya-publicados", type=int, default=0, help="Tweets ya publicados dentro de la ventana del mercado")
    ap.add_argument("--horas", type=float, default=0.0, help="Horas transcurridas de la ventana")
    ap.add_argument("--paso", type=int, default=1, help="Paso actual del ciclo (1-5) para calcular el stake")
    ap.add_argument("--backtest", action="store_true", help="Simular la estrategia sobre el histórico")
    args = ap.parse_args()

    datos = cargar_csv(args.csv)

    if args.backtest:
        backtest(datos, args.bin[0], 9999 if args.bin[1] == 9999 else args.bin[1], args.precio)
        return

    m = metricas(datos)
    paso = max(1, min(args.paso, PASOS_MAX))
    formatear_senal(m, args.bin[0], 9999 if args.bin[1] == 9999 else args.bin[1],
                    args.precio, args.ya_publicados, args.horas, paso=paso)



# === SENAL_EMP_ARENA (27/08): probabilidad empirica (dispersion real) ===
# Sustituye la campana Poisson por la DISTRIBUCION REAL de los ultimos 14
# dias del CSV (convolucion exacta), manteniendo la media con el ajuste de
# momentum. La interfaz no cambia: metricas() y p_bin() reciben y devuelven
# lo mismo, asi que senal_vivo y operar_real funcionan sin tocarlos.
#
# Por que: el Poisson asume una dispersion de +-raiz(lam) (ej. +-9 tweets
# en 48h) cuando Musk se mueve realmente +-40. El modelo compraba
# "certezas" de 60-70% que valian 20-30%.
#
# Interruptor: variable de entorno SENAL_EMP=0 para volver al Poisson
# original al instante (o senal._EMP["on"] = False en codigo/pruebas).
from collections import Counter as _Counter_emp

try:
    import os as _os_emp
    _EMP_ON_DEF = str(_os_emp.environ.get("SENAL_EMP", "1")).strip().lower() not in ("0", "false", "no", "off")
except Exception:
    _EMP_ON_DEF = True

_EMP = {"on": _EMP_ON_DEF, "dias": [], "avg7": None, "ajuste": None}
_EMP_N_DIAS = 14
_EMP_CACHE = {}


def _emp_dist(k, frac, dias):
    """Distribucion EXACTA de la suma de k dias + frac*otro dia,
    muestreando con reposicion los dias reales (peso 1/n cada dia).
    Convolucion exacta (sin Montecarlo) con cache."""
    clave = (k, round(frac, 4), tuple(dias))
    d = _EMP_CACHE.get(clave)
    if d is not None:
        return d
    nd = float(len(dias))
    base = {}
    for v, c in _Counter_emp(dias).items():
        base[float(v)] = c / nd
    dist = {0.0: 1.0}
    for _ in range(k):
        ndist = {}
        for v1, w1 in dist.items():
            for v2, w2 in base.items():
                v = v1 + v2
                ndist[v] = ndist.get(v, 0.0) + w1 * w2
        dist = ndist
    if frac > 1e-9:
        ndist = {}
        for v1, w1 in dist.items():
            for v2, w2 in base.items():
                v = v1 + v2 * frac
                ndist[v] = ndist.get(v, 0.0) + w1 * w2
        dist = ndist
    if len(_EMP_CACHE) > 64:
        _EMP_CACHE.clear()
    _EMP_CACHE[clave] = dist
    return dist


_metricas_emp_orig = metricas


def metricas(datos):
    m = _metricas_emp_orig(datos)
    try:
        dias = [float(t) for _, t in datos[-_EMP_N_DIAS:]]
        if len(dias) >= 5:
            _EMP["dias"] = dias
            _EMP["avg7"] = m.get("avg7")
            _EMP["ajuste"] = m.get("ajuste")
    except Exception:
        pass
    return m


_p_bin_orig = p_bin


def p_bin(lo, hi, lam):
    """P(lo <= X <= hi). Empirica si hay estado; Poisson original si no."""
    if not _EMP["on"]:
        return _p_bin_orig(lo, hi, lam)
    try:
        dias = _EMP["dias"]
        avg7 = _EMP["avg7"]
        aj = _EMP["ajuste"]
        if (not dias) or (not avg7) or avg7 <= 0 or (not aj) or aj <= 0 \
                or lam is None or lam <= 0 or hi is None or lo is None:
            return _p_bin_orig(lo, hi, lam)
        base_diaria = avg7 * aj
        dias_eq = lam / base_diaria          # = horas restantes / 24
        k = int(dias_eq)
        frac = dias_eq - k
        dist = _emp_dist(k, frac, dias)
        lo2 = lo / aj
        hi2 = hi / aj                         # hi=inf -> inf/aj = inf (ok)
        p = 0.0
        for v, w in dist.items():
            if lo2 <= v <= hi2:
                p += w
        return p
    except Exception:
        return _p_bin_orig(lo, hi, lam)


def emp_info():
    """Diagnostico: estado del motor empirico (para comparar/pruebas)."""
    return {"on": _EMP["on"], "n_dias": len(_EMP["dias"]),
            "dias": _EMP["dias"], "avg7": _EMP["avg7"], "ajuste": _EMP["ajuste"]}


# === FIXVAR_ARENA (30/08): descuento por alta variabilidad de actividad ===
# Si el CV (desviacion_tipica/media) de los ultimos 7 dias supera 1.2,
# el modelo empirico es menos fiable. Se acerca p hacia 0.5 para ser
# mas conservador cuando la actividad es muy irregular.
import statistics as _stats_var
CV_MAX_VAR  = 1.2    # umbral de coeficiente de variacion
DESC_VAR    = 0.30   # descuento por unidad de CV excedente

_metricas_var_orig = metricas
def metricas(datos):
    m = _metricas_var_orig(datos)
    try:
        ult7 = m.get("ult7", [])
        avg7 = m.get("avg7", 0)
        m["cv7"] = (_stats_var.stdev(ult7) / avg7) if (len(ult7) >= 2 and avg7 > 0) else 0.0
    except Exception:
        m["cv7"] = 0.0
    return m

_decision_var_orig = decision
def decision(m, lo, hi, precio_yes, ya_publicados=0, horas=0):
    p, cy, cn, veredicto, razon = _decision_var_orig(m, lo, hi, precio_yes, ya_publicados, horas)
    try:
        cv = m.get("cv7", 0.0)
        if cv > CV_MAX_VAR and p is not None:
            factor = max(0.5, 1.0 - (cv - CV_MAX_VAR) * DESC_VAR)
            p = 0.5 + (p - 0.5) * factor
            if veredicto.startswith("APOSTAR"):
                ok_yes = p >= P_MIN_YES and precio_yes <= 1.0 / CUOTA_MINIMA
                ok_no  = p <= P_MAX_NO  and (1 - precio_yes) <= 1.0 / CUOTA_MINIMA
                if not ok_yes and not ok_no:
                    veredicto = "PASAR"
                    razon = f"FIXVAR: CV={cv:.2f}>{CV_MAX_VAR}, p ajustada {p:.1%} insuficiente"
    except Exception:
        pass
    return p, cy, cn, veredicto, razon


# === FIXCAL_ARENA (30/08): calibracion de stake por historial real ===
# Lee el historial del bot y calcula win rate + Kelly fraction.
# Con >=15 trades cerradas: ajusta STAKE_INICIAL automaticamente (max +/-30%).
# Con menos datos: solo informa en el log.
import json as _json_cal, os as _os_cal
_FIXCAL_JOURNAL = "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"
_FIXCAL_STAKE_BASE = STAKE_INICIAL

def _fixcal_calibrar():
    global STAKE_INICIAL
    try:
        if not _os_cal.path.exists(_FIXCAL_JOURNAL):
            return
        data = _json_cal.load(open(_FIXCAL_JOURNAL, encoding="utf-8"))
        hist = data.get("historial", []) if isinstance(data, dict) else data
        cerradas = [r for r in hist if r.get("resultado") in ("G", "P")]
        n = len(cerradas)
        if n < 5:
            return
        wins = sum(1 for r in cerradas if r.get("resultado") == "G")
        p_real = wins / n
        cuotas = [float(r["cuota"]) for r in cerradas if r.get("cuota")]
        b = (sum(cuotas) / len(cuotas)) - 1 if cuotas else (CUOTA_MINIMA - 1)
        kelly = (p_real * b - (1 - p_real)) / b if b > 0 else 0
        factor = max(0.70, min(1.30, 1.0 + kelly / 4)) if n >= 15 else 1.0
        nuevo = round(_FIXCAL_STAKE_BASE * factor, 2)
        estado = "APLICADO" if n >= 15 else "INFORMATIVO (faltan datos)"
        print(f"[FIXCAL] win={p_real:.0%} ({wins}/{n}) cuota_med={b+1:.2f} kelly={kelly:.3f} factor={factor:.3f} stake={nuevo} ({estado})")
        if n >= 15:
            STAKE_INICIAL = nuevo
    except Exception as _e:
        print(f"[FIXCAL] error: {_e}")

_fixcal_calibrar()

if __name__ == "__main__":
    main()
