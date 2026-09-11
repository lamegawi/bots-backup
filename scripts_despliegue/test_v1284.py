#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_v1284.py — v12.8.4: 🟡 SEMI DE VERDAD + ⚖️ ventaja 5% + ✅ modo + 🧮 cuentas
================================================================================
Todo con STUBS (no toca Polymarket ni firma nada): la red se simula con
crear_rfq/obtener_identidad_rfq falsos y el saldo a $0, de modo que el flujo se
detiene JUSTO después del filtro de ventaja (así se comprueba que lo PASÓ sin
llegar a comprar).

  A (1-12)  🟡 SEMI: propone con ✅/❌, no reserva, no duplica, caduca a los 10
            min, ❌ descarta, ✅ ejecuta por la ruta de AUTO, respeta tope y
            anti-duplicados, doble ✅ inofensivo.
  B (13-19) ⚖️ filtro de ventaja: EV<5% no compra (AUTO y FIJO), EV≥5% pasa,
            manual 🚀/💥 siempre pasa, libera la reserva al omitir.
  C (20-25) ✅ tick en el botón del MODO activo + handler tolerante (_sin_tick).
  D (26-30) 🧮 cuentas de compensación en 📊 Stats con el libro real del user.
  E (31-35) auto_pasada/auto_loop: SEMI propone, AUTO ejecuta, OFF nada.
  F (36-41) cosméticos + no-regresión de v12.8.3/v12.8.2.
  G (42-44) 🟡 el modo guardado sobrevive al reinicio (main() no leía estado["modo"]:
            el bot volvía SIEMPRE en AUTO por mucho que pulsaras SEMI).
Uso: python3 test_v1284.py [ruta_bot_v1284.py]
"""
import importlib.util, json, sys, time

RUTA = sys.argv[1] if len(sys.argv) > 1 else "/home/user/v12.8.4_semi/bot_v1284.py"
spec = importlib.util.spec_from_file_location("bot", RUTA)
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)

bot.WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"
SRC = open(RUTA, encoding="utf-8").read()
CHAT = 123456789
bot.CHAT_ID = CHAT

MENSAJES, LOGS, KBS, CALLBACKS, EDICIONES, EJECUTADAS = [], [], [], [], [], []
bot.log = lambda s: LOGS.append(str(s))


def _enviar(cid, txt, reply_markup=None):
    MENSAJES.append(txt)
    KBS.append(reply_markup)
    return True


bot.enviar = lambda cid, txt, reply_markup=None: _enviar(cid, txt, reply_markup)
bot.enviar_largo = lambda cid, txt, **kw: _enviar(cid, txt)


def _tgapi(metodo, params=None):
    CALLBACKS.append((metodo, params or {}))
    if metodo == "editMessageReplyMarkup":
        EDICIONES.append(json.loads((params or {}).get("reply_markup") or "{}"))
    return None


bot.telegram_api = _tgapi
EJECUTAR_ORIG = bot.ejecutar_combo_rfq      # la de verdad (se restaura tras cada stub)
MAXOPS_ORIG, OPSHOY_ORIG = bot.max_ops, bot.ops_pagadas_hoy
PROPONER_ORIG = bot.proponer_combo_semi

ok, fallos = [], []


def check(n, p, x=""):
    ok.append((n, bool(p)))
    if not p:
        fallos.append(n)
    x = x if isinstance(x, str) else str(x)
    print(f"  {'✅' if p else '❌'} {n}{(' · ' + x) if x else ''}")


# ------------------------------------------------------------------- fixtures
SEL = [
    {"question": "US Open ATP: Zverev vs Khachanov", "yes_token": "111222333",
     "yes_price": 0.94, "volumen": 500000, "event_slug": "us-open-2026",
     "condition_id": "0xaaa", "slug": "atp-zverev"},
    {"question": "Will FC Barcelona win on 2026-09-13?", "yes_token": "444555666",
     "yes_price": 0.85, "volumen": 400000, "event_slug": "laliga-2026",
     "condition_id": "0xbbb", "slug": "fcb-win"},
]
PIDS = [c["yes_token"] for c in SEL]
PROD = 0.94 * 0.85                       # 0.799 → cuota est. 1.25
CUOTA_EST = round(1 / PROD, 2)
H8 = bot.hash8_sel(SEL)

RESERVADAS, LIBERADAS = set(), set()
ESTADO = {"stake_mode": "AUTO", "combos_rfq": {"huellas": {}}, "historial": [],
          "trades_copiados": [], "max_ops_dia": 10}
bot.reservar_combo = lambda pids: RESERVADAS.add(tuple(pids))
bot.liberar_combo = lambda pids: LIBERADAS.add(tuple(pids))
bot.cargar_estado = lambda: json.loads(json.dumps(ESTADO))
bot.guardar_estado = lambda e: None
bot.obtener_identidad_rfq = lambda: {"falsa": True}
bot.saldo_disponible_clob = lambda: 0.0      # $0 → corta el flujo tras el filtro


def _crear_rfq(cuota):
    """RFQ falso: cotización con la cuota_real pedida (blended = 1/cuota)."""
    def f(pids, stake, identidad, *a, **k):
        cuerpo = {"rfq_id": "rfq-test", "status": "AWAITING_REQUESTER_ACCEPTANCE",
                  "request": {"request_id": "rq1"},
                  "quote": {"quote_id": "q1",
                            "blended_price_e6": int(round(1e6 / cuota)),
                            "net_receive_e6": int(stake * cuota * 1e6),
                            "total_required_e6": int(stake * 1e6)}}
        return 200, json.dumps(cuerpo)
    return f


def limpiar():
    for L in (MENSAJES, LOGS, KBS, CALLBACKS, EDICIONES, EJECUTADAS,
              RESERVADAS, LIBERADAS):
        L.clear()
    bot.PROPUESTAS.clear()
    ESTADO["combos_rfq"]["huellas"] = {}
    ESTADO["stake_mode"], ESTADO["stake"] = "AUTO", 5.0
    bot.ejecutar_combo_rfq = EJECUTAR_ORIG
    bot.max_ops, bot.ops_pagadas_hoy = MAXOPS_ORIG, OPSHOY_ORIG
    bot.proponer_combo_semi = PROPONER_ORIG


def cbq(data, mid=777):
    return {"id": "cbq1", "data": data, "message": {"message_id": mid,
            "chat": {"id": CHAT}}, "from": {"id": CHAT}}


def esperar(fn, timeout=4.0):
    """Espera a que se cumpla fn (el ✅ de SEMI ejecuta en un hilo)."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if fn():
            return True
        time.sleep(0.05)
    return fn()


