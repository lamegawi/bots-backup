#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cirugia_demo.py - Cirugia de las posiciones fantasma del DEMO.

Reglas (la disciplina del bot, aplicada a mano):
  1. ORBS: no se toca (mercado sin liquidez, ya tiene orden de cierre esperando)
  2. Perdida flotante peor de -10.5 USD (mas de 1R): se CIERRA al mercado
  3. Sin SL o con SL mas holgado de 10 USD desde la entrada: se coloca SL
     a 10 USD de riesgo desde la entrada (reduceOnly, como el bot)
Los TP no se tocan.
"""
import json
import sys

sys.path.insert(0, "/root")
e = {}
for l in open("/root/.okx_demo_env"):
    l = l.strip()
    if "=" in l and not l.startswith("#"):
        k, v = l.split("=", 1)
        e[k.replace("export", "").strip()] = v.strip().strip('"').strip("'")
import okx_client as OKX  # noqa: E402

c = OKX.Cliente(e.get("OKX_DEMO_KEY", ""), e.get("OKX_DEMO_SECRET", ""),
                e.get("OKX_DEMO_PASSPHRASE", ""), demo=True)

RIESGO = 10.0
TOLERANCIA = 10.5
SALTAR = {"ORBS"}

posiciones = c.posiciones() or []
algos = c.algo_pendientes() or []
sl_actual = {}
for a in algos:
    if a.get("slTriggerPx"):
        sl_actual[a.get("instId", "")] = float(a["slTriggerPx"])

print("=== CIRUGIA DEL DEMO: riesgo a $%g por posicion ===" % RIESGO)
print("Posiciones encontradas:", len(posiciones))
for p in posiciones:
    inst = p.get("instId", "")
    base = inst.split("-")[0]
    if base in SALTAR:
        print("  %s: SIN LIQUIDEZ, no se toca (su orden de cierre sigue esperando)" % base)
        continue
    try:
        pos = float(p.get("pos", 0) or 0)
    except Exception:
        continue
    if pos == 0:
        continue
    entry = float(p.get("avgPx", 0) or 0)
    upl = float(p.get("upl", 0) or 0)
    notional = abs(float(p.get("notionalUsd", 0) or 0))
    direccion = "LONG" if pos > 0 else "SHORT"
    sz = abs(int(pos))
    print("")
    print("  %s %s %d ct | entrada %.6g | P&L %+.2f | nocional $%.0f" %
          (base, direccion, sz, entry, upl, notional))

    if upl <= -TOLERANCIA:
        lado = "sell" if pos > 0 else "buy"
        try:
            r = c.orden_mercado(inst, lado, sz)
            ok = (r or {}).get("code") == "0"
        except Exception as ex:
            ok = False
            print("    fallo cerrando:", str(ex)[:80])
        print("    -> CERRADA al mercado (superaba -%.1f USD): %s" %
              (TOLERANCIA, "OK" if ok else "FALLO"))
        if ok:
            for a in algos:
                if a.get("instId") == inst:
                    try:
                        c.cancelar_algo(inst, a.get("algoId"))
                    except Exception:
                        pass
        continue

    if notional <= 0 or entry <= 0:
        print("    -> sin datos de nocional/entrada: no se toca")
        continue
    pct = RIESGO / notional
    sl_obj = entry * (1 - pct) if direccion == "LONG" else entry * (1 + pct)
    sl_viejo = sl_actual.get(inst)
    if sl_viejo:
        mas_estrecho = (sl_obj > sl_viejo) if direccion == "LONG" else (sl_obj < sl_viejo)
        if not mas_estrecho:
            riesgo_viejo = abs(entry - sl_viejo) / entry * notional if entry else 0
            print("    -> SL actual OK (%.6g, riesgo ~$%.1f)" % (sl_viejo, riesgo_viejo))
            continue
        for a in algos:
            if a.get("instId") == inst and a.get("slTriggerPx"):
                try:
                    c.cancelar_algo(inst, a.get("algoId"))
                except Exception:
                    pass
    lado_cierre = "sell" if pos > 0 else "buy"
    try:
        aid = c.orden_algo_sl(inst, lado_cierre, round(sl_obj, 8), sz)
        print("    -> SL colocado @ %.6g (riesgo $%.1f, algoId %s)" % (sl_obj, RIESGO, aid))
    except Exception as ex:
        print("    -> FALLO colocando SL:", str(ex)[:100])

print("")
print("=== CIRUGIA terminada ===")
