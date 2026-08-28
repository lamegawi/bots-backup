#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Registro de motores (versiones de la estrategia) con sus estadísticas.

Uso:
  python3 motores.py                 -> tabla comparativa de motores
  python3 motores.py --snapshot NOMBRE -> guarda el código actual en motores/NOMBRE/
"""
import json
import os
import shutil
import sys

BASE = "/opt/polymarket"
REG = os.path.join(BASE, "motores", "motores.json")
DIR = os.path.join(BASE, "motores")
REPOS = ["bot-polymarket-elon", "bot-polymarket-elon-v2",
         "bot-polymarket-elon-semanal", "bot-polymarket-elon-semanal-v2",
         "bot-polymarket-elon-mensual", "bot-polymarket-elon-mensual-v2"]
ARCHIVOS = ["senal.py", "senal_vivo.py", "operar_real.py", "operar_real_48h.py",
            "operar_real_semanal.py", "operar_real_mensual.py", "bot.py",
            "bot_semanal.py", "bot_mensual.py"]


def tabla():
    d = json.load(open(REG, encoding="utf-8"))
    print(f"Revisar el: {d.get('revisar_el')} · Motor actual: {d['actual']}\n")
    for m in d["motores"]:
        st = m.get("stats") or {}
        print(f"· {m['nombre']}  ({m['fecha_inicio']} → {m['fecha_fin'] or 'activo'})")
        print(f"    {m['descripcion']}")
        if st:
            print(f"    cerradas={st.get('cerradas')} ganadas={st.get('ganadas')} "
                  f"perdidas={st.get('perdidas')} pnl={st.get('pnl')}")
            print(f"    {st.get('detalle', '')}")
        print()


def snapshot(nombre):
    destino = os.path.join(DIR, nombre)
    os.makedirs(destino, exist_ok=True)
    for r in REPOS:
        for a in ARCHIVOS:
            src = os.path.join(BASE, r, a)
            if os.path.exists(src):
                dd = os.path.join(destino, r)
                os.makedirs(dd, exist_ok=True)
                shutil.copy2(src, os.path.join(dd, a))
    print("snapshot guardado en", destino)


if __name__ == "__main__":
    if "--snapshot" in sys.argv and len(sys.argv) > 2:
        snapshot(sys.argv[sys.argv.index("--snapshot") + 1])
    else:
        tabla()