def ult_boton():
    try:
        return EDICIONES[-1]["inline_keyboard"][0][0]["text"]
    except Exception:
        return ""


# =========================================================== A. 🟡 SEMI REAL
print("\nA · 🟡 SEMI de verdad: propuesta con ✅/❌ y caducidad de 10 min")
limpiar()
bot.MODO_OPERACION = "SEMI"
r = bot.proponer_combo_semi(CHAT, SEL)
msg, kb = MENSAJES[-1], KBS[-1]
check(1, r and "🟡 *SEMI — PROPUESTA*" in msg and "caduca en 10 min" in msg,
      "propuesta enviada con cabecera y caducidad de 10 min")
check(2, f"cuota est. *{CUOTA_EST:.2f}*" in msg and "prob *80%*" in msg
      and "Zverev" in msg and "Barcelona" in msg,
      f"legs + cuota est. {CUOTA_EST} + prob 80%")
check(3, "Stake previsto *$" in msg and "ganancia si acierta *+$" in msg
      and "≥5%" in msg and f"cuota real ≥{CUOTA_EST * 1.05:.2f}" in msg,
      "stake, ganancia potencial y condición de ventaja explicadas")
check(4, kb and kb["inline_keyboard"][0][0]["callback_data"] == f"sm:{H8}"
      and kb["inline_keyboard"][0][1]["callback_data"] == f"smx:{H8}"
      and kb["inline_keyboard"][0][0]["text"].startswith("✅")
      and kb["inline_keyboard"][0][1]["text"].startswith("❌"),
      "botones ✅ sm:<h8> / ❌ smx:<h8>")
check(5, H8 in bot.PROPUESTAS and not RESERVADAS,
      "en caché y SIN reservar (si reservara, el anti-dup bloquearía tu propio ✅)")
