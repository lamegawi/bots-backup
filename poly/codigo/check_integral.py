#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""TEST INTEGRAL DIARIO de Polymarket (bot-poly).

Modos (cada uno vigila y notifica a su propio bot de Telegram):
  - por defecto (--elon):  bots de Elon (48h, semanal, mensual)
  - --zelen:               bot de Zelenskyy

Comprueba:
  A. Servicios systemd del grupo activos.
  B. Proxy del PC + IP de salida (85.85.41.76) + CLOB responde.
  C. Telegram configurado en los bots del grupo (token no vacío).
  D. Motor de trading v2 presente (MOTOR_ACTUAL).
  E. mercado_activo.json del grupo fresco (< 30 min).
  F. CSV de datos del grupo fresco (último día dentro de 2 días).
  G. Lock compartido sin entradas caducadas.
  H. POSICIONES FANTASMA: bot con 'activa' pero la cuenta ya no tiene esa
     posición → bot atascado.
  I. Posiciones del grupo abiertas sin dueño (huérfanas).
  J. Las funciones del bot de Telegram del grupo no fallan.

Uso:
  python3 check_integral.py               # grupo Elon
  python3 check_integral.py --zelen       # grupo Zelenskyy
  python3 check_integral.py --test        # imprime también por pantalla
  python3 check_integral.py --fix         # reconcilia los bots atascados
  python3 check_integral.py --solo-fantasmas [--zelen]  # solo fantasmas
