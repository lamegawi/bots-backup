#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prueba_vivo_pasada.py — v12.9.0 en vivo: una pasada 📡 COMPLETA contra las APIs
reales (lb-api + data-api + CLOB), con el estado en memoria (no toca ningún
fichero) y sin firmar ni comprar nada. Imprime el panel /copy resultante.
"""
import importlib.util, sys, time

RUTA = "/home/user/v12.9_copytrading/bot_v1290.py"
spec = importlib.util.spec_from_file_location("bot", RUTA)
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)

SLEEP = time.sleep
bot.time.sleep = lambda s: SLEEP(min(s, 0.05))

ESTADO = {"modo": "SEMI"}
bot.cargar_estado = lambda: ESTADO
bot.guardar_estado = lambda e=None: True
MENSAJES = []
bot.enviar = lambda cid, txt, reply_markup=None: MENSAJES.append(txt)

# 🔒 tripwire: si algo del copy intentara comprar, esto revienta
def tripwire(nombre):
    def _f(*a, **k):
        raise AssertionError(f"💸 el copy-trading intentó llamar a {nombre}()")
    return _f
for n in ("enviar_orden", "firmar_orden_v3", "ejecutar_trade", "ejecutar_combo_rfq",
          "ejecutar_semi_aprobado", "crear_rfq", "obtener_identidad_rfq",
          "aceptar_rfq", "reservar_combo"):
    setattr(bot, n, tripwire(n))

print("=" * 78)
print("PASADA 📡 EN VIVO (estado en memoria · tripwires de gasto armados)")
print("=" * 78)
t0 = time.time()
bot.NEXT_COPY_RESUMEN_TS = 0.0
bot.copy_pasada(None)          # sin chat_id: sólo trabaja, no escribe a Telegram
print(f"\n--- tardó {time.time() - t0:.1f} s ---")

cp = ESTADO.get("copy") or {}
print(f"\n👥 traders elegidos: {len(cp.get('traders') or [])}")
for t in cp.get("traders") or []:
    print(f"   · {t['nombre'][:24]:<24} #{t['puesto']} {bot._din_lb(t['profit'])} · "
          f"{t['compras48h']} compras/48h · {t['ventas48h']} ventas · "
          f"{t['mercados']} mercados · {t['deporte_pct']}% deporte · "
          f"mediana ${t['mediana_usd']:,.0f}")

señ = ESTADO.get("copy_señales") or []
print(f"\n📨 señales registradas: {len(señ)} (tope {bot.COPY_TOPE_DIA}/día) · "
      f"vistos {len(cp.get('vistos') or {})} fills")
for s in señ:
    print(f"   · {s['titulo'][:52]:<52} él {s['precio_trader']:.3f} → "
          f"nosotros {s['precio_nuestro']:.3f} ({s['deriva_pts']:+.1f} pts) · "
          f"cuota {s['cuota_nuestro']:.2f} · {'⚽' if s['deporte'] else '🎲'} "
          f"{'✅combo' if s['en_rango_combo'] else '❌fuera de rango'} · "
          f"{s['escaladas']} escaladas · ${s['usd_trader']:,.0f} suyos · "
          f"retraso {s['retraso_s'] // 60}m{s['retraso_s'] % 60:02d}s")

print("\n" + "=" * 78)
print("PANEL /copy TAL CUAL LO VERÍA EL USER AHORA MISMO")
print("=" * 78)
print(bot.texto_copy(ESTADO))
print("=" * 78)
print(f"💸 gastado: $0.00 · COPY_DINERO={bot.COPY_DINERO} · señales ejecutadas: "
      f"{sum(1 for s in señ if s.get('ejecutada'))}")
