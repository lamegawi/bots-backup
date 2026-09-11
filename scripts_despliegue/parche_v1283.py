#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parche_v1283.py — v12.8.2 → v12.8.3  (panel que dice la verdad + ✅ + 🔍)
=========================================================================
Pedidos del usuario (11-sep noche):
  · "los botones del tiempo … el que esté activo se ponga con un tick verde
    para saber en qué tiempo de espera para leer es el que está activado"
  · "para volver a recargar, para leer"  → botón 🔍 Leer ahora (SÓLO MIRAR:
    elige el usuario; no abre ni vende nada).
Más los 4 arreglos de la v12.8.3 que ya estaban propuestos.

CAMBIOS
  1) ✅ TICK VERDE EN EL BOTÓN ⏱ ACTIVO. `TECLADO_FIJO` deja de ser un dict
     estático y pasa a ser `teclado_fijo()`, que se reconstruye en CADA mensaje
     (Telegram sólo refresca un teclado cuando llega uno nuevo). El botón del
     intervalo activo sale "⏱ 10m ✅"; los demás, sin tick. El tick va AL FINAL
     para que `text.startswith("⏱")` del handler siga casando.
  2) 🔍 LEER AHORA (nuevo botón + /leer): lectura inmediata en un hilo propio,
     SIN PASADA_LOCK y sin tocar el estado: bankroll, catálogo RFQ, qué combo
     abriría (y por qué no), cada posición abierta con su situación REAL y lo
     que hay sin cobrar. No abre, no vende, no archiva.
  3) ⏸ MERCADO SUSPENDIDO / ↩️ ANULADO en cristiano (`situacion_mercado`,
     `situacion_op`): el CLOB dice active=False + accepting_orders=False ⇒ no
     hay libro, no se puede vender ni resolver, y se muestra la fecha de
     resolución prevista (end_date_iso → Madrid). Es el caso de Seyboth Wild
     (partido aplazado al 15-sep): antes salía "precio ahora: n/d" y ya está.
  4) ÚLTIMO PRECIO PUBLICADO cuando /midpoint da 404 (`precio_vivo_op`): el
     mercado del CLOB trae `price` por cara; con eso un mercado suspendido
     SÍ tiene valor en el panel (Seyboth 0.559 → $10.96 sobre 19.63 sh),
     etiquetado "últ. precio (libro cerrado)" para no vender humo.
  5) 🧹 CURACIÓN POR EVIDENCIA DE CADENA (`fills_wallet` + `casar_fills` +
     `curar_abiertas`): los registros de ABIERTAS se casan con los fills REALES
     de data-api /activity?type=TRADE (mismo token, shares ±0.05, ±1 h, cada
     fill se usa una vez). Los que se quedan sin fill son DUPLICADOS FANTASMA y
     los registros vacíos son BASURA: ambos salen de Abiertas a
     estado["descartadas"] (no se borran: quedan auditables). Sin prueba no se
     toca nada (si un token no aparece en /activity, la op se queda).
     Caso real verificado el 11-sep: Barranquilla tenía 4 registros y en cadena
     sólo hay 2 fills (03:15:06 y 03:20:52, 9.9 sh a $4.95 cada uno).
  6) ↩️ MERCADOS ANULADOS: `resolver_operacion()` (rama SIMPLE) ya no espera
     para siempre cuando el mercado cierra SIN ganador declarado. Si la wallet
     YA cobró (REDEEM casado por token o título) se archiva con el dinero REAL
     recibido. Barranquilla cerró anulada: 19.8 tokens devueltos a $0.50 =
     $9.90 (lo mismo que costó) ⇒ PnL ≈ $0, no "+$4.90 por cada fill".
  7) 💰 REPARTO DEL COBRO (`_reparto_mapa`/`reparto_cobro`): el usdcSize de un
     REDEEM se reparte entre TODOS los fills del mismo mercado en proporción a
     sus shares. Antes cada fill se anotaba el cobro ENTERO (con 4 registros
     fantasma de Barranquilla eso habría inventado +$39.60 cobrados).
  8) "anulada" como tercer resultado (ni ✅ ni ❌): stats, /cerradas y la
     auditoría lo cuentan aparte; el PnL sigue sumando (−$0.05 × 2 = −$0.10).
  9) Versiones: cabecera, /start, /status y /reclamar a v12.8.3 (en v12.8.2 se
     quedaron en v12.8.1).

