#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bot de Telegram de Polymarket Zelenskyy (Lamegawi_zelenskyy_bot).

Botones (teclado fijo), igual que el bot de Elon:
  1. 🟢 Abiertas     -> apuesta abierta del bot de Zelenskyy
  2. 📅 Finalizadas  -> historial del bot de Zelenskyy (con saldo)
  3. 💰 Saldo        -> saldo real de la cuenta + balance del bot Zelenskyy
  4. 🪟 Ventanas     -> ventanas activas de «Zelenskyy # posts» (con margen)
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
ZELEN = f"{BASE}/bot-polymarket-zelenskyy"
TOKEN = os.environ.get("ZELEN_BOT_TOKEN", "").strip() or \
        os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
OFFSET_FILE = "/opt/polymarket/zelen_tg_offset.txt"

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
        return json.load(open(f"{ZELEN}/mercado_activo.json",
                              encoding="utf-8")).get("mercados", [])
    except Exception:
        return []


def cargar_tweets():
    out = {}
    try:
        for line in open(f"{ZELEN}/datos_zelen.csv", encoding="utf-8"):
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
    try:
        d = json.load(open(f"{ZELEN}/real_zelen.json", encoding="utf-8"))
    except Exception:
        return {"saldo": 500.0, "paso": 1, "activa": None, "historial": []}
    for k, v in (("saldo", 500.0), ("paso", 1), ("activa", None),
                 ("historial", [])):
        d.setdefault(k, v)
    return d


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
        est = json.load(open(f"{ZELEN}/estado_tweets_zelen.json",
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
    try:
        r = subprocess.run(
            [sys.executable, "-c",
             "import mercado_polymarket as mp; mp.actualizar_mercado()"],
            cwd=ZELEN, capture_output=True, text=True, timeout=90)
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


def mercado_por_slug(mercados, slug):
    for m in mercados:
        if m.get("slug") == slug:
            return m
    return None


def balance_apuesta(m, act):
    """PnL no realizado según el precio actual del bin."""
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


# ---------------------------------------------------------------- comandos
def cmd_abiertas():
    est = cargar_estado()
    act = est.get("activa")
    if not act:
        return "⚪ El bot de Zelenskyy no tiene ninguna apuesta abierta ahora."
    lineas = ["🟢 *APUESTA ABIERTA (Zelenskyy)*", ""]
    q = (act.get("mercado") or act.get("slug") or "?").replace(
        "Zelenskyy # posts ", "").replace("?", "").strip()
    lineas.append(f"*{q}*")
    lado = act.get("lado", "YES")
    bin_t = act.get("bin_titulo", "?")
    lineas.append(f"  · {bin_t} {lado} @ {act.get('precio', 0):.4f}")
    lineas.append(f"  · stake ${act.get('stake', 0):.2f} · paso {act.get('paso', 1)}")
    if act.get("p_modelo"):
        lineas.append(f"  · p_modelo {float(act['p_modelo'])*100:.0f}%")
    # valor actual desde el mercado
    m = mercado_por_slug(cargar_mercados(), act.get("slug"))
    if m:
        pnl = balance_apuesta(m, act)
        if pnl is not None:
            ic = "🟢" if pnl >= 0 else "🔴"
            lineas.append(f"  {ic} ahora ${pnl:+.2f}")
        resta = tiempo_restante(m.get("fin_iso"))
        lineas.append(f"  ⏱ resta {resta}")
    return "\n".join(lineas)


def cmd_finalizadas():
    est = cargar_estado()
    hist = est.get("historial") or []
    if not hist:
        return "📅 *Finalizadas (Zelenskyy)*\n\n⚪ Todavía no hay operaciones cerradas."
    lineas = ["📅 *FINALIZADAS (Zelenskyy)*", ""]
    total = 0.0
    for r in hist:
        res = r.get("resultado")
        pnl = float(r.get("beneficio", 0) or 0)
        total += pnl
        ic = "✅" if res == "G" else "❌"
        bin_t = r.get("bin", "?")
        lado = r.get("lado", "")
        fecha = r.get("fecha", "?")
        lineas.append(f"{ic} {bin_t} {lado} · ${pnl:+.2f} · {fecha}")
    lineas.append("")
    ic = "🟢" if total >= 0 else "🔴"
    lineas.append(f"*Total: {ic} ${total:+.2f}*")
    return "\n".join(lineas)


def cmd_saldo():
    # saldo real (misma cuenta) + balance del bot Zelenskyy
    try:
        import saldo_ntfy
        saldo_txt = saldo_ntfy.saldo_real_texto() or "Saldo real: ?"
    except Exception as e:
        saldo_txt = f"Saldo real: ? ({e})"
    est = cargar_estado()
    pnl_hist = round(sum(float(r.get("beneficio", 0) or 0)
                         for r in est.get("historial") or []), 2)
    lineas = ["💰 *SALDO (Zelenskyy)*", ""]
    lineas.append(saldo_txt)
    lineas.append("")
    lineas.append("*Bot de Zelenskyy:*")
    lineas.append(f"  · Paso del ciclo: {est.get('paso', 1)}")
    lineas.append(f"  · P&L cerradas: ${pnl_hist:+.2f}")
    return "\n".join(lineas)


def cmd_ventanas():
    forzado = refrescar_mercados()
    mercados = cargar_mercados()
    est = cargar_estado()
    act = est.get("activa")
    lineas = ["🪟 *VENTANAS ZELENSKYY*" + (" (releídas)" if forzado else ""), ""]
    hay = False
    for m in mercados:
        if m.get("cerrado"):
            continue
        hay = True
        titulo = (m.get("titulo") or m.get("slug", "?")).replace(
            "Zelenskyy # posts ", "").replace("?", "").strip()
        tw = tweets_en_ventana_vivo(m)
        resta = tiempo_restante(m.get("fin_iso"))
        linea = f"*{titulo}*"
        if tw is not None:
            linea += f" · *{tw} posts escritos*"
        b = bin_actual(m.get("bins", []), tw)
        if b is not None:
            t_bin = b.get("titulo") or f"{b.get('lo')}-{b.get('hi')}"
            p_yes = b.get("precio_yes")
            linea += f"\n  📍 bin *{t_bin}*"
            if p_yes is not None:
                linea += f" · YES {p_yes:.3f}"
        linea += f"\n  ⏱ resta {resta}"
        if act and act.get("slug") == m.get("slug"):
            linea += " · 💰 apuesta aquí"
        else:
            linea += " · ⚪ sin apuesta"
        lineas.append(linea)
        lineas.append("")
    if not hay:
        lineas.append("⚪ No hay ventanas activas ahora.")
    return "\n".join(lineas)


def cmd_salud():
    import check_salud as CS
    res = CS.check(servicios=CS.SERVICIOS_ZELEN)
    if res["ok"]:
        return ("🩺 *SALUD ZELENSKYY: TODO OK*\n\n" +
                "\n".join(f"• {d}" for d in res["detalles"]))
    return ("🩺 *SALUD ZELENSKYY: HAY FALLOS*\n\n" +
            "\n".join(f"• ❌ {f}" for f in res["fallos"]) +
            "\n\n*Detalle:*\n" + "\n".join(f"• {d}" for d in res["detalles"]))


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


def resumen_diario(slot):
    """Resumen diario UNIFICADO (10:00 y 20:00 hora de Madrid): un SOLO
    mensaje con saldo + abiertas + ventanas + finalizadas."""
    hoy = datetime.now(MAD).strftime("%d/%m/%Y")
    icono = "☀️" if slot == "mañana" else "🌆"
    partes = [f"{icono} *RESUMEN DIARIO ZELENSKYY · {hoy}*", ""]
    for fn, nombre in ((cmd_saldo, "saldo"), (cmd_abiertas, "abiertas"),
                       (cmd_ventanas, "ventanas"),
                       (cmd_finalizadas, "finalizadas")):
        try:
            partes.append(fn())
        except Exception as e:
            print(f"resumen {nombre}:", e)
            partes.append(f"⚠️ No pude traer *{nombre}*: {e}")
        partes.append("")
    texto = "\n".join(partes).strip()
    if len(texto) > 4000:
        texto = texto[:3900] + "\n\n… _(recortado: usa los botones para el detalle)_"
    try:
        enviar(texto)
    except Exception as e:
        print("resumen enviar:", e)


def main():
    if not TOKEN or not CHAT_ID:
        raise SystemExit("Faltan ZELEN_BOT_TOKEN / TELEGRAM_CHAT_ID")
    offset = 0
    try:
        offset = int(open(OFFSET_FILE).read().strip())
    except Exception:
        pass
    last_m, last_t = "", ""
    print("[poly-telegram-zelen] arrancado, escuchando…")
    while True:
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
                if txt.startswith("/start"):
                    tg("sendMessage", chat_id=CHAT_ID,
                       text=("👋 *Bot de Polymarket Zelenskyy listo*\n\n"
                             "Usa los botones de abajo:\n"
                             "🟢 Abiertas · 📅 Finalizadas · 💰 Saldo · "
                             "🪟 Ventanas · 🩺 Salud"),
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
