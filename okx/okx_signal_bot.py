#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""SIGNAL-BOT OKX 24/7 — ÚNICO poller del bot real de Telegram (@Bitget_real_trade_bot).

Lee señales (texto o capturas) en el bot real, las analiza y ofrece
EJECUTAR / DESCARTAR (o auto-ejecuta con confianza >= 85 en modo auto).

Reutiliza okx_real_bot (RB) para el análisis de tendencia, el plan (SL + multi-TP)
y la apertura de posiciones REALES en OKX (X-Perps).

- Nada se ejecuta sin confianza ALTA (>= 70) y, en modo automático, >= 85.
- Riesgo por operación: RISK_USD (10 USDC). Máx MAX_OPS posiciones.
"""
import os
import sys
import json
import re
import time
import threading
import unicodedata
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    MAD = ZoneInfo("Europe/Madrid")
except Exception:
    MAD = timezone.utc

sys.path.insert(0, "/root")
import okx_client as OKX
import okx_real_bot as RB

try:
    import ocr_senal as OCR   # OCR + filtro (señal/análisis/ruido)
except Exception:
    OCR = None

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
RISK_USD = float(os.environ.get("RISK_USD", "10"))
MAX_OPS = int(os.environ.get("MAX_OPS", "5"))

OFFSET_FILE = "/root/okx_signal_offset.txt"
STATE_FILE = "/root/okx_signal_state.json"
LOG_FILE = "/root/okx_signal.log"

client = None   # OKX (real)


# ------------------------------------------------------------------ utilidades
def log(txt):
    try:
        with open(LOG_FILE, "a") as f:
            f.write(f"{datetime.now(MAD).isoformat()} {txt}\n")
    except Exception:
        pass


def _tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
        data=data, method="POST")
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def safe_send(text, keyboard=None):
    try:
        p = {"chat_id": TELEGRAM_CHAT_ID, "text": text,
             "disable_web_page_preview": "true"}
        if keyboard is not None:
            p["reply_markup"] = json.dumps(keyboard)
        _tg("sendMessage", **p)
        return True
    except Exception as e:
        log(f"send fallida: {e}")
        return False


def safe_answer(cb_id, text=""):
    try:
        _tg("answerCallbackQuery", callback_query_id=cb_id, text=text)
    except Exception as e:
        log(f"answer fallida: {e}")


def safe_edit_markup(chat_id, mid):
    try:
        _tg("editMessageReplyMarkup", chat_id=chat_id, message_id=mid)
    except Exception:
        pass


# ------------------------------------------------------------------ estado
def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except Exception:
        return {"signals": {}, "executed": [], "esperando_canal": False}


def save_state(st):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(st, f, indent=2)
    except Exception:
        pass


# ------------------------------------------------------------------ parser
NUM = r"[0-9][0-9.,]*[0-9]|[0-9]"


def _n(s):
    return float(str(s).replace(",", ".").replace("€", "").replace("$", "")
                .replace("x", "").strip())


def _detectar_direccion(texto):
    t = texto.lower()
    if "long" in t and "short" in t:
        return "LONG" if t.find("long") < t.find("short") else "SHORT"
    if "long" in t:
        return "LONG"
    if "short" in t:
        return "SHORT"
    for w, d in (("compra", "LONG"), ("buy", "LONG"), ("alcista", "LONG"),
                 ("bullish", "LONG"), ("venta", "SHORT"), ("sell", "SHORT"),
                 ("bajista", "SHORT"), ("bearish", "SHORT")):
        if re.search(rf"\b{w}\b", t):
            return d
    for e, d in (("🔼", "LONG"), ("▲", "LONG"), ("⬆", "LONG"), ("📈", "LONG"),
                 ("🔽", "SHORT"), ("▼", "SHORT"), ("⬇", "SHORT"), ("📉", "SHORT")):
        if e in texto:
            return d
    if "🟢" in texto and "🔴" not in texto:
        return "LONG"
    if "🔴" in texto and "🟢" not in texto:
        return "SHORT"
    return None


def _base(sym):
    b = (sym or "").upper().replace("USDT", "").replace("USDC", "")
    b = re.sub(r"[^A-Z0-9]", "", b)
    return b


def parse_signal(texto):
    """Devuelve {symbol(base), direction, entry, sl, tps} o None."""
    t = texto.lower()
    direction = _detectar_direccion(texto)
    sym = None
    m = re.search(r"\b([A-Z0-9]{2,12}USDT)\b", texto, re.I)
    if m:
        sym = m.group(1)
    if not sym:
        m = re.search(r"#\s*([a-z0-9]{2,10})\b", t)
        if m:
            sym = m.group(1)
    if not sym:
        m = re.search(r"coin\s*[:=]\s*([a-z0-9.]+)", t)
        if m:
            sym = m.group(1)
    if not sym:
        m = re.search(r"([a-z]{2,10})/usdt", t)
        if m:
            sym = m.group(1)
    if not sym:
        m = re.search(r"\b(?:long|short)\s+([a-z0-9]{2,12})\b", t)
        if m:
            sym = m.group(1)
    if not sym:
        m = re.search(r"\b([A-Z]{3,10})\b", texto)
        if m and m.group(1).upper() not in ("LONG", "SHORT", "FREE", "SIGNAL",
                                            "USDT", "USDC", "TREND", "VIP"):
            sym = m.group(1)
    if not sym:
        return None
    base = _base(sym)
    if not base:
        return None
    # entrada
    entry = None
    m = re.search(r"(?:entry|entrada|precio)\s*(?:zone|zona)?\s*[:=\s]\s*(" + NUM + r")", t)
    if m:
        entry = _n(m.group(1))
    sl = None
    m = re.search(r"⛔️\s*(" + NUM + r")", t)
    if m:
        sl = _n(m.group(1))
    if sl is None:
        m = re.search(r"(?:stop\s*loss|stoploss|sl)\s*[:=\s]*\s*-?\s*(" + NUM + r")", t)
        if m:
            sl = _n(m.group(1))
    tps = []
    for m in re.finditer(r"(?:tp|target)\s*\d*\s*[:.=\s]*\$?\s*(" + NUM + r")", t):
        s = m.group(1)
        v = _n(s)
        if ("." not in s and "," not in s) and v < 100 and v == int(v):
            continue
        tps.append(v)
    tps = sorted(set(round(x, 10) for x in tps))
    return {"symbol": base, "direction": direction, "entry": entry,
            "sl": sl, "tps": tps, "raw": texto}


# ------------------------------------------------------------------ indicadores
def rsi(closes, p=14):
    if len(closes) < p + 1:
        return 50.0
    gains = losses = 0.0
    for i in range(1, p + 1):
        d = closes[i] - closes[i - 1]
        gains += max(d, 0); losses += max(-d, 0)
    ag, al = gains / p, losses / p
    for i in range(p + 1, len(closes)):
        d = closes[i] - closes[i - 1]
        ag = (ag * (p - 1) + max(d, 0)) / p
        al = (al * (p - 1) + max(-d, 0)) / p
    if al == 0:
        return 100.0
    return 100 - 100 / (1 + ag / al)


def tendencia(base, tf):
    kl = RB.get_klines_tf(base, tf)
    if len(kl) < 55:
        return None, None, None
    closes = [k["close"] for k in kl]
    e20 = RB.ema(closes, 20)
    e50 = RB.ema(closes, 50)
    lc = closes[-1]
    slope = e50[-1] - e50[-6]
    bull = e20[-1] > e50[-1] and lc > e20[-1] and slope > 0
    bear = e20[-1] < e50[-1] and lc < e20[-1] and slope < 0
    tend = "ALCISTA" if bull else ("BAJISTA" if bear else "LATERAL")
    return tend, lc, (e20[-1], e50[-1], rsi(closes))


def ticker(base):
    inst = client.inst_id(base)
    if not inst:
        raise RuntimeError(f"{base}: sin X-Perp")
    return client.ticker(inst)


# ------------------------------------------------------------------ análisis
def _puntuar(dirn, t15, t1h, t4h, rsi1, vol, rr_best, dist):
    favor = "ALCISTA" if dirn == "LONG" else "BAJISTA"
    pts = 0
    for tt in (t15, t1h, t4h):
        if tt == favor:
            pts += 20
    if dirn == "LONG":
        if 45 <= rsi1 <= 65:
            pts += 10
        elif 40 <= rsi1 <= 70:
            pts += 4
    else:
        if 35 <= rsi1 <= 55:
            pts += 10
        elif 30 <= rsi1 <= 60:
            pts += 4
    if vol >= 1_000_000:
        pts += 10
    elif vol >= 200_000:
        pts += 4
    if rr_best >= 2.0:
        pts += 10
    elif rr_best >= 1.5:
        pts += 5
    if dist and 0.01 <= dist <= 0.05:
        pts += 5
    elif dist and 0.003 <= dist <= 0.08:
        pts += 2
    tier = "ALTA" if pts >= 70 else ("MEDIA" if pts >= 45 else "BAJA")
    return pts, tier


def construir_entrada(base, dirn, last, atr_val, ema20_1h):
    """Entrada a mercado, SL por ATR (1.5x, entre 1% y 8%), TPs 1.5/2.5/4R."""
    dist = min(0.08, max(0.01, 1.5 * atr_val / last))
    sl = last * (1 - dist) if dirn == "LONG" else last * (1 + dist)
    tps = []
    for m in (1.5, 2.5, 4.0):
        tp = last * (1 + m * dist) if dirn == "LONG" else last * (1 - m * dist)
        tps.append(round(tp, 8))
    lev = max(1, min(10, int(1 / (dist * 5))))
    return {"entry": last, "sl": round(sl, 8), "tps": tps, "dist": dist,
            "lev": lev, "tipo": "market",
            "rrs": " / ".join(f"{m:.1f}R" for m in (1.5, 2.5, 4.0))}


def analizar_moneda(base):
    out = {"viable": False, "mejor": None, "lineas": [], "pts": 0,
           "confianza": None, "dirn": None, "last": None, "atr": None}
    info = RB.info_instr(base)
    if not info:
        out["lineas"].append(f"⚠️ {base} no tiene X-Perp en OKX.")
        return out
    try:
        tk = ticker(base)
    except Exception as e:
        out["lineas"].append(f"⚠️ No pude leer el precio: {e}")
        return out
    last = float(tk.get("last", 0) or 0)
    vol = float(tk.get("volCcy24h", 0) or 0)
    if last <= 0:
        out["lineas"].append("⚠️ Sin precio.")
        return out
    out["last"] = last

    t15, c15, ind15 = tendencia(base, "15m")
    t1h, c1h, ind1h = tendencia(base, "1H")
    t4h, c4h, ind4h = tendencia(base, "4H")
    rsi1 = ind1h[2] if ind1h else 50

    out["lineas"].append(f"🔎 *{base}*")
    out["lineas"].append(f"Precio ahora: {last:.6g} · vol 24h: {vol:,.0f} USDC")
    out["lineas"].append(f"Tendencia: 15m {t15 or '?'} · 1H {t1h or '?'} · "
                         f"4H {t4h or '?'} · RSI(1H) {rsi1:.0f}")

    if t1h == "ALCISTA" and t4h != "BAJISTA":
        dirn = "LONG"
    elif t1h == "BAJISTA" and t4h != "ALCISTA":
        dirn = "SHORT"
    elif t1h == "ALCISTA":
        dirn = "LONG"
    elif t1h == "BAJISTA":
        dirn = "SHORT"
    else:
        dirn = None

    if not dirn:
        out["lineas"].append("🤷 Sin tendencia clara (1H lateral). No es buen momento.")
        return out
    out["dirn"] = dirn
    out["lineas"].append(f"🎯 Dirección sugerida: *{dirn}*")

    kl = RB.get_klines_tf(base, "1H")
    if len(kl) < 15:
        out["lineas"].append("⚠️ Sin suficientes velas.")
        return out
    highs = [k["high"] for k in kl]
    lows = [k["low"] for k in kl]
    closes = [k["close"] for k in kl]
    atr_val = RB.atr(highs, lows, closes, 14)
    if not atr_val or atr_val <= 0:
        out["lineas"].append("⚠️ ATR inválido.")
        return out
    out["atr"] = atr_val

    mod = construir_entrada(base, dirn, last, atr_val, ind1h[0] if ind1h else None)
    pts, tier = _puntuar(dirn, t15, t1h, t4h, rsi1, vol, 4.0, mod["dist"])
    out["pts"] = pts
    out["confianza"] = tier
    out["lineas"].append(f"🎲 Confianza: *{tier}* ({pts}/100)")
    if tier != "ALTA":
        out["lineas"].append("❌ No llega a confianza ALTA: no recomiendo operar.")
        return out
    out["mejor"] = mod
    out["viable"] = True
    out["lineas"].append("")
    out["lineas"].append("🛠️ *POSIBLE ENTRADA*:")
    out["lineas"].append(f"   🎯 Entrada: {mod['entry']:.6g} (mercado)")
    out["lineas"].append(f"   🛑 SL: {mod['sl']:.6g} (-{mod['dist']*100:.1f}%)")
    out["lineas"].append(f"   ✅ TPs: " + " / ".join(f"{x:.6g}" for x in mod["tps"]))
    out["lineas"].append(f"   📐 R:R: {mod['rrs']} · Apalancamiento {mod['lev']}x")
    out["lineas"].append("   🛡️ Multi-TP (5 niveles) · break-even al 1:1")
    return out


# ------------------------------------------------------------------ ejecución
def execute_now(sig):
    base = sig["symbol"]; dirn = sig["direction"]
    abiertas = RB.get_all_positions()
    if len(abiertas) >= MAX_OPS:
        raise RuntimeError(f"Ya hay {len(abiertas)}/{MAX_OPS} posiciones abiertas.")
    for p in abiertas:
        if p["base"] == base:
            raise RuntimeError(f"Ya tienes una posición abierta en {base}.")

    tk = ticker(base)
    last = float(tk.get("last", 0) or 0)
    kl = RB.get_klines_tf(base, "1H")
    if len(kl) < 15:
        raise RuntimeError("Sin suficientes velas 1H.")
    highs = [k["high"] for k in kl]; lows = [k["low"] for k in kl]
    closes = [k["close"] for k in kl]
    atr_val = RB.atr(highs, lows, closes, 14)
    if not atr_val:
        raise RuntimeError("ATR inválido.")

    best = {"symbol": base, "direction": dirn, "entry": last, "atr": atr_val,
            "info": RB.info_instr(base)}
    plan = RB.build_plan(best)
    if not plan:
        raise RuntimeError("No pude construir el plan.")
    res = RB.open_position(plan)
    RB._tg_send(f"✅ *Operación ejecutada (REAL):* {dirn} {base}\n"
                f"Entrada ~{res['entry']:.6g} · {res['contratos']} ct\n"
                f"SL {res['sl']:.6g} · riesgo ~{res['risk']:.2f} USDC\n"
                f"Multi-TP + break-even al 1:1.", RB.teclado())
    log(f"EJECUTADA {dirn} {base}")
    return res


def enviar_analisis(base, a, sid):
    lineas = a["lineas"][:]
    kb = None
    if a.get("confianza") != "ALTA":
        kb = {"inline_keyboard": [[
            {"text": "2️⃣ DESCARTAR", "callback_data": f"no:{sid}"}]]}
        lineas.append("\nSin confianza ALTA: no ofrezco ejecución. "
                      "Pulsa 2 para descartar.")
    elif a["viable"]:
        kb = {"inline_keyboard": [[
            {"text": "1️⃣ EJECUTAR AHORA", "callback_data": f"ej:{sid}"},
            {"text": "2️⃣ DESCARTAR", "callback_data": f"no:{sid}"}]]}
        lineas.append("\nPulsa 1 para lanzar la orden (mercado, riesgo 10 USDC) "
                      "o 2 para descartar.")
    else:
        kb = {"inline_keyboard": [[
            {"text": "2️⃣ DESCARTAR", "callback_data": f"no:{sid}"}]]}
        lineas.append("\nNo hay entrada de calidad. Pulsa 2 para descartar.")
    safe_send("\n".join(lineas), kb)


def _auto_ejecutar(base, a):
    if not RB.auto_activo():
        return False
    pts = a.get("pts") or 0
    if pts >= 85 and (a.get("viable") and a.get("mejor")):
        try:
            res = execute_now({"symbol": base, "direction": a.get("dirn")})
            safe_send(f"🤖 *MODO AUTOMÁTICO* — entrada directa (confianza {pts}/100 ≥ 85)\n\n"
                      f"{res['direction']} {res['symbol']} ✅ EJECUTADA en OKX.")
            return True
        except Exception as e:
            log(f"AUTO-ejecución fallida: {e}")
            safe_send(f"🤖 MODO AUTOMÁTICO: confianza {pts}/100 ≥85 pero no pude ejecutar: {e}")
            return True
    # descartar
    safe_send(f"🤖 *MODO AUTOMÁTICO* — señal descartada.\n\n{base} {a.get('dirn') or '?'}\n"
              f"Motivo: confianza {pts}/100 < 85 o sin entrada de calidad.\n"
              f"_Desactiva el modo automático si quieres revisarlas tú._")
    log(f"AUTO-descartada {base} pts={pts}")
    return True


# ------------------------------------------------------------------ flujo
def procesar_texto(texto):
    texto = (texto or "").strip()
    if not texto:
        return

    # comandos "mira X" / "analiza X"
    m = re.match(r"^\s*(mira|mirar|ver|comprueba|comprobar|revisa|revisar|"
                 r"analiza|analizar|check|consulta|consultar)\s+([A-Za-z0-9.]+)\s*$",
                 texto, re.I)
    if m:
        base = _base(m.group(2))
        a = analizar_moneda(base)
        sid = str(int(time.time()))
        st = load_state()
        st["signals"][sid] = {"symbol": base, "direction": a.get("dirn") or "LONG"}
        save_state(st)
        if _auto_ejecutar(base, a):
            return
        enviar_analisis(base, a, sid)
        return

    # menú fijo (botones de texto)
    norm = "".join(c for c in unicodedata.normalize("NFKD", texto.lower())
                   if not unicodedata.combining(c))
    norm = "".join(c for c in norm if c.isalpha())
    if texto.startswith("/start"):
        RB.enviar_panel()
        return
    if norm == "estado":
        RB.boton_estado(); return
    if norm == "saldo":
        RB.boton_saldo(); return
    if norm.startswith("auto"):
        RB.boton_auto(); return
    if norm.startswith("lectura"):
        RB.boton_canales_auto(); return
    if norm in ("ayuda", "panel", "menu"):
        RB.enviar_ayuda(); return

    # ---- gestión de CANALES de señales (los lee el userbot canales_bot.py) ----
    st_c = load_state()
    if st_c.get("esperando_canal"):
        st_c["esperando_canal"] = False
        save_state(st_c)
        ok, msg = RB.canal_agregar(texto)
        safe_send((f"✅ Canal añadido: *{msg}*\n"
                   f"_El lector automático lo empezará a leer en unos segundos._")
                  if ok else f"⚠️ No se pudo añadir: {msg}")
        return
    if norm in ("anadircanal", "agregarcanal", "nuevocanal", "canal"):
        st_c["esperando_canal"] = True
        save_state(st_c)
        safe_send("✍️ Envíame el canal:\n"
                  "• `@usuario` (canal público)\n"
                  "• enlace `t.me/+...` (canal privado al que YA estés unido)\n"
                  "• o su ID numérico")
        return
    if norm in ("quitarcanal", "eliminarcanal"):
        ls = RB.canales_list()
        if not ls:
            safe_send("ℹ️ No hay canales en la lista.")
            return
        kb = {"inline_keyboard": [[
            {"text": f"❌ {c}", "callback_data": f"real:canal_quitar:{c}"}
        ] for c in ls]}
        safe_send("🚫 Elige el canal a quitar:", kb)
        return
    if norm in ("canales", "listarcanales", "vercanales"):
        ls = RB.canales_list()
        safe_send("📋 *Canales en lectura:*\n" +
                  ("\n".join("• " + c for c in ls) if ls else "_(ninguno todavía)_"))
        return

    # señal de texto
    sig = parse_signal(texto)
    if not sig:
        safe_send("🤔 No entendí la señal. Formato esperado:\n\n"
                  "Coin, Long/Short, Entry, Stop Loss, Take Profits.")
        return
    if not sig.get("direction"):
        safe_send("🚫 *Señal descartada.* No he detectado si es LONG o SHORT.")
        return
    base = sig["symbol"]
    a = analizar_moneda(base)
    sid = str(int(time.time()))
    st = load_state()
    st["signals"][sid] = {"symbol": base, "direction": a.get("dirn") or sig["direction"]}
    save_state(st)
    if _auto_ejecutar(base, a):
        return
    enviar_analisis(base, a, sid)


def procesar_foto(msg):
    if not OCR:
        safe_send("🖼️ No pude leer imágenes (OCR no disponible).")
        return
    # descargar la foto
    foto = msg.get("photo")
    doc = msg.get("document") or {}
    if foto:
        file_id = foto[-1]["file_id"]
    elif (doc.get("mime_type") or "").startswith("image/"):
        file_id = doc["file_id"]
    else:
        return
    try:
        d = _tg("getFile", file_id=file_id)
        fp = (d.get("result") or {}).get("file_path")
        if not fp:
            safe_send("🖼️ No pude obtener la imagen.")
            return
        with urllib.request.urlopen(
                f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{fp}",
                timeout=30) as r:
            data = r.read()
    except Exception as e:
        log(f"descarga foto: {e}")
        safe_send("🖼️ No pude descargar la imagen.")
        return

    ocr_txt = OCR.ocr_de_bytes(data) or ""
    texto = ((msg.get("caption") or "") + "\n" + ocr_txt).strip()
    if not texto:
        safe_send("🖼️ No pude leer texto de esa imagen.")
        return

    clase = OCR.clasificar(texto) if OCR else "otro"
    mon = OCR.detectar_moneda(texto) if OCR else None
    base = _base(mon or "") if mon else None

    if clase in ("senal", "analisis") and base and client.inst_id(base):
        a = analizar_moneda(base)
        sid = str(int(time.time()))
        st = load_state()
        st["signals"][sid] = {"symbol": base, "direction": a.get("dirn") or "LONG"}
        save_state(st)
        safe_send(f"🔎 He leído de la imagen un análisis de *{base}*. "
                  f"Lo analizo como una posible entrada.")
        if _auto_ejecutar(base, a):
            return
        enviar_analisis(base, a, sid)
        return

    if clase == "senal" and base and not client.inst_id(base):
        safe_send(f"🖼️ Leí *{base}* en la imagen pero no tiene X-Perp en OKX.")
        return

    safe_send("🚫 *Imagen descartada.*\n\nNo parece una señal ni un análisis de "
              "ninguna moneda (noticia, anuncio, meme…).\n"
              "_Si creo que me equivoco, pégame el texto._")
    log("FILTRO imagen (ruido): " + texto[:120].replace("\n", " | "))


def procesar_callback(cb):
    data = cb.get("data") or ""
    cb_id = cb.get("id")
    cmsg = cb.get("message") or {}
    chat_id = (cmsg.get("chat") or {}).get("id")
    mid = cmsg.get("message_id")
    safe_answer(cb_id)
    if str(chat_id) != str(TELEGRAM_CHAT_ID):
        return
    # ---- botones del bot real (panel): "real:<accion>:<args…>" ----
    if data == "real:power":
        import subprocess as _sp
        _st = _sp.run(["systemctl", "is-active", "okx-real-bot.service"], capture_output=True, text=True).stdout.strip()
        if _st == "active":
            _sp.run(["systemctl", "stop", "okx-real-bot.service"], check=False)
            safe_send("⛔ BOT REAL PARADO desde Telegram.\nLas posiciones abiertas siguen con sus SL/TP en el exchange.")
        else:
            _sp.run(["systemctl", "start", "okx-real-bot.service"], check=False)
            safe_send("▶ BOT REAL ARRANCADO de nuevo.")
        safe_answer(cb_id, "Hecho")
        return
    if data.startswith("real:"):
        try:
            partes = data[len("real:"):].split(":")
            accion = partes[0]
            if accion == "canal_quitar" and len(partes) > 1:
                RB.boton_canal_quitar(partes[1])
        except Exception as e:
            log(f"ERROR botón real: {e}")
        return
    try:
        accion, sid = data.split(":", 1)
    except Exception:
        return
    st = load_state()
    if accion == "no":
        safe_answer(cb_id, "Descartada")
        safe_edit_markup(chat_id, mid)
        safe_send("❌ Operación descartada. OK.")
        return
    if accion == "ej":
        if sid in st.get("executed", []):
            safe_answer(cb_id, "Ya ejecutada antes")
            safe_edit_markup(chat_id, mid)
            return
        sig = st.get("signals", {}).get(sid)
        if not sig:
            safe_answer(cb_id)
            safe_edit_markup(chat_id, mid)
            safe_send("⌛ Esa señal ya expiró. Vuelve a pedirla.")
            return
        st.setdefault("executed", []).append(sid)
        save_state(st)
        try:
            execute_now(sig)
            safe_answer(cb_id, "Ejecutada ✅")
            safe_edit_markup(chat_id, mid)
        except Exception as e:
            safe_send(f"❌ No se pudo ejecutar: {e}")
            log(f"ERROR EJECUCION: {e}")


# ------------------------------------------------------------------ bucle
def main():
    global client
    if not (RB.REAL_KEY and RB.REAL_SECRET and RB.REAL_PASSPHRASE):
        raise SystemExit("Faltan OKX_REAL_* en el entorno")
    client = OKX.Cliente(RB.REAL_KEY, RB.REAL_SECRET, RB.REAL_PASSPHRASE, demo=False)
    RB.client = client
    print("[signal-bot OKX] arrancado, escuchando en el bot real de Telegram")

    offset = 0
    try:
        offset = int(open(OFFSET_FILE).read().strip())
    except Exception:
        pass

    while True:
        try:
            url = (f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                   f"?offset={offset}&timeout=25"
                   f"&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D")
            with urllib.request.urlopen(url, timeout=35) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            log(f"getUpdates ERROR: {e}")
            time.sleep(5)
            continue

        for upd in d.get("result", []):
            offset = max(offset, upd["update_id"] + 1)
            try:
                cb = upd.get("callback_query")
                if cb:
                    procesar_callback(cb)
                    continue
                msg = upd.get("message") or {}
                chat = (msg.get("chat") or {}).get("id")
                if str(chat) != str(TELEGRAM_CHAT_ID):
                    continue
                hay_foto = bool(msg.get("photo")) or bool(
                    (msg.get("document") or {}).get("mime_type", "").startswith("image/"))
                if hay_foto:
                    procesar_foto(msg)
                else:
                    procesar_texto(msg.get("text") or msg.get("caption") or "")
            except Exception as e:
                log(f"ERROR update: {e}")

        try:
            with open(OFFSET_FILE, "w") as f:
                f.write(str(offset))
        except Exception:
            pass


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()
