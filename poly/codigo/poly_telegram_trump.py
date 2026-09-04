#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Bot de Telegram de Polymarket Trump (Lamegawi_trump_bot).

Botones (teclado fijo), igual que el bot de Zelenskyy:
  1. 🟢 Abiertas     -> apuesta abierta del bot de Trump
  2. 📅 Finalizadas  -> historial del bot de Trump (con saldo)
  3. 💰 Saldo        -> saldo real de la cuenta + balance del bot Trump
  4. 🪟 Ventanas     -> ventanas activas de «Trump Truth Social posts» (con margen)
  5. 🩺 Salud        -> estado de los servicios de Polymarket + IP de salida
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BASE = "/opt/polymarket"
TRUMP = f"{BASE}/bot-polymarket-trump"
TOKEN = os.environ.get("TRUMP_BOT_TOKEN", "").strip() or \
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
OFFSET_FILE = "/opt/polymarket/trump_tg_offset.txt"

ET = ZoneInfo("America/New_York")
MAD = ZoneInfo("Europe/Madrid")

sys.path.insert(0, BASE)
sys.path.insert(0, f"{BASE}/bot-polymarket-elon")  # para saldo_ntfy


# ---------------------------------------------------------------- telegram
def tg(method, **params):
    url = f"https://api.telegram.org/bot{TOKEN}/{method}"
    data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def enviar(texto):
    return tg("sendMessage", chat_id=CHAT_ID, text=texto,
              disable_web_page_preview=True)


def teclado():
    return json.dumps({
        "keyboard": [
            ["🟢 Abiertas", "📅 Finalizadas"],
            ["💰 Saldo", "🪟 Ventanas"],
            ["🩺 Salud"],
        ],
        "resize_keyboard": True,
    })


# ------------------------------------------------------------------ datos
def cargar_mercados():
    try:
        return json.load(open(f"{TRUMP}/mercado_activo.json",
                              encoding="utf-8")).get("mercados", [])
    except Exception:
        return []


def cargar_tweets():
    """Carga los datos de Truth Social del bot de Trump."""
    out = {}
    try:
        for line in open(f"{TRUMP}/datos_trump.csv", encoding="utf-8"):
            line = line.strip()
            if not line or line.lower().startswith("fecha") or "," not in line:
                continue
            fecha, tw = line.split(",", 1)
            try:
                out[fecha.strip()] = int(tw)
            except ValueError:
                pass
    except Exception:
        pass
    return out


def cargar_estado():
    """Carga el estado real del bot de Trump."""
    try:
        d = json.load(open(f"{TRUMP}/real_trump.json", encoding="utf-8"))
    except Exception:
        return {"saldo": 500.0, "paso": 1, "activa": None, "historial": []}
    for k, v in (("saldo", 500.0), ("paso", 1), ("activa", None),
                 ("historial", [])):
        d.setdefault(k, v)
    return d


def tweets_en_ventana(m, tweets):
    """Suma los tweets en la ventana de un mercado.
    Usa los campos inicio_iso/fin_iso (como hace el bot de Zelenskyy)."""
    try:
        ini = datetime.fromisoformat((m.get("inicio_iso") or "").replace("Z", "+00:00")).date()
        fin = datetime.fromisoformat((m.get("fin_iso") or "").replace("Z", "+00:00")).date()
    except Exception:
        return None
    hoy = datetime.now(ET).date()
    tope = min(fin, hoy + timedelta(days=1))
    total = 0
    for fecha, tw in tweets.items():
        try:
            d = datetime.strptime(fecha, "%Y-%m-%d").date()
        except Exception:
            continue
        if ini <= d < tope:
            total += tw
    return total


# ---------------------------------------------------------------- format
def fmt_ventana(m):
    fi = m.get("inicio_iso", "")[:10]
    ff = m.get("fin_iso", "")[:10]
    return f"{fi} → {ff}"


def fmt_activa(estado, tweets, mercados):
    a = estado.get("activa")
    if not a:
        return "  (ninguna operación activa)"
    slug = a.get("slug", "?")
    bin_titulo = a.get("bin_titulo", "?")
    lado = a.get("lado", "?")
    precio = a.get("precio", 0)
    stake = a.get("stake", 0)
    ventana_fin = a.get("ventana_fin", "")
    # Buscar el mercado
    m = next((mm for mm in mercados if mm.get("slug") == slug), None)
    tweets_tot = tweets_en_ventana(m, tweets) if m else None
    rango = f"  ({fmt_ventana(m)})" if m else ""
    linea = (
        f"  {slug[:50]}\n"
        f"  bin: {bin_titulo} ({lado}) | stake: ${stake:.2f} @ ${precio:.3f}\n"
    )
    if tweets_tot is not None:
        linea += f"  tweets hasta ahora: {tweets_tot}{rango}\n"
    if ventana_fin:
        linea += f"  cierre: {ventana_fin}\n"
    return linea