check(6, bot.proponer_combo_semi(CHAT, SEL) is None
      and "ya hay una propuesta viva" in LOGS[-1], "no duplica una propuesta viva")
ESTADO["combos_rfq"]["huellas"] = {bot.huella_combo(PIDS): {"ts": time.time()}}
check(7, bot.proponer_combo_semi(CHAT, SEL) is None
      and "combo ya operado" in LOGS[-1], "no propone un combo ya operado")

# caducidad a los 10 min
limpiar()
bot.PROPUESTAS[H8] = (time.time() - bot.PROPUESTA_VALIDA_S - 1, SEL, CHAT, msg)
bot.respuesta_propuesta(cbq(f"sm:{H8}"), H8, True)
al = [p for m, p in CALLBACKS if m == "answerCallbackQuery" and p.get("show_alert")]
check(8, al and "caducada" in al[0]["text"] and H8 not in bot.PROPUESTAS
      and ult_boton() == "⌛ caducada" and not EJECUTADAS,
      "a los 10 min: aviso de caducada, botones fuera y no compra")

# ❌ descartar
limpiar()
bot.ejecutar_combo_rfq = lambda *a, **k: EJECUTADAS.append((a, k)) or (True, "NO")
bot.PROPUESTAS[H8] = (time.time(), SEL, CHAT, msg)
bot.respuesta_propuesta(cbq(f"smx:{H8}"), H8, False)
check(9, not EJECUTADAS and H8 not in bot.PROPUESTAS and ult_boton() == "❌ descartada"
      and any("Propuesta descartada" in m for m in MENSAJES),
      "❌ descarta: no compra ($0), quita botones y avisa")

# ✅ aceptar → ejecuta por la ruta de AUTO
limpiar()
bot.ejecutar_combo_rfq = lambda *a, **k: EJECUTADAS.append((a, k)) or (True, "OK")
bot.PROPUESTAS[H8] = (time.time(), SEL, CHAT, msg)
bot.respuesta_propuesta(cbq(f"sm:{H8}"), H8, True)
check(10, esperar(lambda: bool(EJECUTADAS)) and ult_boton() == "✅ aceptada"
      and H8 not in bot.PROPUESTAS
      and any("*SEMI aprobado*" in m for m in MENSAJES),
      "✅ acepta: pide cotización nueva y ejecuta (botones → ✅ aceptada)")
_args, _kw = EJECUTADAS[0]
check(11, _kw.get("manual") is not True and _kw.get("stake") is None
      and _kw.get("franja") == "base" and _kw.get("chat_id") == CHAT,
      "stake dinámico AUTO (no manual): pasan tope, anti-dup y filtro de ventaja")

# tope diario y anti-duplicados al aceptar
limpiar()
bot.ejecutar_combo_rfq = lambda *a, **k: EJECUTADAS.append((a, k)) or (True, "OK")
bot.max_ops = lambda estado=None: 2
bot.ops_pagadas_hoy = lambda estado=None: 2
bot.PROPUESTAS[H8] = (time.time(), SEL, CHAT, msg)
bot.respuesta_propuesta(cbq(f"sm:{H8}"), H8, True)
esperar(lambda: any("Tope diario" in m for m in MENSAJES))
check(12, not EJECUTADAS and any("⛔ *Tope diario alcanzado* (2/2" in m for m in MENSAJES),
      "si al aceptar ya se llegó al tope diario, no compra")

# ===================================================== B. ⚖️ FILTRO VENTAJA 5%
print("\nB · ⚖️ filtro de ventaja: prob × cuota_real ≥ 1.05")


def intento(cuota_real, manual=False, stake_mode="AUTO"):
    """ejecutar_combo_rfq con RFQ falso y saldo $0 (para justo tras el filtro)."""
    RESERVADAS.clear(); LIBERADAS.clear(); MENSAJES.clear(); LOGS.clear()
    bot.ejecutar_combo_rfq = EJECUTAR_ORIG
    ESTADO["stake_mode"], ESTADO["stake"] = stake_mode, 5.0
    bot.crear_rfq = _crear_rfq(cuota_real)
    out = bot.ejecutar_combo_rfq(list(SEL), chat_id=CHAT, franja="base", manual=manual)
    ESTADO["stake_mode"] = "AUTO"
    return out


