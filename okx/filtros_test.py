#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filtros_test.py - Muestra el veredicto de los filtros FIX5 para cada moneda
del bot REAL, sin operar nada. Se puede lanzar cuando quieras:

    python3 /root/filtros_test.py
"""
import os
import sys

sys.path.insert(0, "/root")


def cargar_env(path):
    env = {}
    try:
        for line in open(path):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.replace("export", "").strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


# cargar credenciales en el entorno ANTES de importar el bot
env = cargar_env("/root/.okx_real_env")
for k, v in env.items():
    os.environ.setdefault(k, v)

import okx_client            # noqa: E402
import okx_real_bot as RB    # noqa: E402

if not getattr(RB, "client", None):
    RB.client = okx_client.Cliente(env.get("OKX_REAL_KEY", ""), env.get("OKX_REAL_SECRET", ""),
                                   env.get("OKX_REAL_PASSPHRASE", ""), demo=False)

RB.filtros_diagnostico()

try:
    import json
    if os.path.exists("/root/okx_real_filtro_stats.json"):
        print("\nFiltros hoy: " + str(json.load(open("/root/okx_real_filtro_stats.json"))))
except Exception:
    pass
