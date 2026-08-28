#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bot de Telegram de Polymarket (Elon_polymarket_bot).

Botones (teclado fijo):
  1. 🟢 Abiertas     -> operaciones abiertas, por ventana (tweets, P&L, tiempo)
  2. 📅 Finalizadas  -> operaciones cerradas del mes en curso (con saldo)
  3. 💰 Saldo        -> saldo real de la cuenta + P&L total acumulado
  4. 🪟 Ventanas     -> todas las ventanas activas (48h, semanal, mensual)

Fuentes de datos (lectura en vivo):
  - mercado_activo.json (gamma API de Polymarket, refrescado por los bots)
  - datos_elon.csv (tweets diarios)
  - real*.json (estado REAL de los 6 bots)
  - CLOB (saldo real de la cuenta)
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
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
OFFSET_FILE = "/opt/polymarket/poly_tg_offset.txt"

ET = ZoneInfo("America/New_York")
MAD = ZoneInfo("Europe/Madrid")

sys.path.insert(0, BASE)
import posiciones_reales as PR

# Los 6 bots -> fichero de estado real
BOTS = [
    ("48h",        f"{BASE}/bot-polymarket-elon/real.json"),
    ("48h-V2",     f"{BASE}/bot-polymarket-elon-v2/real.json"),
    ("Semanal",    f"{BASE}/bot-polymarket-elon-semanal/real_semanal.json"),
    ("Semanal-V2", f"{BASE}/bot-polymarket-elon-semanal-v2/real_semanal.json"),
    ("Mensual",    f"{BASE}/bot-polymarket-elon-mensual/real_mensual.json"),
    ("Mensual-V2", f"{BASE}/bot-polymarket-elon-mensual-v2/real_mensual.json"),
]


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
    p = f"{BASE}/bot-polymarket-elon/mercado_activo.json"
    try:
        return json.load(open(p, encoding="utf-8")).get("mercados", [])
    except Exception:
        return []


def cargar_tweets():
    p = f"{BASE}/bot-polymarket-elon/datos_elon.csv"
    out = {}
    try:
        for line in open(p, encoding="utf-8"):
            line = line.strip()
            if not line or line.lower().startswith("fecha"):
                continue
            if "," not in line:
                continue
            fecha, tw = line.split(",", 1)
            try:
                out[fecha.strip()] = int(tw)
            except ValueError:
                pass
    except Exception:
        pass
    return out


def tweets_en_ventana(m, tweets):
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


