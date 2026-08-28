#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gestor de cierre anticipado de posiciones de Elon en Polymarket.

Cada N minutos:
  1. Lee las posiciones ABIERTAS de Elon del data-api.
  2. Para cada una, proyecta los tweets al final de la ventana usando el
     ritmo real de publicación (datos_elon.csv).
  3. Si la proyección queda FUERA del margen apostado (bin), vende la
     posición: en positivo si el precio actual lo permite, o con la
     mínima pérdida (mejor salir que esperar a 0).

Reglas de seguridad:
  - No se vende en las últimas 2 horas de la ventana (se deja resolver).
  - Margen de tolerancia: no se cierra si la proyección roza el borde.
  - Solo gestiona posiciones de Elon Musk (las demás no se tocan).

Uso:
  python3 gestionar_posiciones.py --dry      # simula (no vende)
  python3 gestionar_posiciones.py --loop N   # bucle cada N minutos
"""
import json
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
FUNDER = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
TELEGRAM_BOT_TOKEN = __import__("os").environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = __import__("os").environ.get("TELEGRAM_CHAT_ID", "").strip()

MARGEN_TWEETS = 2          # tolerancia en tweets para no cerrar por los pelos
MIN_HORAS_RESTANTES = 2    # no cerrar si quedan menos de 2 h (dejar resolver)
LOOP_MIN = 5


def _curl(url):
    r = subprocess.run(["curl", "-s", "--max-time", "40", url],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


def tg_send(texto):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": TELEGRAM_CHAT_ID,
                                       "text": texto}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception:
        return False


def get_client():
    sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
    import operar_real as op
    return op.get_client()


def cargar_tweets():
    tweets = {}
    try:
        for line in open("/opt/polymarket/bot-polymarket-elon/datos_elon.csv",
                         encoding="utf-8"):
            line = line.strip()
            if not line or line.lower().startswith("fecha") or "," not in line:
                continue
            f, tw = line.split(",", 1)
            try:
                tweets[f.strip()] = int(tw)
            except ValueError:
                pass
    except Exception:
        pass
    return tweets


def cargar_ventanas():
    """{eventSlug: (inicio_iso, fin_iso)} de mercado_activo.json."""
    out = {}
    try:
        mercados = json.load(open(
            "/opt/polymarket/bot-polymarket-elon/mercado_activo.json",
            encoding="utf-8")).get("mercados", [])
        for m in mercados:
            slug = m.get("slug", "")
            if slug and m.get("inicio_iso") and m.get("fin_iso"):
                out[slug] = (m["inicio_iso"], m["fin_iso"])
    except Exception:
        pass
    return out


def parse_bin(question):
    """Extrae [lo, hi] de 'Will Elon Musk post 140-159 tweets from ...'."""
    m = re.search(r"post\s+<?(\d+)-(\d+)\s+tweets", question or "")
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"post\s+<(\d+)\s+tweets", question or "")
    if m:
        return 0, int(m.group(1)) - 1
    return None


def proyectar(event_slug, tweets_csv, ventanas):
    """Devuelve dict con proyección o None si no hay datos suficientes.

    Usa días COMPLETOS (hasta ayer) para el ritmo, para no sobrestimar
    el día de hoy (que aún no ha terminado)."""
    if event_slug not in ventanas:
        return None
    inicio_iso, fin_iso = ventanas[event_slug]
    try:
        ini_dt = datetime.fromisoformat(inicio_iso.replace("Z", "+00:00"))
        fin_dt = datetime.fromisoformat(fin_iso.replace("Z", "+00:00"))
    except Exception:
        return None
    if ini_dt.tzinfo is None:
        ini_dt = ini_dt.replace(tzinfo=timezone.utc)
    if fin_dt.tzinfo is None:
        fin_dt = fin_dt.replace(tzinfo=timezone.utc)
    ahora = datetime.now(timezone.utc)
    dias_totales = max((fin_dt - ini_dt).total_seconds() / 86400, 0.05)
    # días completos transcurridos (hasta ayer)
    hoy = datetime.now(ET).date()
    ini_date = ini_dt.astimezone(ET).date()
    dias_completos = (hoy - ini_date).days
    if dias_completos < 1:
        return None
    # tweets en días completos (excluye hoy)
    tweets_comp = 0
    for fecha, tw in tweets_csv.items():
        try:
            d = datetime.strptime(fecha, "%Y-%m-%d").date()
        except Exception:
            continue
        if ini_date <= d < hoy:
            tweets_comp += tw
    ritmo = tweets_comp / dias_completos
    proyeccion = ritmo * dias_totales
    horas_rest = (fin_dt - ahora).total_seconds() / 3600
    return {
        "tweets_comp": tweets_comp,
        "dias_completos": dias_completos,
        "dias_totales": dias_totales,
        "ritmo": ritmo,
        "proyeccion": proyeccion,
        "horas_rest": horas_rest,
        "fin": fin_dt,
    }


def posiciones_elon():
    pos = _curl(f"https://data-api.polymarket.com/positions?user={FUNDER}") or []
    out = []
    for p in pos:
        try:
            cur = float(p.get("currentValue", 0) or 0)
        except Exception:
            continue
        if cur <= 0.001:
            continue
        title = (p.get("title") or "").lower()
        if "elon musk" not in title:
            continue
        out.append(p)
    return out


def vender(token_id, shares, cur_price, dry):
    """Vende shares a mercado. Devuelve (ok, detalle)."""
    if dry:
        return True, f"(seco) vendería {shares} shares @ ~{cur_price}"
    client = get_client()
    from py_clob_client_v2.clob_types import MarketOrderArgsV2
    try:
        resp = client.create_and_post_market_order(
            MarketOrderArgsV2(token_id=token_id, amount=shares, side="SELL",
                              order_type="FOK"))
        oid = resp.get("orderID") or resp.get("order_id") or str(resp)[:80]
        return True, f"vendidas {shares} shares (order {oid})"
    except Exception as e:
        # fallback: orden límite al precio actual
        try:
            from py_clob_client_v2.clob_types import OrderArgs
            resp = client.create_and_post_order(
                OrderArgs(token_id=token_id, price=round(cur_price, 4),
                          size=shares, side="SELL"))
            oid = resp.get("orderID") or resp.get("order_id") or str(resp)[:80]
            return True, f"orden límite SELL {shares} @ {cur_price} (order {oid})"
        except Exception as e2:
            return False, f"no se pudo vender: {e} / {e2}"


def evaluar(p, tweets_csv, ventanas, dry):
    """Evalúa una posición y devuelve (accion, texto). accion en
    {'vender', 'mantener', 'sin_datos', 'ultimas_horas'}."""
    bin_ = parse_bin(p.get("title"))
    if bin_ is None:
        return "mantener", "sin bin parseable"
    lo, hi = bin_
    event_slug = p.get("eventSlug", "")
    proy = proyectar(event_slug, tweets_csv, ventanas)
    if proy is None:
        return "mantener", "sin datos de ventana"
    proj = proy["proyeccion"]
    horas = proy["horas_rest"]
    if horas <= MIN_HORAS_RESTANTES:
        return "ultimas_horas", f"quedan {horas:.1f}h (dejar resolver)"

    fuera_arriba = proj > hi + MARGEN_TWEETS
    fuera_abajo = proj < lo - MARGEN_TWEETS
    if not (fuera_arriba or fuera_abajo):
        return "mantener", (f"proyección {proj:.1f} dentro de [{lo},{hi}]")

    # hay que cerrar
    side = p.get("outcome", "Yes")
    if side == "No":
        # para NO, gana si NO cae en el bin: fuera es BUENO, dentro es MALO
        return "mantener", "posición NO (no se gestiona)"
    cur = float(p.get("curPrice", 0) or 0)
    avg = float(p.get("avgPrice", 0) or 0)
    pnl_pct = (cur / avg - 1) * 100 if avg > 0 else 0
    shares = float(p.get("size", 0) or 0)
    token_id = p.get("asset", "")
    razon = (f"se pasa por arriba ({proj:.0f}>{hi})" if fuera_arriba
             else f"no llega al mínimo ({proj:.0f}<{lo})")
    if not token_id or shares <= 0:
        return "mantener", f"sin token/tamaño (token={bool(token_id)})"
    ok, detalle = vender(token_id, shares, cur, dry)
    init_val = float(p.get("initialValue", 0) or 0)
    cur_val = float(p.get("currentValue", 0) or 0)
    pnl = cur_val - init_val
    ic_bal = "🟢" if pnl >= 0 else "🔴"
    txt = (f"{'🧪 SECO' if dry else '🔻 CIERRE ANTICIPADO'} {p.get('title')}\n"
           f"   bin [{lo}-{hi}] · proyección {proj:.0f} → {razon}\n"
           f"   {shares:.1f} shares · entrada {avg:.4f} · ahora {cur:.4f} "
           f"({pnl_pct:+.0f}%)\n"
           f"   💰 Balance de la operación: {ic_bal} ${pnl:+.2f} "
           f"(invertido ${init_val:.2f} → ahora ${cur_val:.2f})\n"
           f"   → {detalle}")
    if ok and not dry:
        _guardar_cierre({
            "fecha": datetime.now(ET).strftime("%Y-%m-%d"),
            "titulo": (p.get("title") or "?").replace("Elon Musk # tweets ", "").replace("?", ""),
            "bin": f"{lo}-{hi}",
            "lado": p.get("outcome", "Yes"),
            "invertido": round(init_val, 2),
            "valor": round(cur_val, 2),
            "pnl": round(pnl, 2),
        })
    if ok:
        tg_send(txt)
    return ("vender" if ok else "fallo"), txt


def _guardar_cierre(registro):
    """Añade un cierre anticipado al registro mensual."""
    try:
        path = "/opt/polymarket/cierres_anticipados.json"
        try:
            d = json.load(open(path, encoding="utf-8"))
        except Exception:
            d = {"cierres": []}
        d.setdefault("cierres", []).append(registro)
        json.dump(d, open(path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  [aviso] no se pudo registrar el cierre: {e}")


def main():
    dry = "--dry" in sys.argv
    loop = "--loop" in sys.argv
    intervalo = LOOP_MIN
    if loop:
        for i, a in enumerate(sys.argv):
            if a == "--loop" and i + 1 < len(sys.argv):
                try:
                    intervalo = int(sys.argv[i + 1])
                except Exception:
                    pass
    tweets_csv = cargar_tweets()
    ventanas = cargar_ventanas()

    while True:
        print(f"[{datetime.now(ET).strftime('%H:%M %Z')}] gestor pasada"
              f"{' (SECO)' if dry else ''}")
        try:
            for p in posiciones_elon():
                accion, texto = evaluar(p, tweets_csv, ventanas, dry)
                print(f"  · {p.get('title')[:60]} -> {accion}: {texto[:100]}")
        except Exception as e:
            print(f"  ERROR: {e}")
        if not loop:
            break
        print(f"  próxima pasada en {intervalo} min")
        time.sleep(intervalo * 60)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass
    main()