res = intento(1.21)          # el caso REAL de esta noche: mercado 1.25, RFQ 1.21
check(13, res[0] is False and str(res[1]).startswith("ventaja_-3.2")
      and any("falta de ventaja" in m for m in MENSAJES)
      and tuple(PIDS) in LIBERADAS and tuple(PIDS) in RESERVADAS,
      "RFQ 1.21 vs mercado 1.25 (EV −3.2%) → NO compra y libera la reserva")
res = intento(1.25)
check(14, res[0] is False and str(res[1]).startswith("ventaja_+0.0"),
      "EV 0% (empatar con el mercado) → NO compra")
res = intento(1.31)
check(15, res[0] is False and str(res[1]).startswith("ventaja_+4.8"),
      "EV +4.8% (justo por debajo del 5%) → NO compra")
res = intento(1.32)
check(16, res[0] is False and str(res[1]).startswith("saldo_insuficiente"),
      "EV +5.6% → PASA el filtro (sólo lo paró el saldo $0 del test)")
res = intento(1.21, manual=True)
check(17, res[0] is False and str(res[1]).startswith("saldo_insuficiente"),
      "manual 🚀/💥 con EV negativo → pasa el filtro (los eliges tú)")
res = intento(1.21, stake_mode="FIJO")
check(18, res[0] is False and str(res[1]).startswith("ventaja_-3.2"),
      "con stake FIJO también se respeta el filtro")
check(19, "VENTAJA_MIN_EV = 0.05" in SRC and "PROPUESTA_VALIDA_S = 600" in SRC
      and SRC.count("⚖️ ventaja insuficiente") == 1,
      "constantes 5% / 10 min y un único punto de control")

# ============================================== C. ✅ TICK EN EL MODO ACTIVO
print("\nC · ✅ tick verde en el botón del modo activo + handler")
limpiar()
bot.INTERVALO_AUTO_S = 600
bot.MODO_OPERACION = "SEMI"
check(20, [b["text"] for b in bot.teclado_fijo()["keyboard"][3]] ==
      ["🟢 AUTO", "🟡 SEMI ✅", "🔴 OFF"], "en SEMI: 🟡 SEMI ✅")
bot.MODO_OPERACION = "AUTO"
check(21, [b["text"] for b in bot.teclado_fijo()["keyboard"][3]] ==
      ["🟢 AUTO ✅", "🟡 SEMI", "🔴 OFF"], "en AUTO: 🟢 AUTO ✅")
bot.MODO_OPERACION = "OFF"
check(22, [b["text"] for b in bot.teclado_fijo()["keyboard"][3]] ==
      ["🟢 AUTO", "🟡 SEMI", "🔴 OFF ✅"], "en OFF: 🔴 OFF ✅")
check(23, [b["text"] for b in bot.teclado_fijo()["keyboard"][6]] ==
      ["⏱ 5m", "⏱ 10m ✅", "⏱ 20m", "⏱ 30m", "⏱ 60m"],
      "no-regresión v12.8.3: ⏱ 10m ✅ sigue marcando el intervalo")
check(24, bot._sin_tick("🟡 SEMI ✅") == "🟡 SEMI" and bot._sin_tick("🟢 AUTO") == "🟢 AUTO"
      and bot._sin_tick("🔴 OFF ✅") == "🔴 OFF", "_sin_tick() quita el tick")
limpiar()
bot.MODO_OPERACION = "AUTO"
bot.procesar_update({"message": {"chat": {"id": CHAT}, "text": "🟡 SEMI ✅",
                                 "message_id": 1}})
check(25, bot.MODO_OPERACION == "SEMI" and any("*Modo: SEMI* ✅" in m for m in MENSAJES)
      and "✅ Aceptar / ❌ Descartar" in MENSAJES[-1]
      and "caduca a los 10 min" in MENSAJES[-1] and "Nada se compra sin tu ✅" in MENSAJES[-1],
      "pulsar '🟡 SEMI ✅' cambia el modo Y explica qué hace de verdad")

