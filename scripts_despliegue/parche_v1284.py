#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parche_v1284.py — v12.8.3 → v12.8.4  (🟡 SEMI de verdad + ⚖️ ventaja 5%)
========================================================================
Lo pidió el usuario el 11-sep noche: "el botón de SEMI, el que tengo yo que
aceptar las operaciones, no está funcionando bien".

DIAGNÓSTICO (confirmado en el código): SEMI era un modo MUERTO.
    def auto_pasada(chat_id):
        if MODO_OPERACION != "AUTO":      # ← en SEMI sale al instante
            return
    def auto_loop():
        if MODO_OPERACION == "AUTO" and CHAT_ID and ahora >= NEXT_PASADA_TS:
                                          # ← en SEMI ni escanea
O sea: 🟡 SEMI ≡ 🔴 OFF (sólo guardaba el modo y contestaba "Modo: SEMI"). No
existía en ningún sitio el flujo "te propongo y tú apruebas": se perdió en la
reescritura v11 (RFQ).

CAMBIOS
  1) 🟡 SEMI DE VERDAD. En SEMI el bot escanea igual que en AUTO y, cuando hay
     un combo válido, PROPONE: mensaje con legs, cuota est., probabilidad,
     stake previsto y botones ✅ Aceptar y comprar / ❌ Descartar. Nada se compra
     sin tu ✅. La propuesta CADUCA a los 10 min (PROPUESTA_VALIDA_S) y los
     botones se sustituyen por el resultado (✅ aceptada / ❌ descartada /
     ⌛ caducada) para que no se pueda aprobar dos veces. Al aceptar se pide una
     cotización NUEVA —las del RFQ viven segundos: esta noche expires_at ≈ +5 s—
     y se ejecuta por la misma ruta que AUTO (stake dinámico, tope diario,
     anti-duplicados y el filtro de ventaja). Si al aceptar ya no hay margen, te
     lo dice y NO compra ($0).
  2) ⚖️ FILTRO DE VENTAJA 5% (VENTAJA_MIN_EV). Un combo sólo se compra si
     prob × cuota_real ≥ 1.05, siendo prob = 1/cuota_est (el precio implícito de
     los legs). Antes sólo se exigía que el RFQ no fuera PEOR que el mercado
     (edge ≥ −0.5%), o sea esperanza ≈ 0: comprar algo que sólo empata es
     perder. Vale para AUTO y para SEMI; los botones manuales 🚀/💥 siguen
     operando siempre (manual=True) porque los eliges tú.
     Caso real de esta noche (log 21:11): cuota est 1.25, RFQ 1.21 → EV −3.2%
     → ya se omitió; con el filtro se omite también cualquier RFQ por debajo de
     1.31 (= 1.25 × 1.05).
  3) ✅ TICK VERDE EN EL MODO ACTIVO (🟢 AUTO ✅ / 🟡 SEMI ✅ / 🔴 OFF ✅) y
     `_sin_tick()` en el handler para que los botones marcados sigan casando.
     cmd_modo ahora EXPLICA qué hace cada modo (SEMI ya no es un OFF disfrazado).
  4) 🧮 CUENTAS DE COMPENSACIÓN en 📊 Stats, con TU libro real: media por
     ganada, media por pérdida, victorias necesarias por derrota, win-rate de
     equilibrio frente al tuyo, y tabla de victorias para recuperar una derrota
     media a cuota 1.5/2.0/2.5 con tu stake medio.
  5) 🟡 EL MODO GUARDADO SOBREVIVE AL REINICIO. main() restauraba intervalo,
     stake, tope y probabilidad… pero NO estado["modo"]: el bot arrancaba SIEMPRE
     en AUTO. O sea, pulsabas 🟡 SEMI y en cuanto había un despliegue, una caída o
     un reinicio del server volvías al automático sin aviso (otra mitad de por qué
     "el botón SEMI no funciona bien"). Ahora restaurar_modo() lo recupera.
  6) Cosméticos de v12.8.3: la línea de arranque decía "v12.8.1 cargado"; las
     ops anuladas archivadas por sincronizar_operaciones no guardaban cobro_real
     ni fuente_verdad; /status y 🔍 contaban como "sin cobrar" los avisos con
     importe 0 (que son "ya revisado: saldo 0 on-chain", no dinero pendiente) →
     ahora sólo cuentan los de importe > 0 (7 · $82.98 → 4 · $82.98).

