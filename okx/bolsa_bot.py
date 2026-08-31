#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bot informativo de acciones (@lamegawi_bolsa_bot).

Funciones:
  - 📊 Precios: cotización en vivo de la watchlist (Yahoo Finance, gratis).
  - 🔔 Alertas: avisa si un valor sube/baja más del umbral (3%) en el día.
  - 💰 Saldo: cartera comprada -> cantidad, precio compra, precio actual,
    valor actual y P&L (€ y %) de cada posición + totales.
  - ➕ Añadir acción: pregunta si es COMPRADA (pide ticker -> cantidad ->
    precio por acción) o para SEGUIMIENTO (solo se añade a la watchlist).
  - ➖ Quitar acción: de la cartera o de la watchlist.
  - Resumen diario a las 9:00 y 21:00 (hora de Madrid).

Fuente: Yahoo Finance (chart API, sin clave).
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

TOKEN = os.environ.get("BOLSA_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
CONFIG = "/root/bolsa_config.json"
CARTERA_FILE = "/root/bolsa_cartera.json"
ESTADO_ALERTAS = "/root/bolsa_alertas.json"
MAD = ZoneInfo("Europe/Madrid")

CONFIG_DEFECTO = {
    "umbral_pct": 3.0,
    "tickers": [
        {"simbolo": "SPCX", "nombre": "SpaceX", "yahoo": "SPCX"},
        {"simbolo": "CMG", "nombre": "Chipotle", "yahoo": "CMG"},
        {"simbolo": "HVE", "nombre": "Innoviva", "yahoo": "HVE.F"},
        {"simbolo": "I1V", "nombre": "CoreWeave", "yahoo": "I1V.F"},
        {"simbolo": "E6Z", "nombre": "AECOM", "yahoo": "E6Z.F"},
        {"simbolo": "2ON", "nombre": "Peloton", "yahoo": "2ON.F"},
        {"simbolo": "MIGA", "nombre": "Strategy", "yahoo": "MIGA.F"},
        {"simbolo": "02M", "nombre": "Mosaic", "yahoo": "02M.F"},
    ],
}

# Estado de conversación (en memoria)
ESPERA = {"paso": None, "datos": {}}


def cargar_config():
    try:
        with open(CONFIG, encoding="utf-8") as f:
            cfg = json.load(f)
        for k, v in CONFIG_DEFECTO.items():
            cfg.setdefault(k, v)
        return cfg
    except Exception:
        return json.loads(json.dumps(CONFIG_DEFECTO))


def guardar_config(cfg):
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def cargar_cartera():
    try:
        with open(CARTERA_FILE, encoding="utf-8") as f:
            d = json.load(f)
            return d.get("posiciones", [])
    except Exception:
        return []


def guardar_cartera(posiciones):
    try:
        with open(CARTERA_FILE, "w", encoding="utf-8") as f:
            json.dump({"posiciones": posiciones}, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def cargar_alertas():
    try:
        with open(ESTADO_ALERTAS, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def guardar_alertas(d):
    try:
        with open(ESTADO_ALERTAS, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    except Exception:
        pass


# ---------------------------------------------------------------- telegram
def tg(method, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def enviar(texto, keyboard=None):
    p = {"chat_id": CHAT_ID, "text": texto, "disable_web_page_preview": True}
    if keyboard is not None:
        p["reply_markup"] = json.dumps(keyboard)
    return tg("sendMessage", **p)


def teclado():
    return {"keyboard": [["📊 Precios", "🔔 Alertas"],
                         ["💰 Saldo", "➕ Añadir"],
                         ["✏️ Modificar", "➖ Quitar"],
                         ["👀 Seguimiento", "🆘 Ayuda"]],
            "resize_keyboard": True}


def kb_inline(botones):
    return {"inline_keyboard": botones}


def _norm_texto(t):
    """Normaliza el texto de un botón para compararlo sin tildes ni símbolos:
    '➕ Añadir' -> 'anadir', '💰 Saldo' -> 'saldo'."""
    import unicodedata as _ud
    s = (t or "").lower()
    s = "".join(c for c in _ud.normalize("NFKD", s) if not _ud.combining(c))
    return re.sub(r"[^a-z]", "", s)


# ------------------------------------------------------------------ datos
def get_quote(yahoo):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo)}"
           f"?range=1d&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode())
    res = (d.get("chart") or {}).get("result") or []
    if not res:
        return None
    meta = res[0].get("meta") or {}
    precio = meta.get("regularMarketPrice")
    previo = meta.get("previousClose") or meta.get("chartPreviousClose")
    if precio is None:
        return None
    cambio = pct = None
    if previo:
        cambio = precio - previo
        pct = (cambio / previo) * 100
    return {
        "precio": precio, "previo": previo, "cambio": cambio, "pct": pct,
        "moneda": meta.get("currency") or "",
        "nombre": meta.get("shortName") or meta.get("longName") or yahoo,
        "yahoo": yahoo,
    }


def buscar_quote(simbolo):
    """Prueba el símbolo tal cual; si no existe, prueba con .F (bolsa alemana)."""
    for cand in (simbolo, simbolo + ".F"):
        try:
            q = get_quote(cand)
            if q:
                return q
        except Exception:
            continue
    return None


def fetch_watchlist(cfg):
    out = []
    for t in cfg["tickers"]:
        try:
            q = get_quote(t["yahoo"])
            out.append({"ticker": t, "ok": True, "q": q})
        except Exception as e:
            out.append({"ticker": t, "ok": False, "error": str(e)})
    return out


def fmt_pct(pct):
    return "—" if pct is None else f"{pct:+.2f}%"


def flecha(pct):
    if pct is None:
        return "⚪"
    return "🟢" if pct > 0 else ("🔴" if pct < 0 else "⚪")


def circulo_dia(valor):
    """Indicador visual de la variación de la sesión actual."""
    if valor is None:
        return "⚪"
    return "🟢" if valor > 0 else ("🔴" if valor < 0 else "⚪")


def fmt_precio(q):
    if q["moneda"] == "USD":
        return f"${q['precio']:,.2f}"
    return f"{q['precio']:,.2f} €"


def texto_precios(cfg, titulo="📊 *PRECIOS EN VIVO*"):
    datos = fetch_watchlist(cfg)
    lineas = [titulo, ""]
    for d in datos:
        t = d["ticker"]
        if not d["ok"]:
            lineas.append(f"• {t['simbolo']} ({t['nombre']}): ⚠️ sin datos")
            continue
        q = d["q"]
        # No mostrar dominios en el nombre: Telegram los convierte en enlaces
        # automáticamente (p.ej. bet-at-home.com en ACX).
        nombre = t.get("nombre", "") or ""
        nombre = re.sub(r"(?i)\b[\w-]+\.(?:com|net|org|es|de|fr|it)\b", "", nombre).strip()
        lineas.append(f"{flecha(q['pct'])} *{t['simbolo']}*" + (f" {nombre}" if nombre else ""))
        lineas.append(f"    {fmt_precio(q)} · Hoy {circulo_dia(q.get('cambio'))} {fmt_pct(q['pct'])}")
    return "\n".join(lineas)


def texto_saldo():
    posiciones = cargar_cartera()
    lineas = ["💰 *SALDO (cartera)*", ""]
    if not posiciones:
        lineas.append("Aún no has añadido acciones compradas.\n"
                      "Usa ➕ *Añadir* → 💵 *Comprada*.")
        return "\n".join(lineas)

    total_invertido = 0.0
    total_valor = 0.0
    for p in posiciones:
        simbolo = p["simbolo"]
        cantidad = p["cantidad"]
        pc = p["precio_compra"]
        invertido = cantidad * pc
        total_invertido += invertido
        try:
            q = get_quote(p["yahoo"])
        except Exception:
            q = None
        lineas.append(f"*{simbolo}* ({p.get('nombre', '')})")
        lineas.append(f"    {cantidad:g} × {pc:,.2f} {p.get('moneda', '')}")
        if q:
            valor = cantidad * q["precio"]
            pnl = valor - invertido
            pnl_pct = (q["precio"] / pc - 1) * 100 if pc else 0.0
            total_valor += valor
            ic = "🟢" if pnl >= 0 else "🔴"
            lineas.append(f"    ahora {fmt_precio(q)} · valor {fmt_cant(valor, q['moneda'])}")
            # Variación de la cotización durante la sesión actual.
            cambio_hoy = q.get("cambio")
            if cambio_hoy is not None:
                lineas.append(f"    Hoy: {circulo_dia(cambio_hoy)} {fmt_cant(cambio_hoy, q['moneda'])} · {fmt_pct(q.get('pct'))}")
            else:
                lineas.append("    Hoy: —")
            lineas.append(f"    {ic} {fmt_cant(pnl, q['moneda'])} ({pnl_pct:+.2f}%)")
        else:
            lineas.append("    ⚠️ sin cotización ahora")
            total_valor += invertido
        lineas.append("")

    pnl_total = total_valor - total_invertido
    ic_t = "🟢" if pnl_total >= 0 else "🔴"
    lineas.append(f"*Total invertido*: {total_invertido:,.2f}")
    lineas.append(f"*Valor actual*: {total_valor:,.2f}")
    lineas.append(f"{ic_t} *P&L total*: {pnl_total:+,.2f}")
    return "\n".join(lineas)


def fmt_cant(v, moneda):
    if moneda == "USD":
        return f"${v:,.2f}"
    return f"{v:,.2f} €"


def texto_alertas(cfg):
    datos = fetch_watchlist(cfg)
    umbral = cfg["umbral_pct"]
    activas = [(d["ticker"], d["q"]) for d in datos
               if d["ok"] and d["q"]["pct"] is not None and abs(d["q"]["pct"]) >= umbral]
    lineas = [f"🔔 *ALERTAS (umbral {umbral:g}%)*", ""]
    if not activas:
        lineas.append("Ningún valor supera el umbral ahora mismo. ✅")
    for t, q in activas:
        dir_ = "SUBIDA" if q["pct"] > 0 else "BAJADA"
        lineas.append(f"{flecha(q['pct'])} *{t['simbolo']}* {t['nombre']}")
        lineas.append(f"    {q['pct']:+.2f}% ({dir_})")
    return "\n".join(lineas)


def texto_watchlist(cfg):
    return ", ".join(t["simbolo"] for t in cfg["tickers"])


# ---------------------------------------------------------------- comandos
def cmd_precios():
    enviar(texto_precios(cargar_config()))


def cmd_alertas():
    enviar(texto_alertas(cargar_config()))


def cmd_saldo():
    enviar(texto_saldo())


def historial_diario(yahoo, rango="1y"):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(yahoo)}"
           f"?range={rango}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        d = json.loads(r.read().decode())
    res = ((d.get("chart") or {}).get("result") or [None])[0]
    if not res:
        return []
    q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
    return [(float(c), float(h), float(l)) for c, h, l in zip(
        q.get("close") or [], q.get("high") or [], q.get("low") or [])
        if c is not None and h is not None and l is not None]


def analisis_ia(ticker, quote):
    """Análisis técnico orientativo para ayudar a decidir; no ejecuta órdenes."""
    try:
        velas = historial_diario(ticker["yahoo"])
        closes = [x[0] for x in velas]
        precio = float(quote["precio"])
        sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else None
        sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
        tr = []
        for i, (_, hi, lo) in enumerate(velas[-15:]):
            prev = velas[-16 + i][0]
            tr.append(max(hi - lo, abs(hi - prev), abs(lo - prev)))
        atr = sum(tr) / len(tr) if tr else None
        soporte = min(x[2] for x in velas[-60:]) if len(velas) >= 10 else None
        resistencia = max(x[1] for x in velas[-60:]) if len(velas) >= 10 else None
        alcista = bool(sma20 and sma50 and precio > sma20 > sma50)
        bajista = bool(sma20 and sma50 and precio < sma20 < sma50)
        tendencia = "alcista" if alcista else ("bajista" if bajista else "mixta")
        if atr and alcista:
            entrada = max(precio - atr, soporte or precio - atr)
            stop = entrada - 1.5 * atr
            escenario = f"pullback cerca de {entrada:.2f} o ruptura de {resistencia:.2f}" if resistencia else f"pullback cerca de {entrada:.2f}"
        elif atr and bajista:
            entrada = min(precio + atr, resistencia or precio + atr)
            stop = entrada + 1.5 * atr
            escenario = f"rechazo cerca de {entrada:.2f} o pérdida de {soporte:.2f}" if soporte else f"rechazo cerca de {entrada:.2f}"
        else:
            escenario = "esperar confirmación; no hay señal limpia"
            stop = precio - 1.5 * atr if atr else None
        lineas = [f"🤖 *ANÁLISIS IA — {ticker['simbolo']}*", "",
                  f"Precio actual: {fmt_precio(quote)} · Día: {fmt_pct(quote['pct'])}",
                  f"Tendencia técnica: *{tendencia}*", f"SMA20: {sma20:.2f}" if sma20 else "SMA20: —",
                  f"SMA50: {sma50:.2f}" if sma50 else "SMA50: —",
                  f"Soporte 60 sesiones: {soporte:.2f}" if soporte else "Soporte: —",
                  f"Resistencia 60 sesiones: {resistencia:.2f}" if resistencia else "Resistencia: —",
                  "", f"Posible entrada: {escenario}",
                  f"Stop loss aconsejado: {stop:.2f}" if stop else "Stop loss: esperar más datos",
                  "", "⚠️ Orientativo: no es asesoramiento financiero ni una orden."]
    except Exception as e:
        lineas = [f"🤖 *ANÁLISIS IA — {ticker['simbolo']}*", "",
                  "No he podido calcular los indicadores ahora.", "Revisa la cotización e inténtalo de nuevo."]
    enviar("\n".join(lineas), teclado())


def cmd_analisis(simbolo):
    cfg = cargar_config()
    ticker = next((t for t in cfg.get("tickers", []) if t.get("simbolo") == simbolo), None)
    if not ticker:
        enviar(f"No encuentro *{simbolo}* en seguimiento.", teclado())
        return
    try:
        quote = get_quote(ticker["yahoo"])
    except Exception:
        quote = None
    if not quote:
        enviar(f"⚠️ No hay cotización para *{simbolo}* ahora.", teclado())
        return
    analisis_ia(ticker, quote)


def cmd_seguimiento():
    """Lista los valores y ofrece un análisis IA clicable para cada uno."""
    cfg = cargar_config()
    tickers = cfg["tickers"]
    if not tickers:
        enviar("👀 *Seguimiento*\n\n⚪ No sigues ninguna acción todavía.\n"
               "Usa ➕ *Añadir* → 👀 *Para seguimiento*.")
        return
    lineas = ["👀 *ACCIONES EN SEGUIMIENTO*", "",
              "Pulsa el botón de cada acción para ver posibles entradas y stop loss:"]
    botones = []
    for t in tickers:
        # ACX es Acerinox; evitamos mostrar el nombre comercial contaminado
        # que devuelve el proveedor ("... AG") en algunos mercados.
        nombre = "Acerinox" if t.get("simbolo") == "ACX" else (t.get("nombre", "") or "")
        nombre = re.sub(r"(?i)\b[\w-]+\.(?:com|net|org|es|de|fr|it)\b", "", nombre).strip()
        linea = f"• *{t['simbolo']}*"
        if nombre:
            linea += f" — {nombre}"
        lineas.append(linea)
        botones.append([{"text": f"🤖 Análisis IA {t['simbolo']}",
                          "callback_data": f"ana:{t['simbolo']}"}])
    enviar("\n".join(lineas), kb_inline(botones))

def cmd_ayuda():
    cfg = cargar_config()
    enviar("🆘 *Bot de acciones*\n\n"
           "• 📊 *Precios* → cotización en vivo de tu watchlist.\n"
           "• 🔔 *Alertas* → aviso si algo sube/baja más del "
           f"{cfg['umbral_pct']:g}% en el día.\n"
           "• 💰 *Saldo* → valor actual y P&L de tus acciones compradas.\n"
           "• ➕ *Añadir* → añade una acción (comprada o para seguir).\n"
           "• ✏️ *Modificar* → cambia precio y/o cantidad de una posición.\n"
           "• ➖ *Quitar* → quita una acción de la cartera o de la watchlist.\n"
           "• 👀 *Seguimiento* → lista las acciones en seguimiento.\n\n"
           f"Watchlist: {texto_watchlist(cfg)}\n"
           "Resumen automático: 9:00 y 21:00 (hora de Madrid).",
           teclado())


# ---------------------------------------------------------------- añadir
def empezar_anadir():
    ESPERA["paso"] = "add_tipo"
    ESPERA["datos"] = {}
    enviar("➕ *Añadir acción*\n\n¿Cómo la quieres añadir?",
           kb_inline([[{"text": "💵 Comprada", "callback_data": "add_tipo:compra"},
                       {"text": "👀 Para seguimiento", "callback_data": "add_tipo:seg"}],
                      [{"text": "❌ Cancelar", "callback_data": "add_tipo:cancelar"}]]))


def add_tipo(tipo):
    if tipo == "cancelar":
        ESPERA["paso"] = None
        enviar("❌ Cancelado.", teclado())
        return
    ESPERA["datos"]["tipo"] = tipo
    ESPERA["paso"] = "add_sym"
    if tipo == "compra":
        enviar("✍️ Escríbeme el *ticker* de la acción (tal como aparece, "
               "p.ej. `NVDA`, `BBVA.MC`, `SAP.DE`).")
    else:
        enviar("✍️ Escríbeme el *ticker* de la acción a seguir "
               "(p.ej. `NVDA`, `BBVA.MC`, `SAP.DE`).")


def add_sym(simbolo):
    simbolo = (simbolo or "").strip().upper()
    if not simbolo:
        enviar("El ticker no puede estar vacío. Inténtalo otra vez.")
        return
    q = buscar_quote(simbolo)
    if not q:
        enviar(f"⚠️ No encuentro cotización para *{simbolo}*.\n"
               "Revisa el ticker (p.ej. `BBVA.MC`, `NVDA`) o cancela con ❌.",
               kb_inline([[{"text": "❌ Cancelar", "callback_data": "add_tipo:cancelar"}]]))
        return
    ESPERA["datos"]["yahoo"] = q["yahoo"]
    ESPERA["datos"]["nombre"] = q["nombre"]
    ESPERA["datos"]["moneda"] = q["moneda"]
    ESPERA["datos"]["simbolo"] = simbolo
    if ESPERA["datos"]["tipo"] == "seg":
        cfg = cargar_config()
        if any(t["simbolo"] == simbolo for t in cfg["tickers"]):
            enviar(f"ℹ️ *{simbolo}* ya estaba en la watchlist.")
        else:
            cfg["tickers"].append({"simbolo": simbolo, "nombre": q["nombre"],
                                   "yahoo": q["yahoo"]})
            guardar_config(cfg)
            enviar(f"✅ *{simbolo}* ({q['nombre']}) añadido a seguimiento.")
        ESPERA["paso"] = None
        enviar("Listo. Usa 📊 Precios para verlo.", teclado())
    else:
        ESPERA["paso"] = "add_cantidad"
        enviar(f"🔢 *{simbolo}* ({q['nombre']})\n\n"
               f"Precio actual: {fmt_precio(q)}\n"
               f"Escríbeme la *cantidad de acciones* compradas "
               f"(ej. `10` o `2.5`).")


def add_cantidad(txt):
    try:
        cantidad = float(txt.replace(",", ".").strip())
    except Exception:
        enviar("Dame solo el número de la cantidad (ej. `10` o `2.5`).")
        return
    if cantidad <= 0:
        enviar("La cantidad debe ser mayor que 0.")
        return
    ESPERA["datos"]["cantidad"] = cantidad
    ESPERA["paso"] = "add_precio"
    enviar("💵 Ahora el *precio de compra* por acción (ej. `130` o `130.50`).")


def add_precio(txt):
    try:
        precio = float(txt.replace(",", ".").replace("€", "").replace("$", "").strip())
    except Exception:
        enviar("Dame solo el número del precio por acción (ej. `130.50`).")
        return
    if precio <= 0:
        enviar("El precio debe ser mayor que 0.")
        return
    d = ESPERA["datos"]
    d["precio_compra"] = precio
    cantidad = d["cantidad"]
    posiciones = cargar_cartera()
    # si ya existe la misma posición, sumar (precio medio ponderado correcto)
    for p in posiciones:
        if p["simbolo"] == d["simbolo"]:
            cant_prev = p["cantidad"]
            p["precio_compra"] = round(
                (p["precio_compra"] * cant_prev + precio * cantidad)
                / (cant_prev + cantidad), 6)
            p["cantidad"] = round(cant_prev + cantidad, 6)
            guardar_cartera(posiciones)
            enviar(f"✅ Añadidas {cantidad:g} de *{d['simbolo']}* a tu posición "
                   f"(ahora {p['cantidad']:g} acciones).")
            ESPERA["paso"] = None
            enviar("Usa 💰 Saldo para ver el resultado.", teclado())
            return
    posiciones.append({"simbolo": d["simbolo"], "nombre": d["nombre"],
                       "yahoo": d["yahoo"], "moneda": d["moneda"],
                       "precio_compra": precio,
                       "cantidad": cantidad})
    guardar_cartera(posiciones)
    # también a la watchlist si no está
    cfg = cargar_config()
    if not any(t["simbolo"] == d["simbolo"] for t in cfg["tickers"]):
        cfg["tickers"].append({"simbolo": d["simbolo"], "nombre": d["nombre"],
                               "yahoo": d["yahoo"]})
        guardar_config(cfg)
    enviar(f"✅ *{d['simbolo']}* guardada:\n"
           f"{cantidad:g} × {precio:,.2f} {d['moneda']}.")
    ESPERA["paso"] = None
    enviar("Usa 💰 Saldo para ver el resultado.", teclado())


# ---------------------------------------------------------------- modificar
def empezar_modificar():
    posiciones = cargar_cartera()
    if not posiciones:
        enviar("ℹ️ No tienes acciones compradas todavía.\n"
               "Usa ➕ *Añadir* → 💵 *Comprada*.")
        return
    botones = [[{"text": f"{p['simbolo']} ({p['cantidad']:g})",
                 "callback_data": f"mod_sel:{p['simbolo']}"}] for p in posiciones]
    botones.append([{"text": "❌ Cancelar", "callback_data": "mod_sel:cancelar"}])
    enviar("✏️ *Modificar acción*\n\n¿Cuál quieres modificar?",
           kb_inline(botones))


def mod_sel(simbolo):
    if simbolo == "cancelar":
        ESPERA["paso"] = None
        ESPERA["datos"] = {}
        enviar("❌ Cancelado.", teclado())
        return
    posiciones = cargar_cartera()
    p = next((x for x in posiciones if x["simbolo"] == simbolo), None)
    if not p:
        enviar("Esa acción ya no está en la cartera.")
        return
    ESPERA["datos"]["mod_simbolo"] = simbolo
    ESPERA["paso"] = "mod_que"
    enviar(f"✏️ *{simbolo}* ({p['cantidad']:g} × {p['precio_compra']:,.2f} "
           f"{p.get('moneda', '')})\n\n¿Qué quieres modificar?",
           kb_inline([[{"text": "💰 Precio de compra", "callback_data": "mod_que:precio"},
                       {"text": "🔢 Nº de acciones", "callback_data": "mod_que:cantidad"},
                       {"text": "🔁 Ambos", "callback_data": "mod_que:ambos"}],
                      [{"text": "❌ Cancelar", "callback_data": "mod_que:cancelar"}]]))


def mod_que(que):
    if que == "cancelar":
        ESPERA["paso"] = None
        ESPERA["datos"] = {}
        enviar("❌ Cancelado.", teclado())
        return
    ESPERA["datos"]["mod_que"] = que
    if que in ("precio", "ambos"):
        ESPERA["paso"] = "mod_precio"
        enviar("💵 Nuevo *precio de compra* por acción (ej. `130.50`).")
    else:
        ESPERA["paso"] = "mod_cantidad"
        enviar("🔢 Nueva *cantidad* de acciones (ej. `10`).")


def mod_precio(txt):
    try:
        precio = float(txt.replace(",", ".").replace("€", "").replace("$", "").strip())
    except Exception:
        enviar("Dame solo el número del precio (ej. `130.50`).")
        return
    if precio <= 0:
        enviar("El precio debe ser mayor que 0.")
        return
    ESPERA["datos"]["mod_precio"] = precio
    if ESPERA["datos"]["mod_que"] == "ambos":
        ESPERA["paso"] = "mod_cantidad"
        enviar("🔢 Ahora la nueva *cantidad* de acciones.")
    else:
        aplicar_mod()


def mod_cantidad(txt):
    try:
        cantidad = float(txt.replace(",", ".").strip())
    except Exception:
        enviar("Dame solo el número de la cantidad (ej. `10`).")
        return
    if cantidad <= 0:
        enviar("La cantidad debe ser mayor que 0.")
        return
    ESPERA["datos"]["mod_cantidad"] = cantidad
    if ESPERA["datos"]["mod_que"] == "ambos":
        ESPERA["paso"] = "mod_precio"
        enviar("💵 Y el nuevo *precio de compra* por acción.")
    else:
        aplicar_mod()


def aplicar_mod():
    d = ESPERA["datos"]
    simbolo = d["mod_simbolo"]
    posiciones = cargar_cartera()
    p = next((x for x in posiciones if x["simbolo"] == simbolo), None)
    if not p:
        enviar("Esa acción ya no está en la cartera.")
        ESPERA["paso"] = None
        return
    precio = d.get("mod_precio", p["precio_compra"])
    cantidad = d.get("mod_cantidad", p["cantidad"])
    p["precio_compra"] = round(precio, 6)
    p["cantidad"] = round(cantidad, 6)
    guardar_cartera(posiciones)
    ESPERA["paso"] = None
    ESPERA["datos"] = {}
    enviar(f"✅ *{simbolo}* actualizada:\n"
           f"{p['cantidad']:g} × {p['precio_compra']:,.2f} {p.get('moneda', '')}.",
           teclado())
    enviar(texto_saldo())


# ---------------------------------------------------------------- quitar
def empezar_quitar():
    enviar("➖ *Quitar acción*\n\n¿De dónde la quieres quitar?",
           kb_inline([[{"text": "💵 De la cartera", "callback_data": "del_lista:cart"},
                       {"text": "👀 De seguimiento", "callback_data": "del_lista:seg"}],
                      [{"text": "❌ Cancelar", "callback_data": "del_lista:cancelar"}]]))


def del_lista(que):
    if que == "cancelar":
        enviar("❌ Cancelado.", teclado())
        return
    if que == "cart":
        posiciones = cargar_cartera()
        if not posiciones:
            enviar("ℹ️ La cartera está vacía.", teclado())
            return
        botones = [[{"text": f"❌ {p['simbolo']} ({p['cantidad']:g})",
                     "callback_data": f"del_cart:{p['simbolo']}"}] for p in posiciones]
        enviar("Elige qué posición quitar de la cartera:", kb_inline(botones))
    else:
        cfg = cargar_config()
        if not cfg["tickers"]:
            enviar("ℹ️ La watchlist está vacía.", teclado())
            return
        botones = [[{"text": f"❌ {t['simbolo']}",
                     "callback_data": f"del_seg:{t['simbolo']}"}] for t in cfg["tickers"]]
        enviar("Elige qué ticker quitar de seguimiento:", kb_inline(botones))


def del_cart(simbolo):
    posiciones = [p for p in cargar_cartera() if p["simbolo"] != simbolo]
    guardar_cartera(posiciones)
    enviar(f"✅ *{simbolo}* quitada de la cartera.", teclado())


def del_seg(simbolo):
    cfg = cargar_config()
    cfg["tickers"] = [t for t in cfg["tickers"] if t["simbolo"] != simbolo]
    guardar_config(cfg)
    enviar(f"✅ *{simbolo}* quitada de seguimiento.", teclado())


# ---------------------------------------------------------------- flujo
def procesar_callback(cb):
    data = cb.get("data") or ""
    partes = data.split(":")
    # responder siempre para quitar el spinner
    tg("answerCallbackQuery", callback_query_id=cb.get("id"))
    if data.startswith("ana:"):
        cmd_analisis(partes[1])
    elif data.startswith("add_tipo:"):
        add_tipo(partes[1])
    elif data.startswith("del_lista:"):
        del_lista(partes[1])
    elif data.startswith("del_cart:"):
        del_cart(partes[1])
    elif data.startswith("del_seg:"):
        del_seg(partes[1])
    elif data.startswith("mod_sel:"):
        mod_sel(partes[1])
    elif data.startswith("mod_que:"):
        mod_que(partes[1])


BOTONES_MENU = {"precios", "alertas", "saldo", "seguimiento", "watchlist",
                "seguir", "seguidas", "anadir", "agregar", "modificar",
                "editar", "quitar", "eliminar", "ayuda", "start", "menu",
                "cancelar"}


def procesar_texto(t):
    # FIXBOLSA: un boton del teclado SIEMPRE manda. Si habia un flujo
    # a medias (esperando ticker/cantidad/precio) se cancela, en vez de
    # tomar el texto del boton como si fuera el dato pedido.
    _n = _norm_texto(t)
    if _n in BOTONES_MENU and ESPERA.get("paso"):
        ESPERA["paso"] = None
        ESPERA["datos"] = {}
    if _n == "cancelar":
        enviar("Cancelado.", teclado())
        return
    # si hay un flujo en curso, el texto va a ese flujo
    paso = ESPERA.get("paso")
    if paso == "add_sym":
        add_sym(t)
        return
    if paso == "add_precio":
        add_precio(t)
        return
    if paso == "add_cantidad":
        add_cantidad(t)
        return
    if paso == "mod_precio":
        mod_precio(t)
        return
    if paso == "mod_cantidad":
        mod_cantidad(t)
        return

    norm = _norm_texto(t)
    if norm == "precios":
        cmd_precios()
    elif norm == "alertas":
        cmd_alertas()
    elif norm == "saldo":
        cmd_saldo()
    elif norm in ("seguimiento", "watchlist", "seguir", "seguidas"):
        cmd_seguimiento()
    elif norm in ("anadir", "agregar"):
        empezar_anadir()
    elif norm in ("modificar", "editar"):
        empezar_modificar()
    elif norm in ("quitar", "eliminar"):
        empezar_quitar()
    elif norm in ("ayuda", "start", "menu"):
        cmd_ayuda()


# ---------------------------------------------------------------- resumen
def resumen_diario(slot):
    cfg = cargar_config()
    icono = "☀️" if slot == "mañana" else "🌆"
    enviar(texto_precios(cfg, f"{icono} *RESUMEN DE ACCIONES ({slot.upper()})*"))
    pos = cargar_cartera()
    if pos:
        enviar(texto_saldo())


# ------------------------------------------------------------------ alertas
def check_alertas():
    cfg = cargar_config()
    umbral = cfg["umbral_pct"]
    hoy = datetime.now(MAD).strftime("%Y-%m-%d")
    estado = cargar_alertas()
    dia = estado.get(hoy, {})
    datos = fetch_watchlist(cfg)
    avisos = []
    for d in datos:
        if not d["ok"]:
            continue
        t, q = d["ticker"], d["q"]
        if q["pct"] is None or abs(q["pct"]) < umbral:
            continue
        if dia.get(t["simbolo"]):
            continue
        dia[t["simbolo"]] = True
        avisos.append((t, q))
    if avisos:
        for t, q in avisos:
            dir_ = "sube" if q["pct"] > 0 else "baja"
            enviar(f"🔔 *ALERTA*: {t['simbolo']} ({t['nombre']}) {dir_} "
                   f"*{q['pct']:+.2f}%* hoy.\nPrecio: {fmt_precio(q)}.")
        estado[hoy] = dia
        guardar_alertas(estado)


def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Faltan BOLSA_BOT_TOKEN / TELEGRAM_CHAT_ID")
    offset = 0
    last_alerta = 0
    last_res_m, last_res_t = "", ""
    print("[bolsa-bot] arrancado")
    while True:
        if time.time() - last_alerta >= 300:
            last_alerta = time.time()
            try:
                check_alertas()
            except Exception as e:
                print("alertas:", e)

        try:
            ahora = datetime.now(MAD)
            hoy = ahora.strftime("%d/%m/%Y")
            if ahora.hour == 9 and 0 <= ahora.minute < 5 and last_res_m != hoy:
                last_res_m = hoy
                resumen_diario("mañana")
            if ahora.hour == 21 and 0 <= ahora.minute < 5 and last_res_t != hoy:
                last_res_t = hoy
                resumen_diario("noche")
        except Exception as e:
            print("resumen:", e)

        try:
            url = (f"https://api.telegram.org/bot{TOKEN}/getUpdates"
                   f"?offset={offset}&timeout=25"
                   f"&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D")
            with urllib.request.urlopen(url, timeout=35) as r:
                d = json.loads(r.read().decode())
        except Exception:
            time.sleep(3)
            continue
        for upd in d.get("result", []):
            offset = max(offset, upd["update_id"] + 1)
            try:
                cb = upd.get("callback_query")
                if cb:
                    chat = ((cb.get("message") or {}).get("chat") or {}).get("id")
                    if str(chat) == str(CHAT_ID):
                        procesar_callback(cb)
                    continue
                msg = upd.get("message") or {}
                txt = msg.get("text") or ""
                chat = (msg.get("chat") or {}).get("id")
                if str(chat) != str(CHAT_ID):
                    continue
                if txt.startswith("/start"):
                    enviar("👋 *Bot de acciones listo*\n\nUsa los botones de "
                           "abajo:\n📊 Precios · 🔔 Alertas · 💰 Saldo · "
                           "➕ Añadir · ➖ Quitar", teclado())
                else:
                    procesar_texto(txt)
            except Exception as e:
                print("update:", e)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()