def tweets_en_ventana_vivo(m):
    """Tweets ESCRITOS en la ventana: días completos (CSV) + parcial de hoy
    (estado_tweets.json), igual que el conteo del mercado (posts+reposts+quotes)."""
    completo = tweets_en_ventana(m, cargar_tweets())
    if completo is None:
        completo = 0
    try:
        ini = datetime.fromisoformat((m.get("inicio_iso") or "").replace("Z", "+00:00")).astimezone(timezone.utc)
        fin = datetime.fromisoformat((m.get("fin_iso") or "").replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return completo or None
    ahora = datetime.now(timezone.utc)
    try:
        est = json.load(open(f"{BASE}/bot-polymarket-elon/estado_tweets.json",
                             encoding="utf-8")).get("tweets", {})
    except Exception:
        est = {}
    hoy_et = datetime.now(ET).date()
    extra = 0
    for v in est.values():
        try:
            ts = datetime.strptime(v["created_at"], "%a %b %d %H:%M:%S +0000 %Y").replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if ts.astimezone(ET).date() == hoy_et and ini <= ts <= ahora:
            extra += 1
    return completo + extra


def bin_actual(bins, tw):
    """Devuelve el bin (rango) donde caen los tweets escritos, o None."""
    if tw is None or not bins:
        return None
    for b in bins:
        lo = b.get("lo", 0)
        hi = b.get("hi")
        if hi is None or hi == float("inf"):
            if tw >= lo:
                return b
        elif lo <= tw <= hi:
            return b
    return None


def refrescar_mercados():
    """Fuerza la relectura de TODAS las ventanas activas (gamma API)."""
    try:
        r = subprocess.run(
            [sys.executable, "-c",
             "import mercado_polymarket as mp; mp.actualizar_mercado()"],
            cwd=f"{BASE}/bot-polymarket-elon",
            capture_output=True, text=True, timeout=90)
        return r.returncode == 0
    except Exception as e:
        print("refrescar_mercados:", e)
        return False


def tiempo_restante(fin_iso):
    try:
        fin = datetime.fromisoformat((fin_iso or "").replace("Z", "+00:00"))
    except Exception:
        return "?"
    d = fin - datetime.now(timezone.utc)
    if d.total_seconds() <= 0:
        return "finalizada"
    dias = d.days
    horas = d.seconds // 3600
    minutos = (d.seconds % 3600) // 60
    if dias > 0:
        return f"{dias}d {horas}h"
    if horas > 0:
        return f"{horas}h {minutos}m"
    return f"{minutos}m"


def cargar_estados():
    out = []
    for nombre, path in BOTS:
        try:
            st = json.load(open(path, encoding="utf-8"))
        except Exception:
            st = {"saldo": 0.0, "historial": []}
        out.append({"nombre": nombre, "estado": st})
    return out


def mercado_por_slug(mercados, slug):
    for m in mercados:
        if m.get("slug") == slug:
            return m
    return None


def balance_apuesta(m, act):
    """PnL no realizado según el precio actual del bin en Polymarket."""
    try:
        precio = float(act.get("precio", 0) or 0)
        if precio <= 0:
            return None
        shares = float(act.get("stake", 0)) / precio
        lado = act.get("lado")
        for b in m.get("bins", []):
            if b.get("titulo") == act.get("bin_titulo"):
                cur = float(b.get("precio_yes" if lado == "YES" else "precio_no", 0) or 0)
                return shares * cur - float(act.get("stake", 0))
    except Exception:
        pass
    return None


def saldo_real():
    """Saldo real de la cuenta vía CLOB."""
    sys.path.insert(0, f"{BASE}/bot-polymarket-elon")
    try:
        import saldo_ntfy
        return saldo_ntfy.saldo_real_texto()
    except Exception as e:
        return f"(no se pudo leer: {e})"


# ---------------------------------------------------------------- comandos
def cmd_abiertas():
    """Operaciones ABIERTAS reales, leídas de Polymarket (data-api)."""
    try:
        return PR.texto_abiertas()
    except Exception as e:
        return f"⚠️ No pude leer las posiciones: {e}"


def cmd_finalizadas():
    """Operaciones finalizadas (cashPnl del data-api)."""
    try:
        return PR.texto_finalizadas()
    except Exception as e:
        return f"⚠️ No pude leer las finalizadas: {e}"


def cmd_saldo():
    """Solo saldo REAL de la cuenta + P&L acumulado."""
    try:
        return PR.texto_saldo()
    except Exception as e:
        return f"⚠️ No pude leer el saldo: {e}"


def cmd_ventanas():
    # Forzar relectura de TODAS las ventanas activas antes de mostrar
    forzado = refrescar_mercados()
    mercados = cargar_mercados()
    estados = cargar_estados()
    activas = {}
    for bot in estados:
        act = bot["estado"].get("activa")
        if act:
            activas[act.get("slug")] = bot["nombre"]
    tipo_txt = {"48h": "Diario", "semanal": "Semanal", "mensual": "Mensual"}
    lineas = ["🪟 *VENTANAS ACTIVAS*" + (" (releídas)" if forzado else ""), ""]
    hay = False
    for m in mercados:
        if m.get("cerrado"):
            continue
        hay = True
        titulo = (m.get("titulo") or m.get("slug", "?")).replace(
            "Elon Musk # tweets ", "").replace("?", "").strip()
        tipo = tipo_txt.get(m.get("tipo"), m.get("tipo", "?"))
        tw = tweets_en_ventana_vivo(m)
        resta = tiempo_restante(m.get("fin_iso"))
        apuesta = activas.get(m.get("slug"))
        linea = f"*{titulo}* · {tipo}"
        if tw is not None:
            linea += f" · *{tw} tweets escritos*"
        # margen (bin) donde caen los tweets escritos
        b = bin_actual(m.get("bins", []), tw)
        if b is not None:
            t_bin = b.get("titulo") or f"{b.get('lo')}-{b.get('hi')}"
            p_yes = b.get("precio_yes")
            linea += f"\n  📍 bin *{t_bin}*"
            if p_yes is not None:
                linea += f" · YES {p_yes:.3f}"
        linea += f"\n  ⏱ resta {resta}"
        if apuesta:
            linea += f" · 💰 apuesta en [{apuesta}]"
        else:
            linea += " · ⚪ sin apuesta"
        lineas.append(linea)
        lineas.append("")
    if not hay:
        lineas.append("⚪ No hay ventanas activas ahora.")
    return "\n".join(lineas)


# ------------------------------------------------------------------ bucle
def procesar_texto(t):
    norm = re.sub(r"[^a-záéíóúñ]", "", t.lower())
    if norm == "abiertas":
        return cmd_abiertas()
    if norm == "finalizadas":
        return cmd_finalizadas()
    if norm == "saldo":
        return cmd_saldo()
    if norm == "ventanas":
        return cmd_ventanas()
    if norm == "salud":
        return cmd_salud()
    return ("Comando no reconocido. Usa los botones de abajo:\n"
            "🟢 Abiertas · 📅 Finalizadas · 💰 Saldo · 🪟 Ventanas · 🩺 Salud")


def cmd_salud():
    """Estado de salud de Polymarket (botón 🩺 Salud), con la IP de salida."""
    import check_salud as CS
    res = CS.check()
    if res["ok"]:
        return ("🩺 *SALUD POLYMARKET: TODO OK*\n\n" +
                "\n".join(f"• {d}" for d in res["detalles"]))
    return ("🩺 *SALUD POLYMARKET: HAY FALLOS*\n\n" +
            "\n".join(f"• ❌ {f}" for f in res["fallos"]) +
            "\n\n*Detalle:*\n" +
            "\n".join(f"• {d}" for d in res["detalles"]))


def resumen_diario(slot):
    """Resumen diario UNIFICADO (10:00 y 20:00 hora de Madrid): un SOLO
    mensaje con saldo + abiertas + finalizadas (sin ráfaga de mensajes)."""
    hoy = datetime.now(MAD).strftime("%d/%m/%Y")
    icono = "☀️" if slot == "mañana" else "🌆"
    partes = [f"{icono} *RESUMEN DIARIO POLYMARKET (ELON) · {hoy}*", ""]
    for fn, nombre in ((PR.texto_saldo, "saldo"),
                       (PR.texto_abiertas, "abiertas"),
                       (PR.texto_finalizadas, "finalizadas")):
        try:
            partes.append(fn())
        except Exception as e:
            print(f"resumen {nombre}:", e)
            partes.append(f"⚠️ No pude traer *{nombre}*: {e}")
        partes.append("")
    texto = "\n".join(partes).strip()
    if len(texto) > 4000:
        texto = texto[:3900] + "\n\n… _(recortado: usa 📅 Finalizadas para el detalle)_"
    try:
        enviar(texto)
    except Exception as e:
        print("resumen enviar:", e)


def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Faltan TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID")
    offset = 0
    try:
        offset = int(open(OFFSET_FILE).read().strip())
    except Exception:
        pass
    last_m, last_t = "", ""
    print("[poly-telegram] arrancado, escuchando…")
    while True:
        # Resumen diario 10:00 y 20:00 (hora de Madrid)
        try:
            ahora = datetime.now(MAD)
            hoy = ahora.strftime("%d/%m/%Y")
            if ahora.hour == 10 and 0 <= ahora.minute < 5 and last_m != hoy:
                last_m = hoy
                resumen_diario("mañana")
            if ahora.hour == 20 and 0 <= ahora.minute < 5 and last_t != hoy:
                last_t = hoy
                resumen_diario("tarde")
        except Exception as e:
            print("resumen diario:", e)

        try:
            url = (f"https://api.telegram.org/bot{TOKEN}/getUpdates"
                   f"?offset={offset}&timeout=25&allowed_updates=%5B%22message%22%5D")
            with urllib.request.urlopen(url, timeout=35) as r:
                d = json.loads(r.read().decode())
        except Exception as e:
            print("getUpdates:", e)
            time.sleep(5)
            continue
        for upd in d.get("result", []):
            offset = max(offset, upd["update_id"] + 1)
            try:
                msg = upd.get("message") or {}
                txt = msg.get("text") or ""
                chat = (msg.get("chat") or {}).get("id")
                if str(chat) != str(CHAT_ID):
                    continue
                if txt.startswith("/start") or txt.lower().startswith("/start"):
                    tg("sendMessage", chat_id=CHAT_ID,
                       text=("👋 *Bot de Polymarket listo*\n\n"
                             "Usa los botones de abajo:\n"
                             "🟢 Abiertas · 📅 Finalizadas · 💰 Saldo · 🪟 Ventanas"),
                       reply_markup=teclado())
                else:
                    enviar(procesar_texto(txt))
            except Exception as e:
                print("update:", e)
        with open(OFFSET_FILE, "w") as f:
            f.write(str(offset))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()
