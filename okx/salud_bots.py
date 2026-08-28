#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""salud_bots.py - Chequeo nocturno de salud de los bots OKX (demo y real).

Comprueba: servicios activos, conexión OKX, posiciones sin SL,
posiciones fantasma, registros huérfanos y órdenes zombis.
Repara (conservador): arranca servicios parados, coloca SL protectores,
adopta fantasmas, limpia registros, cancela órdenes zombis (>2h, no reduceOnly).
NUNCA cierra posiciones. Informe por Telegram + log en /root/salud_bots.log.
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.path.insert(0, "/root")
import okx_client as OKX

MAD = ZoneInfo("Europe/Madrid")
LOG_FILE = "/root/salud_bots.log"
ZOMBI_HORAS = 2.0          # orden viva sin rellenar > N horas -> cancelar
SL_PROTECTOR_PCT = 0.04    # distancia del SL de emergencia (4%)

BOTS = [
    {"nombre": "DEMO", "service": "okx-demo-bot.service", "env": "/root/.okx_demo_env",
     "managed": "/root/okx_demo_managed.json", "demo": True},
    {"nombre": "REAL", "service": "okx-real-bot.service", "env": "/root/.okx_real_env",
     "managed": "/root/okx_real_managed.json", "demo": False},
]


def log(txt):
    linea = "[" + datetime.now(MAD).strftime("%Y-%m-%d %H:%M") + "] " + txt
    print(linea)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(linea + "\n")
    except Exception:
        pass


def cargar_env(path):
    env = {}
    try:
        for line in open(path):
            line = line.strip()
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                env[k.replace("export", "").strip()] = v.strip().strip('"').strip("'")
    except Exception:
        pass
    return env


def tg_send(token, chat, texto):
    if not token or not chat:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": texto}).encode()
        req = urllib.request.Request(
            "https://api.telegram.org/bot" + token + "/sendMessage", data=data)
        urllib.request.urlopen(req, timeout=20)
    except Exception:
        pass


def systemctl(accion, servicio):
    try:
        r = subprocess.run(["systemctl", accion, servicio], capture_output=True, text=True)
        return r.returncode == 0
    except Exception:
        return False


def servicio_activo(servicio):
    try:
        r = subprocess.run(["systemctl", "is-active", servicio], capture_output=True, text=True)
        return r.stdout.strip() == "active"
    except Exception:
        return False


def _guardar_json(path, data):
    try:
        json.dump(data, open(path, "w"), indent=1)
    except Exception:
        pass


