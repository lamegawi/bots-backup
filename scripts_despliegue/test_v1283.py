#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_v1283.py — v12.8.3: ✅ tick del intervalo · 🔍 Leer ahora · panel honesto
==============================================================================
Cuatro bloques:
  A (1-8)    teclado dinámico: el botón ⏱ activo lleva ✅ y el handler sigue
             casando; botón 🔍 Leer ahora presente.
  B (9-15)   situación REAL de los mercados, EN VIVO contra el CLOB: Seyboth
             Wild suspendido (fin 15-sep) y Barranquilla cerrado sin ganador.
  C (16-24)  evidencia de cadena: fills reales de data-api, dedup de los 4
             registros de Barranquilla (sólo hubo 2 fills) y red de seguridad.
  D (25-31)  reparto del cobro + mercado anulado → resultado "anulada" (↩️).
  E (32-38)  🔍 Leer ahora: informe completo SIN abrir, vender ni guardar nada.
  F (39-42)  no-regresión (vivo_de de v12.8.2, versiones, compatibilidad).
Uso: python3 test_v1283.py [ruta_bot_v1283.py]
"""
import importlib.util, json, os, sys, time, urllib.request

RUTA = sys.argv[1] if len(sys.argv) > 1 else "/home/user/v12.8.3_panel/bot_v1283.py"
spec = importlib.util.spec_from_file_location("bot", RUTA)
bot = importlib.util.module_from_spec(spec); sys.modules["bot"] = bot
spec.loader.exec_module(bot)

bot.WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"
MENSAJES, LOGS, ENVIADOS_KB = [], [], []
bot.log = lambda s: LOGS.append(str(s))


def _enviar(cid, txt, reply_markup=None):
    MENSAJES.append(txt)
    ENVIADOS_KB.append(reply_markup)
    return True


bot.enviar = lambda cid, txt, reply_markup=None: _enviar(cid, txt, reply_markup)
bot.enviar_largo = lambda cid, txt, **kw: _enviar(cid, txt)

ok, saltos = [], []


def check(n, p, x=""):
    ok.append((n, bool(p)))
    x = x if isinstance(x, str) else str(x)
    print(f"  {'✅' if p else '❌'} {n}{(' · ' + x) if x else ''}")


def skip(n, why):
    saltos.append(n)
    print(f"  ⚠️ {n} — OMITIDO ({why})")


SRC = open(RUTA, encoding="utf-8").read()

# ------------------------------------------------------------------ constantes
CID_SEYB = "0xe0b5ba4d3407f7eb578d55fe41b34aeb99f0d32b8a32f1da0b330c05b0a30ae6"
TOK_SEYB = "92783053747398236762251536426104690600174713178023607434513935536465849458039"
CID_BARR = "0xf4ae1e2d985191bb2249a435c3b31a4e1d7089b987b27070763226cf4c04b280"
TOK_BARR = "102190795601065752692316941866482150736520688268644150542153831580824160844279"
TOK_COMB = "1613136820142094934430549049612190577488752848523650892747122065814218342400"
TIT_BARR = "Barranquilla: Julieta Pareja vs Lucrezia Stefanini"
TIT_SEYB = "Genoa: Thiago Seyboth Wild vs Francesco Ferrari"
TX_COMBO = ("0xc6c3351126051b5470", "0xcbc6ab40e954e4512b")


def get(u, timeout=25):
    q = urllib.request.Request(u, headers={"User-Agent": "poly-combos-bot"})
    with urllib.request.urlopen(q, timeout=timeout) as r:
        return json.loads(r.read().decode())


# mercados REALES (se usan como stub cuando la red falla)
M_SEYB = M_BARR = None
try:
    M_SEYB = get(f"https://clob.polymarket.com/markets/{CID_SEYB}")
    M_BARR = get(f"https://clob.polymarket.com/markets/{CID_BARR}")
except Exception as e:
    print("  ⚠️ sin mercados vivos del CLOB:", str(e)[:60])
if not M_SEYB:
    M_SEYB = {"question": TIT_SEYB, "closed": False, "active": False,
              "accepting_orders": False, "end_date_iso": "2026-09-15T00:00:00Z",
              "tokens": [{"token_id": TOK_SEYB, "outcome": "Thiago Seyboth Wild",
                          "winner": False, "price": 0.5585}]}
if not M_BARR:
    M_BARR = {"question": TIT_BARR, "closed": True, "active": True,
              "end_date_iso": "2026-09-08T00:00:00Z",
              "tokens": [{"token_id": TOK_BARR, "outcome": "Julieta Pareja",
                          "winner": False, "price": 0.5},
                         {"token_id": "90593246943649738327367837558409886137480337618311932667397922284159793475318",
                          "outcome": "Lucrezia Stefanini", "winner": False, "price": 0.5}]}

# ---------------------------------------------------------------- utilidades
REAL = {k: getattr(bot, k) for k in
        ("mercado_clob", "cargar_estado", "guardar_estado", "cobros_wallet",
         "fills_wallet", "precio_mid", "vivo_de", "threading", "telegram_api",
         "listar_combos", "seleccionar_combo", "saldo_disponible_clob",
         "resolver_operacion", "estado_leg", "token_clob_de_leg", "auto_pasada")}
REAL_CACHE_COBROS = list(bot._COBROS_CACHE)
REAL_CACHE_REPARTO = list(bot._REPARTO_CACHE)
REAL_CACHE_FILLS = list(bot._FILLS_CACHE)
REAL_INT = bot.INTERVALO_AUTO_S
REAL_NEXT = bot.NEXT_PASADA_TS


def restaurar():
    for k, v in REAL.items():
        setattr(bot, k, v)
    bot._COBROS_CACHE[:] = REAL_CACHE_COBROS
    bot._REPARTO_CACHE[:] = REAL_CACHE_REPARTO
    bot._FILLS_CACHE[:] = REAL_CACHE_FILLS
    bot.INTERVALO_AUTO_S = REAL_INT
    bot.NEXT_PASADA_TS = REAL_NEXT


def op_simple(titulo, cid, tok, shares, stake, fecha, **extra):
    d = {"question": titulo, "condition_id": cid, "real_token": tok,
         "size_shares": shares, "stake_dolares": stake, "fecha": fecha,
         "status": "ejecutado", "slug": ""}
    d.update(extra)
    return d


print("\n" + "=" * 74)
print("A · TECLADO DINÁMICO: el botón ⏱ ACTIVO lleva ✅ verde")
print("=" * 74)
bot.INTERVALO_AUTO_S = 600                      # 10 min (el de producción)
kb = bot.teclado_fijo()
fila_int = kb["keyboard"][6]
marcados = [b["text"] for b in fila_int if bot.TICK_ACTIVO in b["text"]]
check("1. sólo UN botón ⏱ lleva el tick ✅", len(marcados) == 1, str(marcados))
check("2. el tick está en el intervalo activo (10 min)",
      marcados == ["⏱ 10m ✅"], marcados[0] if marcados else "—")
check("3. los demás botones van sin tick",
      all(bot.TICK_ACTIVO not in b["text"] for b in fila_int if b["text"] != "⏱ 10m ✅"))
bot.INTERVALO_AUTO_S = 1800
check("4. al cambiar el intervalo el tick se mueve (30 min)",
      [b["text"] for b in bot.teclado_fijo()["keyboard"][6] if bot.TICK_ACTIVO in b["text"]]
      == ["⏱ 30m ✅"])
bot.INTERVALO_AUTO_S = 600
check("5. el tick va AL FINAL: el handler text.startswith('⏱') sigue casando",
      "⏱ 10m ✅".startswith("⏱"))
bot.cargar_estado = lambda: {}
bot.guardar_estado = lambda e: True
bot.programar_paso = lambda ts: None
MENSAJES.clear()
bot.cmd_intervalo(1, "⏱ 20m ✅")               # tal cual llega el botón marcado
check("6. cmd_intervalo acepta el texto CON tick (⏱ 20m ✅)",
      any("Pasada cada 20 min" in m for m in MENSAJES), str(MENSAJES)[:70])
check("7. la confirmación avisa de que el botón queda marcado",
      any("queda marcado como el activo" in m for m in MENSAJES))
bot.INTERVALO_AUTO_S = 600
kb = bot.teclado_fijo()
check("8. el teclado trae el botón 🔍 Leer ahora",
      any(b["text"] == "🔍 Leer ahora" for fila in kb["keyboard"] for b in fila))
check("8b. INTERVALOS_MIN intacto y definido una sola vez",
      bot.INTERVALOS_MIN == (5, 10, 20, 30, 60)
      and SRC.count("INTERVALOS_MIN = (5, 10, 20, 30, 60)") == 1)
restaurar()

print("\n" + "=" * 74)
print("B · SITUACIÓN REAL DEL MERCADO (datos vivos del CLOB)")
print("=" * 74)
bot.mercado_clob = lambda cid: {CID_SEYB: M_SEYB, CID_BARR: M_BARR}.get(str(cid))
cl, tx = bot.situacion_mercado(CID_SEYB)
check("9. Seyboth Wild → SUSPENDIDO (sin libro)", cl == "suspendido", tx[:80])
check("10. el mensaje de suspendido trae la resolución prevista",
      "resolución prevista" in tx and "15/09" in tx, tx[-46:])
cl2, tx2 = bot.situacion_mercado(CID_BARR)
check("11. Barranquilla → cerrado SIN ganador (anulado)", cl2 == "sin_ganador", tx2[:70])
check("12. el mensaje de anulado explica la devolución a ~$0.50", "0.50" in tx2)
op_seyb = op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.81, 5.0, "2026-09-08T11:16:04")
cl3, tx3 = bot.situacion_op(op_seyb)
check("13. situacion_op de la simple suspendida → 'suspendida'", cl3 == "suspendida", tx3[:60])
op_combo = {"question": TIT_SEYB + " + Real Madrid O/U 1.5", "size_shares": 8.56,
            "stake_dolares": 5.0, "fecha": "2026-09-08T14:15:31+00:00",
            "combo_yes_position_id": TOK_COMB, "tx_hash": TX_COMBO[0],
            "legs": [{"question": TIT_SEYB, "condition_id": CID_SEYB, "outcome": None,
                      "position_id": "724302561751616008899238"},
                     {"question": "Real Madrid CF vs. FC Internazionale: O/U 1.5",
                      "condition_id": CID_BARR, "outcome": None, "position_id": "1"}]}
cl4, tx4 = bot.situacion_op(op_combo)
check("14. combo con una leg suspendida → 'suspendida' y avisa de que no se vende",
      cl4 == "suspendida" and "no se puede vender" in tx4, tx4[:88])
# leg perdida ⇒ el parlay no paga
M_MUERTA = {"closed": True, "active": True,
            "tokens": [{"token_id": "1", "outcome": "A", "winner": True, "price": 1.0},
                       {"token_id": "2", "outcome": "B", "winner": False, "price": 0.0}]}
bot.mercado_clob = lambda cid: M_MUERTA
op_muerta = {"question": "x + y", "size_shares": 5, "stake_dolares": 5,
             "legs": [{"question": "y", "condition_id": "0xzz", "outcome": "B"}]}
cl5, tx5 = bot.situacion_op(op_muerta)
check("15. combo con una leg perdida → 'muerta' (no paga)", cl5 == "muerta", tx5[:60])
restaurar()

print("\n" + "=" * 74)
print("C · EVIDENCIA DE CADENA: fills reales y dedup de duplicados fantasma")
print("=" * 74)
bot.mercado_clob = lambda cid: {CID_SEYB: M_SEYB, CID_BARR: M_BARR}.get(str(cid))
fills = []
try:
    fills = bot.fills_wallet(refrescar=True)
except Exception as e:
    print("   sin data-api:", str(e)[:60])
if fills:
    check("16. fills_wallet devuelve los fills REALES de la wallet", len(fills) > 100,
          f"{len(fills)} fills")
    b = [f for f in fills if f["asset"] == TOK_BARR]
    check("17. Barranquilla tiene 2 fills reales en cadena (no 4)", len(b) == 2,
          " · ".join(f"{f['size']}sh@{f['usdc']}" for f in b))
    ops_barr = [op_simple(TIT_BARR, CID_BARR, TOK_BARR, 9.9, 5.0, f"2026-09-08T03:{m}:00")
                for m in ("11:46", "17:30", "22:45", "27:59")]
    for o, m in zip(ops_barr, ("11:46", "17:30", "22:45", "27:59")):
        o["fecha"] = f"2026-09-08T03:{m}"
    cas, fan, sin = bot.casar_fills(ops_barr)
    check("18. dedup: de los 4 registros de Barranquilla → 2 casados, 2 FANTASMA",
          len(cas) == 2 and len(fan) == 2 and not sin,
          f"casadas={len(cas)} fantasma={len(fan)} sin_evidencia={len(sin)}")
    check("19. los casados guardan su fill real (tx/size/usdc)",
          all(o.get("fill_real", {}).get("tx", "").startswith("0x") for o in cas))
    ops_seyb = [op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.81, 5.0, "2026-09-08T11:16:04"),
                op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.82, 5.0, "2026-09-08T11:18:13")]
    cas2, fan2, sin2 = bot.casar_fills(ops_seyb)
    check("20. Seyboth: 2 registros = 2 fills reales ⇒ ninguno se descarta",
          len(cas2) == 2 and not fan2, f"casadas={len(cas2)} fantasma={len(fan2)}")
    ops_combo = [{"question": "combo", "combo_yes_position_id": TOK_COMB, "tx_hash": t,
                  "size_shares": s, "stake_dolares": 5.0, "fecha": "2026-09-08T14:15:31",
                  "legs": [{"question": "a", "condition_id": CID_SEYB}]}
                 for t, s in zip(TX_COMBO, (8.56, 8.62))]
    cas3, fan3, _ = bot.casar_fills(ops_combo)
    check("21. el combo de 2 fills casa por TX y no se toca",
          len(cas3) == 2 and not fan3, f"casadas={len(cas3)} fantasma={len(fan3)}")
    sin_tok = [op_simple("Mercado inventado", "0xabc", "999999999999999999999", 5.0, 5.0,
                         "2026-09-08T03:11:46")]
    _, fan4, sin4 = bot.casar_fills(sin_tok)
    check("22. RED DE SEGURIDAD: sin fill de ese token en cadena → no se descarta",
          not fan4 and len(sin4) == 1)
    bot._FILLS_CACHE[:] = [time.time(), []]
    bot.fills_wallet = lambda **kw: []
    _, fan5, sin5 = bot.casar_fills(ops_barr)
    check("23. si data-api no da fills, NADIE se descarta (sin prueba no se borra)",
          not fan5 and len(sin5) == 4, f"fantasma={len(fan5)} sin_evidencia={len(sin5)}")
    bot.fills_wallet = REAL["fills_wallet"]
    bot._FILLS_CACHE[:] = REAL_CACHE_FILLS
else:
    for i in range(16, 24):
        skip(f"{i}. (bloque de fills)", "data-api sin respuesta")

basura_real = {"fecha": "2026-09-05T19:00:01.832312", "status": "error",
               "cerrada_manual": False}
check("24. es_basura detecta el registro vacío real del estado",
      bot.es_basura(basura_real) is True
      and bot.es_basura(op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.81, 5.0, "x")) is False
      and bot.es_basura({"status": "fallido", "question": ""}) is False)
restaurar()

print("\n" + "=" * 74)
print("D · REPARTO DEL COBRO REAL + MERCADO ANULADO (↩️)")
print("=" * 74)
bot.mercado_clob = lambda cid: {CID_SEYB: M_SEYB, CID_BARR: M_BARR}.get(str(cid))
tit_norm = bot._norm_titulo(TIT_BARR)
bot.cobros_wallet = lambda **kw: {}
bot._COBROS_CACHE[:] = [time.time(), {}, {tit_norm: {"usdc": 9.9, "ts": 1788840703, "n": 1}}]
ops2 = [op_simple(TIT_BARR, CID_BARR, TOK_BARR, 9.9, 5.0, "2026-09-08T03:11:46"),
        op_simple(TIT_BARR, CID_BARR, TOK_BARR, 9.9, 5.0, "2026-09-08T03:17:30")]
estado_fake = {"trades_copiados": list(ops2), "historial": []}
mapa = bot._reparto_mapa(estado_fake, forzar=True)
rep = mapa.get(tit_norm) or {}
check("25. el cobro de $9.90 se reparte entre 19.8 shares → $0.50 por share",
      abs(float(rep.get("por_share") or 0) - 0.5) < 1e-6, str(rep))
r = bot.resolver_operacion(ops2[0])
check("26. mercado anulado YA cobrado → se archiva (antes se esperaba para siempre)",
      r.get("resuelta") is True and r.get("fuente") == "cobro_real_simple", str(r)[:110])
check("27. el cobro anotado es SU parte ($4.95), no el redeem entero ($9.90)",
      abs(float(r.get("cobro_real") or 0) - 4.95) < 1e-6, f"cobro_real={r.get('cobro_real')}")
check("28. resultado 'anulada' con PnL real ≈ −$0.05 (devuelta, no ganada)",
      r.get("anulada") is True and abs(float(r.get("pnl") or 0) + 0.05) < 0.011,
      f"pnl={r.get('pnl')}")
r_seyb = bot.resolver_operacion(op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.81, 5.0,
                                          "2026-09-08T11:16:04"))
check("29. la simple SUSPENDIDA sin cobrar sigue abierta (no se archiva por error)",
      r_seyb.get("resuelta") is not True, str(r_seyb)[:80])
# stats con anuladas
bot.cargar_estado = lambda: {"trades_copiados": [], "historial": [
    {"question": "a", "pnl": 4.95, "resultado": "ganada", "stake_dolares": 5.0},
    {"question": "b", "pnl": -5.0, "resultado": "perdida", "stake_dolares": 5.0},
    {"question": TIT_BARR, "pnl": -0.05, "resultado": "anulada", "stake_dolares": 5.0},
    {"question": TIT_BARR, "pnl": -0.05, "resultado": "anulada", "stake_dolares": 5.0}]}
s = bot.calcular_stats()
check("30. calcular_stats cuenta las anuladas aparte (ni ✅ ni ❌) y suma su PnL",
      s["wins"] == 1 and s["losses"] == 1 and s["anuladas"] == 2
      and abs(s["pnl"] - (-0.15)) < 0.01, f"✅{s['wins']} ❌{s['losses']} ↩️{s['anuladas']} PnL ${s['pnl']:+.2f}")
# sincronizar_operaciones de punta a punta con mocks
guardados = []
estado_sync = {"trades_copiados": [
    basura_real.copy(),
    op_simple(TIT_BARR, CID_BARR, TOK_BARR, 9.9, 5.0, "2026-09-08T03:11:46"),
    op_simple(TIT_BARR, CID_BARR, TOK_BARR, 9.9, 5.0, "2026-09-08T03:17:30"),
    op_simple(TIT_BARR, CID_BARR, TOK_BARR, 9.9, 5.0, "2026-09-08T03:22:45"),
    op_simple(TIT_BARR, CID_BARR, TOK_BARR, 9.9, 5.0, "2026-09-08T03:27:59"),
    op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.81, 5.0, "2026-09-08T11:16:04"),
    op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.82, 5.0, "2026-09-08T11:18:13"),
], "historial": []}
bot.cargar_estado = lambda: json.loads(json.dumps(estado_sync))
bot.guardar_estado = lambda e: (guardados.append(e), True)[1]
bot._REPARTO_CACHE[:] = [0.0, {}]
quedan, nuevas, est = bot.sincronizar_operaciones()
desc = est.get("descartadas") or []
anu = [o for o in nuevas if o.get("resultado") == "anulada"]
check("31. cura+sincroniza: 1 basura + 2 fantasma fuera, 2 anuladas archivadas, Seyboth abierta",
      len(desc) == 3 and len(anu) == 2 and len(quedan) == 2,
      f"descartadas={len(desc)} anuladas={len(anu)} quedan={len(quedan)} "
      f"pnl_anuladas={sum(float(o.get('pnl') or 0) for o in anu):+.2f}")
restaurar()

print("\n" + "=" * 74)
print("E · 🔍 LEER AHORA: informe completo SIN abrir, vender ni guardar nada")
print("=" * 74)
PROHIBIDAS = ["ejecutar_combo_rfq", "lanzar_combo_manual", "enviar_orden", "vender_clob",
              "aceptar_rfq", "crear_rfq", "firmar_orden_v3", "auto_pasada",
              "cerrar_grupo", "guardar_estado", "sincronizar_operaciones",
              "reauditar_estado", "curar_abiertas"]
LLAMADAS = []


class ThreadShim:
    """Ejecuta el hilo EN EL SITIO para poder inspeccionar el resultado."""
    def __init__(self, mod): self._m = mod
    def __getattr__(self, k): return getattr(self._m, k)
    def Thread(self, target=None, daemon=None, **kw):
        class T:
            def start(self_):
                if target:
                    target()
        return T()


for fn in PROHIBIDAS:
    def _make(nombre):
        def _f(*a, **k):
            LLAMADAS.append(nombre)
            raise AssertionError(f"🔍 Leer ahora NO debe llamar a {nombre}()")
        return _f
    setattr(bot, fn, _make(fn))
bot.threading = ThreadShim(REAL["threading"])
bot.mercado_clob = lambda cid: {CID_SEYB: M_SEYB, CID_BARR: M_BARR}.get(str(cid))
bot.saldo_disponible_clob = lambda: 123.45
bot.listar_combos = lambda: [
    {"question": "Leg A", "slug": "a-2026-09-12", "condition_id": CID_SEYB,
     "yes_price": 0.75, "volumen": 50000, "yes_token": TOK_SEYB},
    {"question": "Leg B", "slug": "b-2026-09-12", "condition_id": CID_BARR,
     "yes_price": 0.80, "volumen": 40000, "yes_token": TOK_BARR}]
bot.seleccionar_combo = lambda legs, estado: None
bot.NEXT_PASADA_TS = time.time() + 420
bot.INTERVALO_AUTO_S = 600
MENSAJES.clear()
estado_leer = {"trades_copiados": [
    op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.81, 5.0, "2026-09-08T11:16:04"),
    op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.82, 5.0, "2026-09-08T11:18:13")],
    "historial": [], "reclamos_avisados": {"t1": {"importe": 82.97}},
    "ultimo_auditoria_resumen": {"reabiertas": 0, "corregidas": 0, "nuevas_cerradas": 2,
                                 "pnl_despues": 11.26},
    "ultima_auditoria": "2026-09-11T20:11:00+00:00"}
bot.cargar_estado = lambda: json.loads(json.dumps(estado_leer))
bot.precio_mid = lambda tok: None            # mercado suspendido: /midpoint 404
antes_next = bot.NEXT_PASADA_TS
bot.cmd_leer_ahora(1)
informe = "\n".join(MENSAJES)
check("32. 🔍 no llama a NADA que abra, venda o guarde",
      not LLAMADAS, str(LLAMADAS)[:90])
check("33. 🔍 no mueve la próxima pasada AUTO (sigue a su hora)",
      bot.NEXT_PASADA_TS == antes_next)
check("34. el informe dice el intervalo activo con ✅ y la próxima lectura",
      "pasada cada *10 min* ✅" in informe and "próxima lectura en " in informe
      and ("min" in informe or " s " in informe),
      [l for l in informe.split("\n") if "pasada cada" in l][:1])
check("35. el informe trae bankroll, catálogo y qué abriría",
      "$123.45" in informe and "Qué abriría ahora" in informe and "NADA" in informe)
check("36. el informe muestra la posición SUSPENDIDA con su último precio",
      "SUSPENDIDO" in informe and "últ. precio (libro cerrado)" in informe
      and "vs pago $19.63" in informe, [l for l in informe.split("\n") if "📈" in l][:1])
check("37. el informe recuerda lo que hay sin cobrar ($82.97)",
      "Sin cobrar" in informe and "82.97" in informe)
check("38. el informe deja claro que NO abre nada",
      "NO abre ni vende nada" in informe and "sólo mirar" in MENSAJES[0].lower())
check("38b. LECTURA_LOCK se libera al terminar (se puede repetir)",
      bot.LECTURA_LOCK.acquire(blocking=False) is True)
try:
    bot.LECTURA_LOCK.release()
except Exception:
    pass
restaurar()

print("\n" + "=" * 74)
print("F · NO-REGRESIÓN (v12.8.2 intacto) + versiones")
print("=" * 74)
bot.mercado_clob = lambda cid: {CID_SEYB: M_SEYB, CID_BARR: M_BARR}.get(str(cid))
bot.token_clob_de_leg = lambda lg: TOK_SEYB
bot.precio_mid = lambda tok: 0.5585 if str(tok) == TOK_SEYB else None
p, fte = bot.precio_vivo_op(op_combo)
check("39. precio_vivo_op usa el mid cuando hay libro (fuente 'mid')",
      p is not None and fte == "mid", f"p={p} fuente={fte}")
bot.precio_mid = lambda tok: None
p2, fte2 = bot.precio_vivo_op(op_simple(TIT_SEYB, CID_SEYB, TOK_SEYB, 9.81, 5.0, "x"))
check("40. sin libro usa el ÚLTIMO precio publicado (fuente 'ult')",
      p2 == 0.5585 and fte2 == "ult", f"p={p2} fuente={fte2}")
check("41. vivo_de() de v12.8.2 sigue intacto (token real del CLOB por leg)",
      SRC.count("def vivo_de(") == 1 and "token_clob_de_leg(lg)" in SRC)
check("42. versiones a v12.8.3 en cabecera, /start, /status y /reclamar",
      all(x in SRC for x in ("POLY COMBOS BOT v12.8.3", "🤖 *POLY COMBOS BOT v12.8.3*",
                             "📊 *ESTADO v12.8.3 (Combos)*", "💰 *RECLAMAR v12.8.3*",
                             'log("v12.8.3 iniciado")')))
check("42b. TECLADO_FIJO sigue existiendo (compatibilidad) y enviar() usa el dinámico",
      isinstance(bot.TECLADO_FIJO, dict) and "json.dumps(teclado_fijo())" in SRC)
restaurar()

# ------------------------------------------------------------------- resumen
buenas = sum(1 for _, p in ok if p)
malas = [n for n, p in ok if not p]
print("\n" + "=" * 74)
print(f"RESULTADO: {buenas}/{len(ok)} pruebas OK"
      + (f" · {len(saltos)} omitidas" if saltos else ""))
if malas:
    print("FALLAN:")
    for m in malas:
        print("   ❌", m)
    sys.exit(1)
print("✅ v12.8.3 lista: tick ✅ del intervalo, 🔍 Leer ahora (sólo mirar),")
print("   panel honesto (⏸ suspendido / ↩️ anulado) y curación por evidencia de cadena.")
sys.exit(0)
