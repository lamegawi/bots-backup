#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parche_v1290.py — v12.8.4 → v12.9.0  (🏆 Top real + 📡 copy-trading EN PAPEL)
=============================================================================
Decisión del usuario (12-sep, tras el estudio con datos reales):
  · Fase 1 EN PAPEL ~7 días (sin gastar un dólar)
  · seguir al top 5 por beneficio en 30 días CON FILTROS automáticos
  · tope PROPIO de 5 señales/día (no toca el de 10 ops de combos)
  · sus compras son una SEÑAL para futuros combos propios: NADA de líneas sueltas

QUÉ SE AÑADE
  1) 🏆 TOP REAL EN VIVO. cmd_top() era una lista ESCRITA A MANO y falsa
     ("pleaseplease123 +$1.0M"…). Ahora llama a lb-api.polymarket.com/profit
     (y /volume) con ventanas 1d/7d/30d/all, botones inline para cambiar de
     ventana, y enseña la wallet de cada uno. Comprobado: el top real de 24 h lo
     encabeza ripley86alien +$1.084M y el histórico swisstony +$23.6M.
  2) 📡 SEGUIMIENTO EN PAPEL (Fase 1). Cada COPY_SONDEO_S lee los fills de las
     wallets vigiladas (data-api /activity), deduplica por tx+asset, y anota la
     señal con DOS precios: el del trader y el mid REAL al que nosotros
     podríamos entrar (precio_mid). Si el precio ya se movió más de
     COPY_DERIVA_MAX (5 pts) la señal se descarta por tardía: llegó el momento
     y ya no está. Nada se firma, nada se compra.
  3) FILTROS de selección medidos sobre su actividad real de 48 h: activo
     (≥5 compras), no market maker (ventas/compras ≤0.5), no concentrado
     (≥3 mercados) y ≥40% deporte. Motivo medido: el top histórico está parado
     (9 de 10 no operan), RN1 dio −48.8% en 48 h, ArmageddonRewardsBilly hace
     213 compras/287 ventas (MM) y 00gringo00 metió 103 fills en UN mercado.
  4) RESOLUCIÓN de señales: cuando el mercado se resuelve se anota si la señal
     acertó y el PnL teórico a $5 al precio NUESTRO y al SUYO (la diferencia es
     lo que cuesta llegar tarde). Los mercados anulados (closed sin ganador) se
     cierran a 0, igual que las ↩️ del panel.
  5) /copy + botón 📡 Copy: panel del seguimiento (día, señales, acierto, ROI al
     precio nuestro, deriva media, retraso medio y desglose POR TRADER) y el
     criterio objetivo para pasar a Fase 2: ≥30 señales resueltas y ROI positivo.
  6) Informe diario al chat con esos mismos números.

GARANTÍAS
  · COPY_DINERO = False: no existe ningún camino de esta versión a firmar una
    orden. Las señales viven en estado["copy_señales"], NUNCA en
    trades_copiados, así que panel, auditoría, curación y cierre 🔒 no se enteran.
  · Todo el seguimiento es LECTURA pública (lb-api/data-api/CLOB) sin proxy: no
    depende de que el PC esté encendido, y va serializado con PASADA_LOCK.
