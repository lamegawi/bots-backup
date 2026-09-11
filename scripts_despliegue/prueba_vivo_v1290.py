#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prueba_vivo_v1290.py — ejecuta el código REAL de v12.9.0 contra las APIs públicas
(lb-api + data-api + CLOB), sin stubs y SIN firmar ni comprar nada.
Sirve para confirmar que el bot desplegado va a ver datos de verdad.
"""
import importlib.util, sys, time

RUTA = "/home/user/v12.9_copytrading/bot_v1290.py"
spec = importlib.util.spec_from_file_location("bot", RUTA)
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)
bot.time.sleep = lambda *_a, **_k: None

print("=" * 78)
print("1) 🏆 top_traders() con lb-api REAL")
print("=" * 78)
for ven in ("1d", "30d"):
    t0 = time.time()
    filas = bot.top_traders(ven, 8, refrescar=True)
    print(f"\n-- ventana {ven} ({bot.VENTANAS_LB[ven]}) · {len(filas)} filas · "
          f"{time.time() - t0:.1f} s")
    for i, nom, w, prof, vol in filas[:8]:
        m = f"{prof / vol * 100:>5.1f}%" if vol else "   n/d"
        print(f"   {i:>2}. {str(nom)[:24]:<24} {bot._din_lb(prof):>9} · vol "
              f"{bot._din_lb(vol):>9} · margen {m} · {w[:10]}…{w[-6:]}")

print("\n" + "=" * 78)
print(f"2) 📡 perfil REAL + filtros de los 12 primeros del top {bot.COPY_VENTANA}")
print("=" * 78)
top = bot.top_traders(bot.COPY_VENTANA, 12, refrescar=True)
elegidos = []
for puesto, nom, w, prof, vol in top:
    p = bot.perfil_trader(w)
    okk, mot = bot.filtros_perfil(p)
    print(f"   #{puesto:<2} {str(nom)[:22]:<22} {'✅ ELEGIDO ' if okk else '❌ fuera   '} {mot}")
    if p:
        print(f"        compras {p['compras']:>4} · ventas {p['ventas']:>4} · "
              f"ratio {p['ratio']:.2f} · mercados {p['mercados']:>3} · "
              f"deporte {p['deporte'] * 100:>3.0f}% · mediana ${p['mediana_usd']:,.0f} · "
              f"hace {(time.time() - p['ultimo']) / 60:,.0f} min")
    if okk:
        elegidos.append((puesto, nom, w))
    if len(elegidos) >= bot.COPY_N_TRADERS:
        break
print(f"\n   → vigilando {len(elegidos)}: " + ", ".join(n for _, n, _ in elegidos))

print("\n" + "=" * 78)
print("3) 📨 ¿hay señales AHORA MISMO? (fills recientes + mid real, sólo lectura)")
print("=" * 78)
desde = time.time() - 3600
n_tot, n_ok, n_tardia, n_sinlibro = 0, 0, 0, 0
for puesto, nom, w in elegidos:
    fills = bot.fills_recientes(w, desde)
    print(f"   {str(nom)[:20]:<20} {len(fills):>3} compras en la última hora")
    for f in fills[:4]:
        n_tot += 1
        p_el = float(f.get("price") or 0)
        p_no = bot.precio_mid(str(f.get("asset") or ""))
        titulo = str(f.get("title") or "?")[:52]
        if p_no is None:
            n_sinlibro += 1
            print(f"      · {titulo:<52} él {p_el:.3f} · sin libro")
            continue
        d = (p_no - p_el) * 100
        if abs(d) > bot.COPY_DERIVA_MAX * 100:
            n_tardia += 1
            print(f"      · {titulo:<52} él {p_el:.3f} → {p_no:.3f} ({d:+.1f} pts) TARDÍA")
        else:
            n_ok += 1
            r = {"precio_trader": p_el, "precio_nuestro": p_no}
            print(f"      · {titulo:<52} él {p_el:.3f} → {p_no:.3f} ({d:+.1f} pts) "
                  f"✅ cuota {1 / p_no:.2f} · retraso {(time.time() - int(f.get('timestamp') or 0)) / 60:,.0f} min")
print(f"\n   resumen: {n_tot} fills mirados · {n_ok} servirían · {n_tardia} tardías · "
      f"{n_sinlibro} sin libro")

print("\n" + "=" * 78)
print("4) 🔒 GARANTÍA: nada de lo anterior ha firmado ni comprado")
print("=" * 78)
print(f"   COPY_DINERO={bot.COPY_DINERO} · COPY_ACTIVO={bot.COPY_ACTIVO} · "
      f"stake papel ${bot.COPY_STAKE_PAPEL:.0f} · tope {bot.COPY_TOPE_DIA}/día")
print("   (esta prueba sólo llama a top_traders/perfil_trader/fills_recientes/precio_mid)")