# ============================================== D. 🧮 CUENTAS EN 📊 STATS
print("\nD · 🧮 cuentas de compensación en 📊 Stats (libro real)")
limpiar()
ops = [{"resultado": "ganada", "pnl": 7.65, "stake_dolares": 5.0, "question": f"g{i}",
        "franja": "base", "fuente_verdad": "cobro_real"} for i in range(25)]
ops += [{"resultado": "perdida", "pnl": -8.31, "stake_dolares": 5.0, "question": f"p{i}",
         "franja": "base", "fuente_verdad": "fill"} for i in range(25)]
ops.append({"resultado": "anulada", "pnl": -0.05, "stake_dolares": 5.0,
            "question": "anulada", "franja": "base"})
ESTADO["trades_copiados"], ESTADO["historial"] = ops, []
s = bot.calcular_stats()
check(26, s["wins"] == 25 and s["losses"] == 25 and s["anuladas"] == 1
      and round(s["pnl_wins"], 2) == 191.25 and round(s["pnl_losses"], 2) == -207.75
      and round(s["stake_wins"], 2) == 125.0,
      "calcular_stats acumula los brutos por banda (anuladas fuera)")
bot.cmd_stats(CHAT)
t = MENSAJES[-1]
check(27, "🧮 *CUENTAS DE COMPENSACIÓN*" in t and "*+$7.65*" in t and "*-$8.31*" in t,
      "medias reales: +$7.65 por ganada / −$8.31 por pérdida")
check(28, "*1.09 victorias*" in t, "1.09 victorias por cada derrota (8.31 ÷ 7.65)")
check(29, "*52.1%*" in t and "*50.0%*" in t and "❌ por debajo" in t,
      "win-rate de equilibrio 52.1% frente al tuyo 50.0% → por debajo")
check(30, "cuota 1.5 → 3.3" in t and "cuota 2.0 → 1.7" in t and "cuota 2.5 → 1.1" in t
      and "prob × cuota ≥ 1.05" in t,
      "tabla de victorias por cuota + recordatorio del filtro")

# ============================================== E. PASADAS POR MODO
print("\nE · auto_pasada/auto_loop: SEMI propone, AUTO ejecuta, OFF nada")
PROPUESTAS_HECHAS = []
bot.listar_combos = lambda: list(SEL)
bot.seleccionar_combo = lambda legs, estado: list(SEL)
bot.proponer_combo_semi = lambda cid, sel, estado=None: PROPUESTAS_HECHAS.append(cid)
for modo, etiqueta in (("SEMI", "propone"), ("AUTO", "ejecuta"), ("OFF", "nada")):
    EJECUTADAS.clear(); PROPUESTAS_HECHAS.clear()
    bot.MODO_OPERACION = modo
    bot.ejecutar_combo_rfq = lambda *a, **k: EJECUTADAS.append((a, k)) or (True, "OK")
    bot.auto_pasada(CHAT)
    if etiqueta == "propone":
        check(31, PROPUESTAS_HECHAS == [CHAT] and not EJECUTADAS,
              "SEMI: PROPONE y no compra")
    elif etiqueta == "ejecuta":
        check(32, EJECUTADAS and not PROPUESTAS_HECHAS, "AUTO: ejecuta sin proponer")
    else:
        check(33, not EJECUTADAS and not PROPUESTAS_HECHAS, "OFF: ni propone ni compra")
check(34, 'if MODO_OPERACION in ("AUTO", "SEMI") and CHAT_ID and ahora >= NEXT_PASADA_TS' in SRC
      and 'if MODO_OPERACION not in ("AUTO", "SEMI")' in SRC,
      "auto_loop y auto_pasada despiertan también en SEMI")
check(35, 'data.startswith("sm:")' in SRC and 'data.startswith("smx:")' in SRC
      and SRC.count("def respuesta_propuesta(") == 1
      and SRC.count("def ejecutar_semi_aprobado(") == 1,
      "callbacks ✅/❌ cableados en procesar_callback")

# ============================================== F. COSMÉTICOS + NO-REGRESIÓN
print("\nF · cosméticos y no-regresión")
check(36, "v12.8.1 cargado" not in SRC and 'log(f"v12.8.4 cargado · modo=' in SRC,
      "la línea de arranque ya no dice v12.8.1")
check(37, 'op["fuente_verdad"] = r.get("fuente")' in SRC
      and 'op["cobro_real"] = r["cobro_real"]' in SRC,
      "sincronizar_operaciones guarda cobro_real/fuente (anuladas)")