def chequear_bot(bot):
    rep = []
    reparaciones = 0

    # 1) Servicio
    if servicio_activo(bot["service"]):
        rep.append("✅ Servicio: activo")
    else:
        # FIXPAUSA_ARENA: no arrancar el REAL si hay pausa manual
        if bot.get("nombre") == "REAL" and os.path.exists("/root/.okx_real_pausado"):
            rep.append("Servicio: PARADO a proposito (pausa manual) -> NO arrancado")
        elif systemctl("start", bot["service"]):
            rep.append("🔧 Servicio: estaba PARADO -> ARRANCADO")
            reparaciones += 1
        else:
            rep.append("🔴 Servicio: PARADO y no pude arrancarlo")

    # 2) Credenciales + conexión
    env = cargar_env(bot["env"])
    pref = "OKX_DEMO_" if bot["demo"] else "OKX_REAL_"
    key = env.get(pref + "KEY", "")
    sec = env.get(pref + "SECRET", "")
    pas = env.get(pref + "PASSPHRASE", "")
    if not (key and sec and pas):
        rep.append("🔴 Credenciales: no encontradas en " + bot["env"])
        return rep, reparaciones, env
    try:
        c = OKX.Cliente(key, sec, pas, demo=bot["demo"])
        bal = c.saldo()
        rep.append("✅ Conexión OKX: OK (equity " + format(bal.get("equity", 0), ".2f") + " USD)")
    except Exception as e:
        rep.append("🔴 Conexión OKX: FALLA - " + str(e)[:100])
        return rep, reparaciones, env

    # 3) Posiciones vs registro
    try:
        posiciones = c.posiciones()
    except Exception as e:
        rep.append("🔴 No pude leer posiciones: " + str(e)[:80])
        posiciones = []
    managed = {}
    try:
        managed = json.load(open(bot["managed"]))
    except Exception:
        managed = {}

    pos_map = {}
    for p in posiciones:
        base = p.get("instId", "?").split("-")[0]
        pos_map[base] = p

    # 3a) registros huerfanos -> limpiar
    cambiado = False
    for clave in list(managed.keys()):
        base = str(managed[clave].get("symbol", ""))
        if base and base not in pos_map:
            del managed[clave]
            cambiado = True
            reparaciones += 1
            rep.append("🧹 Registro huérfano limpiado: " + base)
    if cambiado:
        _guardar_json(bot["managed"], managed)

    # 3b) SL en cada posicion + fantasmas
    for base, p in pos_map.items():
        try:
            qty_raw = float(p.get("pos", 0) or 0)
        except Exception:
            continue
        if qty_raw == 0:
            continue
        direccion = "LONG" if qty_raw > 0 else "SHORT"
        pos_qty = abs(int(qty_raw))
        iid = p.get("instId", "")
        clave = base + ": " + direccion
        conocida = clave in managed
        tiene_sl = False
        try:
            for a in c.algo_pendientes(iid):
                if a.get("slTriggerPx"):
                    tiene_sl = True
                    break
        except Exception:
            tiene_sl = True  # si no puedo comprobar, no toco nada
        if tiene_sl:
            continue
        entrada = float(p.get("avgPx", 0) or 0)
        ref = float(p.get("markPx", 0) or 0)
        if ref <= 0:
            ref = entrada
        side_cierre = "sell" if direccion == "LONG" else "buy"
        # FIXADOPT_ARENA: capar el riesgo del adoptado a ~12 USD (antes 4% fijo = ~20 USD)
        _pct_sl = SL_PROTECTOR_PCT
        try:
            _notional = abs(float(p.get("notionalUsd", 0) or 0))
            if _notional > 0:
                _pct_sl = min(SL_PROTECTOR_PCT, 12.0 / _notional)
        except Exception:
            pass
        if direccion == "LONG":
            sl_px = ref * (1 - _pct_sl)
        else:
            sl_px = ref * (1 + _pct_sl)
        try:
            nuevo_sl = c.orden_algo_sl(iid, side_cierre, round(sl_px, 8), pos_qty)
            reparaciones += 1
            if conocida:
                managed[clave]["sl_algo_id"] = nuevo_sl
                managed[clave]["initial_sl"] = round(sl_px, 8)
            else:
                managed[clave] = {"symbol": base, "direction": direccion, "entry": entrada,
                                  "contratos": pos_qty, "sl_algo_id": nuevo_sl,
                                  "state": "adopted", "risk_usd": 10.0,
                                  "opened_at": time.time(), "dist": SL_PROTECTOR_PCT,
                                  "initial_sl": round(sl_px, 8), "tp_levels": []}
            _guardar_json(bot["managed"], managed)
            if conocida:
                rep.append("🔧 " + base + ": SIN stop-loss -> SL protector colocado @" + format(sl_px, "g"))
            else:
                rep.append("👻🔧 " + base + ": posición FANTASMA -> SL protector + adoptada")
        except Exception as e:
            rep.append("🔴 " + base + ": SIN SL y no pude colocar protector: " + str(e)[:80])

    rep.append("✅ Posiciones: " + str(len(pos_map)) + " (" + ", ".join(sorted(pos_map.keys())) + ")")

    # 4) ordenes zombis (>2h vivas y NO reduceOnly -> cancelar)
    try:
        pend = c._req("GET", "/api/v5/trade/orders-pending") or {}
        ahora = time.time() * 1000
        for o in (pend.get("data") or []):
            try:
                t = float(o.get("cTime", 0) or 0)
            except Exception:
                t = 0
            if not t or (ahora - t) <= ZOMBI_HORAS * 3600000:
                continue
            if str(o.get("reduceOnly", "")).lower() == "true":
                continue
            try:
                c._req("POST", "/api/v5/trade/cancel-order",
                       {"instId": o.get("instId"), "ordId": o.get("ordId")})
                reparaciones += 1
                rep.append("⛔ Orden zombi cancelada: " + str(o.get("instId")) + " " +
                           str(o.get("side")) + " " + str(o.get("sz")) + " ct")
            except Exception:
                pass
    except Exception:
        pass

    # 4b) FIXR_ARENA: ALGOS zombis (TPs/SLs huerfanos de posiciones cerradas)
    try:
        _ahora = time.time() * 1000
        for _a in c.algo_pendientes() or []:
            _ba = str(_a.get("instId", "")).split("-")[0]
            if (not _ba) or (_ba in pos_map):
                continue
            try:
                _t = float(_a.get("cTime", 0) or 0)
            except Exception:
                _t = 0
            if (not _t) or (_ahora - _t) <= ZOMBI_HORAS * 3600000:
                continue
            try:
                c.cancelar_algo(_a.get("instId", ""), _a.get("algoId"))
                reparaciones += 1
                rep.append("Algo zombi cancelada: " + _ba)
            except Exception:
                pass
    except Exception:
        pass

    return rep, reparaciones, env


def main():
    log("=== SALUD NOCTURNA: empieza ===")
    for bot in BOTS:
        try:
            rep, reparaciones, env = chequear_bot(bot)
        except Exception as e:
            rep = ["🔴 ERROR inesperado: " + str(e)[:120]]
            reparaciones = 0
            env = {}
        if reparaciones:
            resultado = "🟡 REPARADO (" + str(reparaciones) + " correcciones)"
        else:
            resultado = "🟢 SANO"
        msg = "🩺 *Salud nocturna - Bot " + bot["nombre"] + " OKX*\n\n" + \
              "\n".join(rep) + "\n\nRESULTADO: " + resultado
        log("Bot " + bot["nombre"] + ": " + resultado)
        tg_send(env.get("TELEGRAM_BOT_TOKEN", ""), env.get("TELEGRAM_CHAT_ID", ""), msg)
    if os.path.exists("/root/.okx_signal_pausado"):
        log("signal-bot: parado a proposito (pausa manual) -> no lo arranco")
    elif servicio_activo("okx-signal-bot.service"):
        log("signal-bot: activo")
    else:
        if systemctl("start", "okx-signal-bot.service"):
            log("signal-bot: estaba parado -> ARRANCADO")
        else:
            log("signal-bot: PARADO y no pude arrancarlo")
    log("=== SALUD NOCTURNA: termina ===")


if __name__ == "__main__":
    main()