#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Escapa los `$` literales de dos echo del actualizador: dentro de comillas
dobbles el shell se los comía ($82.97 → "2.97"; $0 → nombre del script).
Se aplica al .sh generado Y al generador, para que no vuelva a salir roto."""
import io

SH = "/home/user/bots-backup/scripts_despliegue/actualizar_v1282.sh"
GEN = "/home/user/v12.8_reclamar/gen_actualizador_v1282.py"

PARES_SH = [
    ('SIN cobrar ($82.97) ===', 'SIN cobrar (\\$82.97) ==='),
    ('cotización de venta SIN vender ($0) —', 'cotización de venta SIN vender (\\$0) —'),
]
# en el generador las cadenas son Python no-crudas: hay que duplicar la barra
PARES_GEN = [
    ('SIN cobrar ($82.97) ===', 'SIN cobrar (\\\\$82.97) ==='),
    ('cotización de venta SIN vender ($0) —', 'cotización de venta SIN vender (\\\\$0) —'),
]

for ruta, pares in ((SH, PARES_SH), (GEN, PARES_GEN)):
    s = io.open(ruta, encoding="utf-8").read()
    n = 0
    for a, b in pares:
        c = s.count(a)
        if c:
            s = s.replace(a, b)
            n += c
        else:
            print(f"   (ya estaba o no encontrado en {ruta.split('/')[-1]}: {a[:34]}…)")
    io.open(ruta, "w", encoding="utf-8").write(s)
    print(f"✅ {ruta.split('/')[-1]}: {n} sustitución(es)")

s = io.open(SH, encoding="utf-8").read()
assert "(\\$82.97)" in s and "(\\$0)" in s, "el .sh no quedó escapado"
print("   verificado en el .sh:",
      [l.strip()[:78] for l in s.splitlines() if "\\$82.97" in l or "SIN vender (\\$0)" in l])