check(38, SRC.count('if float(v.get("importe") or 0) > 0.000001}') == 2
      and "saldo 0 on-chain\", que no es un reclamo pendiente" in SRC,
      "'sin cobrar' filtra importe 0 en /status y en 🔍 (7 avisos → 4 reales)")
_rec7 = {f"t{i}": {"importe": (0.0 if i < 3 else 20.75)} for i in range(7)}
_rec_f = {k: v for k, v in _rec7.items() if float(v.get("importe") or 0) > 0.000001}
check(38.1, len(_rec_f) == 4 and round(sum(float(v["importe"]) for v in _rec_f.values()), 2) == 83.0,
      "con el filtro: 4 posiciones · $83.00 (antes salían 7 · $82.98)")
check(39, "🟡 Propuestas SEMI vivas" in SRC and SRC.count("def cmd_leer_ahora(") == 1,
      "🔍 Leer ahora también lista las propuestas SEMI vivas")
check(40, all(f"def {f}(" in SRC for f in
              ("curar_abiertas", "reclamar_check", "_reparto_mapa", "situacion_op",
               "precio_vivo_op", "teclado_fijo", "intervalo_min_actual", "stake_para",
               "lanzar_combo_manual"))
      and SRC.count("def main()") == 1 and SRC.count("def ejecutar_combo_rfq(") == 1,
      "v12.8.2/v12.8.3 intactos (curación, reparto, situación real, teclado)")
check(41, "v12.8.4" in SRC.splitlines()[3] and "v12.8.4: 🟡 SEMI DE VERDAD" in SRC
      and SRC.count("*POLY COMBOS BOT v12.8.4*") == 1
      and SRC.count("*ESTADO v12.8.4 (Combos)*") == 1
      and SRC.count("*RECLAMAR v12.8.4*") == 1,
      "versiones v12.8.4 en cabecera, /start, /status y /reclamar")

# ================================ G. 🟡 EL MODO GUARDADO SOBREVIVE AL REINICIO
print("\nG · el modo guardado sobrevive al reinicio (main() no lo leía)")
limpiar()
# guardar_estado PERSISTE de verdad (como el fichero del server): cmd_modo guarda
# modo=SEMI y programar_paso relee+reguarda el estado, así que el modo tiene que
# seguir ahí después de las dos escrituras.
bot.guardar_estado = lambda e: ESTADO.update(e)
ESTADO["modo"] = "AUTO"
bot.MODO_OPERACION = "AUTO"
bot.cmd_modo(CHAT, "SEMI")                       # pulsas 🟡 SEMI
check(42, ESTADO.get("modo") == "SEMI" and bot.MODO_OPERACION == "SEMI"
      and ESTADO.get("proximo_paso_ts", 0) > time.time(),
      "cmd_modo persiste modo=SEMI (y sobrevive a la 2ª escritura de programar_paso)")
bot.MODO_OPERACION = "AUTO"                      # …y el proceso muere/reinicia
check(43, bot.restaurar_modo(json.loads(json.dumps(ESTADO))) == "SEMI"
      and bot.MODO_OPERACION == "SEMI",
      "al arrancar, restaurar_modo devuelve SEMI (antes volvía en AUTO siempre)")
bot.MODO_OPERACION = "AUTO"
check(44, bot.restaurar_modo({"modo": "off"}) == "OFF"
      and bot.restaurar_modo({}) == "OFF"          # sin clave: no revienta, no cambia
      and bot.restaurar_modo({"modo": "chirimbolo"}) == "OFF"
      and "restaurar_modo(_est0)" in SRC and SRC.count("def restaurar_modo(") == 1,
      "tolera OFF, minúsculas, claves ausentes y basura; main() lo llama")

# ------------------------------------------------------------------- resumen
pasan = sum(1 for _, p in ok if p)
print(f"\n{'=' * 66}\nRESULTADO: {pasan}/{len(ok)} checks OK"
      + (f" · FALLAN: {fallos}" if fallos else " · TODO EN VERDE ✅"))
print(f"bot: {RUTA} · {len(SRC.splitlines())} líneas")
sys.exit(0 if not fallos else 1)
