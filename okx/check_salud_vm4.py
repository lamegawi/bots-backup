#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chequeo de salud de los bots de bot-vm4 (Bitget real/demo/señales + fútbol).

Comprueba los 4 servicios systemd y avisa por Telegram a cada bot:
  - real-bot   -> @Bitget_real_trade_bot
  - demo-bot   -> @Bitget_demo_trade_bot
  - signal-bot -> @Bitget_real_trade_bot (mismo bot que real)
  - empatebot  -> bot de fútbol (@empates_Portu_bot)

Solo notifica cuando cambia el estado. Con --test envía el estado completo.
"""
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request

ESTADO_FILE = "/root/salud_estado.json"


def leer_env(path):
    """Lee un fichero .env a un dict."""
    d = {}
    try:
        for line in open(path, encoding="utf-8"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip()
    except Exception:
        pass
    return d


def tg_send(token, chat_id, texto):
    if not token or not chat_id:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": texto}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception:
        return False


def estado_servicio(nombre):
    r = subprocess.run(["systemctl", "is-active", nombre], capture_output=True, text=True)
    return r.stdout.strip()


def main():
    test = "--test" in sys.argv

    env_real = leer_env("/root/.bitget_real_env")
    env_demo = leer_env("/root/.bitget_demo_env")
    env_empate = leer_env("/etc/empatebot.env")
    env_okx_real = leer_env("/root/.okx_real_env")
    env_okx_demo = leer_env("/root/.okx_demo_env")

    canales = {
    "okx-real-bot": (env_okx_real.get("TELEGRAM_BOT_TOKEN", ""), env_okx_real.get("TELEGRAM_CHAT_ID", "")),
    "okx-demo-bot": (env_okx_demo.get("TELEGRAM_BOT_TOKEN", ""), env_okx_demo.get("TELEGRAM_CHAT_ID", "")),
    "okx-signal-bot": (env_okx_real.get("TELEGRAM_BOT_TOKEN", ""), env_okx_real.get("TELEGRAM_CHAT_ID", "")),
        "empatebot":  (env_empate.get("TELEGRAM_TOKEN", ""), env_empate.get("OWNER_CHAT_ID", "") or env_empate.get("TELEGRAM_CHAT_ID", "250818720")),
        "bolsa-bot":  (os.environ.get("BOLSA_BOT_TOKEN", "8009484057:AAEUcufEtcq6k_lb1idmuH1trTXJTLv_Kdc"), "250818720"),
    }

    estado = {}
    for s in canales:
        estado[s] = estado_servicio(s)

    try:
        prev = json.load(open(ESTADO_FILE, encoding="utf-8"))
    except Exception:
        prev = {}

    for s, st in estado.items():
        token, chat = canales[s]
        antes = prev.get(s)
        if test or antes != st:
            if st == "active":
                txt = f"✅ Bot *{s}* funcionando correctamente."
            else:
                txt = f"⚠️ Bot *{s}* FALLA: estado `{st}`.\nMira: `systemctl status {s}`"
            ok = tg_send(token, chat, txt)
            print(f"[{s}] {st} -> enviado a {chat}: {ok}")

    json.dump(estado, open(ESTADO_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    print("---")
    for s, st in estado.items():
        print(f"{s}: {st}")


if __name__ == "__main__":
    main()
