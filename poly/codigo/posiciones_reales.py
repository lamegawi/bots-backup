#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Lista las posiciones ABIERTAS reales (data-api) mapeadas con CLOB get_market.

Usado por el bot de Telegram (botón "Abiertas") y como utilidad de diagnóstico.
"""
import json
import subprocess
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
MAD = ZoneInfo("Europe/Madrid")   # hora local del usuario (España)

FUNDER = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"

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

_client = None

def _get_client():
    global _client
    if _client is None:
        sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
        import operar_real as op
        _client = op.get_client()
    return _client


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


def _datos_tweets():
    """Devuelve (ventanas: {event_slug: (inicio_iso, fin_iso)}, tweets: {fecha: n})."""
    ventanas = {}
    try:
        mercados = json.load(
            open("/opt/polymarket/bot-polymarket-elon/mercado_activo.json",
                 encoding="utf-8")).get("mercados", [])
        for m in mercados:
            slug = m.get("slug", "")
            if slug and m.get("inicio_iso") and m.get("fin_iso"):
                ventanas[slug] = (m["inicio_iso"], m["fin_iso"])
    except Exception:
        pass
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
    return ventanas, tweets


def _tweets_ventana(inicio_iso, fin_iso, tweets):
    """Tweets dentro de la ventana [inicio, fin) hasta hoy (hora ET)."""
    from datetime import timedelta as _td
    try:
        ini = datetime.fromisoformat((inicio_iso or "").replace("Z", "+00:00")).date()
        fin = datetime.fromisoformat((fin_iso or "").replace("Z", "+00:00")).date()
    except Exception:
        return None
    hoy = datetime.now(ET).date()
    tope = min(fin, hoy + _td(days=1))
    total = 0
    for fecha, tw in tweets.items():
        try:
            d = datetime.strptime(fecha, "%Y-%m-%d").date()
        except Exception:
            continue
        if ini <= d < tope:
            total += tw
    return total


def posiciones_abiertas():
    """Devuelve lista de dicts con las posiciones abiertas (valor actual > 0)."""
    pos = _curl(f"https://data-api.polymarket.com/positions?user={FUNDER}") or []
    abiertas = [p for p in pos
                if float(p.get("size", 0) or 0) > 0
                and float(p.get("currentValue", 0) or 0) > 0.001]
    ventanas, tweets_csv = _datos_tweets()
    out = []
    client = None
    for p in abiertas:
        asset = str(p.get("asset"))
        size = float(p.get("size", 0) or 0)
        avg = float(p.get("avgPrice", 0) or 0)
        cur_val = float(p.get("currentValue", 0) or 0)
        init_val = float(p.get("initialValue", 0) or 0)
        pnl = cur_val - init_val
        event_slug = p.get("eventSlug", "") or ""
        info = {"question": (p.get("conditionId") or "")[:12], "bin": "?",
                "lado": "?", "end": "", "slug": ""}
        cid = p.get("conditionId")
        if cid:
            try:
                if client is None:
                    client = _get_client()
                m = client.get_market(cid)
                if m:
                    tokens = m.get("tokens") or []
                    lado = "?"
                    for t in tokens:
                        if str(t.get("token_id")) == asset:
                            lado = "Yes" if t.get("outcome") == "Yes" else "No"
                            break
                    info = {
                        "question": m.get("question") or cid[:12],
                        "bin": m.get("groupItemTitle") or "",
                        "lado": lado,
                        "end": m.get("end_date_iso") or "",
                        "slug": m.get("market_slug") or "",
                    }
            except Exception:
                pass
        # tweets en la ventana (solo si es un mercado de Elon registrado)
        tw = None
        if event_slug in ventanas:
            ini, fin = ventanas[event_slug]
            tw = _tweets_ventana(ini, fin, tweets_csv)
        out.append({
            "question": info["question"],
            "title": p.get("title") or "",
            "bin": info["bin"],
            "lado": info["lado"],
            "size": size,
            "avg": avg,
            "cur_val": cur_val,
            "init_val": init_val,
            "pnl": pnl,
            "end": info["end"],
            "slug": info["slug"],
            "tweets": tw,
        })
    # ordenar por tiempo restante: el que antes acaba, primero (sin fecha al final)
    out.sort(key=lambda x: x["end"] or "9999-12-31")
    return out


def texto_abiertas():
    """Texto del botón 'Abiertas' (solo posiciones de Elon Musk).

    Se ocultan el resto de posiciones de la cuenta (Zelenskyy va en su propio
    bot; Zema, Balance of Power y otras posiciones personales no se muestran).
    """
    ops = posiciones_abiertas()
    ops = [o for o in ops
           if "elon musk" in (o.get("title") or "").lower()
           or "elon musk" in (o["question"] or "").lower()]
    if not ops:
        return "⚪ No hay operaciones abiertas ahora."
    lineas = ["🟢 *OPERACIONES ABIERTAS*", ""]
    for o in ops:
        q = o["question"].replace("Elon Musk # tweets ", "").replace("?", "")
        bin_lado = ""
        if o["bin"]:
            bin_lado = f"{o['bin']} {o['lado']}"
        elif o["lado"] and o["lado"] != "?":
            bin_lado = o["lado"]
        linea = f"*{q}*"
        if bin_lado:
            linea += f" · {bin_lado}"
        if o["tweets"] is not None:
            linea += f" · {o['tweets']} tweets"
        linea += f"\n  · {o['size']:.1f} shares @ {o['avg']:.4f}"
        linea += f"\n  · invertido ${o['init_val']:.2f} → ahora ${o['cur_val']:.2f}"
        if o["pnl"] >= 0:
            linea += f" · 🟢 +${o['pnl']:.2f}"
        else:
            linea += f" · 🔴 ${o['pnl']:.2f}"
        if o["end"]:
            linea += f"\n  · ⏱ resta {tiempo_restante(o['end'])}"
        lineas.append(linea)
        lineas.append("")
    tot_inv = sum(o["init_val"] for o in ops)
    tot_val = sum(o["cur_val"] for o in ops)
    tot_pnl = tot_val - tot_inv
    lineas.append(f"💰 Total: invertido ${tot_inv:.2f} · valor ${tot_val:.2f} "
                  f"· {'🟢 ' if tot_pnl >= 0 else '🔴 '}${tot_pnl:+.2f}")
    return "\n".join(lineas)


def datos_pnl():
    """Devuelve {valor_abiertas, pnl_bot_abiertas, pnl_bot, n_abiertas}.

    'bot' = operaciones del bot de Elon (título contiene 'Elon Musk').
    Las demás (Balance of Power, Zema, fútbol...) se excluyen del balance."""
    pos = _curl(f"https://data-api.polymarket.com/positions?user={FUNDER}") or []
    valor_abiertas = 0.0
    pnl_bot_abiertas = 0.0
    n_abiertas = 0
    for p in pos:
        try:
            cur = float(p.get("currentValue", 0) or 0)
            init = float(p.get("initialValue", 0) or 0)
            title = p.get("title", "") or ""
        except Exception:
            continue
        if cur > 0.001:
            valor_abiertas += cur
            n_abiertas += 1
            if "elon musk" in title.lower():
                pnl_bot_abiertas += (cur - init)
    # cerradas en positivo previas al arranque del bot (guardadas)
    pnl_previas = 0.0
    try:
        bb = json.load(open("/opt/polymarket/balance_bot.json", encoding="utf-8"))
        pnl_previas = float(bb.get("pnl_cerradas_previas", 0) or 0)
    except Exception:
        pass
    return {
        "valor_abiertas": valor_abiertas,
        "pnl_bot_abiertas": pnl_bot_abiertas,
        "pnl_bot": pnl_bot_abiertas + pnl_previas,
        "pnl_previas": pnl_previas,
        "n_abiertas": n_abiertas,
    }


def texto_saldo():
    """Texto del botón 'Saldo': solo saldo REAL + balance del bot."""
    sys.path.insert(0, "/opt/polymarket/bot-polymarket-elon")
    import saldo_ntfy
    saldo_txt = saldo_ntfy.saldo_real_texto() or "Saldo real: ?"
    d = datos_pnl()
    total_cuenta = None
    try:
        import re as _re
        m = _re.search(r"\$([0-9,.]+)", saldo_txt)
        if m:
            cash = float(m.group(1).replace(",", ""))
            total_cuenta = cash + d["valor_abiertas"]
    except Exception:
        pass
    lineas = ["💰 *SALDO CUENTA*", ""]
    lineas.append(saldo_txt)
    if total_cuenta is not None:
        lineas.append(f"Total cuenta (efectivo + posiciones): *${total_cuenta:,.2f}*")
    lineas.append("")
    ic = "🟢" if d["pnl_bot"] >= 0 else "🔴"
    lineas.append("*Balance del bot (Elon)* desde que arrancó:")
    lineas.append(f"  · Abiertas ahora: {'🟢' if d['pnl_bot_abiertas']>=0 else '🔴'} "
                  f"${d['pnl_bot_abiertas']:+.2f}")
    if d["pnl_previas"]:
        lineas.append(f"  · Cerradas en positivo: ${d['pnl_previas']:+.2f}")
    lineas.append(f"  {ic} *TOTAL: ${d['pnl_bot']:+.2f}*")
    return "\n".join(lineas)


# Corte: contar solo desde el cierre positivo del 15-17/08 (17/08/2026).
FECHA_INICIO = datetime(2026, 8, 17).date()


def texto_finalizadas():
    """Texto del botón 'Finalizadas': operaciones cerradas del MES EN CURSO.

    - 🔻 Cierres anticipados (hechos por el gestor) con su balance y total.
    - 🏁 Resueltas por Polymarket (data-api), con fecha de resolución.
    - Saldo del mes (anticipadas + resueltas), se pone a 0 cada mes nuevo.
    - Marca con ⭐ la última operación ganada.
    """
    pos = _curl(f"https://data-api.polymarket.com/positions?user={FUNDER}") or []
    hoy = datetime.now(MAD).date()   # mes en curso según la hora del usuario
    mes_txt = hoy.strftime("%m/%Y")

    # ---- 1) cierres anticipados (registrados por el gestor) ----
    anticipados = []
    try:
        d = json.load(open("/opt/polymarket/cierres_anticipados.json",
                           encoding="utf-8"))
        for c in d.get("cierres", []):
            try:
                fecha = datetime.strptime(c.get("fecha", ""), "%Y-%m-%d").date()
            except Exception:
                continue
            if fecha >= FECHA_INICIO:
                anticipados.append({
                    "titulo": c.get("titulo", "?"),
                    "pnl": float(c.get("pnl", 0) or 0),
                    "invertido": float(c.get("invertido", 0) or 0),
                    "end": fecha,
                })
    except Exception:
        pass

    # ---- 2) resueltas por Polymarket (data-api, endDate del mes) ----
    cerradas = []
    for p in pos:
        try:
            cur = float(p.get("currentValue", 0) or 0)
            init = float(p.get("initialValue", 0) or 0)
            pnl = float(p.get("cashPnl", 0) or 0)
        except Exception:
            continue
        if cur > 0.001:
            continue                    # sigue abierta
        if init <= 0.001 or abs(pnl) <= 0.001:
            continue
        try:
            end = datetime.strptime(p.get("endDate", ""), "%Y-%m-%d").date()
        except Exception:
            continue
        if end < FECHA_INICIO:
            continue                    # anterior al cierre del 15-17/08
        cerradas.append({
            "titulo": (p.get("title") or "?").replace("Elon Musk # tweets ", "").replace("?", ""),
            "pnl": pnl,
            "end": end,
        })

    # ---- 3) ganadas ya canjeadas (balance_bot.json) ----
    pnl_previas_mes = []
    try:
        bb = json.load(open("/opt/polymarket/balance_bot.json", encoding="utf-8"))
        for g in bb.get("ganadas", []):
            try:
                end = datetime.strptime(g["fecha"], "%Y-%m-%d").date()
            except Exception:
                continue
            if end >= FECHA_INICIO:
                pnl_previas_mes.append({
                    "titulo": g.get("titulo", "Orden ganada"),
                    "pnl": float(g.get("pnl", 0) or 0),
                    "end": end,
                })
    except Exception:
        pass

    if not cerradas and not pnl_previas_mes and not anticipados:
        return (f"📅 *OPERACIONES FINALIZADAS (desde 17/08/2026)*\n\n"
                f"⚪ Sin operaciones cerradas desde el 17/08 todavía.\n"
                f"_Cuenta desde el cierre positivo del 15-17/08._")

    # mezclar resueltas + canjeadas para ordenar y hallar la última ganada
    todas = cerradas + pnl_previas_mes
    todas.sort(key=lambda x: x["end"], reverse=True)
    ganadas = [c for c in todas if c["pnl"] > 0]
    ganadas += [c for c in anticipados if c["pnl"] > 0]
    ultima_ganada = max(ganadas, key=lambda x: x["end"]) if ganadas else None

    total_res = sum(c["pnl"] for c in todas)
    total_ant = sum(c["pnl"] for c in anticipados)
    total_mes = total_res + total_ant
    ic = "🟢" if total_mes >= 0 else "🔴"

    lineas = [f"📅 *OPERACIONES FINALIZADAS (desde 17/08/2026)*", ""]

    if anticipados:
        lineas.append("🔻 *Cierres anticipados*")
        for c in anticipados:
            estrella = "⭐ " if (ultima_ganada and c is ultima_ganada) else ""
            ico = "🟢" if c["pnl"] >= 0 else "🔴"
            lineas.append(f"{ico} {estrella}{c['titulo']}\n"
                          f"   ${c['pnl']:+.2f}  (invertido ${c['invertido']:.2f}) "
                          f"({c['end'].strftime('%d/%m')})")
        ic_a = "🟢" if total_ant >= 0 else "🔴"
        lineas.append(f"*Total cierres anticipados: {ic_a} {total_ant:+.2f} $*")
        lineas.append("")

    if todas:
        lineas.append("🏁 *Resueltas por Polymarket*")
        for c in todas:
            estrella = "⭐ " if (ultima_ganada and c is ultima_ganada) else ""
            ico = "🟢" if c["pnl"] > 0 else "🔴"
            lineas.append(f"{ico} {estrella}{c['titulo']}\n"
                          f"   ${c['pnl']:+.2f}  ({c['end'].strftime('%d/%m')})")
        ic_r = "🟢" if total_res >= 0 else "🔴"
        lineas.append(f"*Total resueltas: {ic_r} {total_res:+.2f} $*")
        lineas.append("")

    lineas.append(f"*Saldo desde 17/08: {ic} {total_mes:+.2f} $*")
    lineas.append("")
    lineas.append("_Cuenta desde el cierre positivo del 15-17/08._")
    return "\n".join(lineas)


if __name__ == "__main__":
    print(texto_abiertas())
    print()
    print(texto_saldo())
