#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BOT REAL OKX (X-Perps) 24/7 — migración de real_bot.py (Bitget) a OKX Europa.

Estrategia (igual que el real de Bitget):
  - Escanea la watchlist con velas 4H + 1H: EMA20/50 + ATR + alineación 4H/1H.
  - Solo abre cuando la tendencia 4H y 1H van alineadas (REQUIRE_ALIGNED) y el
    score supera MIN_TREND_SCORE.
  - Entrada a mercado con SL (order-algo) + 5 TP parciales (20% c/u).
  - Break-even al 1:1 (cancela SL y lo recrea en la entrada + buffer).
  - Riesgo 10 USDC por operación, máx 5 posiciones, apalancamiento máx 10x.

Credenciales REALES via env: OKX_REAL_KEY / OKX_REAL_SECRET / OKX_REAL_PASSPHRASE
"""
import os
import sys
import json
import time
import threading
import unicodedata
import urllib.request
import urllib.parse
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
    MAD = ZoneInfo("Europe/Madrid")
except Exception:
    MAD = timezone.utc

sys.path.insert(0, "/root")
import okx_client as OKX

# ------------------------------------------------------------------ CONFIG
RISK_USD        = float(os.environ.get("RISK_USD", "10.0"))
MAX_OPS         = int(os.environ.get("MAX_OPS", "5"))
LEVERAGE        = int(os.environ.get("LEVERAGE", "10"))
SCAN_EVERY_SEC  = int(os.environ.get("SCAN_EVERY_SEC", "900"))
WATCH_EVERY_SEC = int(os.environ.get("WATCH_EVERY_SEC", "60"))

EMA_FAST   = 20
EMA_SLOW   = 50
ATR_PERIOD = 14
ATR_MULT_SL = 1.5
MIN_TREND_SCORE  = float(os.environ.get("MIN_TREND_SCORE", "6.0"))
REQUIRE_ALIGNED  = os.environ.get("REQUIRE_ALIGNED", "1") != "0"

MULTI_TP_ENABLED = True
TP_LEVELS = [
    {"atr_mult": 1.0, "exit_pct": 20},
    {"atr_mult": 1.5, "exit_pct": 20},
    {"atr_mult": 2.0, "exit_pct": 20},
    {"atr_mult": 2.5, "exit_pct": 20},
    {"atr_mult": 3.0, "exit_pct": 20},
]
BREAKEVEN_ENABLED = True
BREAKEVEN_BUFFER = 0.0015

# Watchlist: monedas con X-Perp en OKX (toda la del Bitget real).
SYMBOLS = ["BTC", "ETH", "SOL", "XRP", "ADA", "DOGE", "LINK", "AVAX",
           "DOT", "LTC", "BNB", "TRX"]

REAL_KEY = os.environ.get("OKX_REAL_KEY", "").strip()
REAL_SECRET = os.environ.get("OKX_REAL_SECRET", "").strip()
REAL_PASSPHRASE = os.environ.get("OKX_REAL_PASSPHRASE", "").strip()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

MANAGE_FILE = "/root/okx_real_managed.json"
AUTO_FILE = "/root/okx_real_auto.json"
NOTIFIED_FILE = "/root/okx_real_notified.json"

client = None


# ------------------------------------------------------------------ TELEGRAM
def _tg(method, **params):
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
        data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def _tg_send(texto, keyboard=None):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    try:
        p = {"chat_id": TELEGRAM_CHAT_ID, "text": texto,
             "disable_web_page_preview": "true"}
        if keyboard is not None:
            p["reply_markup"] = json.dumps(keyboard)
        _tg("sendMessage", **p)
        return True
    except Exception as e:
        print(f"  [telegram] {e}")
        return False


def teclado():
    auto = auto_activo()
    lbl_auto = "🤖 Auto: ON 🟢" if auto else "🤖 Auto: OFF 🔴"
    lbl_lec = ("🔛 Lectura auto: ON 🟢" if canales_auto_activo()
               else "🔛 Lectura auto: OFF 🔴")
    return {"keyboard": [
        ["📊 Estado", "💰 Saldo"],
        [lbl_auto, lbl_lec],
        ["➕ Añadir canal", "➖ Quitar canal"],
        ["📋 Canales", "🆘 Ayuda"],
    ], "resize_keyboard": True}


# ------------------------------------------------------------------ CANALES
CANALES_FILE = "/root/canales.json"
CANALES_AUTO_FILE = "/root/canales_auto.json"


def canales_list():
    try:
        d = json.load(open(CANALES_FILE, encoding="utf-8"))
        return d.get("canales", [])
    except Exception:
        return []


def canal_agregar(nombre):
    nombre = (nombre or "").strip()
    if not nombre:
        return False, "nombre vacío"
    ls = canales_list()
    if nombre in ls:
        return False, f"{nombre} ya estaba en la lista"
    ls.append(nombre)
    json.dump({"canales": ls}, open(CANALES_FILE, "w", encoding="utf-8"),
              ensure_ascii=False)
    return True, nombre


def canal_quitar(nombre):
    ls = canales_list()
    if nombre not in ls:
        return False, nombre
    ls = [c for c in ls if c != nombre]
    json.dump({"canales": ls}, open(CANALES_FILE, "w", encoding="utf-8"),
              ensure_ascii=False)
    return True, nombre


def canales_auto_activo():
    try:
        with open(CANALES_AUTO_FILE, encoding="utf-8") as f:
            return bool(json.load(f).get("activo", False))
    except Exception:
        return False


def set_canales_auto(on):
    try:
        with open(CANALES_AUTO_FILE, "w", encoding="utf-8") as f:
            json.dump({"activo": bool(on)}, f, ensure_ascii=False)
    except Exception:
        pass


def boton_canales_auto():
    nuevo = not canales_auto_activo()
    set_canales_auto(nuevo)
    estado = "🟢 ACTIVADA" if nuevo else "🔴 DESACTIVADA"
    _tg_send("🔛 *Lectura automática de canales: " + estado + "*\n\n"
             + ("El lector automático (userbot) vigilará tus canales de señales "
                "y me las reenviará. Tú también puedes seguir reenviando a mano."
                if nuevo else
                "La lectura automática queda pausada: las señales solo entran "
                "si las reenvías tú a mano."),
             teclado())


def boton_canal_quitar(nombre):
    ok, n = canal_quitar(nombre)
    _tg_send(f"🚫 Canal quitado: {n}" if ok else f"ℹ️ {n} no estaba en la lista.",
             teclado())


def enviar_panel():
    auto = "🟢 ACTIVADO" if auto_activo() else "🔴 DESACTIVADO"
    lec = "🟢 ACTIVADA" if canales_auto_activo() else "🔴 DESACTIVADA"
    _tg_send(
        "🎛 *Panel de control — bot real de OKX*\n\n"
        f"Modo automático: *{auto}*\n"
        f"Lectura de canales: *{lec}*\n\n"
        "• 📊 *Estado* → posiciones reales abiertas.\n"
        "• 💰 *Saldo* → balance de la cuenta real.\n"
        "• 🤖 *Automático* → ON/OFF: con ON, las señales con confianza ≥85/100 "
        "entran DIRECTAS, y el resto se descartan solas.\n"
        "• 🔛 *Lectura auto* → ON/OFF: activa o pausa la lectura automática "
        "de canales (el reenvío a mano siempre funciona).\n"
        "• ➕ *Añadir canal* / ➖ *Quitar canal* → canales de Telegram de donde "
        "el lector automático toma las señales.\n"
        "• 📋 *Canales* → ver la lista actual.\n"
        "• 🆘 *Ayuda* → vuelve a mostrar este panel.",
        teclado())


# ------------------------------------------------------------------ AUTO
def auto_activo():
    try:
        with open(AUTO_FILE) as f:
            return bool(json.load(f).get("activo", True))
    except Exception:
        return True


def set_auto(on):
    try:
        with open(AUTO_FILE, "w") as f:
            json.dump({"activo": on}, f)
    except Exception:
        pass


# ------------------------------------------------------------------ ESTADO
def load_managed():
    try:
        with open(MANAGE_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def save_managed(m):
    try:
        with open(MANAGE_FILE, "w") as f:
            json.dump(m, f, indent=2)
    except Exception:
        pass


def load_notified():
    try:
        with open(NOTIFIED_FILE) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_notified(d):
    try:
        with open(NOTIFIED_FILE, "w") as f:
            json.dump(d, f)
    except Exception:
        pass


# ------------------------------------------------------------------ INDICADORES
def ema(v, p):
    if len(v) < p:
        return []
    k = 2.0 / (p + 1)
    c = sum(v[:p]) / p
    out = [c]
    for x in v[p:]:
        c = x * k + c * (1 - k)
        out.append(c)
    return out


def atr(h, l, c, p):
    if len(c) < p + 1:
        return None
    trs = [max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
           for i in range(1, len(c))]
    cur = sum(trs[:p]) / p
    for tr in trs[p:]:
        cur = (cur * (p - 1) + tr) / p
    return cur


# ------------------------------------------------------------------ MERCADO
def get_klines_tf(base, tf="1H", limit=200):
    inst_id = client.inst_id(base)
    if not inst_id:
        return []
    return client.velas(inst_id, bar=tf, limit=limit)


def info_instr(base):
    inst_id = client.inst_id(base)
    if not inst_id:
        return None
    return client.info_instr(inst_id)


# ------------------------------------------------------------------ POSICIONES
def get_all_positions():
    out = []
    for p in client.posiciones():
        try:
            pos = float(p.get("pos", 0) or 0)
        except Exception:
            pos = 0.0
        if pos == 0:
            continue
        out.append({
            "symbol": p.get("instId", "?"),
            "base": p.get("instId", "?").split("-")[0],
            "direction": "LONG" if pos > 0 else "SHORT",
            "qty": abs(pos),
            "entry": float(p.get("avgPx", 0) or 0),
            "mark": float(p.get("markPx", 0) or p.get("last", 0) or 0),
            "pnl": float(p.get("upl", 0) or 0),
            "lever": p.get("lever", "?"),
        })
    return out


# ------------------------------------------------------------------ SCAN
def scan_coins(exclude_symbols=None):
    exclude_symbols = exclude_symbols or set()
    results = []
    for base in SYMBOLS:
        if base in exclude_symbols:
            continue
        try:
            kl4 = get_klines_tf(base, "4H", 200)
            kl1 = get_klines_tf(base, "1H", 200)
            if len(kl4) < EMA_SLOW + ATR_PERIOD + 5 or len(kl1) < 60:
                continue
            def tend(kl):
                highs = [k["high"] for k in kl]
                lows = [k["low"] for k in kl]
                closes = [k["close"] for k in kl]
                e20 = ema(closes, EMA_FAST); e50 = ema(closes, EMA_SLOW)
                a = atr(highs, lows, closes, ATR_PERIOD)
                slope = e50[-1] - e50[-6] if len(e50) >= 6 else 0.0
                lc = closes[-1]
                bull = e20[-1] > e50[-1] and lc > e20[-1] and slope > 0
                bear = e20[-1] < e50[-1] and lc < e20[-1] and slope < 0
                return closes, e20, e50, a, lc, slope, bull, bear
            c4, e204, e504, a4, lc4, sl4, bull4, bear4 = tend(kl4)
            c1, e201, e501, a1, lc1, sl1, bull1, bear1 = tend(kl1)
            if a4 is None or a4 <= 0:
                continue
            if not (bull4 or bear4):
                continue
            direction = "LONG" if bull4 else "SHORT"
            aligned = (bull4 and bull1) or (bear4 and bear1)
            if REQUIRE_ALIGNED and not aligned:
                continue
            sep = abs(e204[-1] - e504[-1]) / lc4 * 100
            pend = abs(sl4) / lc4 * 100
            score = sep + pend * 3
            if aligned:
                score *= 1.3
            if score < MIN_TREND_SCORE:
                continue
            info = info_instr(base)
            if not info:
                continue
            results.append({"symbol": base, "direction": direction,
                            "score": score, "aligned": aligned,
                            "entry": lc1, "atr": a1, "info": info})
        except Exception as e:
            print(f"  [scan] {base}: {e}")
            continue
        time.sleep(0.05)
    results.sort(key=lambda x: -x["score"])
    return results


def build_plan(best):
    base = best["symbol"]; direction = best["direction"]
    info = best["info"]; entry = best["entry"]; atr_val = best["atr"]

    stop_dist = atr_val * ATR_MULT_SL
    if stop_dist <= 0:
        stop_dist = entry * 0.015
    if direction == "LONG":
        stop = entry - stop_dist
        side, side_cierre = "buy", "sell"
    else:
        stop = entry + stop_dist
        side, side_cierre = "sell", "buy"

    ct_val = float(info.get("ctVal", 0) or 0)
    if ct_val <= 0:
        return None
    contratos = RISK_USD / (ct_val * stop_dist)
    contratos = max(1, int(round(contratos)))

    # apalancamiento dinámico seguro: liquidación >= 5x distancia SL
    dist_frac = stop_dist / entry if entry else 0.02
    lev = max(1, min(LEVERAGE, int(1 / (5 * dist_frac)) if dist_frac > 0 else LEVERAGE))

    # tope de margen: no usar más del ~25% del disponible
    try:
        bal = client.saldo()
        disp = bal.get("available", 0) if bal else 0
        nocional = contratos * ct_val * entry
        if disp > 0 and nocional > disp * lev * 0.25:
            contratos = max(1, int(disp * lev * 0.25 / (ct_val * entry)))
    except Exception:
        pass

    tp_levels = []
    if MULTI_TP_ENABLED:
        parts = []
        remaining = contratos
        for i, lvl in enumerate(TP_LEVELS):
            if i == len(TP_LEVELS) - 1:
                parts.append(remaining)
            else:
                part = max(0, min(round(contratos * lvl["exit_pct"] / 100.0),
                                 remaining))
                parts.append(part)
                remaining -= part
        for i, lvl in enumerate(TP_LEVELS):
            dist = atr_val * lvl["atr_mult"]
            precio = entry + dist if direction == "LONG" else entry - dist
            tp_levels.append({"price": round(precio, 8), "sz": parts[i],
                              "atr_mult": lvl["atr_mult"]})

    return {"symbol": base, "direction": direction, "side": side,
            "side_cierre": side_cierre, "entry": entry, "stop": round(stop, 8),
            "atr": atr_val, "contratos": contratos, "lev": lev,
            "ct_val": ct_val, "tp_levels": tp_levels}


# ------------------------------------------------------------------ ÓRDENES
def set_leverage(base, lev):
    try:
        client.set_apalancamiento(client.inst_id(base), lev)
    except Exception as e:
        print(f"  [aviso] palanca {base}: {e}")


def open_position(plan):
    base = plan["symbol"]
    inst_id = client.inst_id(base)
    if not inst_id:
        raise RuntimeError(f"{base}: sin X-Perp")

    set_leverage(base, plan["lev"])
    r = client.orden_mercado(inst_id, plan["side"], plan["contratos"])
    oid = (r.get("data") or [{}])[0].get("ordId")
    print(f"  >>> ORDEN REAL {base} {plan['direction']} {plan['contratos']} ct (ordId={oid}) <<<")
    time.sleep(1.5)

    sl_id = client.orden_algo_sl(inst_id, plan["side_cierre"], plan["stop"],
                                 plan["contratos"])
    print(f"  -> SL @ {plan['stop']} (algoId={sl_id})")

    tps_colocados = []
    for lvl in plan["tp_levels"]:
        if lvl["sz"] <= 0:
            continue
        try:
            aid = client.orden_algo_tp(inst_id, plan["side_cierre"],
                                       lvl["price"], lvl["sz"])
            tps_colocados.append({"nivel": f"{lvl['atr_mult']:.1f}R",
                                  "precio": lvl["price"], "sz": lvl["sz"],
                                  "algoId": aid})
        except Exception as e:
            print(f"  [aviso] TP: {e}")

    managed = load_managed()
    managed[f"{base}:{plan['direction']}"] = {
        "symbol": base, "direction": plan["direction"], "entry": plan["entry"],
        "contratos": plan["contratos"], "sl_algo_id": sl_id, "state": "opened",
        "risk_usd": RISK_USD, "opened_at": time.time(),
        "dist": round((plan["atr"] * ATR_MULT_SL) / plan["entry"], 8),
        "initial_sl": plan["stop"], "tp_levels": tps_colocados,
    }
    save_managed(managed)
    return {"symbol": base, "direction": plan["direction"], "entry": plan["entry"],
            "contratos": plan["contratos"], "sl": plan["stop"],
            "risk": plan["contratos"] * plan["ct_val"] * (plan["atr"] * ATR_MULT_SL)}


# ------------------------------------------------------------------ GESTIÓN
def manage_positions():
    positions = get_all_positions()
    pos_map = {}
    for p in positions:
        pos_map[f"{p['base']}:{p['direction']}"] = p

    managed = load_managed()
    notified = load_notified()
    changed = False

    for key, m in list(managed.items()):
        base = m["symbol"]; direction = m["direction"]
        inst_id = client.inst_id(base)
        if not inst_id:
            continue
        p = pos_map.get(key)
        if not p:
            # FIXW_ARENA: exigir 2 pasadas consecutivas sin verla (evita borrados por fallo de API)
            m["ausente"] = int(m.get("ausente", 0)) + 1
            if m["ausente"] < 2:
                changed = True
                continue
            # la posición se cerró del todo (TPs/SL): leer P&L realizado
            detalle = ""
            ya_avisado = False
            try:
                hist = client.posiciones_cerradas(inst_id, limit=3)
                if hist:
                    ult = hist[0]
                    pnl = float(ult.get("pnl", 0) or 0)
                    close_px = float(ult.get("closeAvgPx", 0) or 0)
                    utime = str(ult.get("uTime", ""))
                    ic = "🟢" if pnl >= 0 else "🔴"
                    detalle = f" · {ic} {pnl:+.2f} USDC"
                    if close_px:
                        detalle += f" (cierre {close_px:g})"
                    if utime and notified.get(base) == utime:
                        ya_avisado = True
                    elif utime:
                        notified[base] = utime
            except Exception as e:
                print(f"  [cierre] histórico: {e}")
            # FIXR_ARENA: cancelar algos huerfanos del cierre
            try:
                _nz = client.cancelar_todas_algo(inst_id)
                if _nz:
                    print("  [LIMPIEZA] " + base + ": " + str(_nz) + " orden(es) huerfana(s) cancelada(s)")
            except Exception as _ez:
                print("  [LIMPIEZA] " + base + ": " + str(_ez))
            del managed[key]
            changed = True
            if not ya_avisado:
                _tg_send(f"🔔 *Posición REAL cerrada*: {base} {direction}\n"
                         f"(entrada ~{m.get('entry'):g}{detalle})", teclado())
            continue

        if m.get("ausente"):
            m["ausente"] = 0
            changed = True
        qty = p["qty"]; unreal = p["pnl"]
        entry = float(p.get("entry", 0) or 0)
        risk_actual = float(m.get("risk_usd", RISK_USD) or RISK_USD)

        # Cierre PARCIAL (TPs): avisar cuando la cantidad baja respecto a la
        # última vista (se ha llenado un TP parcial).
        qty_ant = float(m.get("qty_vista", qty) or qty)
        if qty_ant - qty >= 1e-9:
            cerr = int(qty_ant - qty)
            _tg_send(f"✅ *TP parcial (REAL)*: {base} {direction}\n"
                     f"Cerrados ~{cerr} ct · quedan {qty:g} ct · "
                     f"P&L actual {unreal:+.2f} USDC", teclado())
        m["qty_vista"] = qty

        # Break-even al 1:1
        if (BREAKEVEN_ENABLED and m.get("state") == "opened"
                and unreal >= risk_actual):
            be_price = (entry * (1 + BREAKEVEN_BUFFER) if direction == "LONG"
                        else entry * (1 - BREAKEVEN_BUFFER))
            try:
                client.cancelar_algo(inst_id, m.get("sl_algo_id"))
            except Exception as e:
                print(f"  [BE] cancelar SL: {e}")
            try:
                nuevo_sl = client.orden_algo_sl(
                    inst_id, "sell" if direction == "LONG" else "buy",
                    be_price, int(qty))
                m["sl_algo_id"] = nuevo_sl
                m["state"] = "breakeven"
                changed = True
                print(f"  [BE] {base} {direction} SL a BREAK-EVEN @ {be_price:.6g}")
                _tg_send(f"🛡️ *{base} {direction}* — SL a break-even @ {be_price:.6g}\n"
                         f"Ya no puedes perder en esta operación.")
            except Exception as e:
                print(f"  [BE] recrear SL: {e}")

    if changed:
        save_managed(managed)
        save_notified(notified)


# ------------------------------------------------------------------ BOTONES
MARCADORES = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
              "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def boton_estado():
    pos = get_all_positions()
    if not pos:
        _tg_send("ℹ️ No hay posiciones reales abiertas ahora.", teclado())
        return
    managed = load_managed()
    lineas = []
    for i, p in enumerate(pos):
        marca = MARCADORES[i] if i < len(MARCADORES) else f"{i+1}."
        sym = p["symbol"]; d = p["direction"]
        pnl = p["pnl"]
        if pnl > 0.005:
            ic, pnl_txt = "🔵", f"{pnl:+.2f}"
        elif pnl < -0.005:
            ic, pnl_txt = "🔴", f"{pnl:+.2f}"
        else:
            ic, pnl_txt = "⚪️", "0.00"
        linea = (f"{marca} {sym} {d} · {p['qty']:g} ct · ent {p['entry']:g} · "
                 f"mark {p['mark']:g} · P&L {ic} {pnl_txt} USD")
        m = managed.get(f"{p['base']}:{d}")
        if m and m.get("state") == "breakeven":
            linea += " · 🔒 SL en BE"
        lineas.append(linea)
    _tg_send("📊 *Estado de posiciones (REAL OKX)*\n\n" + "\n".join(lineas),
             teclado())


def boton_saldo():
    bal = client.saldo()
    if not bal:
        _tg_send("❌ No pude leer el saldo real.", teclado())
        return
    _tg_send("💰 *Saldo de la cuenta (REAL OKX)*\n\n"
             f"• Equity total: *{bal['equity']:.2f} USD*\n"
             f"• Disponible (USDC): {bal['available']:.2f} USDC\n"
             f"• P&L no realizado: {bal['unrealized']:+.2f} USD", teclado())


def boton_auto():
    on = auto_activo()
    set_auto(not on)
    estado = "ON 🟢" if not on else "OFF 🔴"
    _tg_send(f"🤖 *Modo automático: {estado}*\n\n"
             f"{'El bot abre posiciones al detectar señales fuertes.'
                if not on else 'El bot NO abrirá nuevas posiciones (solo gestiona las abiertas).'}",
             teclado())


def enviar_ayuda():
    enviar_panel()


def telegram_listener():
    # NOTA: el panel y la lectura de Telegram los atiende okx_signal_bot.py
    # (único poller del token). Este bot solo ENVÍA notificaciones.
    pass


# ------------------------------------------------------------------ MAIN
def main():
    global client
    if not (REAL_KEY and REAL_SECRET and REAL_PASSPHRASE):
        print("ERROR: faltan OKX_REAL_* en el entorno")
        sys.exit(1)

    client = OKX.Cliente(REAL_KEY, REAL_SECRET, REAL_PASSPHRASE, demo=False)
    bal = client.saldo()
    print(f"=== BOT REAL OKX | riesgo {RISK_USD} USDC | lev máx {LEVERAGE}x ===")
    print(f"[auth OK] cuenta REAL OKX — equity {bal['equity']:.2f} USD · "
          f"disponible {bal['available']:.2f} USDC")

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        # El panel de Telegram lo atiende okx_signal_bot.py (único poller).
        enviar_panel()

    last_scan = 0
    last_manage = 0
    while True:
        try:
            if time.time() - last_manage >= WATCH_EVERY_SEC:
                last_manage = time.time()
                manage_positions()

            open_positions = get_all_positions()
            open_bases = set(p["base"] for p in open_positions)

            if time.time() - last_scan >= SCAN_EVERY_SEC:
                last_scan = time.time()
                if auto_activo() and len(open_positions) < MAX_OPS:
                    print(f"[scan] {len(open_positions)}/{MAX_OPS} posiciones, escaneando…")
                    candidates = scan_coins(exclude_symbols=open_bases)
                    for cand in candidates:
                        if len(get_all_positions()) >= MAX_OPS:
                            break
                        print(f"*** SEÑAL {cand['direction']} en {cand['symbol']} "
                              f"(score={cand['score']:.2f}) ***")
                        plan = build_plan(cand)
                        if not plan:
                            continue
                        try:
                            res = open_position(plan)
                            _tg_send(
                                f"🔔 *Posición abierta (REAL)*: {res['direction']} {res['symbol']}\n"
                                f"Entrada ~{res['entry']:.6g} · {res['contratos']} ct\n"
                                f"SL {res['sl']:.6g} · riesgo ~{res['risk']:.2f} USDC\n"
                                f"Gestión: multi-TP + break-even al 1:1.", teclado())
                        except Exception as e:
                            print(f"  [error] {cand['symbol']}: {e}")
                            _tg_send(f"⚠️ No pude abrir {cand['symbol']}: {e}", teclado())

            if open_positions:
                for p in open_positions:
                    print(f"  [REAL] {p['symbol']} {p['direction']} P&L={p['pnl']:+.2f}")
        except KeyboardInterrupt:
            print("\nBot real OKX detenido.")
            break
        except Exception as e:
            print(f"  [error loop] {e}")
        time.sleep(10)


# === FIX3_ARENA: protecciones de gestion (tope diario, cooldown, anti-racimo, rango, SL seguro) ===
_PROT3_FILE = "/root/okx_real_protecciones.json"
MAX_TRADES_DIA = int(os.environ.get("MAX_TRADES_DIA", "3"))
REENTRY_HORAS = float(os.environ.get("REENTRY_HORAS", "4"))
MIN_SEG_ENTRE_APERTURAS = int(os.environ.get("MIN_SEG_ENTRE_APERTURAS", "600"))
RANGO_MIN_ATR = float(os.environ.get("RANGO_MIN_ATR", "3.5"))

def _prot3_load():
    try:
        return json.load(open(_PROT3_FILE))
    except Exception:
        return {}

def _prot3_save(d):
    try:
        json.dump(d, open(_PROT3_FILE, "w"))
    except Exception:
        pass

def _prot3_hoy():
    return datetime.now(MAD).strftime("%Y-%m-%d")

def _prot3_check(base):
    d = _prot3_load()
    hoy = _prot3_hoy()
    if d.get("dia") != hoy:
        d = {"dia": hoy}
        _prot3_save(d)
    if int(d.get("abiertas_hoy", 0)) >= MAX_TRADES_DIA:
        return "tope diario de " + str(MAX_TRADES_DIA) + " aperturas"
    ua = float(d.get("ultima_apertura_ts", 0) or 0)
    if ua and (time.time() - ua) < MIN_SEG_ENTRE_APERTURAS:
        return "anti-racimo, esperar " + str(int(MIN_SEG_ENTRE_APERTURAS - (time.time() - ua))) + "s"
    upm = d.get("ultimas_por_moneda", {}) or {}
    if base in upm:
        t = float(upm.get(base) or 0)
        if t and (time.time() - t) < REENTRY_HORAS * 3600:
            return "cooldown " + base + " " + str(round(REENTRY_HORAS - (time.time() - t) / 3600.0, 1)) + "h"
    return None
def _prot3_registrar(base):
    d = _prot3_load()
    hoy = _prot3_hoy()
    if d.get("dia") != hoy:
        d = {"dia": hoy}
    d["abiertas_hoy"] = int(d.get("abiertas_hoy", 0)) + 1
    d["ultima_apertura_ts"] = time.time()
    d.setdefault("ultimas_por_moneda", {})[base] = time.time()
    _prot3_save(d)

def _rango3_ok(base, atr_val):
    try:
        if not atr_val or atr_val <= 0:
            return True
        kl = get_klines_tf(base, "1H", 30)
        if not kl or len(kl) < 24:
            return True
        rango = max(k["high"] for k in kl[-24:]) - min(k["low"] for k in kl[-24:])
        return rango >= RANGO_MIN_ATR * atr_val
    except Exception:
        return True

_scan3_orig = scan_coins
def scan_coins(exclude_symbols=None):
    cands = _scan3_orig(exclude_symbols)
    out = []
    for c in cands:
        motivo = _prot3_check(c["symbol"])
        if motivo:
            print("[PROT] " + c["symbol"] + " bloqueada: " + motivo)
            continue
        if not _rango3_ok(c["symbol"], c.get("atr")):
            print("[PROT] " + c["symbol"] + " bloqueada: mercado comprimido (rango < " + str(RANGO_MIN_ATR) + "xATR)")
            continue
        out.append(c)
    return out
def open_position(plan):
    base = plan["symbol"]
    motivo = _prot3_check(base)
    if motivo:
        raise RuntimeError(base + ": BLOQUEADA (" + motivo + ")")
    if not _rango3_ok(base, plan.get("atr")):
        raise RuntimeError(base + ": BLOQUEADA (mercado comprimido)")
    inst_id = client.inst_id(base)
    if not inst_id:
        raise RuntimeError(base + ": sin X-Perp")
    set_leverage(base, plan["lev"])
    r = client.orden_mercado(inst_id, plan["side"], plan["contratos"])
    oid = (r.get("data") or [{}])[0].get("ordId")
    print(">>> ORDEN REAL " + base + " " + plan["direction"] + " " + str(plan["contratos"]) + " ct (ordId=" + str(oid) + ") <<<")
    _prot3_registrar(base)
    time.sleep(1.5)
    sl_id = None
    try:
        sl_id = client.orden_algo_sl(inst_id, plan["side_cierre"], plan["stop"], plan["contratos"])
        print("-> SL @ " + str(plan["stop"]) + " (algoId=" + str(sl_id) + ")")
    except Exception as e:
        print("[CRITICO] " + base + ": el SL fallo tras abrir -> CERRANDO por seguridad. " + str(e))
        try:
            client.orden_mercado(inst_id, plan["side_cierre"], plan["contratos"])
        except Exception as ce:
            print("[CRITICO] " + base + ": tampoco se pudo cerrar: " + str(ce))
        try:
            _tg_send("*[REAL] " + base + " " + plan["direction"] + ": SL fallo -> cerrada por seguridad*", teclado())
        except Exception:
            pass
        raise RuntimeError(base + ": SL fallo tras abrir; posicion cerrada por seguridad")
    tps_colocados = []
    for lvl in plan["tp_levels"]:
        if lvl["sz"] <= 0:
            continue
        try:
            aid = client.orden_algo_tp(inst_id, plan["side_cierre"], lvl["price"], lvl["sz"])
            tps_colocados.append({"nivel": str(lvl["atr_mult"]) + "R", "precio": lvl["price"], "sz": lvl["sz"], "algoId": aid})
        except Exception as e:
            print("[aviso] TP: " + str(e))
    managed = load_managed()
    managed[base + ": " + plan["direction"]] = {
        "symbol": base, "direction": plan["direction"], "entry": plan["entry"],
        "contratos": plan["contratos"], "sl_algo_id": sl_id, "state": "opened",
        "risk_usd": RISK_USD, "opened_at": time.time(),
        "dist": round((plan["atr"] * ATR_MULT_SL) / plan["entry"], 8),
        "initial_sl": plan["stop"], "tp_levels": tps_colocados}
    save_managed(managed)
    return {"symbol": base, "direction": plan["direction"], "entry": plan["entry"],
            "contratos": plan["contratos"], "sl": plan["stop"],
            "risk": plan["contratos"] * plan["ct_val"] * (plan["atr"] * ATR_MULT_SL)}


# === FIX4_ARENA: panel mejorado (P&L abierto, saldo hoy/total, cierres con P&L) ===
def _cli4():
    global client
    if client is None:
        if REAL_KEY and REAL_SECRET and REAL_PASSPHRASE:
            client = OKX.Cliente(REAL_KEY, REAL_SECRET, REAL_PASSPHRASE, demo=False)
        else:
            return None
    return client

def _hist4(limit=100):
    c = _cli4()
    if c is None:
        return []
    try:
        return c.posiciones_historicas(limit) or []
    except Exception:
        return []

def _pnl_hoy_total4():
    hoy0 = datetime.now(MAD).replace(hour=0, minute=0, second=0, microsecond=0)
    lim_ms = hoy0.timestamp() * 1000.0
    pnl_hoy = 0.0
    pnl_total = 0.0
    n = 0
    for h in _hist4(100):
        try:
            p = float(h.get("realizedPnl", 0) or 0)
            t = float(h.get("uTime", 0) or 0)
        except Exception:
            continue
        pnl_total += p
        n += 1
        if t >= lim_ms:
            pnl_hoy += p
    return pnl_hoy, pnl_total, n

def boton_estado():
    pos = get_all_positions()
    if not pos:
        _tg_send("No hay posiciones reales abiertas ahora.", teclado())
        return
    managed = load_managed()
    lineas = []
    pnl_total_abierto = 0.0
    for i, p in enumerate(pos):
        marca = MARCADORES[i] if i < len(MARCADORES) else str(i + 1) + "."
        sym = p["symbol"]; d = p["direction"]
        pnl = p["pnl"]
        pnl_total_abierto += pnl
        if pnl > 0.005:
            ic, pnl_txt = "🔵", format(pnl, "+.2f")
        elif pnl < -0.005:
            ic, pnl_txt = "🔴", format(pnl, "+.2f")
        else:
            ic, pnl_txt = "⚪", "0.00"
        linea = marca + " " + sym + " " + d + " | " + format(p["qty"], "g") + " ct | ent " + format(p["entry"], "g") + " | mark " + format(p["mark"], "g") + " | P&L " + ic + " " + pnl_txt + " USD"
        m = managed.get(p["base"] + ": " + d)
        if m and m.get("state") == "breakeven":
            linea += " | SL en BE"
        # FIXBE_ARENA: BE real segun el SL vivo del exchange (vale tambien para fantasmas)
        try:
            _g = globals()
            if _g.get("_FIXBE_TS") is None or time.time() - _g["_FIXBE_TS"] > 60:
                _slm = {}
                for _a in client.algo_pendientes() or []:
                    if _a.get("slTriggerPx"):
                        _slm[_a.get("instId", "")] = float(_a["slTriggerPx"])
                _g["_FIXBE_SL"] = _slm
                _g["_FIXBE_TS"] = time.time()
            _slp = (_g.get("_FIXBE_SL") or {}).get(sym)
            if _slp and ((d == "LONG" and _slp >= p["entry"]) or (d == "SHORT" and _slp <= p["entry"])):
                if "BE" not in linea:
                    linea += " | 🔒 BE"
        except Exception:
            pass
        lineas.append(linea)
    ic_t = "🔵" if pnl_total_abierto >= 0 else "🔴"
    lineas.append("")
    lineas.append("P&L ABIERTO TOTAL: " + ic_t + " " + format(pnl_total_abierto, "+.2f") + " USD")
    _tg_send("*Estado de posiciones (REAL OKX)*\n\n" + "\n".join(lineas), teclado())

def boton_saldo():
    c = _cli4()
    bal = c.saldo() if c else None
    if not bal:
        _tg_send("No pude leer el saldo real.", teclado())
        return
    pnl_hoy, pnl_total, n = _pnl_hoy_total4()
    ic_h = "🔵" if pnl_hoy >= 0 else "🔴"
    ic_t = "🔵" if pnl_total >= 0 else "🔴"
    _tg_send("*Saldo de la cuenta (REAL OKX)*\n\n"
             "Equity total: *" + format(bal["equity"], ".2f") + " USD*\n"
             "Disponible (USDC): " + format(bal["available"], ".2f") + " USDC\n"
             "P&L no realizado: " + format(bal["unrealized"], "+.2f") + " USD\n"
             "P&L cerrado HOY: " + ic_h + " " + format(pnl_hoy, "+.2f") + " USD\n"
             "P&L desde el inicio: " + ic_t + " " + format(pnl_total, "+.2f") + " USD (" + str(n) + " ops cerradas)", teclado())

def _pnl_cierre4(texto):
    c = _cli4()
    if c is None:
        return None
    sym = None
    for s in SYMBOLS:
        if s in texto:
            sym = s
            break
    if not sym:
        return None
    try:
        iid = c.inst_id(sym)
    except Exception:
        return None
    mejor = None
    for h in _hist4(20):
        if h.get("instId") == iid:
            try:
                t = float(h.get("uTime", 0) or 0)
            except Exception:
                t = 0
            if mejor is None or t > mejor[1]:
                mejor = (h, t)
    if mejor is None:
        return None
    try:
        p = float(mejor[0].get("realizedPnl", 0) or 0)
    except Exception:
        return None
    ic = "🔵" if p >= 0 else "🔴"
    return "P&L de la operacion: " + ic + " " + format(p, "+.2f") + " USD"

_tg_send_orig4 = _tg_send
def _tg_send(texto, keyboard=None):
    try:
        if texto and "cerrada" in str(texto).lower():
            extra = _pnl_cierre4(str(texto))
            if extra:
                texto = str(texto) + "\n" + extra
    except Exception:
        pass
    return _tg_send_orig4(texto, keyboard)


# === FIX4B_ARENA: boton de emergencia PARAR/ARRANCAR ===
_enviar_panel_orig4b = enviar_panel
def enviar_panel():
    try:
        _enviar_panel_orig4b()
    except Exception:
        pass
    try:
        _btn = chr(0x26D4) + " PARAR / " + chr(0x25B6) + chr(0xFE0F) + " ARRANCAR BOT"
        _tg_send(chr(0x1F6A8) + " *Control de emergencia de la del bot REAL*",
                 {"inline_keyboard": [[{"text": _btn, "callback_data": "real:power"}]]})
    except Exception:
        pass


# === JOURNAL_ARENA: diario de trades (fase 1 autoaprendizaje) ===
_JOURNAL_FILE = "/root/okx_real_journal.json"
_JOURNAL_BOT = "real"
_JOURNAL_ACTIVO = (__name__ == "__main__")

def _journal_load():
    try:
        return json.load(open(_JOURNAL_FILE))
    except Exception:
        return []

def _journal_save(regs):
    try:
        json.dump(regs, open(_JOURNAL_FILE, "w"), ensure_ascii=False, indent=1)
    except Exception:
        pass

_ULTIMO_SCORE = {}
_scan_j_orig = scan_coins
def scan_coins(exclude_symbols=None):
    cands = _scan_j_orig(exclude_symbols)
    try:
        for c in cands:
            _ULTIMO_SCORE[c["symbol"]] = c.get("score")
    except Exception:
        pass
    return cands

def _journal_registrar_apertura(plan, res):
    try:
        base = plan["symbol"]
        try:
            sdp = round(abs(plan["entry"] - plan["stop"]) / plan["entry"] * 100, 3)
        except Exception:
            sdp = None
        reg = {
            "id": int(time.time() * 1000),
            "ts_apertura": datetime.now(MAD).strftime("%Y-%m-%d %H:%M"),
            "bot": _JOURNAL_BOT,
            "moneda": base,
            "direccion": plan["direction"],
            "entrada": plan["entry"],
            "contratos": plan["contratos"],
            "riesgo_usd": RISK_USD,
            "score": _ULTIMO_SCORE.get(base),
            "atr": plan.get("atr"),
            "stop_dist_pct": sdp,
            "apalancamiento": plan.get("lev"),
            "estado": "abierta",
        }
        regs = _journal_load()
        regs.append(reg)
        _journal_save(regs)
        print("[JOURNAL] apertura: " + base + " " + plan["direction"] + " (score=" + str(reg["score"]) + ")")
    except Exception as e:
        print("[JOURNAL] aviso apertura: " + str(e)[:80])

def _journal_resultado(base, desde_ms):
    try:
        if client is None:
            return None
        iid = client.inst_id(base)
        try:
            hist = client.posiciones_historicas(20) or []
        except Exception:
            return None
        mejor = None
        for h in hist:
            if h.get("instId") != iid:
                continue
            try:
                t = float(h.get("uTime", 0) or 0)
            except Exception:
                t = 0
            if t < desde_ms - 120000:
                continue
            if mejor is None or t > mejor[1]:
                mejor = (h, t)
        if mejor is None:
            return None
        return float(mejor[0].get("realizedPnl", 0) or 0)
    except Exception:
        return None

def _journal_check_cierres(pos_actuales):
    try:
        regs = _journal_load()
        cambio = False
        abiertas = set(p.get("base") for p in pos_actuales)
        ahora_ms = time.time() * 1000
        for r in regs:
            if r.get("estado") != "abierta":
                continue
            if ahora_ms - float(r.get("id", 0) or 0) < 120000:
                continue
            if r.get("moneda") in abiertas:
                continue
            pnl = _journal_resultado(r.get("moneda"), float(r.get("id", 0) or 0))
            r["estado"] = "cerrada"
            r["ts_cierre"] = datetime.now(MAD).strftime("%Y-%m-%d %H:%M")
            if pnl is not None:
                r["pnl_usd"] = round(pnl, 2)
                riesgo = float(r.get("riesgo_usd") or 10.0)
                rr = pnl / riesgo if riesgo else None
                r["r_resultado"] = round(rr, 2) if rr is not None else None
                if rr is None:
                    r["motivo"] = "?"
                elif rr <= -0.85:
                    r["motivo"] = "SL"
                elif rr >= 0.1:
                    r["motivo"] = "TP"
                else:
                    r["motivo"] = "BE"
            else:
                r["pnl_usd"] = None
                r["motivo"] = "?"
            cambio = True
            print("[JOURNAL] cierre: " + str(r.get("moneda")) + " pnl=" + str(r.get("pnl_usd")) + " (" + str(r.get("motivo")) + ")")
        if cambio:
            _journal_save(regs)
    except Exception as e:
        print("[JOURNAL] aviso cierres: " + str(e)[:80])

_gap_j_orig = get_all_positions
def get_all_positions():
    pos = _gap_j_orig()
    try:
        if _JOURNAL_ACTIVO:
            _journal_check_cierres(pos)
    except Exception:
        pass
    return pos

_op_j_orig = open_position
def open_position(plan):
    res = _op_j_orig(plan)
    try:
        _journal_registrar_apertura(plan, res)
    except Exception:
        pass
    return res

# === FIX5_ARENA: filtros de calidad de senal ===
# F1: LONG solo si precio > EMA20(4H); SHORT solo si precio < EMA20(4H)
#     (corta antes que esperar al cruce de EMAs)
# F2: bloquear si separacion |EMA20-EMA50| en 4H > EMA_SEP_MAX_PCT
#     (movimiento maduro / sobre-extendido: comprar tarde = comprar el techo)
# F3: la ultima vela 1H completada debe cerrar a favor de la senal
# Ajustes por entorno (opcionales): FILTROS_ON, EMA_SEP_MAX_PCT, CONF_VELA_ON
try:
    _filt_es_demo = "demo" in str(__file__)
except Exception:
    _filt_es_demo = False
_FILTROS_FILE = "/root/okx_" + ("demo" if _filt_es_demo else "real") + "_filtro_stats.json"
_FILT_CACHE = {}
_FILT_TTL = 300


def _filt_env_int(nombre, defecto):
    try:
        return int(float(os.environ.get(nombre, str(defecto))))
    except Exception:
        return defecto


def _filt_env_float(nombre, defecto):
    try:
        return float(os.environ.get(nombre, str(defecto)))
    except Exception:
        return defecto


FILTROS_ON = _filt_env_int("FILTROS_ON", 1)
EMA_SEP_MAX_PCT = _filt_env_float("EMA_SEP_MAX_PCT", 5.0)
CONF_VELA_ON = _filt_env_int("CONF_VELA_ON", 1)


def _filt_kl(base, tf, limit):
    clave = (base, tf)
    g = _FILT_CACHE.get(clave)
    if g and time.time() - g[0] < _FILT_TTL:
        return g[1]
    d = get_klines_tf(base, tf, limit)
    _FILT_CACHE[clave] = (time.time(), d)
    return d


def _filt_ema(v, n):
    if not v or len(v) < n:
        return None
    m = 2.0 / (n + 1)
    e = sum(v[:n]) / float(n)
    for x in v[n:]:
        e = x * m + e * (1 - m)
    return e


def _filt_stats(t):
    hoy = datetime.now(MAD).strftime("%Y-%m-%d")
    try:
        d = json.load(open(_FILTROS_FILE))
        if d.get("dia") != hoy:
            d = {"dia": hoy}
    except Exception:
        d = {"dia": hoy}
    d[t] = int(d.get(t, 0)) + 1
    try:
        json.dump(d, open(_FILTROS_FILE, "w"))
    except Exception:
        pass

def _filt_veredicto(base, direccion, precio=None, contar=True):
    # Devuelve (True, None) si pasa los filtros o (False, motivo) si se bloquea.
    # Ante error o falta de datos NO bloquea (failsafe).
    if not FILTROS_ON:
        return True, None
    try:
        kl4 = [x for x in (_filt_kl(base, "4H", 120) or []) if str(x.get("confirm", "1")) != "0"]
        kl1 = [x for x in (_filt_kl(base, "1H", 30) or []) if str(x.get("confirm", "1")) != "0"]
        if len(kl4) < 55 or not kl1:
            return True, None
        c4 = [x["close"] for x in kl4]
        e20 = _filt_ema(c4, 20)
        e50 = _filt_ema(c4, 50)
        if not e20 or not e50 or e50 <= 0:
            return True, None
        px = float(precio) if precio else float(kl1[-1]["close"])
        sep = abs(e20 - e50) / e50 * 100.0
        if direccion == "LONG" and px <= e20:
            if contar:
                _filt_stats("bloq_ema20")
            return False, "precio %.6g <= EMA20-4H %.6g (4H rota para LONG)" % (px, e20)
        if direccion == "SHORT" and px >= e20:
            if contar:
                _filt_stats("bloq_ema20")
            return False, "precio %.6g >= EMA20-4H %.6g (4H rota para SHORT)" % (px, e20)
        if sep > EMA_SEP_MAX_PCT:
            if contar:
                _filt_stats("bloq_sobreext")
            return False, "sep EMA20/50-4H %.2f%% > %.1f%% (movimiento maduro)" % (sep, EMA_SEP_MAX_PCT)
        if CONF_VELA_ON:
            v = kl1[-1]
            o = v.get("open")
            if o is None and len(kl1) > 1:
                o = kl1[-2]["close"]
            if o is not None:
                verde = float(v["close"]) > float(o)
                if direccion == "LONG" and not verde:
                    if contar:
                        _filt_stats("bloq_vela")
                    return False, "ultima vela 1H roja (sin confirmacion)"
                if direccion == "SHORT" and verde:
                    if contar:
                        _filt_stats("bloq_vela")
                    return False, "ultima vela 1H verde (sin confirmacion)"
        if contar:
            _filt_stats("pasan")
        return True, None
    except Exception as e:
        try:
            print("[FILTRO] " + str(base) + ": error " + str(e) + " -> no bloqueo")
        except Exception:
            pass
        return True, None


_filt_scan5 = scan_coins


def scan_coins(exclude_symbols=None):
    cands = _filt_scan5(exclude_symbols)
    out = []
    for c in (cands or []):
        ok, motivo = _filt_veredicto(c["symbol"], c.get("direction", "LONG"), c.get("entry"))
        if ok:
            out.append(c)
        else:
            print("[FILTRO] " + c["symbol"] + " " + str(c.get("direction")) + " BLOQUEADA: " + motivo)
    return out


_filt_open5 = open_position


def open_position(plan):
    ok, motivo = _filt_veredicto(plan["symbol"], plan.get("direction", "LONG"), plan.get("entry"))
    if not ok:
        raise RuntimeError(plan["symbol"] + ": BLOQUEADA por filtro (" + motivo + ")")
    return _filt_open5(plan)


def filtros_diagnostico():
    # Ver los filtros en vivo sin operar. Requiere cliente inicializado:
    #   RB.client = okx_client.Cliente(...)
    print("=== DIAGNOSTICO FILTROS (sep_max=%.1f%%, vela=%s) ==="
          % (EMA_SEP_MAX_PCT, "ON" if CONF_VELA_ON else "OFF"))
    for base in SYMBOLS:
        try:
            kl4 = [x for x in (_filt_kl(base, "4H", 120) or []) if str(x.get("confirm", "1")) != "0"]
            kl1 = [x for x in (_filt_kl(base, "1H", 30) or []) if str(x.get("confirm", "1")) != "0"]
            if len(kl4) < 55 or not kl1:
                print("%-6s sin datos suficientes" % base)
                continue
            c4 = [x["close"] for x in kl4]
            e20 = _filt_ema(c4, 20)
            e50 = _filt_ema(c4, 50)
            px = float(kl1[-1]["close"])
            sep = abs(e20 - e50) / e50 * 100.0
            okl, ml = _filt_veredicto(base, "LONG", px, contar=False)
            oks, ms = _filt_veredicto(base, "SHORT", px, contar=False)
            print("%-6s px=%-11.6g EMA20-4H=%-11.6g sep=%5.2f%%  LONG:%s SHORT:%s"
                  % (base, px, e20, sep, "SI " if okl else "NO", "SI " if oks else "NO"))
        except Exception as e:
            print("%-6s ERROR %s" % (base, str(e)[:60]))
    print("(LONG: precio>EMA20-4H, vela verde y sep<=max | SHORT: al reves)")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()
