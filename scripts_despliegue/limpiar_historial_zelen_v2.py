#!/usr/bin/env python3
"""
LIMPIAR HISTORIAL FANTASMA DEL BOT DE ZELENSKYY - v2
=====================================================
Encuentra la operacion del 25 de agosto con +$267.80 (bug del bot)
y la corrige con el beneficio real ($3.62) o la elimina.

Tambien detecta otros PnL inflados por stake*(cuota-1).
"""
import json
import os
import sys
import shutil
import re
from datetime import datetime

RUTA = "/opt/polymarket/bot-polymarket-zelenskyy/real_zelen.json"


def main():
    dry = "--dry" in sys.argv
    fix = "--fix" in sys.argv
    delete_only = "--delete" in sys.argv

    print("=" * 70)
    print(f"LIMPIEZA HISTORIAL ZELENSKYY v2 · {datetime.now().isoformat()}")
    print(f"Archivo: {RUTA}")
    print("=" * 70)
    print()

    if not os.path.exists(RUTA):
        print(f"ERROR: no existe {RUTA}")
        sys.exit(1)

    with open(RUTA) as f:
        data = json.load(f)

    historial = data.get("historial", [])
    print(f"Operaciones en historial: {len(historial)}")
    print(f"Saldo actual: ${data.get('saldo', '?')}")
    print()

    # Detectar operaciones con bug: beneficio = stake * (cuota - 1)
    sospechosas = []
    for i, op in enumerate(historial):
        if not isinstance(op, dict):
            continue
        stake = op.get("stake", 0) or 0
        cuota = op.get("cuota", 0) or 0
        beneficio = op.get("beneficio", 0) or 0
        fecha = op.get("fecha", "?")
        bin_titulo = op.get("bin", "?")
        mercado = op.get("mercado", "?")
        real_nota = op.get("real", "")
        resultado = op.get("resultado", "?")

        try:
            stake_f = float(stake)
            cuota_f = float(cuota)
            beneficio_f = float(beneficio)

            # Calcular el "esperado" si el bot calculó stake*(cuota-1)
            esperado_bug = stake_f * (cuota_f - 1) if cuota_f > 1 else 0
            diff = abs(beneficio_f - esperado_bug)
            # Si el beneficio está MUY cerca de stake*(cuota-1) y difiere mucho de un valor realista
            if cuota_f > 5 and diff < 0.1 and abs(beneficio_f) > 10:
                # Probable bug
                # Intentar extraer el valor real de la nota "real"
                real_valor = None
                m = re.search(r'\(\+?([\d.]+)', real_nota)
                if m:
                    real_valor = float(m.group(1))
                sospechosas.append({
                    "indice": i,
                    "fecha": fecha,
                    "bin": bin_titulo,
                    "mercado": mercado,
                    "stake": stake_f,
                    "cuota": cuota_f,
                    "beneficio_falso": beneficio_f,
                    "esperado_bug": esperado_bug,
                    "real_nota": real_nota,
                    "real_valor": real_valor,
                    "resultado": resultado,
                })
        except (ValueError, TypeError):
            pass

    if not sospechosas:
        print("✓ No se encontraron operaciones con bug de cálculo")
        return

    print(f"⚠️  {len(sospechosas)} operaciones con posible bug de cálculo:")
    print()
    for s in sospechosas:
        print(f"  [{s['indice']}] {s['fecha']} | {s['mercado'][:50]}")
        print(f"      bin: {s['bin']}, stake: ${s['stake']:.2f}, cuota: {s['cuota']:.2f}")
        print(f"      beneficio registrado: ${s['beneficio_falso']:.2f}")
        print(f"      esperado por bug (stake*cuota-1): ${s['esperado_bug']:.2f}")
        if s['real_valor'] is not None:
            print(f"      >>> VALOR REAL (de la nota): ${s['real_valor']:.2f}")
        else:
            print(f"      nota real: {s['real_nota']}")
        print()

    if dry:
        print("=" * 70)
        print("DRY RUN: no se ha modificado nada")
        print(f"Para aplicar, ejecuta: python3 {sys.argv[0]} --fix")
        print("=" * 70)
        return

    if fix or delete_only:
        print("=" * 70)
        if delete_only:
            resp = input(f"¿ELIMINAR {len(sospechosas)} operaciones? (escribe SI): ")
        else:
            resp = input(f"¿CORREGIR {len(sospechosas)} operaciones con el valor real? (escribe SI): ")
        if resp.strip() != "SI":
            print("Cancelado")
            return

        # Backup
        backup = RUTA + ".bak_" + datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(RUTA, backup)
        print(f"Backup: {backup}")

        if delete_only:
            indices = {s["indice"] for s in sospechosas}
            data["historial"] = [op for i, op in enumerate(historial) if i not in indices]
            print(f"✓ {len(sospechosas)} operaciones eliminadas")
        else:
            # Corregir usando el valor real si está disponible
            for s in sospechosas:
                i = s["indice"]
                if s["real_valor"] is not None:
                    beneficio_real = s["real_valor"]
                    # Si resultado es G, sumar; si es P, restar
                    if s["resultado"] == "G":
                        data["historial"][i]["beneficio"] = round(beneficio_real, 2)
                    elif s["resultado"] == "P":
                        data["historial"][i]["beneficio"] = -round(beneficio_real, 2)
                    data["historial"][i]["_corregido"] = True
                    data["historial"][i]["_valor_original"] = s["beneficio_falso"]
                    print(f"  [{i}] {s['fecha']}: ${s['beneficio_falso']:.2f} → ${data['historial'][i]['beneficio']:.2f}")
                else:
                    # Si no hay valor real, eliminar
                    data["historial"][i]["_marca"] = "fantasma_sin_valor_real"
                    print(f"  [{i}] {s['fecha']}: marcada como fantasma (sin valor real)")

            # Recalcular saldo
            if "saldo" in data:
                nuevo_saldo = 500.0  # asumiendo bankroll inicial
                for op in data["historial"]:
                    beneficio = float(op.get("beneficio", 0) or 0)
                    # Las correcciones ya están aplicadas
                    nuevo_saldo += beneficio
                print(f"  saldo recalculado: ${data.get('saldo', '?')} → ${nuevo_saldo:.2f}")
                # No modificamos el saldo automáticamente, lo hace el bot
                # pero lo dejamos como pista en una nota
                data["_saldo_recalculado"] = round(nuevo_saldo, 2)

        with open(RUTA, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        print(f"✓ {RUTA} actualizado")
        print()
        print("Ahora abre el bot de Telegram y pulsa '📅 Finalizadas'")
        print("La operación fantasma ya NO debería aparecer.")


if __name__ == "__main__":
    main()
