#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chequeo de salud de los bots de Polymarket (bot-poly).

Modos:
  - por defecto (--elon): vigila SOLO los servicios de Elon
    y notifica al bot de Elon (TELEGRAM_BOT_TOKEN).
  - --zelen: vigila SOLO los servicios de Zelenskyy
    y notifica al bot de Zelenskyy (ZELEN_BOT_TOKEN).

En ambos casos también comprueba: Tailscale con el PC, proxy del PC
(100.83.57.99:8888) + IP de salida, y Polymarket (clob) a través del proxy.

Solo notifica cuando cambia el estado (OK->FALLO o FALLO->OK). Con --test
envía el estado completo.
"""
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

TOKEN_ELON = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TOKEN_ZELEN = os.environ.get("ZELEN_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
ESTADO_FILE = "/opt/polymarket/salud_estado.json"
ESTADO_FILE_ZELEN = "/opt/polymarket/salud_estado_zelen.json"
IP_CASA = "85.85.41.76"
PROXY = "http://100.83.57.99:8888"

SERVICIOS_ELON = ["poly-elon", "poly-semanal", "poly-mensual",
                  "poly-telegram", "poly-gestor"]
SERVICIOS_ZELEN = ["poly-zelenskyy", "poly-telegram-zelen"]


def tg_send(texto, token):
    if not token or not CHAT_ID:
        print("  [sin token telegram]")
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texto}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception as e:
        print(f"  [tg error] {e}")
        return False


def check(servicios=None):
    if servicios is None:
        servicios = SERVICIOS_ELON
    res = {"ok": True, "detalles": [], "fallos": []}

    # 1) servicios
    for s in servicios:
        r = subprocess.run(["systemctl", "is-active", s], capture_output=True, text=True)
        estado = r.stdout.strip()
        if estado != "active":
            res["ok"] = False
            res["fallos"].append(f"servicio {s}: {estado}")
        res["detalles"].append(f"{s}: {estado}")

    # 2) tailscale con el PC
    ts = subprocess.run(["tailscale", "status"], capture_output=True, text=True)
    if "ferpc" not in ts.stdout:
        res["ok"] = False
        res["fallos"].append("PC (ferpc) no visible en Tailscale")
    else:
        res["detalles"].append("tailscale ferpc: OK")

    # 3) proxy + IP de salida
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "15", "-x", PROXY, "https://api.ipify.org"],
            capture_output=True, text=True, timeout=20)
        ip = r.stdout.strip()
        if r.returncode != 0 or not ip:
            raise RuntimeError("curl sin respuesta")
        res["detalles"].append(f"IP de salida: {ip}")
        if ip != IP_CASA:
            res["ok"] = False
            res["fallos"].append(f"IP de salida {ip} != casa {IP_CASA}")
        else:
            res["detalles"].append("proxy + IP casa: OK")
    except Exception as e:
        res["ok"] = False
        res["fallos"].append(f"proxy no responde: {e}")

    # 4) clob a través del proxy
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "15", "-x", PROXY,
             "-o", "/dev/null", "-w", "%{http_code}", "https://clob.polymarket.com/"],
            capture_output=True, text=True, timeout=20)
        code = r.stdout.strip()
        if r.returncode == 0 and code:
            res["detalles"].append(f"clob via proxy: OK (HTTP {code})")
        else:
            raise RuntimeError("curl sin respuesta")
    except Exception as e:
        res["ok"] = False
        res["fallos"].append(f"clob via proxy falla: {e}")

    return res


def load_state(path):
    try:
        return json.load(open(path, encoding="utf-8"))
    except Exception:
        return {"ultimo_ok": None, "ultimos_fallos": []}


def save_state(path, res):
    json.dump({"ultimo_ok": res["ok"], "ultimos_fallos": res["fallos"]},
              open(path, "w", encoding="utf-8"), ensure_ascii=False)


def main():
    test = "--test" in sys.argv
    zelen = "--zelen" in sys.argv

    if zelen:
        token = TOKEN_ZELEN
        servicios = SERVICIOS_ZELEN
        estado_file = ESTADO_FILE_ZELEN
        titulo = "ZELENSKYY"
    else:
        token = TOKEN_ELON
        servicios = SERVICIOS_ELON
        estado_file = ESTADO_FILE
        titulo = "POLYMARKET"

    res = check(servicios)
    prev = load_state(estado_file)
    cambio = prev.get("ultimo_ok") != res["ok"] or \
        set(prev.get("ultimos_fallos", [])) != set(res["fallos"])

    if test or cambio:
        if res["ok"]:
            texto = f"✅ *SALUD {titulo}: TODO OK*\n\n" + "\n".join(
                f"• {d}" for d in res["detalles"])
        else:
            texto = f"⚠️ *SALUD {titulo}: HAY FALLOS*\n\n" + "\n".join(
                f"• ❌ {f}" for f in res["fallos"]) + "\n\n*Detalle:*\n" + \
                "\n".join(f"• {d}" for d in res["detalles"])
        if test:
            print(texto)
        tg_send(texto, token)

    save_state(estado_file, res)
    print("check:", "OK" if res["ok"] else "FALLO")
    for d in res["detalles"]:
        print("  ", d)


if __name__ == "__main__":
    main()