def fmt_historial(estado):
    h = estado.get("historial", [])
    if not h:
        return "  (sin operaciones cerradas todavía)"
    out = []
    # Ordenar por fecha desc
    for op in sorted(h, key=lambda x: x.get("fecha", ""), reverse=True)[:15]:
        fecha = op.get("fecha", "?")
        mercado = op.get("mercado", "?")[:50]
        bin_t = op.get("bin", "?")
        stake = op.get("stake", 0)
        resultado = op.get("resultado", "?")
        beneficio = op.get("beneficio", 0)
        real = op.get("real", "")
        icono = "✅" if resultado == "G" else "❌" if resultado == "P" else "❔"
        out.append(
            f"  {icono} {fecha} | {mercado}\n"
            f"     bin: {bin_t} | stake: ${stake:.2f} | PnL: ${beneficio:+.2f}\n"
            f"     {real}"
        )
    return "\n".join(out)


def fmt_saldo(estado):
    """Muestra el saldo REAL de Polymarket (no el virtual del bot)."""
    try:
        import saldo_ntfy
        real_txt = saldo_ntfy.saldo_real_texto()
    except Exception:
        real_txt = "(no se pudo leer)"
    return f"  {real_txt}"


def fmt_ventanas(mercados, tweets):
    if not mercados:
        return "  (no hay mercados activos)"
    out = []
    for m in mercados[:10]:
        slug = m.get("slug", "?")
        bins = m.get("bins", [])
        tweets_tot = tweets_en_ventana(m, tweets)
        out.append(
            f"  • {slug[:50]}\n"
            f"    {fmt_ventana(m)} | tweets: {tweets_tot}\n"
            f"    bins: {len(bins)}"
        )
    return "\n".join(out)


def fmt_salud():
    """Estado de los servicios + IP de salida."""
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "poly-trump.service"],
            capture_output=True, text=True, timeout=5)
        trump = r.stdout.strip()
    except Exception:
        trump = "?"
    try:
        r = subprocess.run(
            ["systemctl", "is-active", "poly-telegram-trump.service"],
            capture_output=True, text=True, timeout=5)
        tg = r.stdout.strip()
    except Exception:
        tg = "?"
    try:
        r = subprocess.run(
            ["curl", "-s", "--max-time", "5", "https://api.ipify.org"],
            capture_output=True, text=True, timeout=8)
        ip = r.stdout.strip() or "?"
    except Exception:
        ip = "?"
    return (
        f"  poly-trump:        {trump}\n"
        f"  poly-telegram-trump: {tg}\n"
        f"  IP salida: {ip}"
    )


# ---------------------------------------------------------------- handlers
def handle(text):
    mercados = cargar_mercados()
    tweets = cargar_tweets()
    estado = cargar_estado()

    if text == "🟢 Abiertas":
        return (
            "🟢 *OPERACIÓN ACTIVA*\n\n"
            f"{fmt_activa(estado, tweets, mercados)}"
        )

    elif text == "📅 Finalizadas":
        return (
            "📅 *FINALIZADAS*\n\n"
            f"{fmt_historial(estado)}"
        )

    elif text == "💰 Saldo":
        return (
            "💰 *SALDO*\n\n"
            f"{fmt_saldo(estado)}"
        )

    elif text == "🪟 Ventanas":
        return (
            "🪟 *VENTANAS ACTIVAS*\n\n"
            f"{fmt_ventanas(mercados, tweets)}"
        )

    elif text == "🩺 Salud":
        return (
            "🩺 *SALUD*\n\n"
            f"{fmt_salud()}"
        )

    return None


# ----------------------------------------------------------------- main loop
def main():
    if not TOKEN or not CHAT_ID:
        print(f"Falta TELEGRAM_BOT_TOKEN ({'OK' if TOKEN else 'NO'}) "
              f"o TELEGRAM_CHAT_ID ({'OK' if CHAT_ID else 'NO'})")
        sys.exit(1)
    print(f"Trump Telegram bot iniciando (chat_id={CHAT_ID})")
    offset = 0
    if os.path.exists(OFFSET_FILE):
        try:
            offset = int(open(OFFSET_FILE).read().strip() or 0)
        except Exception:
            offset = 0
    while True:
        try:
            updates = tg("getUpdates", offset=offset, timeout=25, allowed_updates='["message"]')
            n = len(updates.get("result", []))
            if n > 0:
                print(f"[{datetime.now().isoformat()}] {n} updates recibidos")
            for u in updates.get("result", []):
                offset = u["update_id"] + 1
                open(OFFSET_FILE, "w").write(str(offset))
                msg = u.get("message") or {}
                chat = msg.get("chat", {})
                if str(chat.get("id")) != str(CHAT_ID):
                    continue
                text = (msg.get("text") or "").strip()
                if not text:
                    continue
                print(f"[{datetime.now().isoformat()}] mensaje: {text[:50]}")
                # Si es /start o primer mensaje, enviar teclado
                if text in ("/start", "/help"):
                    enviar(
                        "🤖 *Bot Trump Polymarket*\n\n"
                        "Pulsa un botón:"
                    )
                    tg("sendMessage", chat_id=CHAT_ID,
                       text="(teclado abajo)", reply_markup=teclado())
                    continue
                resp = handle(text)
                if resp:
                    enviar(resp)
                else:
                    enviar(
                        "🤖 Bot Trump. Pulsa un botón:\n\n"
                        "🟢 Abiertas | 📅 Finalizadas\n"
                        "💰 Saldo | 🪟 Ventanas\n"
                        "🩺 Salud"
                    )
        except KeyboardInterrupt:
            print("Saliendo...")
            break
        except Exception as e:
            print(f"Error en main loop: {type(e).__name__}: {e}")
            time.sleep(5)


if __name__ == "__main__":
    main()