NO se toca: RFQ (crear/firmar/aceptar), cierre 🔒, /reclamar, auditoría,
curación por evidencia de cadena (v12.8.3), ni las franjas manuales.
Uso:  python3 parche_v1284.py <bot_v1283.py> <bot_v1284.py>
"""
import sys, io, hashlib

NUEVAS = r'''
# ============================================
# v12.8.4: 🟡 SEMI DE VERDAD (propuesta + ✅/❌, caduca a los 10 min)
# ============================================
PROPUESTAS = {}          # h8 -> (ts, sel, chat_id, texto)


def _prune_propuestas():
    """v12.8.4: tira las propuestas caducadas (las vivas se quedan)."""
    global PROPUESTAS
    ahora = time.time()
    PROPUESTAS = {k: v for k, v in PROPUESTAS.items()
                  if ahora - v[0] < PROPUESTA_VALIDA_S}


def _sin_tick(t):
    """✅ v12.8.4: quita el tick de un texto de botón para casar con el handler
    (el botón activo llega como "🟡 SEMI ✅" y el handler compara "🟡 SEMI")."""
    return str(t or "").replace(TICK_ACTIVO, "").strip()


def proponer_combo_semi(chat_id, sel, estado=None):
    """🟡 v12.8.4: en SEMI el bot NO compra: PROPONE el combo con botones
    ✅ Aceptar / ❌ Descartar y espera. Caduca a los PROPUESTA_VALIDA_S (10 min).
    No reserva la huella (si no, el anti-duplicados bloquearía tu propio ✅);
    la reserva la hace ejecutar_combo_rfq al aceptar, como en AUTO."""
    _prune_propuestas()
    estado = estado if estado is not None else cargar_estado()
    pids = [str(c.get("yes_token")) for c in sel]
    if huella_combo(pids) in (estado.get("combos_rfq", {}) or {}).get("huellas", {}):
        log("  [SEMI] combo ya operado: no se propone")
        return None
    h8 = hash8_sel(sel)
    if any(hash8_sel(v[1]) == h8 for v in PROPUESTAS.values()):
        log(f"  [SEMI] ya hay una propuesta viva para este combo ({h8})")
        return None
    prod = 1.0
    for c in sel:
        prod *= float(c.get("yes_price") or 0)
    cuota_est = round(1 / prod, 2) if prod > 0 else 0.0
    try:
        stake = float(stake_operacion(estado, cuota_est, cuota_est) or 0)
    except Exception:
        stake = 0.0
    if stake < STAKE_MIN_AUTO:
        stake = STAKE_MIN_AUTO
    gana = round(stake * max(0.0, cuota_est - 1), 2)
    cuota_min_real = round(cuota_est * (1 + VENTAJA_MIN_EV), 2)
    caduca = datetime.fromtimestamp(time.time() + PROPUESTA_VALIDA_S,
                                    tz=timezone.utc).strftime("%H:%M:%S")
    txt = (f"🟡 *SEMI — PROPUESTA* (caduca en {int(PROPUESTA_VALIDA_S // 60)} min)\n\n"
           f"🎫 Combo de {len(sel)} legs · cuota est. *{cuota_est:.2f}* · "
           f"prob *{prod * 100:.0f}%*\n")
    for c in sel:
        txt += (f"   · {str(c.get('question') or '?')[:64]} "
                f"(p={float(c.get('yes_price') or 0):.2f})\n")
    txt += (f"💵 Stake previsto *${stake:.2f}* · ganancia si acierta *+${gana:.2f}*\n"
            f"⚖️ Al aceptar pediré cotización NUEVA (las del RFQ viven segundos) y sólo "
            f"compro si mejora el mercado ≥{int(VENTAJA_MIN_EV * 100)}% "
            f"(cuota real ≥{cuota_min_real:.2f}). Si no, te lo digo y no gasto nada.\n"
            f"🔢 hoy {ops_pagadas_hoy(estado)}/{max_ops(estado)} ops · ⏱ caduca {caduca} UTC")
    kb = {"inline_keyboard": [
        [{"text": "✅ Aceptar y comprar", "callback_data": f"sm:{h8}"},
         {"text": "❌ Descartar", "callback_data": f"smx:{h8}"}]]}
    PROPUESTAS[h8] = (time.time(), sel, chat_id, txt)
    log(f"  [SEMI] propuesta {h8}: {len(sel)} legs · cuota est {cuota_est} · "
        f"prob {prod:.2f} · stake ${stake} · caduca en {int(PROPUESTA_VALIDA_S // 60)} min")
    return enviar(chat_id, txt, kb)


def ejecutar_semi_aprobado(chat_id, sel, h8=None):
    """✅ v12.8.4: aprobaste la propuesta → se ejecuta por la MISMA ruta que
    AUTO (stake dinámico con la cuota real, filtro de ventaja, tope diario y
    anti-duplicados). Hilo propio serializado con PASADA_LOCK."""
    PROPUESTAS.pop(h8, None)
    titulo = " + ".join(str(c.get("question", "?"))[:38] for c in sel)

    def _run():
        try:
            with PASADA_LOCK:
                estado = cargar_estado()
                _mx, _hoy = max_ops(estado), ops_pagadas_hoy(estado)
                if _hoy >= _mx:
                    return enviar(chat_id, f"⛔ *Tope diario alcanzado* ({_hoy}/{_mx} ops pagadas hoy)")
                pids = [str(c.get("yes_token")) for c in sel]
                if huella_combo(pids) in (estado.get("combos_rfq", {}) or {}).get("huellas", {}):
                    return enviar(chat_id, f"⛔ *Combo ya operado* (anti-duplicados):\n{titulo[:80]}")
                log(f"[SEMI] aprobado con ✅: {titulo[:70]}")
                enviar(chat_id, f"✅ *SEMI aprobado* — pidiendo cotización nueva…\n📌 {titulo[:80]}")
                ok, res = ejecutar_combo_rfq(sel, chat_id=chat_id, franja="base")
                if not ok:
                    enviar(chat_id, f"❌ *No comprado* (tu ✅ no ha gastado nada)\n"
                                    f"📌 {titulo[:70]}\nMotivo: `{str(res)[:70]}`")
        except Exception as e:
            log(f"[SEMI] error: {e}")
            try:
                enviar(chat_id, f"❌ Error ejecutando la propuesta: {str(e)[:100]}")
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()


def _marcar_propuesta(chat_id, message_id, etiqueta):
    """v12.8.4: sustituye los botones de la propuesta por su resultado, para que
    nadie pueda pulsar ✅ dos veces ni aceptar una propuesta caducada."""
    if not chat_id or not message_id:
        return
    try:
        telegram_api("editMessageReplyMarkup", {
            "chat_id": chat_id, "message_id": message_id,
            "reply_markup": json.dumps({"inline_keyboard": [
                [{"text": etiqueta, "callback_data": "noop"}]]})})
    except Exception as e:
        log(f"  [SEMI] sin editar botones: {str(e)[:60]}")


def respuesta_propuesta(cbq, h8, aceptar):
    """v12.8.4: atiende ✅/❌ de una propuesta SEMI, con caducidad de 10 min."""
    cbid = cbq.get("id")
    msg = cbq.get("message") or {}
    cid = (msg.get("chat") or {}).get("id") or (cbq.get("from") or {}).get("id")
    mid = msg.get("message_id")
    hit = PROPUESTAS.get(h8)
    if not hit or time.time() - hit[0] > PROPUESTA_VALIDA_S:
        PROPUESTAS.pop(h8, None)
        telegram_api("answerCallbackQuery", {
            "callback_query_id": cbid, "show_alert": True,
            "text": (f"⌛ Propuesta caducada o ya atendida (valía "
                     f"{int(PROPUESTA_VALIDA_S // 60)} min). No se compra dos veces: "
                     "la pasada SEMI siguiente te propondrá otro combo.")})
        _marcar_propuesta(cid, mid, "⌛ caducada")
        log(f"  [SEMI] propuesta {h8} caducada (pulsada fuera de tiempo)")
        return
    if not aceptar:
        PROPUESTAS.pop(h8, None)
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid, "text": "❌ Descartada"})
        _marcar_propuesta(cid, mid, "❌ descartada")
        log(f"  [SEMI] propuesta {h8} descartada por el usuario")
        return enviar(cid, "❌ *Propuesta descartada* — no se ha comprado nada ($0).\n"
                           "_La pasada SEMI siguiente te propondrá otro combo._")
    telegram_api("answerCallbackQuery", {"callback_query_id": cbid,
                                         "text": "✅ Aceptada, pidiendo cotización…"})
    _marcar_propuesta(cid, mid, "✅ aceptada")
    return ejecutar_semi_aprobado(cid, hit[1], h8)


'''


def aplicar(src):
    cambios = []

    def sustituir(viejo, nuevo, etiqueta):
        nonlocal src
        n = src.count(viejo)
        if n != 1:
            raise SystemExit(f"[parche v12.8.4] '{etiqueta}': {n} coincidencias (esperaba 1)")
        src = src.replace(viejo, nuevo, 1)
        cambios.append(etiqueta)

    # ---------------------------------------------------------- 0) versiones
    sustituir('POLY COMBOS BOT v12.8.3 — COMBOS REALES (parlays multi-leg) via RFQ',
              'POLY COMBOS BOT v12.8.4 — COMBOS REALES (parlays multi-leg) via RFQ',
              "cabecera v12.8.4")
    sustituir('    log("v12.8.3 iniciado")', '    log("v12.8.4 iniciado")',
              "log de arranque v12.8.4")
    sustituir('    txt = ("💰 *RECLAMAR v12.8.3*\\n\\n"',
              '    txt = ("💰 *RECLAMAR v12.8.4*\\n\\n"', "título /reclamar v12.8.4")
    sustituir('    texto = (f"🤖 *POLY COMBOS BOT v12.8.3*\\n\\n"',
              '    texto = (f"🤖 *POLY COMBOS BOT v12.8.4*\\n\\n"', "título /start v12.8.4")
    sustituir('    texto = (f"📊 *ESTADO v12.8.3 (Combos)*\\n\\n"',
              '    texto = (f"📊 *ESTADO v12.8.4 (Combos)*\\n\\n"', "título /status v12.8.4")
    sustituir('    log(f"v12.8.1 cargado · modo={MODO_OPERACION}',
              '    log(f"v12.8.4 cargado · modo={MODO_OPERACION}',
              "línea 'cargado' (decía v12.8.1)")

    sustituir('   v12.8.3: EL PANEL DICE LA VERDAD + ✅ + 🔍.',
              '''   v12.8.4: 🟡 SEMI DE VERDAD + ⚖️ VENTAJA MÍNIMA 5%. SEMI era un modo muerto
   (auto_pasada salía al instante si el modo no era AUTO, y auto_loop ni
   escaneaba): pulsar 🟡 dejaba el bot parado, sin nada que aprobar. Ahora en
   SEMI el bot busca y TE PROPONE el combo con ✅ Aceptar / ❌ Descartar, la
   propuesta caduca a los 10 min y al aceptar se pide una cotización nueva
   (las del RFQ viven segundos) y se ejecuta por la ruta de AUTO. Además sólo
   compra si prob × cuota_real ≥ 1.05 (antes bastaba con que el RFQ no fuera
   peor que el mercado, o sea esperanza ≈ 0). Además el MODO guardado ya
   sobrevive al reinicio: main() no leía estado["modo"], así que el bot volvía
   siempre en AUTO por mucho que hubieras pulsado 🟡 SEMI. Y: ✅ verde en el botón
   del modo activo, 🧮 cuentas de compensación en 📊 Stats (victorias por
   derrota, win-rate de equilibrio) y cosméticos (arranque decía v12.8.1,
   anuladas sin cobro_real, "sin cobrar" contaba avisos de importe 0).
   v12.8.3: EL PANEL DICE LA VERDAD + ✅ + 🔍.''',
              "changelog v12.8.4 en la cabecera")

    # ---------------------------------------------- 1) constantes nuevas
    sustituir('RFQ_TIMEOUT_FILL_S = 45    # espera de FILLED tras aceptar',
              '''RFQ_TIMEOUT_FILL_S = 45    # espera de FILLED tras aceptar
# v12.8.4: SEMI de verdad + filtro de ventaja
PROPUESTA_VALIDA_S = 600   # lo que vive una propuesta 🟡 SEMI antes de caducar
VENTAJA_MIN_EV = 0.05      # exige prob × cuota_real ≥ 1.05 (5% de ventaja real)''',
              "constantes PROPUESTA_VALIDA_S y VENTAJA_MIN_EV")

    # ---------------------------------------------- 2) teclado: ✅ en el modo
    sustituir('''    act = intervalo_min_actual()
    fila_int = [{"text": f"⏱ {m}m" + (TICK_ACTIVO if act == m else "")}
                for m in INTERVALOS_MIN]''',
              '''    act = intervalo_min_actual()
    fila_int = [{"text": f"⏱ {m}m" + (TICK_ACTIVO if act == m else "")}
                for m in INTERVALOS_MIN]
    # v12.8.4: también el MODO activo lleva su ✅ (🟢 AUTO ✅ / 🟡 SEMI ✅ / 🔴 OFF ✅)
    _modo_txt = {"AUTO": "🟢 AUTO", "SEMI": "🟡 SEMI", "OFF": "🔴 OFF"}.get(
        str(MODO_OPERACION or "").upper())
    fila_modo = [{"text": t + (TICK_ACTIVO if t == _modo_txt else "")}
                 for t in ("🟢 AUTO", "🟡 SEMI", "🔴 OFF")]''',
              "teclado_fijo: fila de modo con ✅")

    sustituir('            [{"text": "🟢 AUTO"}, {"text": "🟡 SEMI"}, {"text": "🔴 OFF"}],',
              '            fila_modo,',
              "teclado_fijo usa fila_modo")

    sustituir('''El botón ⏱ del intervalo ACTIVO sale con un
    tick verde al final ("⏱ 10m ✅") para ver de un golpe cada cuánto lee el bot;''',
              '''El botón ⏱ del intervalo activo y el del MODO
    activo salen con un tick verde al final ("⏱ 10m ✅", "🟡 SEMI ✅") para ver de
    un golpe cada cuánto lee el bot y en qué modo está;''',
              "docstring teclado_fijo (modo + intervalo)")

    sustituir('''    cambiar el intervalo. El tick va AL FINAL para que el handler
    (text.startswith("⏱")) siga casando. Añade el botón 🔍 Leer ahora."""''',
              '''    cambiar el intervalo o el modo. El tick va AL FINAL para que los handlers
    sigan casando: el de ⏱ por startswith y los de modo vía _sin_tick() (v12.8.4).
    Añade el botón 🔍 Leer ahora."""''',
              "docstring teclado_fijo (tick AL FINAL)")

    # ------------------------------- 3) handler: botones de modo con tick ✅
    sustituir('''    elif text == "🟢 AUTO":
        return cmd_modo(chat_id, "AUTO")
    elif text == "🟡 SEMI":
        return cmd_modo(chat_id, "SEMI")
    elif text == "🔴 OFF":
        return cmd_modo(chat_id, "OFF")''',
              '''    elif _sin_tick(text) == "🟢 AUTO":     # v12.8.4: el activo llega con ✅
        return cmd_modo(chat_id, "AUTO")
    elif _sin_tick(text) == "🟡 SEMI":
        return cmd_modo(chat_id, "SEMI")
    elif _sin_tick(text) == "🔴 OFF":
        return cmd_modo(chat_id, "OFF")''',
              "handler de modo tolerante al ✅")

    # ---------------------------------------------- 4) cmd_modo explica SEMI
    sustituir('''def cmd_modo(chat_id, modo):
    global MODO_OPERACION
    modo = modo.upper()
    if modo not in ("AUTO", "SEMI", "OFF"):
        return enviar(chat_id, "❌ AUTO, SEMI, OFF")
    MODO_OPERACION = modo
    estado = cargar_estado()
    estado["modo"] = modo
    guardar_estado(estado)
    enviar(chat_id, f"*Modo: {modo}*")
    if modo == "AUTO":
        programar_pasada_ahora()   # v11.3: sin hilo paralelo''',
              '''def cmd_modo(chat_id, modo):
    """🟢/🟡/🔴 v12.8.4: cambia el modo Y explica qué hace cada uno de verdad.
    AUTO = abre solo. SEMI = propone con ✅/❌ y no compra sin tu visto bueno
    (antes SEMI no hacía NADA: era un OFF disfrazado). OFF = parado."""
    global MODO_OPERACION
    modo = modo.upper()
    if modo not in ("AUTO", "SEMI", "OFF"):
        return enviar(chat_id, "❌ AUTO, SEMI, OFF")
    MODO_OPERACION = modo
    estado = cargar_estado()
    estado["modo"] = modo
    guardar_estado(estado)
    log(f"modo -> {modo}")
    if modo == "AUTO":
        programar_pasada_ahora()   # v11.3: sin hilo paralelo
        return enviar(chat_id, f"🟢 *Modo: AUTO* ✅\\n"
                               f"Abre combos solo cada {INTERVALO_AUTO_S // 60} min "
                               f"(cuota {CUOTA_MIN}-{CUOTA_MAX} · prob ≥{prob_nivel_txt(prob_min_auto(estado))} · "
                               f"tope {max_ops(estado)}/día) y sólo si la cotización mejora el "
                               f"mercado ≥{int(VENTAJA_MIN_EV * 100)}%.")
    if modo == "SEMI":
        # v12.8.4: en SEMI también hay pasadas, pero PROPONEN en vez de comprar
        programar_paso(time.time() + INTERVALO_AUTO_S)
        return enviar(chat_id, f"🟡 *Modo: SEMI* ✅\\n"
                               f"Cada {INTERVALO_AUTO_S // 60} min busco y *te propongo* el mejor combo "
                               f"con botones ✅ Aceptar / ❌ Descartar.\\n"
                               f"*Nada se compra sin tu ✅* · la propuesta caduca a los "
                               f"{int(PROPUESTA_VALIDA_S // 60)} min.\\n"
                               f"_Al aceptar pido cotización nueva y sólo compro si mejora el "
                               f"mercado ≥{int(VENTAJA_MIN_EV * 100)}%; si no, te lo digo y no gasto nada._\\n"
                               f"🔍 *Leer ahora* te enseña qué propondría, sin esperar.")
    return enviar(chat_id, "🔴 *Modo: OFF* ✅\\nNo abro ni propongo nada. Siguen activos los "
                           "paneles, la auto-curación 🩺, /reclamar 💰 y los botones "
                           "manuales 🚀/💥.")''',
              "cmd_modo: SEMI explicado + horario")

    # ---------------------------------------------- 5) auto_loop/auto_pasada
    sustituir('''    if MODO_OPERACION != "AUTO":
        return
    log("[AUTO] pasada (combos RFQ v11)")''',
              '''    if MODO_OPERACION not in ("AUTO", "SEMI"):
        return                      # v12.8.4: en SEMI también hay pasada (propone)
    log(f"[{MODO_OPERACION}] pasada (combos RFQ v11)")''',
              "auto_pasada acepta SEMI")

    sustituir('''    ok, res = ejecutar_combo_rfq(sel, chat_id)
    if ok:
        log(f"  ✅ combo OK: {str(res)[:110]}")
    else:
        log(f"  ❌ combo: {str(res)[:130]}")''',
              '''    if MODO_OPERACION == "SEMI":
        # 🟡 v12.8.4: SEMI de verdad — PROPONE y espera tu ✅ (caduca a los 10 min)
        proponer_combo_semi(chat_id, sel, estado)
        return
    ok, res = ejecutar_combo_rfq(sel, chat_id)
    if ok:
        log(f"  ✅ combo OK: {str(res)[:110]}")
    else:
        log(f"  ❌ combo: {str(res)[:130]}")''',
              "auto_pasada: rama SEMI (propone, no compra)")

    sustituir('''            if MODO_OPERACION == "AUTO" and CHAT_ID and ahora >= NEXT_PASADA_TS:''',
              '''            if MODO_OPERACION in ("AUTO", "SEMI") and CHAT_ID and ahora >= NEXT_PASADA_TS:''',
              "auto_loop escanea también en SEMI")

    sustituir('''    v12.7: también dispara la AUTO-CURACIÓN (re-auditoría) sola: al arrancar y
    cada AUDITORIA_CADA_H horas, serializada con las pasadas (PASADA_LOCK)."""''',
              '''    v12.7: también dispara la AUTO-CURACIÓN (re-auditoría) sola: al arrancar y
    cada AUDITORIA_CADA_H horas, serializada con las pasadas (PASADA_LOCK).
    v12.8.4: en SEMI también hay pasada, pero PROPONE (✅/❌) en vez de comprar."""''',
              "docstring auto_loop (SEMI)")

    # ---------------------------------------- 6) callbacks ✅/❌ de la propuesta
    sustituir('''    if data.startswith("mx:") and cid:''',
              '''    if data.startswith("sm:") and cid:       # v12.8.4: 🟡 SEMI ✅ aceptar
        return respuesta_propuesta(cbq, data.split(":", 1)[1], True)
    if data.startswith("smx:") and cid:      # v12.8.4: 🟡 SEMI ❌ descartar
        return respuesta_propuesta(cbq, data.split(":", 1)[1], False)
    if data.startswith("mx:") and cid:''',
              "procesar_callback: sm:/smx:")

    # ---------------------------------------------- 7) filtro de ventaja 5%
    sustituir('''        liberar_combo(pids)
        return False, f"cuota_real_{cuota_real}_fuera"
    # v12.2: stake definitivo con la cuota REAL y la ventaja sobre los legs''',
              '''        liberar_combo(pids)
        return False, f"cuota_real_{cuota_real}_fuera"
    # ⚖️ v12.8.4: FILTRO DE VENTAJA (esperanza positiva). prob = 1/cuota_est es el
    # precio implícito de los legs, así que EV = prob × cuota_real − 1. Exigimos
    # ≥5%: un RFQ que sólo iguala al mercado (EV≈0) no compensa. Los botones
    # manuales 🚀/💥 (manual=True) siguen operando siempre: los eliges tú.
    if not manual and cuota_est > 0:
        _ev = (cuota_real / cuota_est) - 1.0
        if _ev < VENTAJA_MIN_EV:
            liberar_combo(pids)
            log(f"  ⚖️ ventaja insuficiente: RFQ {cuota_real} vs mercado ~{cuota_est} "
                f"= EV {_ev * 100:+.1f}% < {VENTAJA_MIN_EV * 100:.0f}% exigidos — NO se acepta ($0)")
            if chat_id:
                enviar(chat_id, f"⚖️ *Combo omitido por falta de ventaja* ($0)\\n"
                                f"Cuota real {cuota_real} vs mercado ~{cuota_est} = "
                                f"EV {_ev * 100:+.1f}% · se exigen ≥{VENTAJA_MIN_EV * 100:.0f}% "
                                f"(cuota ≥{cuota_est * (1 + VENTAJA_MIN_EV):.2f}).\\n"
                                f"_Comprar algo que sólo empata es perder: no se acepta._")
            return False, f"ventaja_{_ev * 100:+.1f}_insuficiente"
    # v12.2: stake definitivo con la cuota REAL y la ventaja sobre los legs''',
              "filtro de ventaja EV ≥ 5%")

    # ---------------------------------------------- 8) cuentas en calcular_stats
    sustituir('''        "total": len(copiados), "wins": 0, "losses": 0, "anuladas": 0,''',
              '''        "total": len(copiados), "wins": 0, "losses": 0, "anuladas": 0,
        # v12.8.4: brutos para las cuentas de compensación (📊 Stats)
        "pnl_wins": 0.0, "pnl_losses": 0.0, "stake_wins": 0.0, "stake_losses": 0.0,''',
              "calcular_stats: acumuladores de brutos")

    sustituir('''            # ↩️ v12.8.3: las anuladas (mercado devuelto) no son ni ✅ ni ❌
            if str(op.get("resultado")) == "anulada": s["anuladas"] += 1
            elif pnl > 0: s["wins"] += 1
            else: s["losses"] += 1''',
              '''            # ↩️ v12.8.3: las anuladas (mercado devuelto) no son ni ✅ ni ❌
            if str(op.get("resultado")) == "anulada":
                s["anuladas"] += 1
            elif pnl > 0:
                s["wins"] += 1
                s["pnl_wins"] += pnl        # v12.8.4
                s["stake_wins"] += stake
            else:
                s["losses"] += 1
                s["pnl_losses"] += pnl      # v12.8.4
                s["stake_losses"] += stake''',
              "calcular_stats: acumula brutos por banda")

    # ---------------------------------------------- 9) 🧮 cuentas en /stats
    sustituir('''    if s["mejor"]:
        m = s["mejor"]''',
              '''    # 🧮 v12.8.4: cuántas victorias compensan una derrota, con TU libro real
    if s["wins"] and s["losses"] and s["pnl_wins"] > 0 and s["pnl_losses"] < 0:
        _mw = s["pnl_wins"] / s["wins"]              # media ganada (+)
        _ml = -s["pnl_losses"] / s["losses"]         # media perdida (+)
        _sw = (s["stake_wins"] / s["wins"]) if s["wins"] else 0.0
        _wr_eq = (_ml / (_mw + _ml) * 100) if (_mw + _ml) > 0 else 0.0
        _wr_tu = s["wins"] / (s["wins"] + s["losses"]) * 100
        texto += ("\\n🧮 *CUENTAS DE COMPENSACIÓN* (tu libro real)\\n"
                  f"Media por ganada: *+${_mw:.2f}* ({s['wins']} ops)\\n"
                  f"Media por pérdida: *-${_ml:.2f}* ({s['losses']} ops)\\n"
                  f"⇒ *{_ml / _mw:.2f} victorias* por cada derrota\\n"
                  f"Win-rate de equilibrio: *{_wr_eq:.1f}%* · el tuyo: *{_wr_tu:.1f}%* "
                  + ("✅ por encima\\n" if _wr_tu >= _wr_eq else "❌ por debajo\\n"))
        if _sw > 0:
            _t = []
            for _q in (1.5, 2.0, 2.5):
                _b = _sw * (_q - 1)
                _t.append(f"cuota {_q:.1f} → {_ml / _b:.1f}" if _b > 0 else f"cuota {_q:.1f} → ∞")
            texto += (f"_Victorias para recuperar una derrota media (-${_ml:.2f}) "
                      f"apostando ${_sw:.2f}: " + " · ".join(_t) + "_\\n")
        texto += (f"_Sólo se compra con ventaja: prob × cuota ≥ {1 + VENTAJA_MIN_EV:.2f} "
                  f"(filtro activo en 🟢 AUTO y 🟡 SEMI)_\\n")
    if s["mejor"]:
        m = s["mejor"]''',
              "📊 Stats: bloque 🧮 de compensación")

    # ---------------------------------------------- 10) funciones nuevas
    sustituir('def cmd_status(chat_id):', NUEVAS + 'def cmd_status(chat_id):',
              "bloque de funciones nuevas v12.8.4 (SEMI)")

    # ------------------------------- 11) el modo guardado sobrevive al reinicio
    sustituir('def restaurar_horario():',
              '''def restaurar_modo(estado=None):
    """🟡 v12.8.4: al arrancar recupera el MODO guardado (AUTO/SEMI/OFF).
    main() NO lo leía: el bot volvía SIEMPRE en AUTO aunque hubieras pulsado
    🟡 SEMI, así que cualquier reinicio, despliegue o caída te devolvía al
    automático sin avisar (buena parte de por qué "el SEMI no funcionaba")."""
    global MODO_OPERACION
    try:
        est = estado if estado is not None else cargar_estado()
        md = str(est.get("modo") or "").upper()
    except Exception:
        md = ""
    if md in ("AUTO", "SEMI", "OFF"):
        MODO_OPERACION = md
        log(f"  modo restaurado del estado: {md}")
    else:
        log(f"  modo sin guardar en el estado → sigo en {MODO_OPERACION}")
    return MODO_OPERACION


def restaurar_horario():''',
              "restaurar_modo: el modo guardado sobrevive al reinicio")

    sustituir('''    _im = _est0.get("intervalo_min")
    if _im in INTERVALOS_MIN:
        INTERVALO_AUTO_S = _im * 60
        log(f"intervalo AUTO restaurado: {_im} min")''',
              '''    _im = _est0.get("intervalo_min")
    if _im in INTERVALOS_MIN:
        INTERVALO_AUTO_S = _im * 60
        log(f"intervalo AUTO restaurado: {_im} min")
    restaurar_modo(_est0)   # 🟡 v12.8.4: SEMI/OFF sobreviven al reinicio''',
              "main() restaura el modo guardado")

    # ---------------------------------------------- 12) cosméticos
    sustituir('''            op["pnl"] = r["pnl"]
            op["fin_real"] = r.get("fin")
            op["cerrado_en"] = datetime.now(timezone.utc).isoformat()
            nuevas.append(op)''',
              '''            op["pnl"] = r["pnl"]
            op["fin_real"] = r.get("fin")
            op["fuente_verdad"] = r.get("fuente")       # v12.8.4
            if r.get("cobro_real"):
                op["cobro_real"] = r["cobro_real"]      # v12.8.4: dinero real recibido
            op["cerrado_en"] = datetime.now(timezone.utc).isoformat()
            nuevas.append(op)''',
              "sincronizar_operaciones guarda cobro_real/fuente")

    sustituir('''    _rec = _est.get("reclamos_avisados") or {}
    _rec_txt = (f"💰 Sin cobrar (último aviso): *{len(_rec)}* "''',
              '''    # v12.8.4: sólo los avisos con dinero DE VERDAD (importe 0 = "ya revisado:
    # saldo 0 on-chain", que no es un reclamo pendiente)
    _rec = {k: v for k, v in (_est.get("reclamos_avisados") or {}).items()
            if float(v.get("importe") or 0) > 0.000001}
    _rec_txt = (f"💰 Sin cobrar (último aviso): *{len(_rec)}* "''',
              "/status: sin cobrar sólo con importe > 0")

    sustituir('''                rec = estado.get("reclamos_avisados") or {}
                if rec:''',
              '''                rec = {k: v for k, v in (estado.get("reclamos_avisados") or {}).items()
                       if float(v.get("importe") or 0) > 0.000001}   # v12.8.4
                if rec:''',
              "🔍 Leer ahora: sin cobrar sólo con importe > 0")

    sustituir('''            try:
                sal = saldo_disponible_clob()''',
              '''            try:
                _prune_propuestas()          # v12.8.4: propuestas SEMI vivas
                if PROPUESTAS:
                    _ul = max(v[0] for v in PROPUESTAS.values())
                    _q = max(0, int((PROPUESTA_VALIDA_S - (time.time() - _ul)) // 60))
                    L.append(f"🟡 Propuestas SEMI vivas: *{len(PROPUESTAS)}* "
                             f"(la última caduca en ~{_q} min)")
            except Exception:
                pass
            try:
                sal = saldo_disponible_clob()''',
              "🔍 Leer ahora: propuestas SEMI vivas")

    # ---------------------------------------------- 12) ayuda de /start
    sustituir('''             f"🔍 *Leer ahora* — lectura inmediata (bankroll, catálogo, qué abriría y estado real de cada posición). SÓLO MIRAR: no abre ni vende nada · /leer\\n"''',
              '''             f"🔍 *Leer ahora* — lectura inmediata (bankroll, catálogo, qué abriría y estado real de cada posición). SÓLO MIRAR: no abre ni vende nada · /leer\\n"
             f"🟡 *SEMI* — busco y te PROPONGO el combo con ✅ Aceptar / ❌ Descartar (caduca a los {int(PROPUESTA_VALIDA_S // 60)} min). Nada se compra sin tu ✅\\n"
             f"⚖️ Ventaja mínima *{int(VENTAJA_MIN_EV * 100)}%*: sólo compra si la cotización real mejora el mercado (prob × cuota ≥ {1 + VENTAJA_MIN_EV:.2f}). Vale en 🟢 AUTO y 🟡 SEMI; los botones 🚀/💥 siempre operan\\n"''',
              "ayuda /start: SEMI + ventaja")

    return src, cambios


if __name__ == "__main__":
    ent, sal = sys.argv[1], sys.argv[2]
    src = io.open(ent, encoding="utf-8").read()
    nuevo, cambios = aplicar(src)
    assert "v12.8.4" in nuevo.splitlines()[3], "cabecera sin v12.8.4"
    assert "v12.8.1 cargado" not in nuevo, "queda la línea v12.8.1 cargado"
    for fn in ("def proponer_combo_semi(", "def ejecutar_semi_aprobado(",
               "def respuesta_propuesta(", "def _marcar_propuesta(",
               "def _prune_propuestas(", "def _sin_tick("):
        assert nuevo.count(fn) == 1, f"{fn} debe aparecer 1 vez: {nuevo.count(fn)}"
    assert nuevo.count("PROPUESTA_VALIDA_S = 600") == 1
    assert nuevo.count("VENTAJA_MIN_EV = 0.05") == 1
    assert 'data.startswith("sm:")' in nuevo and 'data.startswith("smx:")' in nuevo
    assert nuevo.count('MODO_OPERACION in ("AUTO", "SEMI")') == 1          # auto_loop
    assert nuevo.count('MODO_OPERACION not in ("AUTO", "SEMI")') == 1      # auto_pasada
    assert nuevo.count("fila_modo") >= 2
    assert nuevo.count("_sin_tick(text)") == 3
    assert "ventaja insuficiente" in nuevo and "CUENTAS DE COMPENSACIÓN" in nuevo
    assert nuevo.count("def restaurar_modo(") == 1 and "restaurar_modo(_est0)" in nuevo
    assert nuevo.count("def cmd_status(") == 1 and nuevo.count("def main()") == 1
    assert nuevo.count("def teclado_fijo(") == 1 and nuevo.count("def cmd_leer_ahora(") == 1
    assert nuevo.count("def curar_abiertas(") == 1                      # v12.8.3 intacto
    io.open(sal, "w", encoding="utf-8").write(nuevo)
    print(f"✅ v12.8.4 generado: {sal} · {len(cambios)} cambios:")
    for c in cambios:
        print(f"     · {c}")
    print(f"   líneas: {len(nuevo.splitlines())} · md5 {hashlib.md5(nuevo.encode()).hexdigest()}")
