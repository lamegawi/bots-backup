#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""compara_senal.py - backtest del mismo bin con los DOS motores:
el original (Poisson) y el parcheado (empirico). Uso:

    python3 compara_senal.py [LO HI [PRECIO]]
    python3 compara_senal.py 60 79 0.33
"""
import os
import sys

sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
os.chdir("/opt/polymarket/bot-polymarket-elon")
import senal  # noqa: E402

lo, hi, precio = 60, 79, 0.33
if len(sys.argv) >= 3:
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
if len(sys.argv) >= 4:
    precio = float(sys.argv[3])
hi_v = float("inf") if hi >= 9999 else hi

datos = senal.cargar_csv("datos_elon.csv")
print("Datos: %d dias completos | bin [%s, %s] | precio YES %.2f"
      % (len(datos), lo, hi if hi < 9999 else "inf", precio))
print()
print("=" * 64)
print("MOTOR ORIGINAL (Poisson - campana estrecha)")
print("=" * 64)
senal._EMP["on"] = False
senal.backtest(datos, lo, hi_v, precio)
print()
print("=" * 64)
print("MOTOR EMPIRICO (parche - dispersion real de tus dias)")
print("=" * 64)
senal._EMP["on"] = True
senal.backtest(datos, lo, hi_v, precio)
print()
info = senal.emp_info()
print("Estado del motor empirico: activo=%s | %d dias: %s | avg7=%.2f ajuste=%.3f"
      % (info["on"], info["n_dias"], info["dias"], info["avg7"] or 0, info["ajuste"] or 0))
