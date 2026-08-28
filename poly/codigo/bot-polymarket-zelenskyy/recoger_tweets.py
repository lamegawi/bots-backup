#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RECOGIDA AUTOMÁTICA DE TWEETS DE @ZelenskyyUa — para mercados Polymarket
=====================================================================
Recoge la actividad de @ZelenskyyUa (posts + quote posts + reposts;
SIN replies, igual que las reglas de resolución de los mercados
«Zelenskyy # tweets») y genera datos_zelen.csv con el formato que
espera senal.py (fecha,tweets) en días COMPLETOS (hora ET).

FUENTES (por orden de preferencia):
  1) x.com renderizado vía r.jina.ai (timestamps EXACTOS de posts Y
     reposts — la hora que se ve en el perfil es la del repost).
     Sin API key. ~15-20 tweets por pasada: en modo --loop se acumula.
  2) xcancel.com (espejo Nitter, página 1) — respaldo si jina falla.
     Ojo: los reposts muestran la fecha del tweet ORIGINAL.
  3) X API v2 oficial (exacta, con paginación completa):
     export X_BEARER_TOKEN=...   (plan Basic $100/mes para conteo
     completo ~60k posts/mes; free tier insuficiente para esto)

USO:
  python3 recoger_tweets.py --dias 30              # pasada única
  python3 recoger_tweets.py --resumen              # conteos diarios + métricas
  python3 recoger_tweets.py --loop --intervalo 20  # continuo (recomendado)
  python3 recoger_tweets.py --manual 2026-08-08 35 # corregir un día a mano
  python3 recoger_tweets.py --limpiar              # borrar datos y empezar de cero

CRON sugerido (1 vez al día basta para la señal del día):
  0 12 * * * cd /ruta/estrategia_elon_tweets && python3 recoger_tweets.py --dias 30 >> recoger.log 2>&1
