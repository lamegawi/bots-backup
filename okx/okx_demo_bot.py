#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""BOT DEMO OKX (X-Perps) 24/7 — migración de demo_bot.py (Bitget) a OKX Europa.

Usa la cuenta DEMO de OKX (cabecera x-simulated-trading: 1, dinero virtual).
Misma estrategia que el demo de Bitget:
  - Escanea la watchlist (velas 1H), EMA20/50 + ATR + alineación 1H.
  - Abre posición a mercado con SL (order-algo) + 5 TP parciales (20% c/u).
  - Break-even al 1:1 (cancela el SL y lo recrea en la entrada).
  - Avisa por Telegram (Estado / Saldo / cierres).

Credenciales DEMO via env: OKX_DEMO_KEY / OKX_DEMO_SECRET / OKX_DEMO_PASSPHRASE
"""
import os
import sys
import json
import time
import threading
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
RISK_USD       = float(os.environ.get("RISK_USD", "10.0"))
MAX_OPS        = int(os.environ.get("MAX_OPS", "5"))
LEVERAGE       = int(os.environ.get("LEVERAGE", "10"))
SCAN_EVERY_SEC = int(os.environ.get("SCAN_EVERY_SEC", "900"))
WATCH_EVERY_SEC = int(os.environ.get("WATCH_EVERY_SEC", "60"))

EMA_FAST = 20
EMA_SLOW = 50
ATR_PERIOD = 14
ATR_MULT_SL = 1.5
ATR_MULT_TP = 3.0
MIN_TREND_SCORE = float(os.environ.get("MIN_TREND_SCORE", "3.0"))

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

# Monedas base con X-Perp en DEMO (ctVal razonable). Se resuelven a su instId.
SYMBOLS = ["DOGE", "ETH", "XRP", "FIL", "ID", "ZEC", "UNI", "AVAX", "NEAR",
           "BCH", "ETC", "ONDO", "IOST", "ORBS", "HYPE", "GRASS", "IP", "KAITO"]

DEMO_KEY = os.environ.get("OKX_DEMO_KEY", "").strip()
DEMO_SECRET = os.environ.get("OKX_DEMO_SECRET", "").strip()
DEMO_PASSPHRASE = os.environ.get("OKX_DEMO_PASSPHRASE", "").strip()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

MANAGE_FILE = "/root/okx_demo_managed.json"
NOTIFIED_FILE = "/root/okx_demo_notified.json"

client = None


# ------------------------------------------------------------------ TELEGRAM
def _tg_send_kb(texto, keyboard):
    if not (TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID):
        return False
    try:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": texto,
                   "reply_markup": json.dumps(keyboard)}
        data = urllib.parse.urlencode(payload).encode()
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  [telegram] {e}")
        return False


def teclado_demo():
    return {"keyboard": [["📊 Estado"], ["💰 Saldo"]], "resize_keyboard": True}


def enviar(texto):
    return _tg_send_kb(texto, teclado_demo())


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
def get_klines(base, tf="1H", limit=200):
    inst_id = client.inst_id(base)
    if not inst_id:
        return []
    return client.velas(inst_id, bar=tf, limit=limit)


def get_klines_tf(base, tf):
    return get_klines(base, tf=tf)


def info_instr(base):
    inst_id = client.inst_id(base)
    if not inst_id:
        return None
    return client.info_instr(inst_id)


def ticker_precio(base):
    inst_id = client.inst_id(base)
    if not inst_id:
        return 0.0
    return float(client.ticker(inst_id).get("last", 0) or 0)


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
            "uplRatio": float(p.get("uplRatio", 0) or 0),
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
            kl = get_klines(base, "1H")
            if len(kl) < EMA_SLOW + ATR_PERIOD + 5:
                continue
            highs = [k["high"] for k in kl]
            lows = [k["low"] for k in kl]
            closes = [k["close"] for k in kl]
            e20 = ema(closes, EMA_FAST); e50 = ema(closes, EMA_SLOW)
            a = atr(highs, lows, closes, ATR_PERIOD)
            if not a or a <= 0:
                continue
            slope = e50[-1] - e50[-6] if len(e50) >= 6 else 0.0
            lc = closes[-1]
            bull = e20[-1] > e50[-1] and lc > e20[-1] and slope > 0
            bear = e20[-1] < e50[-1] and lc < e20[-1] and slope < 0
            if not (bull or bear):
                continue
            direction = "LONG" if bull else "SHORT"
            sep = abs(e20[-1] - e50[-1]) / lc * 100
            pend = abs(slope) / lc * 100
            score = sep + pend * 3
            if score < MIN_TREND_SCORE:
                continue
            info = info_instr(base)
            if not info:
                continue
            results.append({"symbol": base, "direction": direction,
                            "score": score, "entry": lc, "atr": a, "info": info})
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
        side = "buy"
        side_cierre = "sell"
    else:
        stop = entry + stop_dist
        side = "sell"
        side_cierre = "buy"

    ct_val = float(info.get("ctVal", 0) or 0)
    if ct_val <= 0:
        return None
    # contratos = riesgo / (valor de 1 contrato * distancia al SL)
    contratos = RISK_USD / (ct_val * stop_dist)
    contratos = max(1, int(round(contratos)))
    # tope de margen: no usar más del ~25% del disponible con el lev elegido
    try:
        bal = client.saldo()
        disp = bal.get("available", 0) if bal else 0
        dist_frac = stop_dist / entry if entry else 0.02
        lev = max(1, min(LEVERAGE, int(1 / (5 * dist_frac)) if dist_frac > 0 else LEVERAGE))
        nocional = contratos * ct_val * entry
        if disp > 0 and nocional > disp * lev * 0.25:
            contratos = max(1, int(disp * lev * 0.25 / (ct_val * entry)))
    except Exception:
        lev = LEVERAGE

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
            tp_levels.append({"price": round(precio, 8),
                              "sz": parts[i],
                              "atr_mult": lvl["atr_mult"]})

    return {"symbol": base, "direction": direction, "side": side,
            "side_cierre": side_cierre, "entry": entry, "stop": round(stop, 8),
            "atr": atr_val, "contratos": contratos, "lev": lev,
            "ct_val": ct_val, "tp_levels": tp_levels}


# ------------------------------------------------------------------ ÓRDENES
def set_leverage(base, lev):
    inst_id = client.inst_id(base)
    try:
        client.set_apalancamiento(inst_id, lev)
    except Exception as e:
        print(f"  [aviso] palanca {base}: {e}")


def open_position(plan):
    base = plan["symbol"]
    inst_id = client.inst_id(base)
    if not inst_id:
        raise RuntimeError(f"{base}: sin X-Perp en demo")

    set_leverage(base, plan["lev"])

    # 1) orden a mercado
    r = client.orden_mercado(inst_id, plan["side"], plan["contratos"])
    oid = (r.get("data") or [{}])[0].get("ordId")
    print(f"  >>> ORDEN DEMO {base} {plan['direction']} {plan['contratos']} ct (ordId={oid}) <<<")
    time.sleep(1.5)

    # 2) SL total
    sl_id = client.orden_algo_sl(inst_id, plan["side_cierre"], plan["stop"],
                                 plan["contratos"])
    print(f"  -> SL @ {plan['stop']} (algoId={sl_id})")

    # 3) TPs parciales
    tps_colocados = []
    for i, lvl in enumerate(plan["tp_levels"], 1):
        if lvl["sz"] <= 0:
            continue
        try:
            aid = client.orden_algo_tp(inst_id, plan["side_cierre"],
                                       lvl["price"], lvl["sz"])
            tps_colocados.append({"nivel": f"{lvl['atr_mult']:.1f}R",
                                  "precio": lvl["price"], "sz": lvl["sz"],
                                  "algoId": aid})
            print(f"  -> TP parcial {lvl['atr_mult']:.1f}R @ {lvl['price']} ({lvl['sz']} ct)")
        except Exception as e:
            print(f"  [aviso] TP{i}: {e}")

    managed = load_managed()
    managed[f"{base}:{plan['direction']}"] = {
        "symbol": base, "direction": plan["direction"], "entry": plan["entry"],
        "contratos": plan["contratos"], "sl_algo_id": sl_id, "state": "opened",
        "risk_usd": RISK_USD, "opened_at": time.time(),
        "dist": round((plan["atr"] * ATR_MULT_SL) / plan["entry"], 8),
        "initial_sl": plan["stop"],
        "tp_levels": tps_colocados,
    }
    save_managed(managed)
    return {"symbol": base, "direction": plan["direction"], "entry": plan["entry"],
            "contratos": plan["contratos"], "sl": plan["stop"],
            "risk": plan["contratos"] * plan["ct_val"] * (plan["atr"] * ATR_MULT_SL)}


def close_position(base, direction):
    inst_id = client.inst_id(base)
    client.cerrar(inst_id, direction.lower())


# ------------------------------------------------------------------ GESTIÓN
# === FIXTS_ARENA: trailing stop automatico ===
TRAILING_ACTIVAR = True      # False = comportamiento clasico (BE fijo)
TRAILING_CALLBACK = 0.03     # porcentaje de persecucion (3%)
TRAILING_DESDE_R = 1.5       # activacion con +1.5R de ganancia flotante
TRAILING_CANCELAR_TPS = True # al activarse: SL y TPs fuera, manda el trailing

# === FIXTS2_ARENA: trailing a SOFTWARE (el exchange NO soporta move_order_stop
# en X-Perps: error 51155). El bot sube el SL por tramos con amend-algos:
#   activacion +TRAILING_DESDE_R, nuevo = precio*(1-callback) con suelo en el BE,
#   ratchet (solo sube, nunca baja), minimo TRAILING_SW_MIN_PCT de mejora por amend.
# En modo software los TPs se conservan (no se cancelan).
TRAILING_SW = True            # True = trailing por software (recomendado)
TRAILING_SW_MIN_PCT = 0.002   # 0.2% de mejora minima para hacer un amend

def manage_positions():
    positions = get_all_positions()
    pos_map = {}
    for p in positions:
        # FIXK_ARENA: clave CON espacio (igual que open_position y el panel)
        pos_map[f"{p['base']}: {p['direction']}"] = p

    managed = load_managed()
    changed = False
    notified = load_notified()

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
                    # no repetir el mismo cierre (dedupe por uTime)
                    if utime and notified.get(base) == utime:
                        ya_avisado = True
                    elif utime:
                        notified[base] = utime
            except Exception as e:
                print(f"  [cierre] histórico: {e}")
            if not ya_avisado:
                enviar(f"🔔 *Posición DEMO cerrada*: {base} {direction}\n"
                       f"(entrada ~{m.get('entry'):g}{detalle})")
            # FIXR_ARENA: cancelar algos huerfanos del cierre
            try:
                _nz = client.cancelar_todas_algo(inst_id)
                if _nz:
                    print("  [LIMPIEZA] " + base + ": " + str(_nz) + " orden(es) huerfana(s) cancelada(s)")
            except Exception as _ez:
                print("  [LIMPIEZA] " + base + ": " + str(_ez))
            del managed[key]
            changed = True
            continue

        if m.get("ausente"):
            m["ausente"] = 0
            changed = True
        qty = p["qty"]; unreal = p["pnl"]
        # === FIXWDOG_ARENA: watchdog del SL — si el SL del exchange desaparece
        # (cancelado, rollover, fallo), se recoloca YA al nivel vigente.
        _pend_sl = []
        try:
            _pend_sl = client.algo_pendientes(inst_id) or []
        except Exception:
            pass
        if m.get("sl_algo_id"):
            _sl_vivo = any(str(_a.get("algoId")) == str(m.get("sl_algo_id"))
                           for _a in _pend_sl)
            if not _sl_vivo:
                _nivel = m.get("sw_sl_px") or m.get("initial_sl")
                if _nivel:
                    try:
                        _nuevo = client.orden_algo_sl(
                            inst_id, "sell" if direction == "LONG" else "buy",
                            float(_nivel), int(qty))
                        if _nuevo:
                            m["sl_algo_id"] = _nuevo
                            m["sw_sl_px"] = float(_nivel)
                            changed = True
                            print("[WDOG] %s %s: SL ausente en el exchange -> recolocado @ %s (#%s)"
                                  % (base, direction, _nivel, _nuevo))
                            enviar("🚨 *[DEMO] %s %s*: el SL habia desaparecido -> recolocado @ %.6g"
                                   % (base, direction, float(_nivel)))
                        else:
                            print("[WDOG] %s: sin algoId al recolocar (reintenta)" % base)
                    except Exception as _we:
                        print("[WDOG] %s: fallo al recolocar: %s" % (base, str(_we)[:100]))

        # === FIXTS2_ARENA: trailing a SOFTWARE via amend-algos (ratchet) ===
        # El exchange no soporta move_order_stop en X-Perps (error 51155).
        # Nuevo SL = precio*(1-callback) con suelo en el BE; solo sube (ratchet);
        # si queda >= BE la posicion pasa a estado breakeven. Los TPs se conservan.
        try:
            if (TRAILING_ACTIVAR and TRAILING_SW and m
                    and m.get("state") != "trailing" and m.get("sl_algo_id")):
                _riesgo = float(m.get("risk_usd", 0) or 0)
                _rr = (float(unreal or 0) / _riesgo) if _riesgo > 0 else 0.0
                _entry_m = float(m.get("entry", 0) or 0)
                _px = float(p.get("mark", 0) or 0) or float(p.get("entry", 0) or 0)
                if _rr >= TRAILING_DESDE_R and _entry_m > 0 and _px > 0:
                    _is_long = (direction == "LONG")
                    _be_lvl = (_entry_m * (1 + BREAKEVEN_BUFFER) if _is_long
                               else _entry_m * (1 - BREAKEVEN_BUFFER))
                    _cand = (_px * (1 - TRAILING_CALLBACK) if _is_long
                             else _px * (1 + TRAILING_CALLBACK))
                    _cand = max(_cand, _be_lvl) if _is_long else min(_cand, _be_lvl)
                    _cur = float(m.get("sw_sl_px") or 0)
                    if _cur <= 0:
                        for _a in _pend_sl:
                            if str(_a.get("algoId")) == str(m.get("sl_algo_id")) \
                                    and _a.get("slTriggerPx"):
                                _cur = float(_a["slTriggerPx"])
                                break
                    if _cur > 0:
                        _mejora = ((_cand - _cur) if _is_long
                                    else (_cur - _cand)) / _cur
                        if _mejora >= TRAILING_SW_MIN_PCT:
                            client.mover_sl_algo(inst_id, m["sl_algo_id"], _cand)
                            m["sw_sl_px"] = _cand
                            if m.get("state") in ("opened", "adopted"):
                                m["state"] = "breakeven"
                            changed = True
                            print("  [TRAILSW] %s %s: SL a %.6g (px %.6g, cb %.0f%%)"
                                  % (base, direction, _cand, _px,
                                     TRAILING_CALLBACK * 100))
                            enviar("🎯 *%s %s (DEMO)* — trailing: SL a %.6g"
                                   % (base, direction, _cand))
        except Exception as _et:
            print("  [TRAILSW] error: " + str(_et)[:100])

        entry = float(p.get("entry", 0) or 0)
        dist = float(m.get("dist", 0) or 0)
        risk_actual = float(m.get("risk_usd", RISK_USD) or RISK_USD)

        # Cierre PARCIAL (TPs): avisar cuando la cantidad baja
        qty_ant = float(m.get("qty_vista", qty) or qty)
        if qty_ant - qty >= 1e-9:
            cerr = int(qty_ant - qty)
            enviar(f"✅ *TP parcial (DEMO)*: {base} {direction}\n"
                   f"Cerrados ~{cerr} ct · quedan {qty:g} ct · "
                   f"P&L actual {unreal:+.2f} USDC")
        m["qty_vista"] = qty
        changed = True

        # Break-even al 1:1 — FIXBE2_ARENA: crear el SL nuevo ANTES de cancelar
        # el antiguo y verificar que queda vivo (nunca dejar la posicion sin SL).
        # Tambien aplica a posiciones "adopted" (las adoptadas tambien hacen BE).
        if (BREAKEVEN_ENABLED and m.get("state") in ("opened", "adopted")
                and unreal >= risk_actual):
            be_price = (entry * (1 + BREAKEVEN_BUFFER) if direction == "LONG"
                        else entry * (1 - BREAKEVEN_BUFFER))
            try:
                nuevo_sl = client.orden_algo_sl(inst_id,
                                                "sell" if direction == "LONG" else "buy",
                                                be_price, int(qty))
                _pend2 = client.algo_pendientes(inst_id) or []
                _confirmado = any(str(_a.get("algoId")) == str(nuevo_sl)
                                  for _a in _pend2)
                if nuevo_sl and _confirmado:
                    try:
                        client.cancelar_algo(inst_id, m.get("sl_algo_id"))
                    except Exception as e:
                        print(f"  [BE] cancelar SL viejo: {e} (el nuevo esta vivo, OK)")
                    m["sl_algo_id"] = nuevo_sl
                    m["sw_sl_px"] = be_price
                    m["state"] = "breakeven"
                    changed = True
                    print(f"  [BE] {base} {direction} SL a BREAK-EVEN @ {be_price}")
                    enviar(f"🛡️ *{base} {direction} (DEMO)* — SL a break-even @ {be_price:.6g}")
                else:
                    print(f"  [BE] FIXBE2: SL nuevo no confirmado vivo -> se cancela y se mantiene el anterior")
                    try:
                        if nuevo_sl:
                            client.cancelar_algo(inst_id, nuevo_sl)
                    except Exception:
                        pass
            except Exception as e:
                print(f"  [BE] recrear SL: {e} (se mantiene el SL anterior)")

    if changed:
        save_managed(managed)
    if notified != load_notified():
        save_notified(notified)


# ------------------------------------------------------------------ BOTONES
MARCADORES = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣",
              "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def boton_estado():
    pos = get_all_positions()
    if not pos:
        enviar("ℹ️ No hay posiciones demo abiertas ahora.")
        return
    managed = load_managed()
    lineas = []
    for i, p in enumerate(pos):
        marca = MARCADORES[i] if i < len(MARCADORES) else f"{i+1}."
        sym = p["symbol"]; d = p["direction"]
        # Color del P&L: azul positivo, rojo negativo, gris en 0
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
        # FIXBET_ARENA: indicador de TRAILING (cajon move_order_stop, invisible para FIXBE)
        try:
            _g = globals()
            if _g.get("_FIXT_TS") is None or time.time() - _g["_FIXT_TS"] > 60:
                _trm = {}
                for _a in client.trailing_pendientes() or []:
                    _mp = _a.get("moveTriggerPx")
                    if _mp:
                        _trm[_a.get("instId", "")] = _mp
                _g["_FIXT_M"] = _trm
                _g["_FIXT_TS"] = time.time()
            _trp = (_g.get("_FIXT_M") or {}).get(sym)
            if _trp:
                _stop = float(_trp or 0)
                _pxv = 0.0
                try:
                    _pxv = float((client.ticker(sym) or {}).get("last", 0) or 0)
                except Exception:
                    pass
                _ent = float(p.get("entry", 0) or 0)
                _upl = float(p.get("pnl") or p.get("upl") or 0)
                _lock = None
                if _stop > 0 and _ent > 0 and _pxv > 0 and _pxv != _ent:
                    _lock = _upl * (_stop - _ent) / (_pxv - _ent)
                if _lock is not None and _lock > 0:
                    linea += " | \U0001F397 asegura +$%.2f" % _lock
                else:
                    linea += " | \U0001F397 Trail@%s" % _trp
        except Exception:
            pass
        lineas.append(linea)
    enviar("📊 *Estado de posiciones (DEMO OKX)*\n\n" + "\n".join(lineas))


def boton_saldo():
    bal = client.saldo()
    if not bal:
        enviar("❌ No pude leer el saldo demo.")
        return
    enviar("💰 *Saldo de la cuenta (DEMO OKX)*\n\n"
           f"• Equity total: *{bal['equity']:.2f} USD*\n"
           f"• Disponible (USDC): {bal['available']:.2f} USDC\n"
           f"• P&L no realizado: {bal['unrealized']:+.2f} USD")


def telegram_listener():
    offset = 0
    try:
        url = (f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
               f"?offset=-1&timeout=1")
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.loads(r.read().decode())
            ups = d.get("result") or []
            if ups:
                offset = ups[-1]["update_id"] + 1
    except Exception:
        pass
    print("[telegram] hilo del menú DEMO OKX activo")
    while True:
        try:
            url = (f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
                   f"?offset={offset}&timeout=25"
                   f"&allowed_updates=%5B%22message%22%5D")
            with urllib.request.urlopen(url, timeout=35) as r:
                d = json.loads(r.read().decode())
            for upd in d.get("result") or []:
                offset = max(offset, upd["update_id"] + 1)
                msg = upd.get("message") or {}
                chat = (msg.get("chat") or {}).get("id")
                if str(chat) != str(TELEGRAM_CHAT_ID):
                    continue
                texto = msg.get("text") or ""
                import unicodedata as _ud
                norm = "".join(c for c in _ud.normalize("NFKD", texto.lower())
                               if not _ud.combining(c))
                norm = "".join(c for c in norm if c.isalpha())
                if texto.strip().startswith("/start") or norm == "estado":
                    boton_estado()
                elif norm == "saldo":
                    boton_saldo()
        except Exception:
            time.sleep(5)


# ------------------------------------------------------------------ MAIN
def main():
    global client
    if not (DEMO_KEY and DEMO_SECRET and DEMO_PASSPHRASE):
        print("ERROR: faltan OKX_DEMO_* en el entorno")
        sys.exit(1)

    client = OKX.Cliente(DEMO_KEY, DEMO_SECRET, DEMO_PASSPHRASE, demo=True)
    bal = client.saldo()
    print(f"=== BOT DEMO OKX | riesgo {RISK_USD} USD | lev máx {LEVERAGE}x ===")
    print(f"[auth OK] cuenta DEMO OKX — equity {bal['equity']:.2f} {bal['ccy']}")

    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        threading.Thread(target=telegram_listener, daemon=True).start()
        enviar("🎛 *Bot DEMO OKX arrancado.*\n\n📊 Estado · 💰 Saldo")

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
                if len(open_positions) < MAX_OPS:
                    print(f"[scan] {len(open_positions)}/{MAX_OPS} posiciones demo, escaneando…")
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
                            enviar(f"🔔 *Posición abierta (DEMO)*: {res['direction']} {res['symbol']}\n"
                                   f"Entrada ~{res['entry']:.6g} · {res['contratos']} ct\n"
                                   f"SL {res['sl']:.6g} · riesgo ~{res['risk']:.2f} USD")
                        except Exception as e:
                            print(f"  [error] {cand['symbol']}: {e}")

            if open_positions:
                for p in open_positions:
                    print(f"  [DEMO] {p['symbol']} {p['direction']} P&L={p['pnl']:+.2f}")
        except KeyboardInterrupt:
            print("\nBot demo OKX detenido.")
            break
        except Exception as e:
            print(f"  [error loop] {e}")
        time.sleep(10)


# === FIXD_ARENA: blacklist + protecciones de gestion + SL seguro ===
import okx_client as _OKX_BL
_BL_FILE = "/root/okx_demo_blacklist.json"
def _bl_load():
    try:
        return set(json.load(open(_BL_FILE)))
    except Exception:
        return set()
def _bl_add(b):
    s = _bl_load()
    s.add(b)
    try:
        json.dump(sorted(s), open(_BL_FILE, "w"))
    except Exception:
        pass
_orig_om = _OKX_BL.Cliente.orden_mercado
def _om_bl(self, inst_id, side, sz, tp_px=None, sl_px=None):
    try:
        return _orig_om(self, inst_id, side, sz, tp_px=tp_px, sl_px=sl_px)
    except Exception as e:
        m = str(e).lower()
        if "51155" in m or "compliance" in m or "restrict" in m or "can't trade" in m or "cant trade" in m:
            b = inst_id.split("-")[0]
            _bl_add(b)
            global SYMBOLS
            if b in SYMBOLS:
                SYMBOLS = [s for s in SYMBOLS if s != b]
            print("[BLACKLIST] " + b + " restringido en OKX Europa -> excluido de la lista")
        raise
_OKX_BL.Cliente.orden_mercado = _om_bl
SYMBOLS = [s for s in SYMBOLS if s not in _bl_load()]

_PROT_FILE = "/root/okx_demo_protecciones.json"
MAX_TRADES_DIA = int(os.environ.get("MAX_TRADES_DIA", "3"))
REENTRY_HORAS = float(os.environ.get("REENTRY_HORAS", "4"))
MIN_SEG_ENTRE_APERTURAS = int(os.environ.get("MIN_SEG_ENTRE_APERTURAS", "600"))
RANGO_MIN_ATR = float(os.environ.get("RANGO_MIN_ATR", "3.5"))

def _prot_load():
    try:
        return json.load(open(_PROT_FILE))
    except Exception:
        return {}
def _prot_save(d):
    try:
        json.dump(d, open(_PROT_FILE, "w"))
    except Exception:
        pass
def _prot_hoy():
    return datetime.now(MAD).strftime("%Y-%m-%d")
def _prot_check(base):
    d = _prot_load()
    hoy = _prot_hoy()
    if d.get("dia") != hoy:
        d = {"dia": hoy}
        _prot_save(d)
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
def _prot_registrar(base):
    d = _prot_load()
    hoy = _prot_hoy()
    if d.get("dia") != hoy:
        d = {"dia": hoy}
    d["abiertas_hoy"] = int(d.get("abiertas_hoy", 0)) + 1
    d["ultima_apertura_ts"] = time.time()
    d.setdefault("ultimas_por_moneda", {})[base] = time.time()
    _prot_save(d)
def _rango_ok(base, atr_val):
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

_scan_orig = scan_coins
def scan_coins(exclude_symbols=None):
    cands = _scan_orig(exclude_symbols)
    out = []
    for c in cands:
        motivo = _prot_check(c["symbol"])
        if motivo:
            print("[PROT] " + c["symbol"] + " bloqueada: " + motivo)
            continue
        if not _rango_ok(c["symbol"], c.get("atr")):
            print("[PROT] " + c["symbol"] + " bloqueada: mercado comprimido (rango < " + str(RANGO_MIN_ATR) + "xATR)")
            continue
        out.append(c)
    return out

def open_position(plan):
    base = plan["symbol"]
    motivo = _prot_check(base)
    if motivo:
        raise RuntimeError(base + ": BLOQUEADA (" + motivo + ")")
    if not _rango_ok(base, plan.get("atr")):
        raise RuntimeError(base + ": BLOQUEADA (mercado comprimido)")
    inst_id = client.inst_id(base)
    if not inst_id:
        raise RuntimeError(base + ": sin X-Perp en demo")
    set_leverage(base, plan["lev"])
    r = client.orden_mercado(inst_id, plan["side"], plan["contratos"])
    oid = (r.get("data") or [{}])[0].get("ordId")
    print(">>> ORDEN DEMO " + base + " " + plan["direction"] + " " + str(plan["contratos"]) + " ct (ordId=" + str(oid) + ") <<<")
    _prot_registrar(base)
    time.sleep(1.5)
    sl_id = None
    try:
        sl_id = client.orden_algo_sl(inst_id, plan["side_cierre"], plan["stop"], plan["contratos"])
        print("-> SL @" + str(plan["stop"]) + " (algoId=" + str(sl_id) + ")")
    except Exception as e:
        print("[CRITICO] " + base + ": el SL fallo tras abrir -> CERRANDO por seguridad. " + str(e))
        try:
            client.orden_mercado(inst_id, plan["side_cierre"], plan["contratos"])
        except Exception as ce:
            print("[CRITICO] " + base + ": tampoco se pudo cerrar: " + str(ce))
        try:
            enviar("*[DEMO] " + base + " " + plan["direction"] + ": SL fallo -> cerrada por seguridad*")
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
        "initial_sl": plan["stop"], "tp_levels": tps_colocados,
        "sw_sl_px": plan["stop"]}   # FIXTS2_ARENA: nivel SL actual (ratchet SW)
    save_managed(managed)
    return {"symbol": base, "direction": plan["direction"], "entry": plan["entry"],
            "contratos": plan["contratos"], "sl": plan["stop"],
            "risk": plan["contratos"] * plan["ct_val"] * (plan["atr"] * ATR_MULT_SL)}

# === JOURNAL_ARENA: diario de trades (fase 1 autoaprendizaje) ===
_JOURNAL_FILE = "/root/okx_demo_journal.json"
_JOURNAL_BOT = "demo"
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
