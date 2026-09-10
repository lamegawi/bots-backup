#!/usr/bin/env python3
"""dump_senal.py — evalúa todos los mercados SIN filtro ENTRADA_MAX_H para diagnóstico"""
import sys
import json
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
import senal
import senal_vivo
import mercado_polymarket as mp

# 1) métricas
datos = senal.cargar_csv("datos_elon.csv")
m = senal.metricas(datos)
print(f"AVG7 = {m['avg7']:.2f} · V2 = {m['v2']} · λ48 = {m['lam48']:.1f}")

# 2) mercados
mercados = json.load(open("/opt/polymarket/bot-polymarket-elon/mercado_activo.json"))["mercados"]
print(f"Mercados en JSON: {len(mercados)}")

# 3) ver cada uno y los bins
ahora = datetime.now(timezone.utc)
ET = ZoneInfo("America/New_York")
for mk in mercados:
    if mk.get("cerrado"): continue
    inicio = datetime.fromisoformat(mk["inicio_iso"]).astimezone(timezone.utc)
    fin = datetime.fromisoformat(mk["fin_iso"]).astimezone(timezone.utc)
    if ahora < inicio or ahora > fin: continue
    horas_elapsed = (ahora - inicio).total_seconds() / 3600
    horas_rest = (fin - ahora).total_seconds() / 3600
    print(f"\n■ {mk['titulo']} [{mk['tipo']}]")
    print(f"  {inicio.astimezone(ET).strftime('%m-%d %H:%M %Z')} → {fin.astimezone(ET).strftime('%m-%d %H:%M %Z')}")
    print(f"  elapsed={horas_elapsed:.1f}h  rest={horas_rest:.1f}h")
    t0, _ = senal_vivo.conteo_ventana(inicio, ahora)
    print(f"  t0={t0}")
    if mk["tipo"] == "48h":
        lam_rest = m["lam48"] * max(0, horas_rest) / 48
    elif mk["tipo"] == "semanal":
        lam_rest = 7 * m["avg7"] * m["ajuste"] * max(0, horas_rest) / 168
    else:
        lam_rest = m["lam48"] * max(0, horas_rest) / 48
    print(f"  λ_rest={lam_rest:.1f}")
    print(f"  {'bin':<12}{'p_modelo':>10}{'precio':>9}{'t0+l':>6}{'hi':>5}  veredicto")
    for b in mk["bins"]:
        hi = b["hi"] if b["hi"] != float("inf") else math.inf
        if hi != math.inf and t0 > hi:
            p = 0.0; ver = "PASAR(t0>hi)"
        elif hi != math.inf and t0 + lam_rest > hi:
            p = 0.0; ver = "PASAR(t0+l>hi)"
        elif hi == math.inf and t0 >= b["lo"]:
            p = 1.0; ver = "PASAR(t0>=lo)"
        else:
            p = senal.p_bin(b["lo"]-t0, (hi-t0) if hi!=math.inf else math.inf, lam_rest)
            ver = "—"
        precio = b["precio_yes"]
        c = 1.0/precio if precio > 0 else float("inf")
        if hi == math.inf:
            hi_str = "inf"
        else:
            hi_str = str(hi)
        print(f"  {b['titulo']:<12}{p:>10.1%}{precio:>9.3f}{t0+lam_rest:>6.0f}{hi_str:>5}  {ver} cuota={c:.1f}")