NO se toca: RFQ, ejecución, cierre 🔒, /reclamar (lógica), migraciones, ni las
4 ops de agosto inyectadas (están en historial, la curación sólo mira Abiertas).
Uso:  python3 parche_v1283.py <bot_v1282.py> <bot_v1283.py>
"""
import sys, io, hashlib

# =====================================================================
# BLOQUE DE FUNCIONES NUEVAS (se inserta antes de `def cmd_status`)
# =====================================================================
NUEVAS = r'''
# ============================================
# v12.8.3: SITUACIÓN REAL DEL MERCADO + PRECIO DE RESPALDO
# ============================================
def situacion_mercado(cid):
    """v12.8.3: estado REAL de un mercado del CLOB, en cristiano.
    → (clave, texto) con clave ∈ vivo|suspendido|sin_ganador|resuelto|sin_datos.
      · suspendido    = active=False y/o accepting_orders=False sin cerrar: NO
        hay libro ⇒ no se puede vender ni resolver (partido aplazado).
      · sin_ganador   = cerrado sin ganador declarado: normalmente ANULADO, los
        tokens se devuelven a ~$0.50 (explica cobros menores que las shares).
    Verificado el 11-sep: Seyboth Wild (atp-wild-ferrar-2026-09-08) →
    closed=False, active=False, accepting_orders=False, end 2026-09-15T00:00Z;
    Barranquilla (wta-pareja-stefani-2026-09-07) → closed=True, las DOS caras
    winner=False y price 0.5, y la wallet cobró $9.90 por 19.8 tokens."""
    m = mercado_clob(str(cid or ""))
    if not m:
        return "sin_datos", "❔ sin datos del mercado (CLOB/Gamma no responden)"
    toks = m.get("tokens") or []
    if any(tk.get("winner") for tk in toks):
        return "resuelto", "🏁 resuelto (ganador declarado)"
    if m.get("closed"):
        return "sin_ganador", ("↩️ cerrado SIN ganador declarado (anulado): los tokens "
                               "se devuelven a ~$0.50 · no paga $1")
    if (m.get("active") is False) or (m.get("accepting_orders") is False):
        t = "⏸ SUSPENDIDO: sin libro, no se puede vender ni resolver"
        if m.get("end_date_iso"):
            t += f" · resolución prevista {_madrid(m['end_date_iso'])}"
        return "suspendido", t
    return "vivo", "⏳ en juego"


_MAPA_SITUACION = {"vivo": "viva", "suspendido": "suspendida",
                   "sin_ganador": "anulada", "resuelto": "resuelta",
                   "sin_datos": "sin_datos"}


def situacion_op(op):
    """v12.8.3: situación de UNA posición (simple o combo) → (clave, texto).
    clave ∈ viva|suspendida|anulada|resuelta|muerta|sin_datos. En un combo manda
    la peor pata: si una leg ya perdió el parlay no paga; si alguna está
    suspendida no se puede vender el conjunto."""
    legs = op.get("legs") or []
    if not legs:
        cl, tx = situacion_mercado(op.get("condition_id"))
        return _MAPA_SITUACION.get(cl, cl), tx
    claves, isos = [], []
    n_gan = n_susp = n_juego = 0
    for lg in legs:
        cid = str(lg.get("condition_id") or "")
        m = mercado_clob(cid)
        cl, _tx = situacion_mercado(cid)
        est, _info = estado_leg(m, lg.get("outcome"))
        if est == "perdida":
            claves.append("perdida")
        elif est == "ganada":
            claves.append("ganada")
            n_gan += 1
        else:
            claves.append(cl)
            if cl == "suspendido":
                n_susp += 1
            elif cl == "vivo":
                n_juego += 1
        if m and m.get("end_date_iso"):
            isos.append(str(m["end_date_iso"]))
    if "perdida" in claves:
        return "muerta", "❌ una leg ya perdió: el combo NO paga (no se puede vender)"
    if claves and all(c == "ganada" for c in claves):
        return "resuelta", "🏁 todas las legs ganadas (pendiente de cobro)"
    txt = f"⏳ {n_gan} leg(s) ganadas · {n_juego} en juego"
    if n_susp:
        txt += f" · {n_susp} SUSPENDIDA(s) sin libro"
        if isos:
            txt += f" · resolución prevista {_madrid(max(isos))}"
        txt += " ⇒ no se puede vender ahora"
    return ("suspendida" if n_susp else "viva"), txt


def precio_vivo_op(op):
    """v12.8.3: (precio, fuente) de una posición abierta.
      fuente "mid" = libro vivo (midpoint del CLOB, lo de siempre).
      fuente "ult" = ÚLTIMO precio publicado por el mercado del CLOB: con el
        libro cerrado /midpoint da 404, pero el mercado trae `price` por cara,
        así que un mercado suspendido SÍ tiene valor en el panel (etiquetado).
      (None, None) si no hay nada de nada."""
    try:
        v = vivo_de(op)
    except Exception:
        v = None
    if v:
        return v, "mid"
    legs = op.get("legs") or []
    try:
        if legs:
            prod, ok = 1.0, True
            for lg in legs:
                cid = str(lg.get("condition_id") or "")
                m = mercado_clob(cid)
                tok = str(token_clob_de_leg(lg) or "")
                p = None
                for t in ((m or {}).get("tokens") or []):
                    if tok and str(t.get("token_id")) == tok:
                        try:
                            p = float(t.get("price") or 0) or None
                        except Exception:
                            p = None
                if p is None:
                    est, _ = estado_leg(m, lg.get("outcome"))
                    p = 1.0 if est == "ganada" else (0.0 if est == "perdida" else None)
                if p is None:
                    ok = False
                    break
                prod *= p
            return (prod, "ult") if ok else (None, None)
        tok = _token_de(op) or str(op.get("real_token") or "")
        m = mercado_clob(str(op.get("condition_id") or ""))
        for t in ((m or {}).get("tokens") or []):
            if tok and str(t.get("token_id")) == tok:
                try:
                    p = float(t.get("price") or 0)
                except Exception:
                    p = 0.0
                if 0 < p < 1:
                    return p, "ult"
    except Exception:
        pass
    return None, None


# ============================================
# v12.8.3: EVIDENCIA DE CADENA (fills reales) + CURACIÓN DE ABIERTAS
# ============================================
FILLS_PAGINAS = 3              # páginas de /activity?type=TRADE (500 c/u)
FILL_VENTANA_S = 3600          # un fill puede confirmarse minutos después
FILL_TOL_SHARES = 0.05         # tolerancia de shares entre registro y fill
_FILLS_CACHE = [0.0, []]       # [ts, fills BUY/SELL de la wallet]
_REPARTO_CACHE = [0.0, {}]     # [ts, {titulo_norm: {usdc, shares, por_share}}]


def fills_wallet(refrescar=False, limite=500):
    """v12.8.3: fills REALES de la wallet (data-api /activity?type=TRADE).
    → [{"ts","asset","size","usdc","side","tx","titulo"}]. Es la prueba de que
    una op del bot existió de verdad: el 11-sep se comprobó que Barranquilla
    tiene 4 registros del bot y sólo 2 fills en cadena (03:15:06 y 03:20:52).
    Cache 10 min; si la API falla devuelve lo último que tuvo (o []) ⇒ sin
    prueba NO se descarta nada."""
    ahora = time.time()
    if not refrescar and _FILLS_CACHE[1] and ahora - _FILLS_CACHE[0] < 600:
        return _FILLS_CACHE[1]
    out = []
    try:
        for pag in range(FILLS_PAGINAS):
            url = (f"{DATA_API}/activity?user={WALLET}&limit={limite}"
                   f"&offset={pag * limite}&type=TRADE")
            req = urllib.request.Request(url, headers={"User-Agent": "poly-combos-bot"})
            with urllib.request.urlopen(req, timeout=20) as r:
                parte = json.loads(r.read().decode())
            for a in (parte or []):
                if str(a.get("type", "")).upper() != "TRADE":
                    continue
                try:
                    out.append({"ts": int(a.get("timestamp") or 0),
                                "asset": str(a.get("asset") or ""),
                                "size": float(a.get("size") or 0),
                                "usdc": float(a.get("usdcSize") or 0),
                                "side": str(a.get("side") or ""),
                                "tx": str(a.get("transactionHash") or ""),
                                "titulo": a.get("title") or ""})
                except Exception:
                    continue
            if len(parte or []) < limite:
                break
        if out:
            _FILLS_CACHE[0], _FILLS_CACHE[1] = ahora, out
            log(f"  v12.8.3: {len(out)} fills reales de la wallet (evidencia de cadena)")
    except Exception as e:
        log(f"  fills_wallet: sin datos ({str(e)[:60]})")
    return _FILLS_CACHE[1]


def _tx_de_op(op):
    """v12.8.3: hash (o prefijo) de la tx que el bot guardó para esta op."""
    for k in ("tx_hash", "tx", "txHash"):
        v = str(op.get(k) or "").strip()
        if v.startswith("0x"):
            return v.lower()
    return ""


def casar_fills(ops):
    """v12.8.3: casa cada registro del bot con UN fill real de la cadena.
    Reglas: mismo token (asset), shares ±FILL_TOL_SHARES y hasta 1 h de
    diferencia; si la op guardó tx, manda la tx. Cada fill se usa UNA vez, así
    que los registros sobrantes se quedan sin fill ⇒ duplicados fantasma.
    → (casadas, fantasma, sin_evidencia). sin_evidencia = ops cuyo token no
    aparece NUNCA en /activity: no se juzgan (sin prueba no se borra nada)."""
    fills = fills_wallet()
    por_tok = {}
    for f in fills:
        if f.get("asset"):
            por_tok.setdefault(f["asset"], []).append(f)
    for v in por_tok.values():
        v.sort(key=lambda x: x["ts"])
    usados = set()
    casadas, fantasma, sin_ev = [], [], []
    for op in sorted(ops, key=lambda o: _op_ts(o) or 0):
        tok = _token_de(op) or str(op.get("real_token") or "")
        cands = por_tok.get(tok)
        if not cands:
            sin_ev.append(op)
            continue
        ts_op = _op_ts(op) or 0
        try:
            sh_op = float(op.get("size_shares") or 0)
        except Exception:
            sh_op = 0.0
        tx_op = _tx_de_op(op)
        hit = None
        if tx_op:
            for i, f in enumerate(cands):
                if (tok, i) in usados:
                    continue
                if f["tx"] and f["tx"].lower().startswith(tx_op[:18]):
                    hit = (tok, i)
                    break
        if hit is None:
            mejor, mejor_d = None, None
            for i, f in enumerate(cands):
                if (tok, i) in usados:
                    continue
                if sh_op > 0 and abs(f["size"] - sh_op) > FILL_TOL_SHARES:
                    continue
                d = abs(f["ts"] - ts_op) if (ts_op and f["ts"]) else 10 ** 9
                if d > FILL_VENTANA_S:
                    continue
                if mejor_d is None or d < mejor_d:
                    mejor, mejor_d = (tok, i), d
            hit = mejor
        if hit is None:
            fantasma.append(op)
            continue
        usados.add(hit)
        f = cands[hit[1]]
        op["fill_real"] = {"ts": f["ts"], "size": f["size"], "usdc": f["usdc"],
                           "tx": f["tx"], "side": f["side"]}
        casadas.append(op)
    return casadas, fantasma, sin_ev


def es_basura(op):
    """v12.8.3: registro vacío (sin pregunta, sin legs, sin stake, sin shares).
    No es una operación: es basura de un fallo de red. El panel ya la ocultaba,
    pero seguía contando como "abierta" y confundía el recuento."""
    if op.get("status") == "fallido":
        return False
    q = str(op.get("question") or "").strip()
    try:
        stake = float(op.get("stake_dolares") or 0)
        sh = float(op.get("size_shares") or 0)
    except Exception:
        return False
    return q in ("", "?") and not (op.get("legs") or []) and stake <= 0 and sh <= 0


def curar_abiertas(estado, aplicar=True):
    """🧹 v12.8.3: limpia `trades_copiados` ANTES de resolver nada.
      · registros vacíos (basura) → estado["descartadas"]
      · duplicados fantasma (más registros que fills reales en cadena) → idem
    Devuelve (ops_limpias, info). Con aplicar=False no guarda nada (modo seco).
    Nunca borra sin prueba: si data-api no responde o el token no tiene fills,
    la op se queda donde está."""
    ops = list(estado.get("trades_copiados") or [])
    limpias, basura = [], []
    for op in ops:
        if es_basura(op):
            basura.append(op)
        else:
            limpias.append(op)
    info = {"basura": len(basura), "fantasma": 0, "sin_evidencia": 0,
            "casadas": 0, "antes": len(ops)}
    fantasma = []
    if limpias:
        try:
            casadas, fantasma, sin_ev = casar_fills(limpias)
            info.update(fantasma=len(fantasma), sin_evidencia=len(sin_ev),
                        casadas=len(casadas))
            limpias = casadas + sin_ev
        except Exception as e:
            log(f"  curar_abiertas: dedup omitido ({str(e)[:70]})")
    estado["trades_copiados"] = limpias
    info["cura_info"] = info.copy()
    estado["_cura_info"] = info
    if (basura or fantasma) and aplicar:
        desc = list(estado.get("descartadas") or [])
        ahora = datetime.now(timezone.utc).isoformat()
        for o in basura:
            o["descartada"] = "registro vacío (basura): sin pregunta, stake ni legs"
            o["descartada_en"] = ahora
            desc.append(o)
        for o in fantasma:
            o["descartada"] = ("duplicado fantasma: hay más registros que fills "
                               "reales de ese token en la cadena")
            o["descartada_en"] = ahora
            desc.append(o)
        estado["descartadas"] = desc
        try:
            guardar_estado(estado)
        except Exception as e:
            log(f"  curar_abiertas: no se pudo guardar ({str(e)[:60]})")
        log(f"  🧹 v12.8.3 curación: {len(basura)} basura + {len(fantasma)} duplicados "
            f"fantasma fuera de ABIERTAS · quedan {len(limpias)} registros "
            f"({info['casadas']} casados con fill real, {info['sin_evidencia']} sin evidencia)")
    return limpias, info


def _reparto_mapa(estado=None, forzar=False):
    """💰 v12.8.3: reparte el usdcSize de cada REDEEM entre TODOS los fills del
    mismo mercado (por título normalizado) en proporción a sus shares.
    → {titulo_norm: {"usdc","shares","por_share"}}. Cache 5 min.
    Sin esto, cada fill de una posición se anotaba el cobro ENTERO: con los 4
    registros de Barranquilla (2 fantasma) eso habría inventado 4×$9.90."""
    ahora = time.time()
    if not forzar and _REPARTO_CACHE[1] and ahora - _REPARTO_CACHE[0] < 300:
        return _REPARTO_CACHE[1]
    try:
        cobros_wallet()
    except Exception:
        pass
    titulos = _COBROS_CACHE[2] or {}
    est = estado if estado is not None else cargar_estado()
    ops = [o for o in (list(est.get("trades_copiados") or [])
                       + list(est.get("historial") or []))
           if not o.get("descartada")]
    por_titulo = {}
    for o in ops:
        t = _norm_titulo(o.get("question"))
        if not t:
            continue
        try:
            por_titulo[t] = por_titulo.get(t, 0.0) + float(o.get("size_shares") or 0)
        except Exception:
            continue
    mapa = {}
    for t, g in titulos.items():
        try:
            usdc = float(g.get("usdc") or 0)
        except Exception:
            usdc = 0.0
        if usdc <= 0.000001:
            continue
        sh = por_titulo.get(t, 0.0)
        mapa[t] = {"usdc": round(usdc, 6), "shares": round(sh, 6),
                   "por_share": round(usdc / sh, 6) if sh > 0 else None}
    _REPARTO_CACHE[0], _REPARTO_CACHE[1] = ahora, mapa
    return mapa


def reparto_cobro(op):
    """v12.8.3: qué parte del cobro REAL le toca a esta op (o None)."""
    tit = _norm_titulo(op.get("question"))
    if not tit:
        return None
    return _reparto_mapa().get(tit)


# ============================================
# v12.8.3: 🔍 LEER AHORA (lectura inmediata, SÓLO MIRAR)
# ============================================
LECTURA_LOCK = threading.Lock()


def _eta_txt(ts):
    """v12.8.3: 'en 7 min 12 s' / 'ahora mismo' para la próxima pasada."""
    try:
        d = max(0, int(float(ts) - time.time()))
    except Exception:
        return "—"
    if d < 5:
        return "ahora mismo"
    m, s = divmod(d, 60)
    if m >= 60:
        return f"en {m // 60} h {m % 60} min"
    return f"en {m} min {s:02d} s" if m else f"en {s} s"


def cmd_leer_ahora(chat_id):
    """🔍 v12.8.3 — LECTURA INMEDIATA, SÓLO MIRAR (botón 🔍 Leer ahora / /leer).
    Fuerza una lectura AHORA sin esperar al intervalo ⏱ y cuenta qué ve:
    bankroll, catálogo RFQ, qué combo abriría (y por qué no), cada posición
    abierta con su situación REAL (viva / suspendida / anulada / resuelta) y lo
    que hay sin cobrar. NO abre operaciones, NO vende, NO archiva y NO toca el
    estado: la pasada AUTO sigue programada a su hora. Hilo propio con
    LECTURA_LOCK (no bloquea las pasadas ni se solapa consigo mismo)."""
    if not LECTURA_LOCK.acquire(blocking=False):
        return enviar(chat_id, "🔍 Ya hay una lectura en curso, espera unos segundos.")

    def _run():
        t0 = time.time()
        try:
            enviar(chat_id, "🔍 Leyendo ahora… _(sólo mirar: no abre ni vende nada)_")
            estado = {}
            try:
                estado = cargar_estado() or {}
            except Exception as e:
                log(f"  [LEER] estado: {e}")
            mins = intervalo_min_actual() or max(1, int(INTERVALO_AUTO_S // 60))
            eta = datetime.fromtimestamp(NEXT_PASADA_TS, tz=timezone.utc).strftime("%H:%M:%S")
            L = [f"🔍 *LECTURA AHORA* · {datetime.now(timezone.utc).strftime('%d-%m %H:%M:%S')} UTC",
                 (f"Modo *{MODO_OPERACION}* · pasada cada *{mins} min* ✅ · "
                  f"próxima lectura {_eta_txt(NEXT_PASADA_TS)} ({eta} UTC) · "
                  f"hoy {ops_pagadas_hoy(estado)}/{max_ops(estado)} ops · "
                  f"prob mín {prob_nivel_txt(prob_min_auto(estado))}")]
            try:
                sal = saldo_disponible_clob()
                L.append(f"💵 Disponible en la wallet: *${float(sal):.2f}*"
                         if sal is not None else "💵 Disponible: sin dato (proxy/credenciales)")
            except Exception as e:
                L.append(f"💵 Disponible: sin dato ({str(e)[:50]})")
            # ---- catálogo RFQ: qué abriría (SIN abrirlo)
            try:
                legs = listar_combos() or []
                sel = seleccionar_combo(legs, estado) if legs else None
                if sel:
                    prod = 1.0
                    for c in sel:
                        prod *= float(c.get("yes_price") or 0)
                    cuota = round(1 / prod, 2) if prod > 0 else 0.0
                    blk = [f"🎯 *Qué abriría ahora*: combo de {len(sel)} legs · "
                           f"cuota ~{cuota:.2f} · prob ~{prod * 100:.0f}%"]
                    for c in sel:
                        blk.append(f"   • {str(c.get('question') or c.get('slug') or '?')[:74]}"
                                   f" @ {float(c.get('yes_price') or 0):.3f}")
                    try:
                        stk = stake_operacion(estado, cuota, prod)
                        blk.append(f"   Stake que usaría: ${float(stk):.2f}")
                    except Exception:
                        pass
                    blk.append("   _NO se ha abierto: esto sólo lee_")
                    L.append("\n".join(blk))
                else:
                    L.append(f"🎯 *Qué abriría ahora*: NADA — {len(legs)} legs en el catálogo, "
                             f"ninguna combinación pasa el filtro (cuota {CUOTA_MIN}-{CUOTA_MAX}, "
                             f"prob ≥{prob_nivel_txt(prob_min_auto(estado))}, eventos distintos, "
                             f"cooldown de legs, tope {ops_pagadas_hoy(estado)}/{max_ops(estado)} hoy)")
            except Exception as e:
                L.append(f"🎯 Catálogo RFQ: sin lectura ({str(e)[:70]})")
            # ---- posiciones abiertas con su situación REAL
            try:
                ops = [o for o in (estado.get("trades_copiados") or [])
                       if o.get("status") != "fallido"
                       and str(o.get("question", "")).strip() not in ("", "?")
                       and (float(o.get("stake_dolares") or 0) > 0 or o.get("legs"))]
                grupos = agrupar_abiertas(ops)
                if not grupos:
                    L.append("📂 *Posiciones abiertas*: ninguna")
                else:
                    extra = f" ({len(ops)} fills)" if len(ops) != len(grupos) else ""
                    blk = [f"📂 *Posiciones abiertas*: {len(grupos)}{extra}"]
                    for i, g in enumerate(grupos[:12], 1):
                        op0 = g["ops"][0]
                        sh = sum(float(o.get("size_shares") or 0) for o in g["ops"])
                        st = sum(float(o.get("stake_dolares") or 0) for o in g["ops"])
                        _cl, sit = situacion_op(op0)
                        linea = f"\n*#{i}* {str(op0.get('question', '?'))[:78]}"
                        if len(g["ops"]) > 1:
                            linea += f"  ×{len(g['ops'])} fills"
                        linea += f"\n   ${st:.2f} · {sh:.2f} sh · {sit}"
                        p, fte = precio_vivo_op(op0)
                        if p and sh > 0:
                            tag = "precio ahora" if fte == "mid" else "últ. precio (libro cerrado)"
                            linea += (f"\n   📈 {tag} {p:.3f} (~{p * 100:.0f}%) · "
                                      f"valor ~${sh * p:.2f} vs pago ${sh:.2f}")
                        else:
                            linea += "\n   📈 precio: n/d"
                        if op0.get("fin_previsto"):
                            linea += f"\n   🏁 fin previsto {op0['fin_previsto']}"
                        blk.append(linea)
                    if len(grupos) > 12:
                        blk.append(f"\n_… y {len(grupos) - 12} posiciones más_")
                    L.append("\n".join(blk))
            except Exception as e:
                L.append(f"📂 Abiertas: sin lectura ({str(e)[:70]})")
            # ---- sin cobrar + última curación + stats
            try:
                rec = estado.get("reclamos_avisados") or {}
                if rec:
                    imp = sum(float(v.get("importe") or 0) for v in rec.values())
                    L.append(f"💰 *Sin cobrar*: {len(rec)} posiciones · ${imp:.2f} — "
                             f"reclamación abierta con soporte (/reclamar)")
                else:
                    L.append("💰 *Sin cobrar*: nada pendiente según el último aviso")
            except Exception as e:
                L.append(f"💰 Sin cobrar: sin dato ({str(e)[:50]})")
            try:
                aud = estado.get("ultimo_auditoria_resumen") or {}
                if aud:
                    L.append(f"🩺 Última auto-curación: {_madrid(estado.get('ultima_auditoria'))} · "
                             f"⏳{aud.get('reabiertas', 0)} ✏️{aud.get('corregidas', 0)} "
                             f"🏁{aud.get('nuevas_cerradas', 0)} · "
                             f"PnL archivadas ${float(aud.get('pnl_despues') or 0):+.2f}")
                desc = estado.get("descartadas") or []
                if desc:
                    L.append(f"🧹 Registros descartados (basura/duplicados): {len(desc)}")
            except Exception:
                pass
            try:
                s = calcular_stats()
                L.append(f"📊 PnL total *${s['pnl']:+.2f}* · ✅{s['wins']} ❌{s['losses']}"
                         + (f" ↩️{s.get('anuladas', 0)} anuladas" if s.get("anuladas") else ""))
            except Exception:
                pass
            L.append(f"_Leído en {time.time() - t0:.1f} s · esto NO abre ni vende nada · "
                     f"la pasada AUTO sigue a su hora ({mins} min ✅)_")
            enviar_largo(chat_id, "\n\n".join(L))
            log(f"  [LEER] lectura inmediata completada en {time.time() - t0:.1f} s (sólo mirar)")
        except Exception as e:
            log(f"  [LEER] error: {e}")
            try:
                enviar(chat_id, f"🔍 La lectura ha fallado: {str(e)[:150]}")
            except Exception:
                pass
        finally:
            try:
                LECTURA_LOCK.release()
            except Exception:
                pass

    threading.Thread(target=_run, daemon=True).start()
    return None


'''

def aplicar(src):
    cambios = []

    def sustituir(viejo, nuevo, etiqueta):
        nonlocal src
        n = src.count(viejo)
        if n != 1:
            raise SystemExit(f"[parche v12.8.3] '{etiqueta}': {n} coincidencias (esperaba 1)")
        src = src.replace(viejo, nuevo, 1)
        cambios.append(etiqueta)

    # ------------------------------------------------- 0) versiones a v12.8.3
    sustituir('POLY COMBOS BOT v12.8.2 — COMBOS REALES (parlays multi-leg) via RFQ',
              'POLY COMBOS BOT v12.8.3 — COMBOS REALES (parlays multi-leg) via RFQ',
              "cabecera v12.8.3")
    sustituir('    log("v12.8.2 iniciado")',
              '    log("v12.8.3 iniciado")', "log de arranque v12.8.3")
    sustituir('    txt = ("💰 *RECLAMAR v12.8.2*\\n\\n"',
              '    txt = ("💰 *RECLAMAR v12.8.3*\\n\\n"', "título /reclamar v12.8.3")
    sustituir('    texto = (f"🤖 *POLY COMBOS BOT v12.8.1*\\n\\n"',
              '    texto = (f"🤖 *POLY COMBOS BOT v12.8.3*\\n\\n"', "título /start v12.8.3")
    sustituir('    texto = (f"📊 *ESTADO v12.8.1 (Combos)*\\n\\n"',
              '    texto = (f"📊 *ESTADO v12.8.3 (Combos)*\\n\\n"', "título /status v12.8.3")

    # ------------------------------------------------- 0b) changelog cabecera
    sustituir('   v12.8.2: 🔒 EL CIERRE DE UN COMBO VUELVE A SER POSIBLE. `vivo_de()` pedía el',
              '''   v12.8.3: EL PANEL DICE LA VERDAD + ✅ + 🔍. (1) El botón ⏱ del intervalo
   ACTIVO lleva un tick verde ✅ (teclado dinámico, se reconstruye en cada
   mensaje). (2) Nuevo botón 🔍 Leer ahora (+ /leer): lectura inmediata que
   cuenta bankroll, catálogo, qué abriría y el estado REAL de cada posición,
   SIN abrir ni vender nada. (3) ⏸ mercado SUSPENDIDO y ↩️ ANULADO en
   cristiano, con la fecha de resolución prevista, y último precio publicado
   cuando /midpoint da 404. (4) 🧹 curación por evidencia de cadena: los
   registros de Abiertas se casan con los fills reales de data-api; los
   sobrantes (duplicados fantasma) y los vacíos (basura) salen a
   estado["descartadas"]. (5) Mercados simples cerrados SIN ganador declarado
   ya no se esperan para siempre: si la wallet cobró, se archivan con el
   dinero REAL, repartido entre los fills del mismo mercado en proporción a
   sus shares, y cuentan como "anulada" (↩️), no como ganada/perdida.
   v12.8.2: 🔒 EL CIERRE DE UN COMBO VUELVE A SER POSIBLE. `vivo_de()` pedía el''',
              "changelog v12.8.3 en la cabecera")

    # ------------------------------------- 1) teclado dinámico con tick ✅ + 🔍
    sustituir('''TECLADO_FIJO = {
    "keyboard": [
        [{"text": "📋 Trades"}, {"text": "💰 Saldo"}, {"text": "📂 Abiertas"}],
        [{"text": "💥 SúperCombos"}, {"text": "💰 Reclamar"}],
        [{"text": "✅ Cerradas"}, {"text": "📊 Stats"}, {"text": "🏆 Top"}],
        [{"text": "🟢 AUTO"}, {"text": "🟡 SEMI"}, {"text": "🔴 OFF"}],
        [{"text": "💵 Stake AUTO"}, {"text": "💵 Stake $5"}],
        [{"text": "🔢 Máx ops/día"}, {"text": "🎯 Prob AUTO"}],
        [{"text": "⏱ 5m"}, {"text": "⏱ 10m"}, {"text": "⏱ 20m"}, {"text": "⏱ 30m"}, {"text": "⏱ 60m"}],
    ],
    "resize_keyboard": True,
    "persistent": True,
}''',
              '''INTERVALOS_MIN = (5, 10, 20, 30, 60)   # v12.8.3: sube aquí (el ✅ lo necesita)
TICK_ACTIVO = " ✅"                     # v12.8.3: tick verde del botón ACTIVO


def intervalo_min_actual():
    """v12.8.3: minutos del intervalo activo, o None si no es uno de los botones
    (p. ej. un /intervalo a mano con un valor raro). Sirve para pintar el ✅."""
    try:
        m = int(round(INTERVALO_AUTO_S / 60))
    except Exception:
        return None
    return m if m in INTERVALOS_MIN else None


def teclado_fijo():
    """✅ v12.8.3: teclado DINÁMICO. El botón ⏱ del intervalo ACTIVO sale con un
    tick verde al final ("⏱ 10m ✅") para ver de un golpe cada cuánto lee el bot;
    los demás van sin tick. Se reconstruye en CADA mensaje porque Telegram sólo
    refresca un teclado cuando llega uno nuevo, así que el tick se mueve solo al
    cambiar el intervalo. El tick va AL FINAL para que el handler
    (text.startswith("⏱")) siga casando. Añade el botón 🔍 Leer ahora."""
    act = intervalo_min_actual()
    fila_int = [{"text": f"⏱ {m}m" + (TICK_ACTIVO if act == m else "")}
                for m in INTERVALOS_MIN]
    return {
        "keyboard": [
            [{"text": "📋 Trades"}, {"text": "💰 Saldo"}, {"text": "📂 Abiertas"}],
            [{"text": "💥 SúperCombos"}, {"text": "💰 Reclamar"}],
            [{"text": "✅ Cerradas"}, {"text": "📊 Stats"}, {"text": "🏆 Top"}],
            [{"text": "🟢 AUTO"}, {"text": "🟡 SEMI"}, {"text": "🔴 OFF"}],
            [{"text": "💵 Stake AUTO"}, {"text": "💵 Stake $5"}],
            [{"text": "🔢 Máx ops/día"}, {"text": "🎯 Prob AUTO"}],
            fila_int,
            [{"text": "🔍 Leer ahora"}],
        ],
        "resize_keyboard": True,
        "persistent": True,
    }


TECLADO_FIJO = teclado_fijo()      # v12.8.3: compatibilidad (ya no es estático)''',
              "teclado dinámico con ✅ y 🔍 Leer ahora")

    sustituir('''    if reply_markup is None:
        params["reply_markup"] = json.dumps(TECLADO_FIJO)''',
              '''    if reply_markup is None:
        # v12.8.3: teclado dinámico (el botón ⏱ activo lleva ✅)
        params["reply_markup"] = json.dumps(teclado_fijo())''',
              "enviar() usa teclado_fijo()")

    # la definición vieja de INTERVALOS_MIN (línea ~1573) ahora es redundante
    sustituir('''INTERVALOS_MIN = (5, 10, 20, 30, 60)

def cmd_intervalo(chat_id, texto):''',
              '''# v12.8.3: INTERVALOS_MIN se define arriba, junto al teclado (lo usa el ✅)

def cmd_intervalo(chat_id, texto):''',
              "INTERVALOS_MIN movido arriba")

    # --------------------------------------- 1b) confirmación del intervalo ✅
    sustituir('''    return enviar(chat_id, f"⏱ *Pasada cada {mins} min*\\nPróxima lectura: ~{datetime.fromtimestamp(NEXT_PASADA_TS, tz=timezone.utc).strftime('%H:%M:%S')} UTC\\n(guardado; sobrevive reinicios)")''',
              '''    return enviar(chat_id, f"⏱ *Pasada cada {mins} min*\\nPróxima lectura: ~{datetime.fromtimestamp(NEXT_PASADA_TS, tz=timezone.utc).strftime('%H:%M:%S')} UTC\\n(guardado; sobrevive reinicios)\\n✅ El botón *⏱ {mins}m* del teclado queda marcado como el activo")''',
              "confirmación del intervalo con ✅")

    # ------------------------------------------- 2) handler del botón 🔍
    sustituir('''    elif text == "💰 Reclamar":          # v12.8
        return cmd_reclamar(chat_id)''',
              '''    elif text == "💰 Reclamar":          # v12.8
        return cmd_reclamar(chat_id)
    elif text.startswith("🔍 Leer") or text in ("/leer", "/leerahora"):
        return cmd_leer_ahora(chat_id)   # v12.8.3: sólo mirar, no abre nada''',
              "handler 🔍 Leer ahora + /leer")

    # ------------------------------- 3) resolver_operacion: simples anulados
    sustituir('''    if not win_tok:
        return out          # v12.6: cerrado sin ganador declarado ⇒ se espera''',
              '''    if not win_tok:
        # ↩️ v12.8.3: cerrado/suspendido SIN ganador declarado. Antes se esperaba
        # para siempre aunque la wallet YA hubiera cobrado: los mercados ANULADOS
        # (partido no jugado) devuelven ~$0.50 por token y ese REDEEM no casa con
        # ningún ganador. Si hay cobro real (casado por token o por título) se
        # archiva con el dinero DE VERDAD recibido, REPARTIDO entre los fills del
        # mismo mercado en proporción a sus shares — nunca el cobro entero a cada
        # fill, que es lo que habría inflado el PnL.
        rep = reparto_cobro(op)
        por_share = (rep or {}).get("por_share")
        if por_share and shares > 0:
            cobro = round(float(por_share) * shares, 6)
            if cobro > 0.000001:
                gan = cobro >= shares * 0.999
                out.update(resuelta=True, ganada=gan, pnl=round(cobro - stake, 2),
                           fuente="cobro_real_simple", cobro_real=cobro,
                           anulada=(not gan),
                           ratio_cobro=(round(cobro / shares, 4) if shares else None))
                return out
        if m.get("closed"):
            out["sin_ganador"] = True    # cerrado sin ganador: sigue en espera
        return out          # v12.6: cerrado sin ganador declarado ⇒ se espera''',
              "simples: cobro real repartido (mercados anulados)")

    # ------------------------------------------- 4) resultado "anulada" (↩️)
    sustituir('''        if r["resuelta"]:
            op["status"] = "cerrado"
            op["resultado"] = "ganada" if r["ganada"] else "perdida"
            op["pnl"] = r["pnl"]''',
              '''        if r["resuelta"]:
            op["status"] = "cerrado"
            # ↩️ v12.8.3: mercado anulado/devuelto = ni ganada ni perdida
            op["resultado"] = ("anulada" if r.get("anulada")
                               else ("ganada" if r["ganada"] else "perdida"))
            op["pnl"] = r["pnl"]''',
              "sincronizar_operaciones: anulada")

    sustituir('''        res_ahora = "ganada" if r.get("ganada") else "perdida"''',
              '''        res_ahora = ("anulada" if r.get("anulada")        # ↩️ v12.8.3
                     else ("ganada" if r.get("ganada") else "perdida"))''',
              "reauditar (historial): anulada")

    sustituir('''        r = resolver_operacion(op)
        if r.get("resuelta"):
            op["status"] = "cerrado"
            op["resultado"] = "ganada" if r.get("ganada") else "perdida"
            op["pnl"] = r.get("pnl")''',
              '''        r = resolver_operacion(op)
        if r.get("resuelta"):
            op["status"] = "cerrado"
            op["resultado"] = ("anulada" if r.get("anulada")     # ↩️ v12.8.3
                               else ("ganada" if r.get("ganada") else "perdida"))
            op["pnl"] = r.get("pnl")''',
              "reauditar (abiertas): anulada")

    sustituir('''        "total": len(copiados), "wins": 0, "losses": 0,''',
              '''        "total": len(copiados), "wins": 0, "losses": 0, "anuladas": 0,''',
              "calcular_stats: contador anuladas")

    sustituir('''            if pnl > 0: s["wins"] += 1
            else: s["losses"] += 1''',
              '''            # ↩️ v12.8.3: las anuladas (mercado devuelto) no son ni ✅ ni ❌
            if str(op.get("resultado")) == "anulada": s["anuladas"] += 1
            elif pnl > 0: s["wins"] += 1
            else: s["losses"] += 1''',
              "calcular_stats: anuladas no cuentan como win/loss")

    sustituir('''    total = s["wins"] + s["losses"]
    wr = (s["wins"]/total*100) if total > 0 else 0''',
              '''    total = s["wins"] + s["losses"]
    wr = (s["wins"]/total*100) if total > 0 else 0
    _anu = s.get("anuladas", 0)          # ↩️ v12.8.3''',
              "cmd_stats: anuladas (variable)")

    sustituir('''        texto += f"Cerradas: {total} (✅{s['wins']} ❌{s['losses']})\\n"''',
              '''        texto += (f"Cerradas: {total} (✅{s['wins']} ❌{s['losses']})"
                  + (f" · ↩️{_anu} anuladas/devueltas" if _anu else "") + "\\n")''',
              "cmd_stats: línea de anuladas")

    sustituir('''    texto = f"✅ *CERRADAS ({len(historial)})* — 🟢 {gan} / 🔴 {len(historial) - gan}\\n_PnL: ${total:+.2f}_\\n"''',
              '''    # ↩️ v12.8.3: las anuladas (mercado devuelto) se cuentan aparte
    anu = sum(1 for h in historial if str(h.get("resultado")) == "anulada")
    texto = (f"✅ *CERRADAS ({len(historial)})* — 🟢 {gan} / 🔴 {len(historial) - gan - anu}"
             + (f" / ↩️ {anu} anuladas" if anu else "") + f"\\n_PnL: ${total:+.2f}_\\n")''',
              "cmd_cerradas: anuladas aparte")

    sustituir('''    for h in historial[-15:]:
        pnl = float(h.get("pnl", 0) or 0)
        ico = "🟢" if pnl >= 0 else "🔴"''',
              '''    for h in historial[-15:]:
        pnl = float(h.get("pnl", 0) or 0)
        ico = "↩️" if str(h.get("resultado")) == "anulada" else ("🟢" if pnl >= 0 else "🔴")''',
              "cmd_cerradas: icono ↩️")

    # ------------------------------- 5) curación ANTES de resolver (auditoría)
    sustituir('''    estado = cargar_estado()
    hist = estado.get("historial", []) or []
    abiertas = estado.get("trades_copiados", []) or []''',
              '''    estado = cargar_estado()
    # 🧹 v12.8.3: ANTES de resolver nada, limpiar Abiertas (basura + duplicados
    # fantasma sin fill real en cadena) y recalcular el reparto de los cobros con
    # la lista YA limpia (si no, cada fill fantasma se llevaría su parte).
    _limpias, _cura = curar_abiertas(estado, aplicar=aplicar)
    _reparto_mapa(estado, forzar=True)
    hist = estado.get("historial", []) or []
    abiertas = estado.get("trades_copiados", []) or []''',
              "reauditar: curación + reparto antes de resolver")

    sustituir('''           f"  🏁 Abiertas resueltas ahora: {len(nuevas_cerr)}\\n"
           f"PnL archivadas: ${pnl_antes_total:+.2f} → *${pnl_despues:+.2f}*\\n")''',
              '''           f"  🏁 Abiertas resueltas ahora: {len(nuevas_cerr)}\\n"
           + (f"  🧹 Limpieza v12.8.3: {_cura.get('basura', 0)} basura · "
              f"{_cura.get('fantasma', 0)} duplicados fantasma · "
              f"{_cura.get('casadas', 0)} casadas con fill real · "
              f"{_cura.get('sin_evidencia', 0)} sin evidencia (intactas)\\n"
              if (_cura.get("basura") or _cura.get("fantasma")
                  or _cura.get("casadas") or _cura.get("sin_evidencia")) else "")
           + f"PnL archivadas: ${pnl_antes_total:+.2f} → *${pnl_despues:+.2f}*\\n")''',
              "informe de auditoría: línea 🧹")

    sustituir('''    resumen = {"reabiertas": len(reabiertas), "corregidas": len(corregidas),''',
              '''    resumen = {"cura": _cura, "reabiertas": len(reabiertas), "corregidas": len(corregidas),''',
              "resumen de auditoría: cura")

    # ------------------------------- 5b) curación también al sincronizar/panel
    sustituir('''    estado = cargar_estado()
    ops = estado.get("trades_copiados", [])
    if not ops:
        return [], [], estado''',
              '''    estado = cargar_estado()
    curar_abiertas(estado, aplicar=True)     # 🧹 v12.8.3: basura + duplicados
    _reparto_mapa(estado, forzar=True)       # 💰 v12.8.3: cobro real repartido
    ops = estado.get("trades_copiados", [])
    if not ops:
        return [], [], estado''',
              "sincronizar_operaciones: curación previa")

    # ------------------------------------------- 6) funciones nuevas (bloque)
    sustituir('''def cmd_status(chat_id):''', NUEVAS + '''def cmd_status(chat_id):''',
              "bloque de funciones nuevas v12.8.3")

    # ------------------------------------------- 7) panel 📂: situación real
    sustituir('''    vivo = vivo_de(op0)
    if vivo and shares > 0:
        valor = shares * vivo
        payout = shares
        txt += (f"   📈 precio ahora {vivo:.3f} (~{vivo * 100:.0f}%) · "
                f"valor ${valor:.2f} vs pago ${payout:.2f}\\n")
        if payout > 0 and valor >= 0.90 * payout:
            txt += f"   💰 CERRAR anticipado aseguraría ~{_din(valor - stake)} (≥90% del pago)\\n"
        elif valor <= 0.55 * stake:
            txt += f"   🔴 Muy caída ({_din(valor - stake)}) — plantéate cortar\\n"
        else:
            txt += f"   🟢 Mantener ({_din(valor - stake)} latente)\\n"
    else:
        # v12.8.2: "n/d" a secas confundía — si ya está resuelta no cotiza
        if r.get("resuelta"):
            txt += "   📈 precio ahora: n/d (posición resuelta: ya no cotiza)\\n"
        else:
            txt += "   📈 precio ahora: n/d\\n"''',
              '''    # v12.8.3: situación REAL (viva/suspendida/anulada/resuelta/muerta) + último
    # precio publicado cuando el libro está cerrado (/midpoint da 404).
    sit_cl, sit_tx = situacion_op(op0)
    if sit_cl in ("suspendida", "anulada", "muerta", "sin_datos"):
        txt += f"   {sit_tx}\\n"
    vivo, fte_precio = precio_vivo_op(op0)
    if vivo and shares > 0:
        valor = shares * vivo
        payout = shares
        etiqueta = "📈 precio ahora" if fte_precio == "mid" else "📈 últ. precio (libro cerrado)"
        txt += (f"   {etiqueta} {vivo:.3f} (~{vivo * 100:.0f}%) · "
                f"valor ${valor:.2f} vs pago ${payout:.2f}\\n")
        if sit_cl in ("suspendida", "muerta"):
            txt += f"   ⏸ No se puede vender ahora ({_din(valor - stake)} latente)\\n"
        elif payout > 0 and valor >= 0.90 * payout:
            txt += f"   💰 CERRAR anticipado aseguraría ~{_din(valor - stake)} (≥90% del pago)\\n"
        elif valor <= 0.55 * stake:
            txt += f"   🔴 Muy caída ({_din(valor - stake)}) — plantéate cortar\\n"
        else:
            txt += f"   🟢 Mantener ({_din(valor - stake)} latente)\\n"
    else:
        # v12.8.2: "n/d" a secas confundía — si ya está resuelta no cotiza
        if r.get("resuelta"):
            txt += "   📈 precio ahora: n/d (posición resuelta: ya no cotiza)\\n"
        elif sit_cl == "suspendida":
            txt += "   📈 precio ahora: n/d (mercado suspendido: sin libro)\\n"
        else:
            txt += "   📈 precio ahora: n/d\\n"''',
              "render_grupo: situación + último precio")

    sustituir('''    texto += "\\n\\n_A la derecha de cada línea: ✅ ya terminó y salió positiva · ❌ perdida · ⏳ sigue en juego_"''',
              '''    texto += ("\\n\\n_A la derecha: ✅ ganada · ❌ perdida · ⏳ en juego_"
              "\\n_⏸ SUSPENDIDO = mercado sin libro (no se puede vender ni resolver; se muestra la fecha prevista)_"
              "\\n_↩️ ANULADO = cerrado sin ganador: los tokens se devuelven a ~$0.50_")''',
              "leyenda del panel 📂")

    # ------------------------------------------- 8) ayuda de /start
    sustituir('''             f"⏩ Botones ⏱ — intervalo entre pasadas ({INTERVALO_AUTO_S // 60} min ahora)\\n"''',
              '''             f"⏩ Botones ⏱ — intervalo entre pasadas ({INTERVALO_AUTO_S // 60} min ahora) · el ACTIVO lleva ✅\\n"
             f"🔍 *Leer ahora* — lectura inmediata (bankroll, catálogo, qué abriría y estado real de cada posición). SÓLO MIRAR: no abre ni vende nada · /leer\\n"''',
              "ayuda /start: ✅ y 🔍")

    return src, cambios


if __name__ == "__main__":
    ent, sal = sys.argv[1], sys.argv[2]
    src = io.open(ent, encoding="utf-8").read()
    nuevo, cambios = aplicar(src)
    # ---------------- verificaciones estructurales
    assert "v12.8.3" in nuevo.splitlines()[3], "cabecera sin v12.8.3"
    for fn in ("def teclado_fijo(", "def intervalo_min_actual(", "def situacion_mercado(",
               "def situacion_op(", "def precio_vivo_op(", "def fills_wallet(",
               "def casar_fills(", "def es_basura(", "def curar_abiertas(",
               "def _reparto_mapa(", "def reparto_cobro(", "def cmd_leer_ahora(",
               "def _eta_txt(", "def _tx_de_op("):
        assert nuevo.count(fn) == 1, f"{fn} debe aparecer 1 vez: {nuevo.count(fn)}"
    assert nuevo.count("INTERVALOS_MIN = (5, 10, 20, 30, 60)") == 1, "INTERVALOS_MIN duplicado"
    assert nuevo.count("json.dumps(teclado_fijo())") == 1
    assert nuevo.count('{"text": "🔍 Leer ahora"}') == 1
    assert nuevo.count("TICK_ACTIVO") >= 2
    assert 'text.startswith("🔍 Leer")' in nuevo
    assert nuevo.count("def cmd_status(") == 1
    assert nuevo.count("def main()") == 1
    assert "anulada" in nuevo and '"anuladas"' in nuevo
    assert nuevo.count("def enviar(") == 1
    assert nuevo.count("def resolver_operacion(") == 1
    assert nuevo.count("def sincronizar_operacion" + "es(") == 1
    assert nuevo.count("def reauditar_estado(") == 1
    io.open(sal, "w", encoding="utf-8").write(nuevo)
    print(f"✅ v12.8.3 generado: {sal} · {len(cambios)} cambios:")
    for c in cambios:
        print(f"     · {c}")
    print(f"   líneas: {len(nuevo.splitlines())} · md5 {hashlib.md5(nuevo.encode()).hexdigest()}")