"""
import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

try:
    import mercado_polymarket as mp
except ImportError:
    mp = None

# ----------------------------------------------------------------------------
SCREEN = "ZelenskyyUa"
try:
    ET = ZoneInfo("America/New_York")
except Exception:
    # Windows sin tzdata: fallback a hora fija de verano (UTC-4)
    from datetime import timedelta
    from datetime import timezone as _tz
    ET = _tz(timedelta(hours=-4), name="EDT")
CSV = "datos_zelen.csv"
ESTADO = "estado_tweets_zelen.json"
RAW_DIR = "datos_raw_zelen"
JINA_X = f"https://r.jina.ai/https://x.com/{SCREEN}"
JINA_TW = f"https://r.jina.ai/https://twitter.com/{SCREEN}"
XCANCEL = f"https://xcancel.com/{SCREEN}"
# Espejos Nitter (markup antiguo tipo xcancel) como respaldo, por orden de
# preferencia. xcancel.com es el más fiable ahora mismo; el resto se prueba
# por si alguno vuelve a estar operativo.
NITTER_ESPEJOS = [
    "xcancel.com",
    "nitter.poast.org",
    "nitter.privacyredirect.com",
    "lightbrd.com",
    "nitter.space",
]
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
T_FMT = "%a %b %d %H:%M:%S +0000 %Y"
MESES = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
         "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}
# ----------------------------------------------------------------------------


def hoy_et():
    return datetime.now(ET).date()


def ahora_utc():
    return datetime.now(timezone.utc)


def curl(url, headers=None, timeout=60):
    cmd = ["curl", "-s", "--max-time", str(timeout), "-L", url]
    for k, v in (headers or {}).items():
        cmd += ["-H", f"{k}: {v}"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"curl falló ({r.returncode}): {r.stderr[:200]}")
    return r.stdout


# ---------------------------------------------------------------- fuentes

def _descargar_jina(url):
    """Render del perfil vía r.jina.ai. Devuelve {status_id: item}.

    Acepta tanto el render de x.com como el de twitter.com (perfil en x.com,
    enlaces de estado en twitter.com o x.com). La hora relativa que muestra el
    perfil se convierte a UTC (exacta)."""
    # Cloudflare es intermitente: reintentar con distintos UA y pausas
    uas = [None, UA, "curl/8.0"]
    ultimo_error = None
    for intento in range(4):
        try:
            hdrs = {"Accept": "text/plain"}
            if uas[intento % len(uas)]:
                hdrs["User-Agent"] = uas[intento % len(uas)]
            md = curl(url, hdrs)
            if ("Just a moment" in md or "Verifying your browser" in md
                    or "Rate limit" in md or "[@ZelenskyyUa]" not in md):
                ultimo_error = "desafío o respuesta sin contenido"
                time.sleep(8 + intento * 5)
                continue
            ahora = ahora_utc()
            vistos = {}
            # Formato timeline (x.com y twitter.com):
            #   [@ZelenskyyUa](https://x.com/ZelenskyyUa)  [17h](https://twitter.com/ZelenskyyUa/status/ID)
            pat = re.compile(
                r"\[@ZelenskyyUa\]\(https://x\.com/ZelenskyyUa\)\s+\[([^\]]+)\]"
                r"\(https://(?:twitter\.com|x\.com)/ZelenskyyUa/status/(\d+)\)")
            posiciones = list(pat.finditer(md))
            for i, m in enumerate(posiciones):
                rel, sid = m.group(1).strip(), m.group(2)
                ts = rel_a_utc(rel, ahora)
                if not ts:
                    continue
                # trozo de la entrada hasta la siguiente entrada
                fin = posiciones[i + 1].start() if i + 1 < len(posiciones) else len(md)
                trozo = md[m.end():fin]
                # es repost si dentro hay un enlace de estado de OTRO usuario
                es_repost = bool(re.search(
                    r"\]\(https://(?:twitter\.com|x\.com)/(?!ZelenskyyUa/status/)"
                    r"[A-Za-z0-9_]+/status/\d+\)", trozo))
                vistos[sid] = {"id": sid,
                               "kind": "repost" if es_repost else "post",
                               "autor": SCREEN,
                               "created_at": ts.strftime(T_FMT),
                               "primera_vista": ahora.strftime(T_FMT),
                               "exacto": True}
            return vistos
        except RuntimeError as e:
            ultimo_error = str(e)
            time.sleep(8 + intento * 5)
    raise RuntimeError(f"jina no disponible tras reintentos: {ultimo_error}")




def descargar_xtracker():
    """Posts del tracker OFICIAL de Polymarket (xtracker.polymarket.com),
    que es la fuente de resolución del mercado. Timestamps exactos (UTC).
    Devuelve {status_id: item}."""
    try:
        raw = curl(f"https://xtracker.polymarket.com/api/users/{SCREEN}/posts",
                   timeout=60)
        d = json.loads(raw)
    except Exception as e:
        raise RuntimeError(f"xtracker no disponible: {e}")
    posts = d.get("data") or []
    ahora = ahora_utc()
    vistos = {}
    for p in posts:
        sid = str(p.get("platformId") or p.get("id") or "").strip()
        created = (p.get("createdAt") or "").strip()
        if not sid or not created:
            continue
        ts = None
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z"):
            try:
                ts = datetime.strptime(created.replace("Z", "+00:00"), fmt)
                break
            except Exception:
                continue
        if ts is None:
            continue
        vistos[sid] = {"id": sid, "kind": "post", "autor": SCREEN,
                       "created_at": ts.strftime(T_FMT),
                       "primera_vista": ahora.strftime(T_FMT),
                       "exacto": True}
    return vistos


def descargar_jina_tw():
    """jina sobre twitter.com (suele esquivar el Cloudflare de x.com)."""
    return _descargar_jina(JINA_TW)


def descargar_jina_x():
    """jina sobre x.com (formato original)."""
    return _descargar_jina(JINA_X)


def _descargar_nitter_instancia(instancia):
    """Página 1 de un espejo Nitter (markup antiguo tipo xcancel).
    Reposts con fecha del original (aprox.)."""
    html = curl(f"https://{instancia}/{SCREEN}", {"User-Agent": UA})
    ahora = ahora_utc()
    vistos = {}
    for b in re.split(r'<div class="timeline-item', html)[1:]:
        es_repost = 'retweet-header' in b
        m_id = re.search(r'/(?:status)/(\d+)', b)
        m_fecha = re.search(r'class="tweet-date"><a[^>]*title="([^"]+)"', b)
        if not m_id or not m_fecha:
            continue
        ts = parse_fecha_nitter(m_fecha.group(1))
        if not ts:
            continue
        vistos[m_id.group(1)] = {"id": m_id.group(1),
                                 "kind": "repost" if es_repost else "post",
                                 "autor": SCREEN,
                                 "created_at": ts.strftime(T_FMT),
                                 "primera_vista": ahora.strftime(T_FMT)}
    return vistos


def descargar_nitter():
    """Prueba varios espejos Nitter (xcancel primero) hasta conseguir items."""
    for _intento in range(2):
        for instancia in NITTER_ESPEJOS:
            try:
                vistos = _descargar_nitter_instancia(instancia)
                if vistos:
                    return vistos
                print(f"  nitter {instancia}: sin items")
            except RuntimeError as e:
                print(f"  nitter {instancia}: {e}")
            time.sleep(3)
    return {}



def descargar_api_v2(max_paginas=50):
    """X API v2 oficial (exacta). Requiere X_BEARER_TOKEN."""
    token = os.environ.get("X_BEARER_TOKEN")
    if not token:
        sys.exit("Modo api requiere: export X_BEARER_TOKEN=<tu token>")
    vistos, token_pag = {}, None
    for p in range(1, max_paginas + 1):
        url = ("https://api.x.com/2/users/44196397/tweets?exclude=replies"
               "&max_results=100&tweet.fields=created_at")
        if token_pag:
            url += f"&pagination_token={token_pag}"
        d = json.loads(curl(url, {"Authorization": f"Bearer {token}"}, timeout=30))
        if d.get("errors"):
            print("  error API:", d["errors"][0].get("detail", d["errors"]))
            break
        for t in d.get("data", []):
            ts = datetime.strptime(t["created_at"], "%Y-%m-%dT%H:%M:%S.000Z") \
                .replace(tzinfo=timezone.utc)
            vistos[t["id"]] = {"id": t["id"], "kind": "post", "autor": SCREEN,
                               "created_at": ts.strftime(T_FMT),
                               "primera_vista": ts.strftime(T_FMT)}
        token_pag = (d.get("meta") or {}).get("next_token")
        print(f"  [página {p}] tweets: {len(vistos)}")
        if not token_pag:
            break
        time.sleep(1.5)
    return vistos


def parse_fecha_nitter(titulo):
    m = re.match(r"([A-Z][a-z]{2} \d{1,2}, \d{4}) · (\d{1,2}:\d{2} [AP]M) UTC", titulo)
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%b %d, %Y %I:%M %p") \
            .replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def rel_a_utc(rel, ahora):
    """Convierte '2h', '3m', '1d', 'Aug 6', 'Aug 6, 2025' a datetime UTC."""
    rel = rel.strip()
    m = re.match(r"^(\d+)([smhd])$", rel)
    if m:
        n, u = int(m.group(1)), m.group(2)
        delta = {"s": 0, "m": 60, "h": 3600, "d": 86400}[u] * n
        return ahora - timedelta(seconds=delta)
    m = re.match(r"^([A-Z][a-z]{2}) (\d{1,2})(?:, (\d{4}))?$", rel)
    if m:
        mes, dia = MESES[m.group(1)], int(m.group(2))
        anio = int(m.group(3)) if m.group(3) else ahora.year
        try:
            ts = datetime(anio, mes, dia, tzinfo=timezone.utc)
        except ValueError:
            return None
        # si la fecha es claramente futura, es del año pasado
        if ts > ahora + timedelta(days=1):
            ts = ts.replace(year=anio - 1)
        return ts
    return None


# ---------------------------------------------------------------- procesado

def conteo_diario(vistos, sin_reposts=False, modo_loop=False):
    """Agrupa por día ET.
    - Items con timestamp exacto (jina/x.com): created_at siempre.
    - Reposts de xcancel (fecha del original): primera_vista en modo_loop
      (≈ momento real, error < intervalo); si no, fecha del original."""
    dias = {}
    for v in vistos.values():
        if v.get("kind") == "repost" and sin_reposts:
            continue
        if v.get("exacto") or v.get("kind") != "repost" or not modo_loop:
            base = v["created_at"]
        else:
            base = v["primera_vista"]
        fecha = datetime.strptime(base, T_FMT).astimezone(ET).date()
        dias[fecha] = dias.get(fecha, 0) + 1
    return dias


def actualizar_csv(dias_conteo, completos=True):
    hoy = hoy_et()
    filas = {}
    if os.path.exists(CSV):
        with open(CSV, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                filas[fila["fecha"]] = int(fila["tweets"])
    nuevos = 0
    for fecha, n in sorted(dias_conteo.items()):
        if completos and fecha >= hoy:
            continue
        # MONÓTONO: el conteo directo es una cota inferior (subconteo parcial);
        # solo se actualiza si el nuevo valor es MAYOR. Así los días
        # reconstruidos desde los mercados resueltos no se degradan.
        if n > filas.get(fecha.isoformat(), -1):
            filas[fecha.isoformat()] = n
            nuevos += 1
    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fecha", "tweets"])
        for fecha in sorted(filas):
            w.writerow([fecha, filas[fecha]])
    return nuevos, len(filas)


def guardar_estado(vistos):
    os.makedirs(RAW_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(RAW_DIR, f"tweets_{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(vistos, f, ensure_ascii=False, indent=1)
    with open(ESTADO, "w", encoding="utf-8") as f:
        json.dump({"actualizado": datetime.now().isoformat(), "tweets": vistos}, f,
                  ensure_ascii=False, indent=1)


def cargar_estado():
    if not os.path.exists(ESTADO):
        return {}
    try:
        return json.load(open(ESTADO, encoding="utf-8")).get("tweets", {})
    except Exception:
        return {}


def fusionar(vistos_nuevos, sin_reposts=False):
    """Fusiona con el estado previo: por status id, gana el item nuevo
    (jina/x.com da el tiempo exacto del repost) pero se CONSERVA la
    primera_vista más antigua (el repost se atribuye al día en que se
    vio por PRIMERA vez). Si sin_reposts, elimina los reposts."""
    estado = cargar_estado()
    if sin_reposts:
        estado = {sid: v for sid, v in estado.items() if v.get("kind") != "repost"}
    for sid, v in vistos_nuevos.items():
        previo = estado.get(sid)
        if previo:
            v["primera_vista"] = min(v["primera_vista"], previo["primera_vista"])
        estado[sid] = v
    return estado


def resumen(dias=14):
    if not os.path.exists(CSV):
        print("Sin datos todavía. Ejecuta primero: recoger_tweets.py")
        return
    with open(CSV, newline="", encoding="utf-8") as f:
        filas = [(r["fecha"], int(r["tweets"])) for r in csv.DictReader(f)]
    hoy = hoy_et().isoformat()
    print(f"{'fecha':<12}{'tweets':>7}")
    for fecha, n in filas[-dias:]:
        marca = "  ← hoy (incompleto, no entra en la señal)" if fecha == hoy else ""
        print(f"{fecha:<12}{n:>7}{marca}")
    if len(filas) >= 9:
        ult7 = [n for _, n in filas[-7:]]
        ult2 = [n for _, n in filas[-2:]]
        avg7 = sum(ult7) / 7
        v2 = sum(ult2)
        r = v2 / (2 * avg7)
        aj = min(1.5, max(0.5, 1 + 0.5 * (r - 1)))
        lam = 2 * avg7 * aj
        print(f"\nAVG7 = {avg7:.2f}  V2 = {v2}  R = {r:.3f}  ajuste = {aj:.3f}  λ48 = {lam:.1f}")
    print("Días completos en CSV:", len(filas))


def main():
    ap = argparse.ArgumentParser(description="Recogida automática de tweets de @ZelenskyyUa")
    ap.add_argument("--fuente", choices=["jina", "xcancel", "api"], default="jina",
                    help="fuente de datos (api requiere X_BEARER_TOKEN)")
    ap.add_argument("--sin-reposts", action="store_true",
                    help="excluir reposts del conteo")
    ap.add_argument("--resumen", action="store_true", help="mostrar conteos y métricas")
    ap.add_argument("--loop", action="store_true", help="modo continuo (polling)")
    ap.add_argument("--intervalo", type=int, default=15, help="minutos entre pasadas")
    ap.add_argument("--mercado", action="store_true",
                    help="refrescar también los precios de Polymarket en cada pasada")
    ap.add_argument("--papel", action="store_true",
                    help="ejecutar también el paper trading (abrir/resolver apuestas simuladas)")
    ap.add_argument("--limpiar", action="store_true", help="borrar estado y CSV y empezar de cero")
    ap.add_argument("--manual", nargs=2, metavar=("FECHA", "N"),
                    help="añadir/corregir un día: --manual 2026-08-08 35")
    args = ap.parse_args()

    if args.limpiar:
        for f in (CSV, ESTADO):
            if os.path.exists(f):
                os.remove(f)
        print("Estado y CSV borrados. Empieza de cero.")
        return

    if args.manual:
        filas = {}
        if os.path.exists(CSV):
            with open(CSV, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    filas[r["fecha"]] = int(r["tweets"])
        filas[args.manual[0]] = int(args.manual[1])
        with open(CSV, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["fecha", "tweets"])
            for f_ in sorted(filas):
                w.writerow([f_, filas[f_]])
        print(f"Manual: {args.manual[0]} = {args.manual[1]} tweets. CSV actualizado.")
        return

    if args.resumen:
        resumen()
        return

    def una_pasada():
        print(f"[{datetime.now(ET).isoformat()}] Recogiendo @{SCREEN} (fuente: {args.fuente})…")
        vistos_n = {}
        if args.fuente in ("jina", "xcancel"):
            # fusionar todas las fuentes en cascada:
            # 1) jina twitter.com  2) jina x.com  3) espejos nitter (xcancel+)
            for nombre, fn in (("xtracker", descargar_xtracker),
                                ("jina-tw", descargar_jina_tw),
                                ("jina-x", descargar_jina_x),
                                ("nitter", descargar_nitter)):
                try:
                    parcial = fn()
                    if parcial:
                        vistos_n.update(parcial)
                        print(f"  {nombre}: {len(parcial)} items")
                        if nombre == "xtracker":
                            break   # fuente oficial: suficiente
                    else:
                        print(f"  {nombre}: sin items")
                except RuntimeError as e:
                    print(f"  {nombre}: [ERROR] {e}")
            if not vistos_n:
                print("  Sin datos de ninguna fuente. Reintenta en un rato.")
                if args.papel:
                    try:
                        subprocess.run([sys.executable, "papel.py"], check=False)
                    except Exception as e:
                        print(f"  papel: [ERROR] {e}")
                return
        else:
            vistos_n = descargar_api_v2()
            if not vistos_n:
                print("  Sin datos. Reintenta en un rato.")
                return
        vistos = fusionar(vistos_n, sin_reposts=args.sin_reposts)
        guardar_estado(vistos)
        dias = conteo_diario(vistos, sin_reposts=args.sin_reposts, modo_loop=args.loop)
        nuevos, total = actualizar_csv(dias)
        n_rep = sum(1 for v in vistos.values() if v["kind"] == "repost")
        print(f"  Tweets únicos: {len(vistos)} (reposts: {n_rep}) · días con datos: {len(dias)} "
              f"· filas CSV: {total} (nuevas/actualizadas: {nuevos})")
        if args.mercado and mp:
            try:
                mk = mp.actualizar_mercado()
                abiertos = [m for m in mk if not m["cerrado"] and m["tipo"] == "48h"]
                print(f"  Polymarket: {len(mk)} mercados · {len(abiertos)} de 48 h abiertos "
                      f"→ mercado_activo.json actualizado")
            except Exception as e:
                print(f"  Polymarket: [ERROR] {e}")
        if args.papel:
            try:
                subprocess.run([sys.executable, "papel.py"], check=False)
            except Exception as e:
                print(f"  papel: [ERROR] {e}")
        resumen(dias=12)

    if args.loop:
        while True:
            try:
                una_pasada()
            except Exception as e:
                print(f"[ERROR general] {e}")
            print(f"[espera] {args.intervalo} min…")
            time.sleep(args.intervalo * 60)
    else:
        una_pasada()



# === FIXT_ARENA (26/08 v2): jina con clave + pausas inteligentes ===
# Mejora sobre v1: la fuente buena (twitter.com via jina) se pregunta en
# CADA pasada; la que falla de forma persistente (x.com con Cloudflare)
# descansa sola 1 hora, sin activar la pausa general. La pausa general de
# 20 min solo entra si falla la fuente buena (averia real). Asi el bot no
# pasa pasadas "sin datos" y deja de mandar la alerta en tono de broma.
import json as _json_t
import os as _os_t
import time as _time_t

JINA_KEY_FILE = "/opt/polymarket/.jina_key"
JINA_BACKOFF_FILE = "/opt/polymarket/.jina_backoff.json"
JINA_BACKOFF_MIN = 20
JINA_X_DESCANSO_S = 3600
_T_ESTADO = {"x_hasta": 0.0}


def _jina_token():
    try:
        t = open(JINA_KEY_FILE, encoding="utf-8").read().strip()
        if t:
            return t
    except Exception:
        pass
    return _os_t.environ.get("JINA_API_KEY", "").strip()


def _tbackoff_activo():
    try:
        d = _json_t.load(open(JINA_BACKOFF_FILE))
        return _time_t.time() < float(d.get("hasta", 0) or 0)
    except Exception:
        return False


def _tbackoff_activar():
    try:
        _json_t.dump({"hasta": _time_t.time() + JINA_BACKOFF_MIN * 60},
                     open(JINA_BACKOFF_FILE, "w"))
    except Exception:
        pass


# 1) curl con clave para jina (envuelve al original; no toca otras webs)
try:
    _curl_t_orig
except NameError:
    _curl_t_orig = curl


def curl(url, headers=None, timeout=60):
    hdrs = dict(headers or {})
    if "r.jina.ai" in url:
        tok = _jina_token()
        if tok:
            hdrs.setdefault("Authorization", "Bearer " + tok)
        hdrs.setdefault("x-no-cache", "true")
    return _curl_t_orig(url, hdrs, timeout)


# 2) jina con pausas inteligentes por fuente
try:
    _descargar_jina_t_orig
except NameError:
    _descargar_jina_t_orig = _descargar_jina


def _descargar_jina(url):
    es_x = "/https://x.com/" in url
    ahora = _time_t.time()
    if es_x and ahora < _T_ESTADO["x_hasta"]:
        raise RuntimeError("x.com en descanso (1h, Cloudflare)")
    if _tbackoff_activo():
        raise RuntimeError("jina en pausa (descanso tras fallos)")
    try:
        return _descargar_jina_t_orig(url)
    except Exception:
        if es_x:
            _T_ESTADO["x_hasta"] = ahora + JINA_X_DESCANSO_S
        else:
            _tbackoff_activar()
        raise


# 3) espejo nitter adicional (por si vuelve a responder)
try:
    if "nitter.tiekoetter.com" not in NITTER_ESPEJOS:
        NITTER_ESPEJOS.insert(0, "nitter.tiekoetter.com")
except Exception:
    pass

if __name__ == "__main__":
    main()