Uso: python3 parche_v1290.py <bot_v1284.py> <bot_v1290.py>
"""
import sys, io, hashlib

SECCION = r'''# ============================================
# v12.9.0: 🏆 TOP REAL EN VIVO + 📡 COPY-TRADING EN PAPEL (FASE 1)
# ============================================
# Estudiado con datos reales antes de escribir una línea (12-sep):
#   · lb-api.polymarket.com/profit?window={1d|7d|30d|all} → ranking con proxyWallet
#   · data-api /activity?user=<wallet>&type=TRADE → sus fills (retraso: minutos)
#   · copiar al "top 1" es la PEOR regla: el top-1 histórico activo (RN1) dio
#     −48.8% en sus últimas 48 h; en 30 días conviven +130% con −100%.
#   · el precio NO se mueve al instante en deporte (−0.6 pts a los 1-30 min),
#     así que la señal se puede aprovechar; en otros mercados sí (media +4.2%).
# Por eso esto arranca EN PAPEL: mide el ROI prospectivo antes de arriesgar nada.
LB_API = "https://lb-api.polymarket.com"
VENTANAS_LB = {"1d": "24 h", "7d": "7 días", "30d": "30 días", "all": "histórico"}
COPY_ACTIVO = True          # 📡 seguimiento en papel ON
COPY_DINERO = False         # ❌ Fase 2 APAGADA: ninguna señal se ejecuta
COPY_VENTANA = "30d"        # ranking de referencia para elegir traders
COPY_N_TRADERS = 5          # a cuántos vigilamos a la vez
COPY_TOPE_DIA = 5           # señales nuevas/día (tope PROPIO, no el de combos)
COPY_SONDEO_S = 180         # cada cuánto leemos sus fills
COPY_MIN_COMPRAS_48H = 5    # filtro: que esté activo
COPY_MAX_RATIO_VENTAS = 0.5  # filtro: no market maker
COPY_MIN_MERCADOS = 3       # filtro: no concentrado en 1-2 mercados
COPY_MIN_DEPORTE = 0.40     # filtro: que juegue donde sabemos combinar
COPY_DERIVA_MAX = 0.05      # si el precio ya se movió >5 pts, la señal es tardía
COPY_RESUMEN_CADA_S = 86400  # informe diario
COPY_STAKE_PAPEL = 5.0      # $ por señal en la simulación (tu stake mínimo)
COPY_ELEGIR_CADA_S = 86400   # la lista se reevalúa a diario
COPY_MAX_SEÑALES = 300      # tope del histórico en el estado (~60 días a 5/día)
COPY_RESOLVER_POR_RONDA = 10  # máx. mercados consultados al resolver por pasada
COPY_MAX_VISTOS = 4000        # tope del dedup de fills (se poda por antigüedad)
COPY_VISTOS_DIAS = 2          # días de dedup que se conservan
NEXT_COPY_TS = 0.0
NEXT_COPY_RESUMEN_TS = 0.0
_LB_CACHE = [0.0, {}]       # [ts, {ventana: [(puesto, nombre, wallet, profit, vol)]}]
_DEPORTE_CLAVES = ("nfl", "nba", "mlb", "nhl", "epl", "laliga", "ucl", "atp", "wta",
                   "f1", "seriea", "bundesliga", "ligue1", "mls", "wnba", "ufc",
                   "soccer", "football", "basketball", "baseball", "tennis", "mma",
                   "hockey", "cricket", "esports", "lol", "csgo", "dota", "ren-", "fl1")


def _lb_get(url, timeout=20):
    """GET público (sin proxy: leer el ranking no necesita el PC encendido)."""
    req = urllib.request.Request(url, headers={"User-Agent": "poly-combos-bot"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _din_lb(v):
    """$1.2M / $918K / $91 — para que el ranking quepa en el mensaje."""
    try:
        v = float(v or 0)
    except Exception:
        return "$0"
    a = abs(v)
    if a >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    if a >= 1_000:
        return f"${v / 1_000:.1f}K"
    return f"${v:.0f}"


def nombre_lb(x, wallet=""):
    """lb-api a veces da como nombre la wallet con un número detrás
    (0x2c33…-1759935795465): eso no se enseña. Mejor el apodo; si no, la wallet."""
    for k in ("pseudonym", "name"):
        v = str((x or {}).get(k) or "").strip()
        if v and not v.startswith("0x") and len(v) <= 24:
            return v
    return str(wallet)[:10] or "anónimo"


def top_traders(ventana="1d", limite=10, refrescar=False):
    """🏆 v12.9.0: ranking REAL (beneficio + volumen + wallet). Cache 15 min.
    → [(puesto, nombre, wallet, profit, volumen)] · [] si no hay red."""
    if ventana not in VENTANAS_LB:
        ventana = "1d"
    ahora = time.time()
    if not refrescar and _LB_CACHE[1].get(ventana) and ahora - _LB_CACHE[0] < 900:
        return _LB_CACHE[1][ventana]
    try:
        prof = _lb_get(f"{LB_API}/profit?window={ventana}&limit={limite}") or []
        try:
            vol = _lb_get(f"{LB_API}/volume?window={ventana}&limit=100") or []
        except Exception:
            vol = []
        vmap = {str(x.get("proxyWallet", "")).lower(): float(x.get("amount") or 0)
                for x in vol}
        filas = []
        for i, x in enumerate(prof, 1):
            w = str(x.get("proxyWallet") or "")
            filas.append((i, nombre_lb(x, w), w,
                          float(x.get("amount") or 0), vmap.get(w.lower(), 0.0)))
        _LB_CACHE[0] = ahora
        _LB_CACHE[1][ventana] = filas
        return filas
    except Exception as e:
        log(f"  [top] lb-api sin respuesta: {str(e)[:60]}")
        return _LB_CACHE[1].get(ventana, [])


def es_deporte_copy(texto):
    t = str(texto or "").lower()
    return any(k in t for k in _DEPORTE_CLAVES)


def perfil_trader(wallet, horas=48, limite=300):
    """📡 Radiografía REAL de una wallet en las últimas horas: compras, ventas,
    mercados distintos, % deporte y tamaño mediano. Decide si entra en la lista."""
    if not wallet:
        return None
    try:
        act = _lb_get(f"{DATA_API}/activity?user={wallet}&limit={limite}&type=TRADE") or []
    except Exception as e:
        log(f"  [copy] sin actividad de {str(wallet)[:10]}…: {str(e)[:50]}")
        return None
    corte = time.time() - horas * 3600
    tr = [x for x in act if x.get("type") == "TRADE"
          and int(x.get("timestamp") or 0) >= corte]
    if not tr:
        return {"compras": 0, "ventas": 0, "ratio": 0.0, "mercados": 0, "deporte": 0.0,
                "mediana_usd": 0.0, "ultimo": 0, "n": 0}
    compras = [x for x in tr if x.get("side") == "BUY"]
    ventas = [x for x in tr if x.get("side") == "SELL"]
    mk = {str(x.get("conditionId")) for x in tr}
    esp = sum(1 for x in tr if es_deporte_copy(
        x.get("eventSlug") or x.get("slug") or x.get("title")))
    usd = sorted(float(x.get("usdcSize") or 0) for x in tr)
    return {"compras": len(compras), "ventas": len(ventas),
            "ratio": len(ventas) / max(len(compras), 1), "mercados": len(mk),
            "deporte": esp / len(tr),
            "mediana_usd": usd[len(usd) // 2] if usd else 0.0,
            "ultimo": max(int(x.get("timestamp") or 0) for x in tr), "n": len(tr)}


def filtros_perfil(p):
    """Por qué un trader entra o se descarta. → (ok, motivo en cristiano)"""
    if not p or int(p.get("compras") or 0) < COPY_MIN_COMPRAS_48H:
        return False, f"inactivo ({int((p or {}).get('compras') or 0)} compras en 48 h)"
    if float(p["ratio"]) > COPY_MAX_RATIO_VENTAS:
        return False, (f"market maker ({p['ventas']} ventas / {p['compras']} compras): "
                       "copiar sólo sus compras sería catastrófico")
    if int(p["mercados"]) < COPY_MIN_MERCADOS:
        return False, f"concentrado en {p['mercados']} mercado(s)"
    if float(p["deporte"]) < COPY_MIN_DEPORTE:
        return False, f"sólo {p['deporte'] * 100:.0f}% deporte"
    return True, (f"activo ({p['compras']} compras, {p['mercados']} mercados, "
                  f"{p['deporte'] * 100:.0f}% deporte)")


def copy_elegir(estado, chat_id=None):
    """📡 Elige a los COPY_N_TRADERS primeros del ranking que PASAN los filtros.
    Se reevalúa cada COPY_ELEGIR_CADA_S porque el top cambia (y porque el que hoy
    gana puede ser el que mañana pierda: por eso filtramos por conducta, no por puesto)."""
    top = top_traders(COPY_VENTANA, 12, refrescar=True)
    cp = estado_copy(estado)
    if not top:
        log("  [copy] sin ranking (lb-api no respondió): sigo con la lista anterior")
        return cp.get("traders") or []
    elegidos = []
    for puesto, nom, w, prof, vol in top:
        if not w:
            continue
        p = perfil_trader(w)
        okk, mot = filtros_perfil(p)
        log(f"  [copy] #{puesto} {str(nom)[:20]:<20} {'ELEGIDO' if okk else 'descartado'} · {mot}")
        if okk:
            elegidos.append({"nombre": str(nom)[:24], "wallet": w, "puesto": puesto,
                             "profit": round(prof, 2), "volumen": round(vol, 2),
                             "compras48h": p["compras"], "ventas48h": p["ventas"],
                             "ratio_ventas": round(p["ratio"], 2),
                             "mercados": p["mercados"],
                             "deporte_pct": round(p["deporte"] * 100),
                             "mediana_usd": round(p["mediana_usd"], 2),
                             "elegido_en": int(time.time())})
        time.sleep(0.2)
        if len(elegidos) >= COPY_N_TRADERS:
            break
    cp["traders"] = elegidos
    cp["ts_eleccion"] = time.time()
    guardar_estado(estado)
    log(f"  [copy] vigilando {len(elegidos)} traders: "
        + ", ".join(t["nombre"] for t in elegidos))
    if chat_id and elegidos:
        lines = "".join(f"   {i}. *{t['nombre']}* {_din_lb(t['profit'])} · "
                        f"{t['compras48h']} compras/48h · {t['deporte_pct']}% deporte\n"
                        for i, t in enumerate(elegidos, 1))
        enviar(chat_id, f"📡 *Copy-trading en papel*: ya vigilo a {len(elegidos)} traders\n"
                        f"{lines}_Top {COPY_VENTANA} filtrado (fuera market makers, "
                        f"inactivos y concentrados). Sus compras son SEÑALES: no compro nada._")
    return elegidos


def fills_recientes(wallet, desde_ts, limite=200):
    """Compras de una wallet posteriores a desde_ts (más recientes primero)."""
    try:
        act = _lb_get(f"{DATA_API}/activity?user={wallet}&limit={limite}&type=TRADE") or []
    except Exception:
        return []
    out = [x for x in act if x.get("type") == "TRADE" and x.get("side") == "BUY"
           and int(x.get("timestamp") or 0) > float(desde_ts)]
    out.sort(key=lambda x: -int(x.get("timestamp") or 0))
    return out


def estado_copy(estado):
    return estado.setdefault("copy", {"traders": [], "vistos": {}, "ts_ultimo": 0,
                                      "ts_inicio": 0, "ts_eleccion": 0, "informes": 0})


def señales_hoy(estado):
    """Señales registradas hoy (UTC): tope PROPIO, independiente del de combos."""
    hoy = time.strftime("%Y-%m-%d", time.gmtime())
    return sum(1 for s in (estado.get("copy_señales") or [])
               if str(s.get("dia") or "") == hoy)


def _caras_de(cid):
    """{token_id: {'winner': bool}} si el mercado YA tiene ganador; si está
    closed sin ganador → 'anulada'; si no, None (sigue vivo)."""
    m = mercado_clob(cid)
    if not isinstance(m, dict):
        return None
    caras = {str(tk.get("token_id")): {"winner": bool(tk.get("winner"))}
             for tk in (m.get("tokens") or [])}
    if not caras:
        return None
    if any(v["winner"] for v in caras.values()):
        return caras
    if m.get("closed"):
        return "anulada"          # ↩️ como las anuladas del panel: devuelve 0
    return None


def registrar_señal(estado, trader, wallet, fill, precio_nuestro):
    """📡 Anota una señal EN PAPEL con los DOS precios (el suyo y el nuestro).
    → registro, o None si el tope diario ya está cubierto.
    Si el trader ESCALA en la misma posición (mismo token, hoy, sin resolver) no se
    crea otra señal: se fusiona el importe y se deja el precio de la PRIMERA entrada
    (el momento en que nosotros habríamos entrado). Así el tope de señales/día cuenta
    MERCADOS distintos, no fills sueltos (medido: 102 fills = 4 posiciones)."""
    hoy = time.strftime("%Y-%m-%d", time.gmtime())
    tok, wal = str(fill.get("asset") or ""), str(wallet)
    for prev in reversed(estado.get("copy_señales") or []):
        if (prev.get("token") == tok and prev.get("wallet") == wal
                and prev.get("dia") == hoy and not prev.get("resuelta")):
            prev["escaladas"] = int(prev.get("escaladas") or 0) + 1
            prev["usd_trader"] = round(float(prev.get("usd_trader") or 0)
                                       + float(fill.get("usdcSize") or 0), 2)
            prev["size_trader"] = round(float(prev.get("size_trader") or 0)
                                        + float(fill.get("size") or 0), 4)
            prev["ts_ultimo_fill"] = int(fill.get("timestamp") or 0)
            prev["precio_nuestro_max"] = round(max(float(prev.get("precio_nuestro_max")
                                                         or prev.get("precio_nuestro") or 0),
                                                   float(precio_nuestro or 0)), 4)
            return prev
    if señales_hoy(estado) >= COPY_TOPE_DIA:
        return None
    p_el = float(fill.get("price") or 0)
    if not (0 < p_el < 1) or not precio_nuestro:
        return None
    ts_fill = int(fill.get("timestamp") or 0)
    reg = {
        "dia": time.strftime("%Y-%m-%d", time.gmtime()),
        "ts": int(time.time()), "ts_fill": ts_fill,
        "retraso_s": int(time.time()) - ts_fill,
        "trader": str(trader)[:24], "wallet": str(wallet),
        "titulo": str(fill.get("title") or "?")[:110],
        "slug": fill.get("slug"), "event_slug": fill.get("eventSlug"),
        "condition_id": str(fill.get("conditionId") or ""),
        "token": str(fill.get("asset") or ""), "outcome": fill.get("outcome"),
        "precio_trader": p_el,
        "cuota_trader": round(1 / p_el, 2),
        "usd_trader": round(float(fill.get("usdcSize") or 0), 2),
        "size_trader": round(float(fill.get("size") or 0), 4),
        "precio_nuestro": round(float(precio_nuestro), 4),
        "cuota_nuestro": round(1 / float(precio_nuestro), 2),
        "deriva_pts": round((float(precio_nuestro) - p_el) * 100, 2),
        "deporte": es_deporte_copy(fill.get("eventSlug") or fill.get("title")),
        # ¿serviría esta pierna para un combo nuestro? (Fase 2)
        "en_rango_combo": bool(1 / CUOTA_MAX <= float(precio_nuestro) <= 1 / CUOTA_MIN),
        "tx": str(fill.get("transactionHash") or "")[:24],
        "resuelta": False, "senal_acerto": None, "anulada": False,
        "pnl_papel_nuestro": None, "pnl_papel_trader": None,
        "ejecutada": False,       # Fase 2: si algún día se convierte en combo propio
        "escaladas": 0,           # compras posteriores en la MISMA posición (fusionadas)
        "precio_nuestro_max": round(float(precio_nuestro), 4),
        "ts_ultimo_fill": ts_fill,
    }
    estado.setdefault("copy_señales", []).append(reg)
    return reg


def resolver_señales(estado):
    """Cierra las señales cuyo mercado ya se resolvió: ¿acertó la SEÑAL? y qué PnL
    teórico habría dado a $5 al precio NUESTRO y al SUYO. → nº resueltas ahora."""
    pend = [s for s in (estado.get("copy_señales") or []) if not s.get("resuelta")]
    if not pend:
        return 0
    # Acotado: como máximo COPY_RESOLVER_POR_RONDA mercados mirados por pasada,
    # para que resolver señales no estire el PASADA_LOCK de los combos.
    n = 0
    for s in pend[:COPY_RESOLVER_POR_RONDA]:
        caras = _caras_de(s.get("condition_id"))
        if caras is None:
            continue
        if caras == "anulada":
            s["resuelta"], s["anulada"], s["senal_acerto"] = True, True, None
            s["pnl_papel_nuestro"] = s["pnl_papel_trader"] = 0.0
            n += 1
            continue
        info = caras.get(str(s.get("token")))
        if info is None:
            continue
        gano = bool(info.get("winner"))
        s["senal_acerto"] = gano
        for kp, kpnl in (("precio_nuestro", "pnl_papel_nuestro"),
                         ("precio_trader", "pnl_papel_trader")):
            p = float(s.get(kp) or 0)
            s[kpnl] = round(COPY_STAKE_PAPEL * (1 / p - 1) if gano
                            else -COPY_STAKE_PAPEL, 3) if 0 < p < 1 else None
        s["resuelta"] = True
        n += 1
    return n


def resumen_copy(estado):
    """Números del seguimiento. La cifra que importa: ROI AL PRECIO NUESTRO."""
    s = estado.get("copy_señales") or []
    res = [x for x in s if x.get("resuelta") and not x.get("anulada")]
    anu = [x for x in s if x.get("anulada")]
    ac = [x for x in res if x.get("senal_acerto")]
    pn_n = sum(float(x.get("pnl_papel_nuestro") or 0) for x in res)
    pn_t = sum(float(x.get("pnl_papel_trader") or 0) for x in res)
    der = [float(x["deriva_pts"]) for x in s if x.get("deriva_pts") is not None]
    ret = [int(x.get("retraso_s") or 0) for x in s if x.get("retraso_s")]
    por = {}
    for x in res:
        g = por.setdefault(x.get("trader", "?"), {"n": 0, "ac": 0, "pnl_n": 0.0, "pnl_t": 0.0})
        g["n"] += 1
        g["ac"] += 1 if x.get("senal_acerto") else 0
        g["pnl_n"] += float(x.get("pnl_papel_nuestro") or 0)
        g["pnl_t"] += float(x.get("pnl_papel_trader") or 0)
    cp = estado.get("copy") or {}
    dias = max(1, int((time.time() - float(cp.get("ts_inicio") or time.time())) // 86400) + 1)
    return {"senales": len(s), "resueltas": len(res), "anuladas": len(anu),
            "aciertos": len(ac),
            "acierto_pct": (len(ac) / len(res) * 100) if res else None,
            "pnl_nuestro": round(pn_n, 2), "pnl_trader": round(pn_t, 2),
            "roi_nuestro": (pn_n / (len(res) * COPY_STAKE_PAPEL) * 100) if res else None,
            "deriva_med": round(sum(der) / len(der), 2) if der else None,
            "retraso_med_s": int(sum(ret) / len(ret)) if ret else None,
            "por_trader": por, "dias": dias, "en_rango": sum(1 for x in s if x.get("en_rango_combo")),
            "hoy": señales_hoy(estado), "tope": COPY_TOPE_DIA,
            "escaladas": sum(int(x.get("escaladas") or 0) for x in s),
            "traders": cp.get("traders") or []}


def texto_copy(estado):
    """📡 /copy — panel del seguimiento en papel."""
    r = resumen_copy(estado)
    t = ("📡 *COPY-TRADING EN PAPEL* (Fase 1 · sin dinero)\n"
         f"_día {r['dias']} de seguimiento · el bot NO compra: sólo anota_\n\n")
    if r["traders"]:
        t += f"👥 *Vigilando* (top {COPY_VENTANA} filtrado):\n"
        for x in r["traders"][:COPY_N_TRADERS]:
            t += (f"   · *{x['nombre']}* {_din_lb(x.get('profit'))} · "
                  f"{x.get('compras48h', '?')} compras/48h · "
                  f"{x.get('deporte_pct', '?')}% deporte\n")
    else:
        t += "👥 _Aún sin traders elegidos (la próxima pasada los filtra)_\n"
    t += (f"\n📨 Señales: *{r['senales']}* · hoy {r['hoy']}/{r['tope']} · "
          f"útiles para un combo (cuota {CUOTA_MIN}-{CUOTA_MAX}): {r['en_rango']}")
    t += (f" · {r['escaladas']} compras repetidas fusionadas\n" if r["escaladas"] else "\n")
    if r["resueltas"]:
        t += (f"🏁 Resueltas: *{r['resueltas']}*"
              + (f" (+{r['anuladas']} ↩️ anuladas)" if r["anuladas"] else "")
              + f" · acierto *{r['acierto_pct']:.1f}%* ({r['aciertos']}/{r['resueltas']})\n")
        t += (f"💵 PnL teórico a ${COPY_STAKE_PAPEL:.0f}/señal: al precio NUESTRO "
              f"*${r['pnl_nuestro']:+.2f}* (ROI {r['roi_nuestro']:+.1f}%) · "
              f"al precio de ellos ${r['pnl_trader']:+.2f}\n")
        if r["deriva_med"] is not None:
            m, sg = divmod(int(r["retraso_med_s"] or 0), 60)
            t += (f"⏱ Llegamos {m} min {sg} s tarde de media · "
                  f"deriva de precio *{r['deriva_med']:+.2f} pts*\n")
        if r["por_trader"]:
            t += "\n*Por trader* (resueltas · acierto · PnL nuestro):\n"
            for nom, g in sorted(r["por_trader"].items(), key=lambda kv: -kv[1]["pnl_n"]):
                t += (f"   · {str(nom)[:20]:<20} {g['n']:>3} · "
                      f"{g['ac'] / max(g['n'], 1) * 100:>5.1f}% · ${g['pnl_n']:>+8.2f}\n")
    else:
        t += "\n🏁 _Ninguna resuelta aún: los mercados tardan horas o días._\n"
    t += ("\n🎯 *Para pasar a Fase 2* (convertir la señal en un combo propio por RFQ): "
          "≥30 señales resueltas y ROI positivo AL PRECIO NUESTRO.\n"
          "_Medido antes de arrancar: el top-1 histórico activo dio −48.8% en 48 h y "
          "en 30 días conviven +130% con −100%. Por eso en papel._")
    return t


def cmd_copy(chat_id):
    estado = cargar_estado()
    estado_copy(estado)
    return enviar(chat_id, texto_copy(estado))


def copy_pasada(chat_id):
    """📡 v12.9.0: una ronda de seguimiento EN PAPEL. LEE (ranking, fills, mid),
    anota señales con tope propio y resuelve las antiguas. NO firma nada: no hay
    ningún camino de esta función a enviar_orden/ejecutar_trade/ejecutar_combo_rfq."""
    global NEXT_COPY_RESUMEN_TS
    if not COPY_ACTIVO:
        return
    estado = cargar_estado()
    cp = estado_copy(estado)
    if not cp.get("ts_inicio"):
        cp["ts_inicio"] = time.time()
        NEXT_COPY_RESUMEN_TS = time.time() + COPY_RESUMEN_CADA_S
    traders = cp.get("traders") or []
    if not traders or time.time() - float(cp.get("ts_eleccion") or 0) > COPY_ELEGIR_CADA_S:
        # La PRIMERA elección se anuncia en el chat; las reevaluaciones diarias, no.
        primera = not float(cp.get("ts_eleccion") or 0)
        traders = copy_elegir(estado, chat_id=chat_id if primera else None)
    if not traders:
        guardar_estado(estado)
        return
    vistos = cp.setdefault("vistos", {})
    desde = float(cp.get("ts_ultimo") or (time.time() - 3600))
    nuevas = 0
    fusiones = 0
    tope = False
    for t in traders:
        if tope:
            break
        for f in fills_recientes(t.get("wallet"), desde):
            clave = f"{str(f.get('transactionHash') or '')[:24]}|{str(f.get('asset') or '')[:20]}"
            if clave in vistos:
                continue
            vistos[clave] = int(time.time())
            p_el = float(f.get("price") or 0)
            p_no = precio_mid(str(f.get("asset") or ""))
            titulo = str(f.get("title") or "?")[:60]
            if not (0 < p_el < 1):
                continue
            if p_no is None:
                log(f"  [copy] sin libro para {titulo} · señal no registrada")
                continue
            if abs(p_no - p_el) > COPY_DERIVA_MAX:
                log(f"  [copy] señal TARDÍA {titulo}: él {p_el:.3f} → ahora {p_no:.3f} "
                    f"({(p_no - p_el) * 100:+.1f} pts) · no cuenta")
                continue
            reg = registrar_señal(estado, t.get("nombre"), t.get("wallet"), f, p_no)
            if reg is None:
                log(f"  [copy] tope diario de señales ({COPY_TOPE_DIA}) alcanzado")
                tope = True
                break
            if int(reg.get("escaladas") or 0):
                fusiones += 1          # una sola línea de log por ronda (no 1 por fill)
                continue
            nuevas += 1
            m, sg = divmod(max(0, reg["retraso_s"]), 60)
            log(f"  [copy] 📡 señal #{reg['ts']} de {reg['trader']}: {titulo} · "
                f"él {p_el:.3f} / nosotros {p_no:.3f} ({reg['deriva_pts']:+.1f} pts) · "
                f"retraso {m}m{sg:02d}s · papel ${COPY_STAKE_PAPEL:.0f}")
            if chat_id:
                enviar(chat_id, f"📡 *SEÑAL (papel, $0)* · {reg['trader']} compró\n"
                                f"📌 {titulo} ({reg.get('outcome') or '?'})\n"
                                f"💵 él a {p_el:.3f} (${reg['usd_trader']:,.0f}) · "
                                f"nosotros entraríamos a {p_no:.3f} "
                                f"({reg['deriva_pts']:+.1f} pts) · cuota {reg['cuota_nuestro']:.2f}\n"
                                f"⏱ Retraso {m} min {sg} s · {'⚽ deporte' if reg['deporte'] else '🎲 no deporte'}"
                                f" · {'✅ sirve para un combo' if reg['en_rango_combo'] else '❌ fuera de tu rango de cuota'}\n"
                                f"_No se ha comprado nada. /copy → el resumen_")
        time.sleep(0.2)
    corte = int(time.time()) - COPY_VISTOS_DIAS * 86400
    limpios = {k: v for k, v in vistos.items() if int(v) >= corte}
    if len(limpios) > COPY_MAX_VISTOS:
        limpios = dict(sorted(limpios.items(), key=lambda kv: -int(kv[1]))[:COPY_MAX_VISTOS])
    cp["vistos"] = limpios
    cp["ts_ultimo"] = time.time()
    resueltas = resolver_señales(estado)
    señ = estado.get("copy_señales") or []
    if len(señ) > COPY_MAX_SEÑALES:
        estado["copy_señales"] = señ[-COPY_MAX_SEÑALES:]
    guardar_estado(estado)
    if nuevas or resueltas or fusiones:
        log(f"  [copy] ronda: {nuevas} señal(es) nueva(s) · {fusiones} compra(s) "
            f"repetida(s) fusionada(s) · {resueltas} resuelta(s) · "
            f"dedup {len(cp['vistos'])} fills")
    if chat_id and time.time() >= NEXT_COPY_RESUMEN_TS:
        NEXT_COPY_RESUMEN_TS = time.time() + COPY_RESUMEN_CADA_S
        cp["informes"] = int(cp.get("informes") or 0) + 1
        guardar_estado(estado)
        try:
            enviar(chat_id, texto_copy(estado))
        except Exception:
            pass


def programar_copy_inicio():
    """📡 Primera ronda ~90 s tras arrancar (deja terminar a la auto-curación)."""
    global NEXT_COPY_TS, NEXT_COPY_RESUMEN_TS
    NEXT_COPY_TS = time.time() + 90
    NEXT_COPY_RESUMEN_TS = time.time() + COPY_RESUMEN_CADA_S


def cmd_top(chat_id, ventana=None):
    """🏆 v12.9.0: ranking REAL y en vivo (antes era una lista escrita a mano y
    falsa). Con botones para cambiar de ventana y la wallet de cada trader."""
    v = ventana if ventana in VENTANAS_LB else "1d"
    filas = top_traders(v, 10)
    if not filas:
        return enviar(chat_id, "🏆 *TOP TRADERS POLYMARKET*\n\n"
                               "_lb-api no respondió ahora mismo (sin datos que enseñar). "
                               "Reintenta en unos minutos: el botón 🏆 no inventa cifras._")
    edad = int(time.time() - _LB_CACHE[0]) if _LB_CACHE[0] else 0
    t = (f"🏆 *TOP TRADERS POLYMARKET* · {VENTANAS_LB[v]}\n"
         f"_ranking real de lb-api · hace {edad // 60 if edad >= 60 else edad}"
         f"{' min' if edad >= 60 else ' s'}_\n\n")
    for i, nom, w, prof, vol in filas:
        margen = f"{prof / vol * 100:.0f}%" if vol > 0 else "n/d"
        t += (f"{i:>2}. *{str(nom)[:22]}* {_din_lb(prof)}\n"
              f"     vol {_din_lb(vol)} · margen {margen} · `{w[:10]}…{w[-6:]}`\n")
    t += ("\n⚠️ Estar arriba NO significa que vayan a seguir ganando: el top-1 histórico "
          "activo dio −48.8% en sus últimas 48 h.\n"
          "📡 /copy → a quiénes vigila el bot y qué dan sus señales (en papel, $0).")
    kb = {"inline_keyboard": [[{"text": ("✅ " if v == k else "") + lab,
                                "callback_data": f"lb:{k}"}
                               for k, lab in VENTANAS_LB.items()]]}
    return enviar(chat_id, t, kb)


'''


def aplicar(src):
    cambios = []

    def sustituir(viejo, nuevo, etiqueta):
        nonlocal src
        n = src.count(viejo)
        if n != 1:
            raise SystemExit(f"[parche v12.9.0] '{etiqueta}': {n} coincidencias (esperaba 1)")
        src = src.replace(viejo, nuevo, 1)
        cambios.append(etiqueta)

    # ---------------------------------------------------------- 0) versiones
    sustituir('POLY COMBOS BOT v12.8.4 — COMBOS REALES (parlays multi-leg) via RFQ',
              'POLY COMBOS BOT v12.9.0 — COMBOS REALES (parlays multi-leg) via RFQ',
              "cabecera v12.9.0")
    sustituir('    log("v12.8.4 iniciado")', '    log("v12.9.0 iniciado")',
              "log de arranque v12.9.0")
    sustituir('    txt = ("💰 *RECLAMAR v12.8.4*\\n\\n"',
              '    txt = ("💰 *RECLAMAR v12.9.0*\\n\\n"', "título /reclamar v12.9.0")
    sustituir('    texto = (f"🤖 *POLY COMBOS BOT v12.8.4*\\n\\n"',
              '    texto = (f"🤖 *POLY COMBOS BOT v12.9.0*\\n\\n"', "título /start v12.9.0")
    sustituir('    texto = (f"📊 *ESTADO v12.8.4 (Combos)*\\n\\n"',
              '    texto = (f"📊 *ESTADO v12.9.0 (Combos)*\\n\\n"', "título /status v12.9.0")
    sustituir('    log(f"v12.8.4 cargado · modo={MODO_OPERACION}',
              '    log(f"v12.9.0 cargado · modo={MODO_OPERACION}', "línea 'cargado' v12.9.0")

    sustituir('   v12.8.4: 🟡 SEMI DE VERDAD + ⚖️ VENTAJA MÍNIMA 5%.',
              '''   v12.9.0: 🏆 TOP REAL EN VIVO + 📡 COPY-TRADING EN PAPEL (FASE 1, $0). El botón
   🏆 era una lista escrita a mano y falsa; ahora llama a lb-api (ventanas
   1d/7d/30d/all con botones) y enseña la wallet de cada trader. Además el bot
   vigila los fills de los 5 mejores (filtrados por conducta: activos, no market
   makers, no concentrados en 1-2 mercados y ≥40% deporte) y ANOTA cada compra
   como señal con dos precios: el suyo y el mid real al que nosotros entraríamos.
   Si el precio ya se movió más de 5 puntos, la señal se descarta por tardía. Escalan
   mucho (medido en vivo: 102 fills de un trader en 1 h eran sólo 4 posiciones), así
   que las compras repetidas del MISMO mercado se FUSIONAN en una señal: cuenta el
   importe total y vale el precio de la primera entrada, que es cuando nosotros
   habríamos entrado. El tope diario cuenta pues MERCADOS distintos, no fills.
   Cuando el mercado se resuelve se apunta si acertó y el PnL teórico a $5 al
   precio nuestro y al suyo → /copy da acierto, ROI, deriva y desglose por
   trader. NO GASTA NADA: COPY_DINERO=False, las señales viven en
   estado["copy_señales"] (nunca en trades_copiados) y no hay camino desde esta
   versión a firmar una orden. Se midió antes: copiar al top-1 histórico activo
   habría dado −48.8% en 48 h, y en 30 días conviven +130% con −100%.
   v12.8.4: 🟡 SEMI DE VERDAD + ⚖️ VENTAJA MÍNIMA 5%.''',
              "changelog v12.9.0 en la cabecera")

    # ------------------------------- 1) sección nueva (sustituye al cmd_top fijo)
    viejo_top = '''def cmd_top(chat_id):
    texto = ("*🏆 TOP TRADERS POLYMARKET*\\n\\n"
             "1. pleaseplease123 +$1.0M\\n"
             "2. ferrariChampions2026 +$791K\\n"
             "3. balthazar +$534K\\n"
             "4. 0xd9670... +$466K\\n"
             "5. Talvez10 +$339K\\n"
             "6. AV23IUa +$311K\\n"
             "7. 11vsldfdsgfkjgos +$272K\\n"
             "8. Flaznorp +$265K\\n"
             "9. sainttroplay +$207K\\n"
             "10. ExplosiveNinja +$189K")
    return enviar(chat_id, texto)'''
    assert src.count(viejo_top) == 1, "no encuentro el cmd_top hardcodeado"
    sustituir(viejo_top, SECCION.rstrip("\n"),
              "sección v12.9.0 (top real + seguimiento en papel) sustituye al cmd_top falso")

    # ---------------------------------------------- 2) teclado + botones
    sustituir('            [{"text": "💥 SúperCombos"}, {"text": "💰 Reclamar"}],',
              '            [{"text": "💥 SúperCombos"}, {"text": "💰 Reclamar"},\n'
              '             {"text": "📡 Copy"}],',
              "teclado: botón 📡 Copy")

    sustituir('''    elif text == "🏆 Top":''',
              '''    elif text == "📡 Copy":                  # v12.9.0: seguimiento en papel
        return cmd_copy(chat_id)
    elif text == "🏆 Top":''',
              "handler del botón 📡 Copy")

    sustituir('''    elif text == "/top":''',
              '''    elif text in ("/copy", "/copytrading", "/señales", "/senales"):
        return cmd_copy(chat_id)          # v12.9.0
    elif text == "/top":''',
              "comando /copy")

    # ---------------------------------------------- 3) callbacks de ventana
    sustituir('''    if data.startswith("sm:") and cid:       # v12.8.4: 🟡 SEMI ✅ aceptar''',
              '''    if data.startswith("lb:") and cid:       # v12.9.0: 🏆 ventana del ranking
        telegram_api("answerCallbackQuery", {"callback_query_id": cbid})
        return cmd_top(cid, data.split(":", 1)[1])
    if data.startswith("sm:") and cid:       # v12.8.4: 🟡 SEMI ✅ aceptar''',
              "procesar_callback: lb:<ventana>")

    # ---------------------------------------------- 4) ronda en el auto_loop
    sustituir('''    global NEXT_PASADA_TS, NEXT_AUDITORIA_TS
    while True:''',
              '''    global NEXT_PASADA_TS, NEXT_AUDITORIA_TS, NEXT_COPY_TS
    while True:''',
              "auto_loop: global NEXT_COPY_TS")

    sustituir('''        # v12.7: auto-curación (no depende del modo: corrige el histórico igual)''',
              '''        # 📡 v12.9.0: seguimiento en papel de los top (no depende del modo y NO
        # gasta dinero: sólo lee ranking/fills/mids y anota señales)
        try:
            if COPY_ACTIVO and CHAT_ID and time.time() >= NEXT_COPY_TS:
                NEXT_COPY_TS = time.time() + COPY_SONDEO_S
                with PASADA_LOCK:
                    copy_pasada(CHAT_ID)
        except Exception as e:
            log(f"copy_loop error: {e}")
        # v12.7: auto-curación (no depende del modo: corrige el histórico igual)''',
              "auto_loop: ronda de seguimiento en papel")

    sustituir('''    v12.8.4: en SEMI también hay pasada, pero PROPONE (✅/❌) en vez de comprar."""''',
              '''    v12.8.4: en SEMI también hay pasada, pero PROPONE (✅/❌) en vez de comprar.
    v12.9.0: además lanza la ronda 📡 de copy-trading EN PAPEL cada COPY_SONDEO_S
    (lectura pública, sin proxy y sin firmar nada)."""''',
              "docstring auto_loop (copy en papel)")

    sustituir('''    restaurar_modo(_est0)   # 🟡 v12.8.4: SEMI/OFF sobreviven al reinicio''',
              '''    restaurar_modo(_est0)   # 🟡 v12.8.4: SEMI/OFF sobreviven al reinicio
    programar_copy_inicio()  # 📡 v12.9.0: 1ª ronda de seguimiento en ~90 s''',
              "main() programa la primera ronda 📡")

    # ---------------------------------------------- 5) ayuda de /start
    sustituir('''             f"⚖️ Ventaja mínima *{int(VENTAJA_MIN_EV * 100)}%*:''',
              '''             f"🏆 *Top* — ranking REAL de Polymarket (lb-api) con botones 24 h / 7 días / 30 días / histórico y la wallet de cada trader. Ya no es una lista escrita a mano\\n"
             f"📡 *Copy* — FASE 1 EN PAPEL ($0): vigilo los fills de los {COPY_N_TRADERS} mejores filtrados (fuera market makers, inactivos y concentrados) y anoto cada compra como señal con su precio y el nuestro; /copy da acierto, ROI y desglose por trader. No compro nada todavía\\n"
             f"⚖️ Ventaja mínima *{int(VENTAJA_MIN_EV * 100)}%*:''',
              "ayuda /start: 🏆 Top real + 📡 Copy en papel")

    return src, cambios


if __name__ == "__main__":
    ent, sal = sys.argv[1], sys.argv[2]
    src = io.open(ent, encoding="utf-8").read()
    nuevo, cambios = aplicar(src)
    assert "v12.9.0" in nuevo.splitlines()[3], "cabecera sin v12.9.0"
    assert "pleaseplease123" not in nuevo, "queda la lista falsa del Top"
    assert nuevo.count("def cmd_top(") == 1 and "def cmd_copy(" in nuevo
    for fn in ("def top_traders(", "def perfil_trader(", "def filtros_perfil(",
               "def copy_elegir(", "def fills_recientes(", "def registrar_señal(",
               "def resolver_señales(", "def resumen_copy(", "def texto_copy(",
               "def copy_pasada(", "def programar_copy_inicio(", "def _caras_de(",
               "def estado_copy(", "def señales_hoy(", "def _lb_get(", "def _din_lb(",
               "def nombre_lb("):
        assert nuevo.count(fn) == 1, f"{fn} debe aparecer 1 vez: {nuevo.count(fn)}"
    assert "COPY_DINERO = False" in nuevo and "COPY_ACTIVO = True" in nuevo
    assert nuevo.count("copy_pasada(CHAT_ID)") == 1
    assert 'prev["escaladas"] = int(prev.get("escaladas") or 0) + 1' in nuevo, \
        "falta la fusión de compras repetidas en la misma posición"
    assert nuevo.count("def proponer_combo_semi(") == 1      # v12.8.4 intacto
    assert nuevo.count("def restaurar_modo(") == 1
    assert nuevo.count("VENTAJA_MIN_EV = 0.05") == 1
    assert nuevo.count("def ejecutar_combo_rfq(") == 1 and nuevo.count("def main()") == 1
    assert nuevo.count("def curar_abiertas(") == 1 and nuevo.count("def cmd_leer_ahora(") == 1
    assert 'data.startswith("lb:")' in nuevo and '{"text": "📡 Copy"}' in nuevo
    io.open(sal, "w", encoding="utf-8").write(nuevo)
    print(f"✅ v12.9.0 generado: {sal} · {len(cambios)} cambios:")
    for c in cambios:
        print(f"     · {c}")
    print(f"   líneas: {len(nuevo.splitlines())} · md5 {hashlib.md5(nuevo.encode()).hexdigest()}")