"""
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

BASE = "/opt/polymarket"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TOKEN_ZELEN = os.environ.get("ZELEN_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
FUNDER = "0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
PROXY = "http://100.83.57.99:8888"
IP_CASA = "85.85.41.76"
MAD = ZoneInfo("Europe/Madrid")

BOTS_ELON = [
    ("48h",       f"{BASE}/bot-polymarket-elon/real.json",                  "bot-polymarket-elon"),
    ("Semanal",   f"{BASE}/bot-polymarket-elon-semanal/real_semanal.json",  "bot-polymarket-elon-semanal"),
    ("Mensual",   f"{BASE}/bot-polymarket-elon-mensual/real_mensual.json",  "bot-polymarket-elon-mensual"),
]
BOTS_ZELEN = [
    ("Zelenskyy", f"{BASE}/bot-polymarket-zelenskyy/real_zelen.json",       "bot-polymarket-zelenskyy"),
]
SERVICIOS_ELON = ["poly-elon", "poly-semanal", "poly-mensual",
                  "poly-telegram", "poly-gestor"]
SERVICIOS_ZELEN = ["poly-zelenskyy", "poly-telegram-zelen"]
MOTOR_ESPERADO = "motor_v2_ev_escalones_tope10"
MESES = {"january", "february", "march", "april", "may", "june", "july",
         "august", "september", "october", "november", "december"}
MESES_ES = {"enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
            "agosto", "septiembre", "octubre", "noviembre", "diciembre",
            "ago"}
LOCK = f"{BASE}/apuestas_compartidas.json"


# ------------------------------------------------------------------- estado
def _cfg():
    """Configuración según el modo (--zelen o no)."""
    zelen = "--zelen" in sys.argv
    if zelen:
        return {
            "nombre": "ZELENSKYY",
            "bots": BOTS_ZELEN,
            "servicios": SERVICIOS_ZELEN,
            "token": TOKEN_ZELEN,
            "clave_titulo": "zelenskyy",
            "mercado_json": f"{BASE}/bot-polymarket-zelenskyy/mercado_activo.json",
            "csv": f"{BASE}/bot-polymarket-zelenskyy/datos_zelen.csv",
            "csv_nombre": "datos_zelen.csv",
            "mercado_nombre": "mercado_activo.json Zelenskyy",
        }
    return {
        "nombre": "POLYMARKET",
        "bots": BOTS_ELON,
        "servicios": SERVICIOS_ELON,
        "token": TOKEN,
        "clave_titulo": "elon musk",
        "mercado_json": f"{BASE}/bot-polymarket-elon/mercado_activo.json",
        "csv": f"{BASE}/bot-polymarket-elon/datos_elon.csv",
        "csv_nombre": "datos_elon.csv",
        "mercado_nombre": "mercado_activo.json",
    }


def tg_send(texto, token):
    if not token or not CHAT_ID:
        return False
    try:
        data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": texto}).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data)
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode()).get("ok", False)
    except Exception as e:
        print("tg error:", e)
        return False


def curl(url, proxy=True):
    cmd = ["curl", "-s", "--max-time", "35"]
    if proxy:
        cmd += ["-x", PROXY]
    cmd += [url]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0 or not r.stdout.strip():
        return None
    try:
        return json.loads(r.stdout)
    except Exception:
        return None


# ------------------------------------------------------------- cheques A-J
def check_servicios(servicios):
    mal = []
    for s in servicios:
        r = subprocess.run(["systemctl", "is-active", s],
                           capture_output=True, text=True)
        if (r.stdout or "").strip() != "active":
            mal.append(f"servicio {s}: {r.stdout.strip()}")
    return mal


def check_proxy():
    mal = []
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "15", "-x", PROXY,
                            "https://api.ipify.org"],
                           capture_output=True, text=True, timeout=20)
        ip = r.stdout.strip()
        if not ip or r.returncode != 0:
            mal.append("proxy del PC no responde")
        elif ip != IP_CASA:
            mal.append(f"IP de salida {ip} ≠ casa {IP_CASA}")
    except Exception as e:
        mal.append(f"proxy: {e}")
    try:
        r = subprocess.run(["curl", "-s", "--max-time", "15", "-x", PROXY,
                            "-o", "/dev/null", "-w", "%{http_code}",
                            "https://clob.polymarket.com/"],
                           capture_output=True, text=True, timeout=20)
        if r.stdout.strip() != "200":
            mal.append(f"clob via proxy: HTTP {r.stdout.strip()}")
    except Exception as e:
        mal.append(f"clob: {e}")
    return mal


def check_telegram_configs(bots):
    mal = []
    for nombre, _, repo in bots:
        p = f"{BASE}/{repo}/config.json"
        try:
            cfg = json.load(open(p, encoding="utf-8"))
            tg = cfg.get("telegram") or {}
            if not (tg.get("token") and tg.get("chat_id")):
                mal.append(f"{nombre}: telegram sin token/chat en config.json")
        except Exception as e:
            mal.append(f"{nombre}: config.json ilegible ({e})")
    return mal


def check_motores(bots):
    mal = []
    for nombre, _, repo in bots:
        p = f"{BASE}/{repo}/senal_vivo.py"
        try:
            src = open(p, encoding="utf-8").read()
        except Exception as e:
            mal.append(f"{nombre}: sin senal_vivo.py ({e})")
            continue
        if "MOTOR_ACTUAL" not in src:
            mal.append(f"{nombre}: senal_vivo.py sin motor")
        elif MOTOR_ESPERADO not in src:
            mal.append(f"{nombre}: motor distinto al esperado")
    return mal


def check_frescura(cfg):
    mal = []
    try:
        d = json.load(open(cfg["mercado_json"], encoding="utf-8"))
        ts = d.get("actualizado", "")
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
        if (datetime.now(timezone.utc) - dt).total_seconds() > 1800:
            mal.append(f"{cfg['mercado_nombre']} viejo ({ts})")
    except Exception as e:
        mal.append(f"{cfg['mercado_nombre']}: {e}")
    try:
        import csv as _csv
        ultima = None
        with open(cfg["csv"], newline="", encoding="utf-8") as f:
            for fila in _csv.DictReader(f):
                ultima = fila.get("fecha", "")
        if not ultima:
            mal.append(f"{cfg['csv_nombre']} vacío")
        else:
            d = datetime.strptime(ultima, "%Y-%m-%d").date()
            hoy = datetime.now(MAD).date()
            if (hoy - d).days > 2:
                mal.append(f"{cfg['csv_nombre']} sin datos recientes (último {ultima})")
    except Exception as e:
        mal.append(f"{cfg['csv_nombre']}: {e}")
    return mal


def check_lock():
    mal = []
    try:
        d = json.load(open(LOCK, encoding="utf-8"))
    except Exception:
        return []  # sin lock no es error
    ahora = datetime.now(timezone.utc)
    for clave, ent in d.items():
        hasta = ent.get("hasta") or ""
        try:
            if hasta and datetime.fromisoformat(hasta).astimezone(timezone.utc) < ahora:
                mal.append(f"lock caducado: {clave}")
        except Exception:
            pass
    return mal


def tokens_de_slug(slug):
    partes = (slug or "").lower().split("-")
    toks = []
    for i, p in enumerate(partes):
        if p in MESES and i + 1 < len(partes) and partes[i + 1].isdigit():
            toks.append(f"{p} {partes[i + 1]}")
    return toks


def _orden_viva(order_id):
    """True si la orden sigue VIVA (resting) en el CLOB y sin llenar.

    Si devuelve False puede ser porque: no existe (cancelada/expirada), ya se
    llenó (size_matched > 0) o no se pudo consultar."""
    if not order_id:
        return False
    try:
        sys.path.insert(0, f"{BASE}/bot-polymarket-elon")
        import operar_real as _op
        det = _op.get_client().get_order(order_id)
    except Exception:
        return False
    if not det:
        return False
    st = (det.get("status") or "").lower()
    sz = float(det.get("size_matched", 0) or 0)
    if sz > 0:
        return False                       # ya llenada → no es "viva"
    return st not in ("cancelled", "canceled", "expired", "cancelled_by_user")


def gamma_info(slug):
    d = curl(f"https://gamma-api.polymarket.com/events?slug={slug}")
    if not d:
        return None, None
    try:
        ev = d[0]
    except Exception:
        return None, None
    cerrado = bool(ev.get("closed"))
    ganador = None
    for m in ev.get("markets", []):
        try:
            p = json.loads(m.get("outcomePrices") or "[]")
        except Exception:
            continue
        if p and p[0] == "1":
            ganador = m.get("groupItemTitle")
    return cerrado, ganador


def posiciones_abiertas():
    d = curl(f"https://data-api.polymarket.com/positions?user={FUNDER}")
    abiertas = []
    for p in (d or []):
        try:
            cur = float(p.get("currentValue", 0) or 0)
        except Exception:
            continue
        if cur > 0.001:
            abiertas.append(p.get("title") or "")
    return abiertas


def coinciden(slug, bin_titulo, titulo):
    t = titulo.lower()
    toks = tokens_de_slug(slug)
    if not toks:
        return False
    for tok in toks:
        if tok not in t:
            return False
    if bin_titulo and bin_titulo.lower() not in t:
        return False
    return True


def check_fantasmas(cfg):
    """Devuelve (avisos, atascados). atascados = [(nombre, path, act)]."""
    abiertas = posiciones_abiertas()
    clave = cfg["clave_titulo"]
    grupo_abiertas = [t for t in abiertas if clave in t.lower()]
    avisos = []
    atascados = []
    reclamadas = []
    for nombre, path, _ in cfg["bots"]:
        try:
            estado = json.load(open(path, encoding="utf-8"))
        except FileNotFoundError:
            continue          # aún no ha operado: sin fichero de estado
        except Exception as e:
            avisos.append(f"{nombre}: real.json ilegible ({e})")
            continue
        act = estado.get("activa")
        if not act:
            continue
        slug = act.get("slug", "")
        bin_t = act.get("bin_titulo", "")
        # Orden PENDIENTE todavía viva en CLOB (aún sin llenar) → NO es
        # fantasma: es el estado normal de espera. No tocar.
        if act.get("pendiente") and _orden_viva(act.get("order_id")):
            continue
        ok = any(coinciden(slug, bin_t, t) for t in grupo_abiertas)
        if ok:
            reclamadas.append(slug)
            continue
        cerrado, ganador = gamma_info(slug)
        if cerrado:
            avisos.append(f"{nombre} ATASCADO: '{bin_t}' ya resuelto (ganó {ganador}) "
                          f"pero el bot sigue con la apuesta activa")
        else:
            avisos.append(f"{nombre} ATASCADO: '{bin_t}' {slug} ya no está en la cuenta "
                          f"(vendida por el gestor o fuera) y el bot sigue bloqueado")
        atascados.append((nombre, path, act))
    # huérfanas: posiciones abiertas del grupo que NINGÚN bot reclama
    for t in grupo_abiertas:
        reclamada = False
        for nombre, path, _ in cfg["bots"]:
            try:
                act = (json.load(open(path, encoding="utf-8")).get("activa") or {})
            except Exception:
                continue
            if coinciden(act.get("slug", ""), act.get("bin_titulo", ""), t):
                reclamada = True
                break
        if not reclamada:
            avisos.append(f"HUÉRFANA: posición abierta sin bot que la reclame: {t[:60]}")
    return avisos, atascados


def check_funciones(cfg):
    mal = []
    sys.path.insert(0, BASE)
    if cfg["nombre"] == "ZELENSKYY":
        try:
            sys.path.insert(0, f"{BASE}/bot-polymarket-elon")  # saldo_ntfy
            import poly_telegram_zelen as Z
            for fn, nom in ((Z.cmd_saldo, "saldo"), (Z.cmd_abiertas, "abiertas"),
                            (Z.cmd_ventanas, "ventanas"), (Z.cmd_finalizadas, "finalizadas")):
                try:
                    fn()
                except Exception as e:
                    mal.append(f"zelenskyy.{nom}: {e}")
        except Exception as e:
            mal.append(f"poly_telegram_zelen: {e}")
    else:
        try:
            import posiciones_reales as PR
            for fn, nom in ((PR.texto_saldo, "saldo"), (PR.texto_abiertas, "abiertas"),
                            (PR.texto_finalizadas, "finalizadas")):
                try:
                    fn()
                except Exception as e:
                    mal.append(f"posiciones_reales.{nom}: {e}")
        except Exception as e:
            mal.append(f"posiciones_reales: {e}")
    return mal


# ------------------------------------------------------------------- fix
def cierre_anticipado(slug, bin_t):
    import re as _re
    toks = tokens_de_slug(slug)
    nums = []
    for tok in toks:
        m = _re.findall(r"\d+", tok)
        if m:
            nums.append(m[-1])
    try:
        d = json.load(open(f"{BASE}/cierres_anticipados.json", encoding="utf-8"))
    except Exception:
        return None
    for c in d.get("cierres", []):
        t = (c.get("titulo") or "").lower()
        if bin_t.lower() not in t:
            continue
        tnums = _re.findall(r"\d+", t)
        if nums and all(n in tnums for n in nums):
            return float(c.get("pnl", 0) or 0)
        if any(m in t for m in MESES_ES):
            return float(c.get("pnl", 0) or 0)
    return None


def arreglar_atascado(nombre, path, act):
    slug = act.get("slug", "")
    bin_t = act.get("bin_titulo", "")
    lado = act.get("lado", "YES")
    stake = float(act.get("stake", 0) or 0)
    cuota = float(act.get("cuota", 0) or 0)

    cerrado, ganador = gamma_info(slug)

    # Caso especial: orden "pendiente" que NUNCA se llenó (el mercado sigue
    # abierto y la orden ya no está en CLOB, cancelada o expirada). NO hay
    # pérdida real: solo limpiamos el estado y liberamos la ventana.
    if not cerrado and act.get("pendiente"):
        no_llena = False
        if act.get("order_id"):
            try:
                sys.path.insert(0, f"{BASE}/bot-polymarket-elon")
                import operar_real as _op
                det = _op.get_client().get_order(act["order_id"])
                st = (det.get("status") or "").lower() if det else ""
                sz = float(det.get("size_matched", 0) or 0) if det else 0.0
                llenada = st in ("matched", "filled") or sz > 0
                no_llena = (det is None) or (not llenada and st in
                            ("cancelled", "canceled", "expired",
                             "cancelled_by_user"))
            except Exception:
                no_llena = False
        if no_llena:
            try:
                estado = json.load(open(path, encoding="utf-8"))
            except Exception:
                return f"{nombre}: no pude leer {path}"
            estado["activa"] = None
            json.dump(estado, open(path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            try:
                lock = json.load(open(LOCK, encoding="utf-8"))
            except Exception:
                lock = {}
            lock.pop(f"{slug}|{bin_t}", None)
            json.dump(lock, open(LOCK, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            return (f"{nombre}: orden '{bin_t}' {lado} nunca se llenó "
                    f"(cancelada/expirada) → estado limpiado, sin pérdida")

    res = None
    detalle = ""
    if cerrado and ganador:
        gana = (ganador.lower() == bin_t.lower()) if lado == "YES" else \
               (ganador.lower() != bin_t.lower())
        res = "G" if gana else "P"
        detalle = f"resuelto por Polymarket: ganó {ganador}"
    else:
        pnl = cierre_anticipado(slug, bin_t)
        if pnl is not None and pnl > 0:
            res = "G"
            detalle = f"vendido por el gestor en positivo ({pnl:+.2f} a nivel cuenta)"
        else:
            res = "P"
            detalle = ("vendido por el gestor" if pnl is not None
                       else "vendido/desaparecido (sin registro del gestor)")

    try:
        estado = json.load(open(path, encoding="utf-8"))
    except Exception:
        return f"{nombre}: no pude leer {path}"

    if res == "G":
        benef = round(stake * (cuota - 1), 2) if cuota else round(stake, 2)
        paso = 1
    else:
        benef = -round(stake, 2)
        paso_ant = int(act.get("paso", 1))
        paso = 1 if paso_ant >= 7 else paso_ant + 1
    estado["saldo"] = round(float(estado.get("saldo", 500.0)) + benef, 2)
    estado["paso"] = paso
    reg = {
        "id": "reconc", "fecha": act.get("fecha", ""), "mercado": slug,
        "bin": bin_t, "lado": lado, "precio": act.get("precio", 0),
        "cuota": cuota, "p_modelo": act.get("p_modelo", 0),
        "paso": int(act.get("paso", 1)), "stake": round(stake, 2),
        "real": detalle, "resultado": res, "beneficio": benef,
        "saldo": round(estado["saldo"], 2),
    }
    estado.setdefault("historial", []).append(reg)
    estado["activa"] = None
    json.dump(estado, open(path, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    try:
        lock = json.load(open(LOCK, encoding="utf-8"))
    except Exception:
        lock = {}
    lock.pop(f"{slug}|{bin_t}", None)
    json.dump(lock, open(LOCK, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return f"{nombre}: reconciliado '{bin_t}' → {res} ({benef:+.2f}) · paso {paso} · {detalle}"


# ------------------------------------------------------------------- main
def solo_fantasmas(test, fix, cfg):
    avisos_fantasma, atascados = check_fantasmas(cfg)
    hora = datetime.now(MAD).strftime("%d/%m/%Y %H:%M")
    if fix and atascados:
        lineas = [arreglar_atascado(nombre, path, act)
                  for nombre, path, act in atascados]
        texto = ("🔧 *FANTASMAS CORREGIDOS* " + cfg["nombre"] + "\n" + hora + "\n\n"
                 + "\n".join("• " + l for l in lineas))
        if test:
            print(texto)
        tg_send(texto, cfg["token"])
    elif avisos_fantasma:
        texto = ("⚠️ *POSICIONES FANTASMA SIN CORREGIR* " + cfg["nombre"] + "\n"
                 + hora + "\n\n" + "\n".join("• " + a for a in avisos_fantasma))
        if test:
            print(texto)
        tg_send(texto, cfg["token"])
    elif test:
        print(f"✅ FANTASMAS {cfg['nombre']}: OK · {hora} · sin posiciones fantasma")
    print("fantasmas:", "CORREGIDOS" if atascados
          else ("AVISOS" if avisos_fantasma else "OK"))


def main():
    test = "--test" in sys.argv
    fix = "--fix" in sys.argv
    cfg = _cfg()

    if "--solo-fantasmas" in sys.argv:
        solo_fantasmas(test, fix, cfg)
        return

    todos = []
    for fn, nom in [(lambda: check_servicios(cfg["servicios"]), "servicios"),
                    (check_proxy, "proxy/IP"),
                    (lambda: check_telegram_configs(cfg["bots"]), "telegram"),
                    (lambda: check_motores(cfg["bots"]), "motores"),
                    (lambda: check_frescura(cfg), "frescura"),
                    (check_lock, "lock"),
                    (lambda: check_funciones(cfg), "funciones")]:
        for x in fn():
            todos.append(f"• {x}")

    avisos_fantasma, atascados = check_fantasmas(cfg)
    todos += [f"• {x}" for x in avisos_fantasma]

    hora = datetime.now(MAD).strftime("%d/%m/%Y %H:%M")
    if fix and atascados:
        lineas_fix = []
        for nombre, path, act in atascados:
            lineas_fix.append(arreglar_atascado(nombre, path, act))
        if test:
            print("FIX aplicado:")
            for l in lineas_fix:
                print(" ", l)
        todos.append("• 🔧 Se reconciliaron " + str(len(atascados)) +
                     " bot(s) atascados")

    ok = not todos
    n_bots = len(cfg["bots"])
    if ok:
        texto = (f"✅ *TEST DIARIO {cfg['nombre']}: TODO OK*\n{hora}\n\n"
                 f"• {n_bots} bot(s) + telegram activos\n"
                 f"• IP de salida {IP_CASA} · CLOB OK\n"
                 f"• Sin posiciones fantasma · sin huérfanas")
    else:
        texto = (f"⚠️ *TEST DIARIO {cfg['nombre']}: {len(todos)} aviso(s)*\n{hora}\n\n"
                 + "\n".join(todos))
    if test:
        print(texto)
    enviado = tg_send(texto, cfg["token"])
    if test:
        print("telegram enviado:", enviado)
    print("resultado:", "OK" if ok else "AVISOS")


if __name__ == "__main__":
    main()
