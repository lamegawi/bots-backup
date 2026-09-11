#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_v1290.py — v12.9.0: 🏆 TOP REAL EN VIVO + 📡 COPY-TRADING EN PAPEL (FASE 1)
================================================================================
TODO con stubs: la red (lb-api / data-api / CLOB) se simula con un _lb_get falso,
precio_mid falso y mercado_clob falso. No se toca Polymarket y NO se firma nada.

  A (1-6)   💸 GARANTÍA DE DINERO: COPY_DINERO=False, ninguna función del copy
            llama a enviar_orden/firmar/ejecutar_trade/ejecutar_combo_rfq/
            crear_rfq/reservar_combo (escaneo de fuente + tripwire en vivo: se
            sustituyen por funciones que revientan si alguien las toca).
  B (7-13)  🏆 top real: parseo profit+volume, caché 15 min, ventana inválida,
            red caída, /volume caído, texto de cmd_top con wallets y botones
            lb:1d/7d/30d/all, y el "no inventa cifras" cuando lb-api no responde.
  C (14-21) 📡 filtros y elección: perfil real (48 h), inactivo, market maker,
            concentrado, poco deporte, elección en orden de ranking, ranking
            vacío conserva la lista anterior, anuncio sólo con chat_id.
  D (22-29) 📨 señales: los DOS precios, cuota, deriva, en_rango_combo, deporte,
            precios inválidos, tope PROPIO 5/día, señal tardía (>5 pts) fuera,
            dedup por tx+asset y poda de "vistos" a 7 días.
  E (30-36) 🏁 resolución y cuentas: winner/perdedor/anulada, PnL a $5 al precio
            nuestro y al suyo, tope de mercados consultados por pasada, ROI y
            desglose por trader, texto con el criterio de Fase 2.
  F (37-44) 🔌 integración: programar_copy_inicio (~90 s), la ronda dentro del
            auto_loop con PASADA_LOCK y try/except, botón 📡 Copy y /copy,
            callback lb:, versiones v12.9.0, no-regresión de v12.8.4 y el
            informe diario.
Uso: python3 test_v1290.py [ruta_bot_v1290.py]
"""
import ast, importlib.util, inspect, json, sys, textwrap, time

RUTA = sys.argv[1] if len(sys.argv) > 1 else "/home/user/v12.9_copytrading/bot_v1290.py"
spec = importlib.util.spec_from_file_location("bot", RUTA)
bot = importlib.util.module_from_spec(spec)
sys.modules["bot"] = bot
spec.loader.exec_module(bot)

SRC = open(RUTA, encoding="utf-8").read()
CHAT = 123456789
bot.CHAT_ID = CHAT
bot.WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"

MENSAJES, LOGS, KBS, CALLBACKS = [], [], [], []
bot.log = lambda s: LOGS.append(str(s))


def _enviar(cid, txt, reply_markup=None):
    MENSAJES.append(txt)
    KBS.append(reply_markup)
    return True


bot.enviar = lambda cid, txt, reply_markup=None: _enviar(cid, txt, reply_markup)
bot.enviar_largo = lambda cid, txt, **kw: _enviar(cid, txt)
bot.telegram_api = lambda m, p=None: CALLBACKS.append((m, p or {}))
bot.time.sleep = lambda *_a, **_k: None

ok, fallos = [], []


def check(n, p, x=""):
    ok.append((n, bool(p)))
    if not p:
        fallos.append(n)
    x = x if isinstance(x, str) else str(x)
    print(f"  {'✅' if p else '❌'} {n}{(' · ' + x) if x else ''}")


# ------------------------------------------------------------------- fixtures
LB = "https://lb-api.polymarket.com"
DA = bot.DATA_API
AHORA = int(time.time())

RANKING = {
    "1d": [("ripley86alien", "0xA1", 1080000.0), ("billyMM", "0xA2", 900000.0),
           ("quieto", "0xA3", 800000.0), ("Diabolical-Prize", "0xA4", 700000.0),
           ("balthazar", "0xA5", 600000.0), ("totoro", "0xA6", 500000.0),
           ("concentrado", "0xA7", 400000.0), ("politiquero", "0xA8", 300000.0)],
    "30d": [("Diabolical-Prize", "0xA4", 2100000.0), ("billyMM", "0xA2", 1500000.0),
            ("quieto", "0xA3", 900000.0), ("ripley86alien", "0xA1", 800000.0),
            ("concentrado", "0xA7", 700000.0), ("politiquero", "0xA8", 600000.0),
            ("balthazar", "0xA5", 500000.0), ("totoro", "0xA6", 400000.0)],
}
VOLUMEN = {"0xa1": 5_000_000.0, "0xa2": 40_000_000.0, "0xa4": 1_600_000.0,
           "0xa5": 3_000_000.0, "0xa6": 2_000_000.0, "0xa7": 900_000.0}


def _fill(wallet, i, side="BUY", precio=0.55, usd=91.0, deporte=True, ts=None,
          cid=None, token=None, titulo=None, mk=None):
    ev = f"nfl-2026-week-{i}" if deporte else f"us-election-{i}"
    j = i if mk is None else mk
    return {"type": "TRADE", "side": side, "price": precio,
            "size": (usd / precio) if precio else 0.0,
            "usdcSize": usd, "timestamp": int(ts if ts is not None else AHORA - 60 * i),
            "asset": token or f"tok{wallet[-2:]}_{i}", "outcome": "Yes",
            "conditionId": cid or f"0xcid{wallet[-2:]}_{j}",
            "title": titulo or (f"Kansas City Chiefs win game {i}?" if deporte
                                else f"Will candidate {i} win?"),
            "slug": f"slug-{i}", "eventSlug": ev, "transactionHash": f"0xtx{wallet[-2:]}{i}"}


# perfiles: compras/ventas/mercados/deporte de cada wallet del ranking
PERFILES = {
    "0xA1": {"compras": 40, "ventas": 0, "mercados": 8, "deporte": True},      # bueno
    "0xA2": {"compras": 213, "ventas": 287, "mercados": 20, "deporte": True},  # MM
    "0xA3": {"compras": 1, "ventas": 0, "mercados": 1, "deporte": True},       # inactivo
    "0xA4": {"compras": 30, "ventas": 2, "mercados": 12, "deporte": True},     # bueno
    "0xA5": {"compras": 20, "ventas": 1, "mercados": 6, "deporte": True},      # bueno
    "0xA6": {"compras": 15, "ventas": 0, "mercados": 5, "deporte": True},      # bueno
    "0xA7": {"compras": 25, "ventas": 0, "mercados": 2, "deporte": True},      # concentrado
    "0xA8": {"compras": 25, "ventas": 0, "mercados": 7, "deporte": False},     # poco deporte
}
FILLS = {}
for w, cfg in PERFILES.items():
    nm = max(1, cfg["mercados"])
    lst = [_fill(w, i, "BUY", deporte=cfg["deporte"], mk=(i - 1) % nm)
           for i in range(1, cfg["compras"] + 1)]
    lst += [_fill(w, 500 + i, "SELL", deporte=cfg["deporte"], mk=i % nm)
            for i in range(cfg["ventas"])]
    FILLS[w] = lst
FILLS["0xA1"].append(_fill("0xA1", 900, ts=AHORA - 200 * 3600))   # fuera de 48 h
HOY = time.strftime("%Y-%m-%d", time.gmtime())

LLAMADAS = []
FALLO_RED = {"on": False, "volume": False}


def _lb_get_falso(url, timeout=20):
    LLAMADAS.append(url)
    if FALLO_RED["on"]:
        raise OSError("red caída (simulado)")
    if "/profit?" in url:
        ven = url.split("window=")[1].split("&")[0]
        return [{"proxyWallet": w, "amount": a, "name": n} for n, w, a in RANKING.get(ven, [])]
    if "/volume?" in url:
        if FALLO_RED["volume"]:
            raise OSError("volume caído")
        ven = url.split("window=")[1].split("&")[0]
        return [{"proxyWallet": w, "amount": VOLUMEN.get(w.lower(), 0.0)}
                for n, w, a in RANKING.get(ven, [])]
    if "/activity?" in url:
        w = url.split("user=")[1].split("&")[0]
        return list(FILLS.get(w, []))
    raise AssertionError(f"URL no prevista en el stub: {url}")


bot._lb_get = _lb_get_falso

MIDS = {}          # token → mid real (precio al que entraríamos nosotros)
bot.precio_mid = lambda tok, **kw: MIDS.get(str(tok))

MERCADOS = {}      # condition_id → dict CLOB falso
bot.mercado_clob = lambda cid, **kw: MERCADOS.get(str(cid))


def mercados_fixture():
    """Mercados CLOB falsos: uno con ganador, uno ANULADO (closed sin ganador) y uno vivo."""
    MERCADOS.clear()
    MERCADOS["0xGANA"] = {"closed": True, "tokens": [{"token_id": "tk1", "winner": True},
                                                     {"token_id": "tk2", "winner": False}]}
    MERCADOS["0xANUL"] = {"closed": True, "tokens": [{"token_id": "tk3", "winner": False}]}
    MERCADOS["0xVIVO"] = {"closed": False, "tokens": [{"token_id": "tk4", "winner": False}]}
    return MERCADOS

ESTADO = {"modo": "SEMI", "copy": {}, "copy_señales": []}
bot.cargar_estado = lambda: ESTADO
bot.guardar_estado = lambda e=None: True

PROHIBIDAS = ("enviar_orden", "firmar_orden_v3", "ejecutar_trade", "ejecutar_combo_rfq",
              "ejecutar_semi_aprobado", "crear_rfq", "obtener_identidad_rfq",
              "aceptar_rfq", "reservar_combo", "post_order", "clob_client")
ORIGINALES = {}


def nombres_usados(fn):
    """Nombres/atributos REALMENTE referenciados en el código de fn (los docstrings
    y comentarios NO cuentan: son Constant, no Name)."""
    try:
        arbol = ast.parse(textwrap.dedent(inspect.getsource(fn)))
    except Exception:
        return set()
    out = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Name):
            out.add(nodo.id)
        elif isinstance(nodo, ast.Attribute):
            out.add(nodo.attr)
    return out


def _tripwire(nombre):
    def _f(*a, **k):
        raise AssertionError(f"💸 la sección de copy-trading llamó a {nombre}()")
    return _f


def armar_tripwires():
    for n in PROHIBIDAS:
        if hasattr(bot, n) and not n.startswith("_"):
            ORIGINALES[n] = getattr(bot, n)
            setattr(bot, n, _tripwire(n))


def desarmar_tripwires():
    for n, f in ORIGINALES.items():
        setattr(bot, n, f)


def reset(vacia=True):
    global ESTADO
    MENSAJES.clear(), LOGS.clear(), KBS.clear(), CALLBACKS.clear(), LLAMADAS.clear()
    MIDS.clear(), MERCADOS.clear()
    FALLO_RED["on"] = FALLO_RED["volume"] = False
    bot._LB_CACHE[0], bot._LB_CACHE[1] = 0.0, {}
    ESTADO = {"modo": "SEMI"} if vacia else ESTADO
    if vacia:
        ESTADO["copy"] = {}
        ESTADO["copy_señales"] = []
    return ESTADO


def fuente(fn):
    try:
        return inspect.getsource(fn)
    except Exception:
        return ""


SECCION_FNS = [bot.top_traders, bot.perfil_trader, bot.filtros_perfil, bot.copy_elegir,
               bot.fills_recientes, bot.estado_copy, bot.señales_hoy, bot._caras_de,
               bot.registrar_señal, bot.resolver_señales, bot.resumen_copy,
               bot.texto_copy, bot.cmd_copy, bot.copy_pasada, bot.programar_copy_inicio,
               bot._lb_get, bot._din_lb, bot.es_deporte_copy, bot.nombre_lb]

print("\n" + "=" * 78)
print("A · 💸 GARANTÍA: el copy-trading NO PUEDE gastar dinero (Fase 1 = papel)")
print("=" * 78)

# 1 — interruptores
check("1 · COPY_DINERO=False y COPY_ACTIVO=True (papel ON, dinero OFF)",
      bot.COPY_DINERO is False and bot.COPY_ACTIVO is True,
      f"COPY_DINERO={bot.COPY_DINERO} COPY_ACTIVO={bot.COPY_ACTIVO}")

# 2 — escaneo AST: ninguna función del copy REFERENCIA nada que firme o compre
sucias = []
for fn in SECCION_FNS:
    usados = nombres_usados(fn)
    for p in PROHIBIDAS:
        if p in usados:
            sucias.append(f"{fn.__name__}→{p}")
check("2 · ninguna función 📡 referencia enviar_orden/firmar/ejecutar_*/crear_rfq/reservar",
      not sucias, ", ".join(sucias) or f"{len(SECCION_FNS)} funciones limpias (AST)")

# 3 — tripwire en vivo: una pasada completa con las funciones de compra reventando
reset()
armar_tripwires()
w = "0xA1"
MIDS.update({f"tokA1_{i}": 0.56 for i in range(1, 4)})
try:
    bot.copy_pasada(CHAT)
    gasto = None
except AssertionError as e:
    gasto = str(e)
n3 = len(ESTADO.get("copy_señales") or [])
check("3 · copy_pasada() completa con tripwires armados: anota señales y no gasta",
      gasto is None and n3 > 0, f"{n3} señales · {'💸 ' + str(gasto) if gasto else 'sin llamadas a compra'}")
desarmar_tripwires()

# 4 — el histórico vive en copy_señales, nunca en trades_copiados
reset()
MIDS.update({f"tokA1_{i}": 0.56 for i in range(1, 4)})
bot.copy_pasada(CHAT)
seccion_ok = ("trades_copiados" not in fuente(bot.copy_pasada)
              and "trades_copiados" not in fuente(bot.registrar_señal))
check("4 · escribe en estado['copy_señales'] y la sección NO toca trades_copiados",
      len(ESTADO.get("copy_señales") or []) > 0 and seccion_ok,
      f"{len(ESTADO['copy_señales'])} señales en copy_señales")

# 5 — toda señal nace con ejecutada=False y nada la pone a True
regs = ESTADO.get("copy_señales") or []
check("5 · cada señal nace ejecutada=False y ningún código la pasa a True",
      regs and all(r.get("ejecutada") is False for r in regs)
      and '"ejecutada"] = True' not in SRC and "'ejecutada'] = True" not in SRC,
      f"{len(regs)} señales · ejecutada={regs[0].get('ejecutada') if regs else 'n/d'}")

# 6 — tope PROPIO: con 3 traders × fills de sobra, nunca más de COPY_TOPE_DIA/día
reset()
cp = bot.estado_copy(ESTADO)
cp["traders"] = [{"nombre": "A", "wallet": "0xA1"}, {"nombre": "B", "wallet": "0xA4"},
                 {"nombre": "C", "wallet": "0xA5"}]
cp["ts_eleccion"] = time.time()
cp["ts_ultimo"] = AHORA - 7200
for i in range(1, 41):
    MIDS[f"tokA1_{i}"] = MIDS[f"tokA4_{i}"] = MIDS[f"tokA5_{i}"] = 0.56
bot.copy_pasada(CHAT)
check(f"6 · tope propio: {bot.COPY_TOPE_DIA} señales/día aunque haya fills de sobra",
      len(ESTADO["copy_señales"]) == bot.COPY_TOPE_DIA,
      f"{len(ESTADO['copy_señales'])} registradas (tope {bot.COPY_TOPE_DIA})")

print("\n" + "=" * 78)
print("B · 🏆 TOP REAL EN VIVO (lb-api) — antes era una lista escrita a mano")
print("=" * 78)

# 7 — parseo de profit + volume (caso-insensible) y puestos
reset()
filas = bot.top_traders("1d", 8)
f1 = filas[0]
check("7 · top_traders() → (puesto, nombre, wallet, profit, volumen) real",
      f1[0] == 1 and f1[1] == "ripley86alien" and f1[2] == "0xA1"
      and f1[3] == 1080000.0 and f1[4] == 5_000_000.0 and len(filas) == 8,
      f"#1 {f1[1]} +${f1[3]:,.0f} vol ${f1[4]:,.0f}")

# 8 — caché de 15 min
LLAMADAS.clear()
bot.top_traders("1d", 8)
sin_red = len(LLAMADAS)
bot.top_traders("1d", 8, refrescar=True)
con_refresco = len(LLAMADAS) - sin_red
check("8 · caché 15 min: 2ª llamada sin red, refrescar=True sí llama",
      sin_red == 0 and con_refresco >= 1, f"cache={sin_red} llamadas · refresco={con_refresco}")

# 9 — ventana inválida → 1d
LLAMADAS.clear()
bot._LB_CACHE[0], bot._LB_CACHE[1] = 0.0, {}
bot.top_traders("1h", 5)
check("9 · ventana no soportada ('1h') cae a '1d' en vez de petar (400 en la API)",
      any("window=1d" in u for u in LLAMADAS) and not any("window=1h" in u for u in LLAMADAS),
      f"urls: {[u.split('?')[1] for u in LLAMADAS if '/profit' in u]}")

# 10 — red caída → [] (o caché) y log, sin excepción
reset()
bot.top_traders("1d", 8)                      # llena caché de 1d
FALLO_RED["on"] = True
res = bot.top_traders("1d", 8)                # caché caliente → sirve la anterior
bot._LB_CACHE[0], bot._LB_CACHE[1] = 0.0, {}  # caché fría → ahora sí intenta la red
res2 = bot.top_traders("1d", 8)
check("10 · lb-api caído: con caché sirve la anterior; sin caché devuelve [] y lo loguea",
      len(res) == 8 and res2 == [] and any("lb-api sin respuesta" in l for l in LOGS),
      f"con caché={len(res)} filas · sin caché={len(res2)} · "
      f"log: {[l for l in LOGS if 'lb-api' in l][:1]}")

# 11 — /volume caído pero /profit bien → margen n/d
reset()
FALLO_RED["volume"] = True
f = bot.top_traders("1d", 3)[0]
MENSAJES.clear(), KBS.clear()
bot.cmd_top(CHAT, "1d")
check("11 · si /volume falla el ranking sigue saliendo (volumen 0 → margen 'n/d')",
      f[4] == 0.0 and MENSAJES and "n/d" in MENSAJES[-1], f"vol={f[4]}")

# 12 — texto y botones de cmd_top
reset()
bot.cmd_top(CHAT, "30d")
t, kb = MENSAJES[-1], KBS[-1]
botones = [b["callback_data"] for b in kb["inline_keyboard"][0]]
etiquetas = [b["text"] for b in kb["inline_keyboard"][0]]
check("12 · cmd_top('30d'): ranking real + wallets + 4 botones lb:1d/7d/30d/all",
      "30 días" in t and "Diabolical-Prize" in t and "0xA4" in t[:1200]
      and botones == ["lb:1d", "lb:7d", "lb:30d", "lb:all"]
      and any(b.startswith("✅") for b in etiquetas)
      and "$2.10M" in t, f"botones={botones} · etiquetas={etiquetas}")

# 13 — sin datos: el botón NO inventa cifras
reset()
FALLO_RED["on"] = True
bot._LB_CACHE[0], bot._LB_CACHE[1] = 0.0, {}
bot.cmd_top(CHAT)
check("13 · sin ranking: avisa de que lb-api no respondió (no enseña una lista falsa)",
      "no respondió" in MENSAJES[-1] and "pleaseplease123" not in MENSAJES[-1]
      and "pleaseplease123" not in SRC, MENSAJES[-1][:70].replace("\n", " "))

print("\n" + "=" * 78)
print("C · 📡 FILTROS AUTOMÁTICOS Y ELECCIÓN DE LOS 5 (top 30d)")
print("=" * 78)

# 14 — perfil real: sólo cuenta las últimas 48 h
reset()
p = bot.perfil_trader("0xA1")
check("14 · perfil_trader(): compras/ventas/mercados/%deporte de las últimas 48 h",
      p["compras"] == 40 and p["ventas"] == 0 and p["ratio"] == 0.0
      and p["mercados"] >= 8 and 0.9 <= p["deporte"] <= 1.0 and p["n"] == 40,
      f"compras={p['compras']} ventas={p['ventas']} mercados={p['mercados']} "
      f"deporte={p['deporte'] * 100:.0f}% (fill de hace 200 h excluido: n={p['n']})")

# 15 — sin actividad reciente → inactivo
reset()
FILLS["0xAZ"] = []
pz = bot.perfil_trader("0xAZ")
okk, mot = bot.filtros_perfil(pz)
check("15 · wallet sin compras en 48 h → descartado como 'inactivo'",
      okk is False and "inactivo" in mot and pz["compras"] == 0, mot)

# 16 — market maker fuera
reset()
pmm = bot.perfil_trader("0xA2")
okk, mot = bot.filtros_perfil(pmm)
check("16 · market maker (213 compras / 287 ventas) → fuera, con el motivo claro",
      okk is False and "market maker" in mot and pmm["ratio"] > 0.5,
      f"ratio={pmm['ratio']:.2f} · {mot[:60]}")

# 17 — concentrado en 1-2 mercados fuera
reset()
pc = bot.perfil_trader("0xA7")
okk, mot = bot.filtros_perfil(pc)
check("17 · concentrado en 2 mercados → fuera (un solo acierto no es sistema)",
      okk is False and "concentrado" in mot, mot)

# 18 — poco deporte fuera / bastante deporte dentro
reset()
pp = bot.perfil_trader("0xA8")
okk8, mot8 = bot.filtros_perfil(pp)
okk1, mot1 = bot.filtros_perfil(bot.perfil_trader("0xA1"))
check("18 · 0% deporte → fuera; 100% deporte → 'activo'",
      okk8 is False and "deporte" in mot8 and okk1 is True and "activo" in mot1,
      f"{mot8[:34]} ‖ {mot1[:44]}")

# 19 — elección: los 5 primeros del ranking 30d QUE PASAN los filtros
reset()
eleg = bot.copy_elegir(ESTADO)
nombres = [e["nombre"] for e in eleg]
check("19 · copy_elegir(): top 30d filtrado en orden de ranking (MM/inactivo fuera)",
      nombres == ["Diabolical-Prize", "ripley86alien", "balthazar", "totoro"]
      and all(e["wallet"] for e in eleg) and eleg[0]["puesto"] == 1
      and len(eleg) <= bot.COPY_N_TRADERS
      and ESTADO["copy"]["traders"] == eleg, f"{nombres}")

# 20 — ranking vacío: conserva la lista anterior (no se queda ciego)
reset()
bot.copy_elegir(ESTADO)
antes = [e["wallet"] for e in ESTADO["copy"]["traders"]]
bot._LB_CACHE[0], bot._LB_CACHE[1] = 0.0, {}    # sin caché: la red tiene que fallar de verdad
FALLO_RED["on"] = True
res = bot.copy_elegir(ESTADO)
check("20 · si lb-api no responde, NO borra la lista de traders vigilados",
      [e["wallet"] for e in res] == antes and antes, f"{antes}")

# 21 — anuncio sólo cuando hay chat_id (la reevaluación diaria no spamea)
reset()
MENSAJES.clear()
bot.copy_elegir(ESTADO)
sin_chat = len(MENSAJES)
bot.copy_elegir(ESTADO, chat_id=CHAT)
check("21 · la 1ª elección se anuncia en el chat; la diaria, no",
      sin_chat == 0 and len(MENSAJES) == 1 and "vigilo a" in MENSAJES[-1],
      f"mensajes sin chat_id={sin_chat} · con chat_id={len(MENSAJES)}")

print("\n" + "=" * 78)
print("D · 📨 SEÑALES: dos precios, deriva, tope propio y dedup")
print("=" * 78)

# 22 — registro con los DOS precios y sus cuotas
reset()
fill = _fill("0xA1", 1, precio=0.50, usd=120.0, deporte=True, cid="0xZZ", token="tkZ")
r = bot.registrar_señal(ESTADO, "ripley86alien", "0xA1", fill, 0.545)
check("22 · registrar_señal(): precio suyo y NUESTRO + cuotas + deriva en puntos",
      r["precio_trader"] == 0.5 and r["precio_nuestro"] == 0.545
      and r["cuota_trader"] == 2.0 and r["cuota_nuestro"] == 1.83
      and abs(r["deriva_pts"] - 4.5) < 0.01 and r["usd_trader"] == 120.0
      and r["resuelta"] is False and r["trader"] == "ripley86alien",
      f"él {r['precio_trader']} (cuota {r['cuota_trader']}) · nosotros {r['precio_nuestro']} "
      f"(cuota {r['cuota_nuestro']}) · deriva {r['deriva_pts']:+} pts")

# 23 — en_rango_combo: sólo sirve para combo si la cuota cae en tu rango
reset()
r_bajo = bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 2, token="tB"), 0.95)
r_ok = bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 3, token="tC"), 0.55)
check(f"23 · en_rango_combo: cuota {bot.CUOTA_MIN}-{bot.CUOTA_MAX} → 0.95 NO, 0.55 SÍ",
      r_bajo["en_rango_combo"] is False and r_ok["en_rango_combo"] is True,
      f"0.95→{r_bajo['en_rango_combo']} (cuota {r_bajo['cuota_nuestro']}) · "
      f"0.55→{r_ok['en_rango_combo']} (cuota {r_ok['cuota_nuestro']})")

# 24 — deporte detectado por eventSlug (clave para tu rango)
reset()
rd = bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 4, deporte=False, token="tD"), 0.5)
check("24 · marca deporte por eventSlug/título (NFL sí, elecciones no)",
      r["deporte"] is True and rd["deporte"] is False,
      f"nfl→{r['deporte']} · us-election→{rd['deporte']}")

# 25 — precios imposibles: no se registra nada
reset()
nulos = [bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 5, precio=0.0, token="x"), 0.5),
         bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 6, precio=1.0, token="y"), 0.5),
         bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 7, token="z"), None),
         bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 8, token="w"), 0)]
check("25 · precio 0/1 o sin mid nuestro → señal NO registrada (evita basura)",
      all(x is None for x in nulos) and not ESTADO.get("copy_señales"),
      f"{len(ESTADO.get('copy_señales') or [])} en el histórico")

# 26 — señales_hoy cuenta sólo las de hoy (UTC)
reset()
ESTADO["copy_señales"] = [
    {"dia": time.strftime("%Y-%m-%d", time.gmtime()), "resuelta": True},
    {"dia": time.strftime("%Y-%m-%d", time.gmtime()), "resuelta": False},
    {"dia": "2026-09-10", "resuelta": True}]
check("26 · señales_hoy(): cuenta las de hoy en UTC, no el histórico entero",
      bot.señales_hoy(ESTADO) == 2, f"hoy={bot.señales_hoy(ESTADO)} de 3")

# 27 — tope diario: la 6ª no entra
reset()
for i in range(bot.COPY_TOPE_DIA):
    bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 10 + i, token=f"tp{i}"), 0.5)
extra = bot.registrar_señal(ESTADO, "t", "0xA1", _fill("0xA1", 99, token="tpX"), 0.5)
check(f"27 · con {bot.COPY_TOPE_DIA} señales hoy, la siguiente devuelve None",
      extra is None and len(ESTADO["copy_señales"]) == bot.COPY_TOPE_DIA,
      f"{len(ESTADO['copy_señales'])} en el histórico")

# 28 — señal tardía (deriva > 5 pts) fuera; dentro de 5 pts entra
reset()
cp = bot.estado_copy(ESTADO)
cp["traders"] = [{"nombre": "ripley86alien", "wallet": "0xA1"}]
cp["ts_eleccion"] = time.time()
cp["ts_ultimo"] = AHORA - 7200
MIDS["tokA1_1"] = 0.70        # él a 0.55 → +15 pts: tarde
MIDS["tokA1_2"] = 0.57        # +2 pts: sirve
MIDS["tokA1_3"] = 0.55        # 0 pts
bot.copy_pasada(CHAT)
señ = ESTADO["copy_señales"]
check(f"28 · deriva >{int(bot.COPY_DERIVA_MAX * 100)} pts → señal TARDÍA descartada (y logueada)",
      len(señ) == 2 and all(s["deriva_pts"] <= 5.01 for s in señ)
      and any("TARDÍA" in l for l in LOGS),
      f"{len(señ)} registradas · {[s['deriva_pts'] for s in señ]} · "
      f"{[l for l in LOGS if 'TARDÍA' in l][:1]}")

# 29 — dedup por tx+asset y poda de vistos a 7 días
reset()
cp = bot.estado_copy(ESTADO)
cp["traders"] = [{"nombre": "ripley86alien", "wallet": "0xA1"}]
cp["ts_eleccion"] = time.time()
cp["ts_ultimo"] = AHORA - 7200
for i in range(1, 4):
    MIDS[f"tokA1_{i}"] = 0.56
bot.copy_pasada(CHAT)
primera = len(ESTADO["copy_señales"])
cp["ts_ultimo"] = AHORA - 7200                      # repite el mismo rango
cp["vistos"]["txVIEJA|assetVIEJO"] = int(time.time()) - 9 * 86400
bot.copy_pasada(CHAT)
check("29 · 2ª pasada sobre los mismos fills: 0 señales nuevas y poda 'vistos' >7 días",
      primera == 3 and len(ESTADO["copy_señales"]) == 3
      and "txVIEJA|assetVIEJO" not in cp["vistos"] and cp["ts_ultimo"] > AHORA - 60,
      f"1ª={primera} · 2ª={len(ESTADO['copy_señales']) - primera} nuevas · "
      f"vistos={len(cp['vistos'])}")

print("\n" + "=" * 78)
print("E · 🏁 RESOLUCIÓN: ¿acertó la señal? PnL teórico a $5 (nuestro y suyo)")
print("=" * 78)

# 30 — _caras_de: ganador / anulada / vivo
reset()
mercados_fixture()
c1, c2, c3 = bot._caras_de("0xGANA"), bot._caras_de("0xANUL"), bot._caras_de("0xVIVO")
check("30 · _caras_de(): ganador → caras · closed sin ganador → 'anulada' · vivo → None",
      isinstance(c1, dict) and c1["tk1"]["winner"] is True and c2 == "anulada" and c3 is None,
      f"gana={bool(c1)} · anulada={c2} · vivo={c3}")

# 31/32/33 — PnL de ganador, perdedor y anulada
reset()
mercados_fixture()
ESTADO["copy_señales"] = [
    {"condition_id": "0xGANA", "token": "tk1", "precio_trader": 0.50,
     "precio_nuestro": 0.545, "deriva_pts": 4.5, "retraso_s": 200, "trader": "A",
     "dia": HOY, "resuelta": False},
    {"condition_id": "0xGANA", "token": "tk2", "precio_trader": 0.60,
     "precio_nuestro": 0.62, "deriva_pts": 2.0, "retraso_s": 200, "trader": "A",
     "dia": HOY, "resuelta": False},
    {"condition_id": "0xANUL", "token": "tk3", "precio_trader": 0.50,
     "precio_nuestro": 0.50, "deriva_pts": 0.0, "retraso_s": 200, "trader": "B",
     "dia": HOY, "resuelta": False}]
n = bot.resolver_señales(ESTADO)
s1, s2, s3 = ESTADO["copy_señales"]
check("31 · señal GANADORA: PnL a $5 al precio nuestro y al suyo (2 cifras distintas)",
      n == 3 and s1["senal_acerto"] is True and s1["resuelta"] is True
      and abs(s1["pnl_papel_nuestro"] - 5 * (1 / 0.545 - 1)) < 0.01
      and abs(s1["pnl_papel_trader"] - 5 * (1 / 0.50 - 1)) < 0.01,
      f"nuestro ${s1['pnl_papel_nuestro']} (a 0.545) · suyo ${s1['pnl_papel_trader']} (a 0.50)")
check("32 · señal PERDEDORA: −$5 a ambos precios y senal_acerto=False",
      s2["senal_acerto"] is False and s2["pnl_papel_nuestro"] == -5.0
      and s2["pnl_papel_trader"] == -5.0, f"${s2['pnl_papel_nuestro']}")
check("33 · mercado ANULADO: PnL 0, acierto None, contado aparte (no ensucia el ROI)",
      s3["anulada"] is True and s3["senal_acerto"] is None
      and s3["pnl_papel_nuestro"] == 0.0 and s3["pnl_papel_trader"] == 0.0,
      f"anulada={s3['anulada']} pnl={s3['pnl_papel_nuestro']}")

# 34 — tope de mercados consultados por pasada (no estira el PASADA_LOCK)
reset()
mercados_fixture()
CONTADOR = {"n": 0}


def _mc_contador(cid, **kw):
    CONTADOR["n"] += 1
    return MERCADOS.get(str(cid))


ORIG_MC = bot.mercado_clob
bot.mercado_clob = _mc_contador
ESTADO["copy_señales"] = [{"condition_id": "0xVIVO", "token": "tk4", "resuelta": False,
                           "trader": "A", "dia": HOY, "precio_nuestro": 0.5,
                           "precio_trader": 0.5, "deriva_pts": 0, "retraso_s": 1}
                          for _ in range(bot.COPY_RESOLVER_POR_RONDA + 8)]
bot.resolver_señales(ESTADO)
bot.mercado_clob = ORIG_MC
check(f"34 · resolver acota a {bot.COPY_RESOLVER_POR_RONDA} mercados por pasada "
      f"(había {bot.COPY_RESOLVER_POR_RONDA + 8} pendientes)",
      CONTADOR["n"] == bot.COPY_RESOLVER_POR_RONDA, f"{CONTADOR['n']} consultas CLOB")

# 35 — resumen: acierto, ROI al precio nuestro, deriva, retraso y por trader
reset()
ESTADO["copy"] = {"ts_inicio": time.time() - 3 * 86400, "traders": [{"nombre": "A"}]}
ESTADO["copy_señales"] = [
    {"resuelta": True, "senal_acerto": True, "anulada": False, "pnl_papel_nuestro": 4.17,
     "pnl_papel_trader": 5.0, "deriva_pts": 4.5, "retraso_s": 200, "trader": "A",
     "dia": HOY, "en_rango_combo": True},
    {"resuelta": True, "senal_acerto": False, "anulada": False, "pnl_papel_nuestro": -5.0,
     "pnl_papel_trader": -5.0, "deriva_pts": 1.5, "retraso_s": 100, "trader": "A",
     "dia": HOY, "en_rango_combo": True},
    {"resuelta": True, "senal_acerto": True, "anulada": False, "pnl_papel_nuestro": 3.0,
     "pnl_papel_trader": 4.0, "deriva_pts": -0.5, "retraso_s": 400, "trader": "B",
     "dia": HOY, "en_rango_combo": False},
    {"resuelta": True, "anulada": True, "senal_acerto": None, "pnl_papel_nuestro": 0.0,
     "pnl_papel_trader": 0.0, "deriva_pts": 0.0, "retraso_s": 50, "trader": "B",
     "dia": HOY, "en_rango_combo": True},
    {"resuelta": False, "trader": "B", "dia": HOY, "deriva_pts": 2.0,
     "retraso_s": 90, "en_rango_combo": True}]
rr = bot.resumen_copy(ESTADO)
roi_exp = (4.17 - 5.0 + 3.0) / (3 * 5.0) * 100
check("35 · resumen_copy(): acierto 66.7%, ROI AL PRECIO NUESTRO, deriva y desglose",
      rr["resueltas"] == 3 and rr["anuladas"] == 1 and rr["aciertos"] == 2
      and abs(rr["acierto_pct"] - 66.67) < 0.05 and abs(rr["roi_nuestro"] - roi_exp) < 0.05
      and abs(rr["deriva_med"] - 1.5) < 0.01 and rr["por_trader"]["A"]["n"] == 2
      and rr["hoy"] == 5 and rr["tope"] == bot.COPY_TOPE_DIA and rr["dias"] == 4
      and rr["en_rango"] == 4,
      f"acierto {rr['acierto_pct']:.1f}% · ROI nuestro {rr['roi_nuestro']:+.1f}% · "
      f"PnL ${rr['pnl_nuestro']} vs suyo ${rr['pnl_trader']} · deriva {rr['deriva_med']} pts")

# 36 — texto de /copy: papel, $0 y el criterio de Fase 2 (con los datos del test 35)
txt = bot.texto_copy(ESTADO)
check("36 · /copy enseña PAPEL/$0, ROI nuestro, por trader y el criterio de Fase 2",
      "PAPEL" in txt and "NO compra" in txt and "≥30 señales resueltas" in txt
      and "ROI" in txt and "Por trader" in txt and "48.8%" in txt
      and "66.7%" in txt,
      f"{len(txt)} chars · Fase 2: ≥30 resueltas + ROI>0 al precio nuestro")

print("\n" + "=" * 78)
print("F · 🔌 INTEGRACIÓN con el bot (auto_loop, teclado, /copy, versiones)")
print("=" * 78)

# 37 — programación de la primera ronda
reset()
bot.NEXT_COPY_TS, bot.NEXT_COPY_RESUMEN_TS = 0.0, 0.0
t0 = time.time()
bot.programar_copy_inicio()
check("37 · programar_copy_inicio(): 1ª ronda a los ~90 s e informe diario programado",
      80 <= bot.NEXT_COPY_TS - t0 <= 100
      and abs(bot.NEXT_COPY_RESUMEN_TS - t0 - bot.COPY_RESUMEN_CADA_S) < 5,
      f"NEXT_COPY_TS en {bot.NEXT_COPY_TS - t0:.0f} s · informe en "
      f"{(bot.NEXT_COPY_RESUMEN_TS - t0) / 3600:.1f} h")

# 38 — la ronda vive dentro del auto_loop, con candado y sin poder romperlo
bloque = SRC.split("# 📡 v12.9.0: seguimiento en papel")[1].split("# v12.7: auto-curación")[0]
check("38 · auto_loop lanza copy_pasada con PASADA_LOCK, guardado por COPY_ACTIVO/CHAT_ID "
      "y try/except",
      "copy_pasada(CHAT_ID)" in bloque and "PASADA_LOCK" in bloque
      and "COPY_ACTIVO" in bloque and "NEXT_COPY_TS" in bloque
      and "copy_loop error" in bloque and bloque.count("except Exception") >= 1
      and "global NEXT_PASADA_TS, NEXT_AUDITORIA_TS, NEXT_COPY_TS" in SRC,
      f"{len(bloque.splitlines())} líneas de bloque")

# 39 — teclado y comandos
check("39 · botón 📡 Copy en el teclado + handler + /copy y sus alias",
      '{"text": "📡 Copy"}' in SRC and 'elif text == "📡 Copy":' in SRC
      and "cmd_copy(chat_id)" in SRC
      and 'text in ("/copy", "/copytrading", "/señales", "/senales")' in SRC,
      "teclado row 2 · /copy · /copytrading · /señales")

# 40 — callback lb: contesta y cambia de ventana
reset()
bot._LB_CACHE[0], bot._LB_CACHE[1] = 0.0, {}
src_cb = fuente(bot.procesar_callback)
check("40 · callback lb:<ventana> antes que sm: (SEMI intacto) y contesta la pulsación",
      'data.startswith("lb:")' in src_cb and "answerCallbackQuery" in src_cb
      and src_cb.index('data.startswith("lb:")') < src_cb.index('data.startswith("sm:")')
      and 'cmd_top(cid, data.split(":", 1)[1])' in src_cb, "lb: → cmd_top(ventana)")

# 41 — versiones y limpieza de la lista falsa
check("41 · v12.9.0 en cabecera/log/start/status/reclamar y SIN lista hardcodeada",
      SRC.splitlines()[3].count("v12.9.0") == 1 and 'log("v12.9.0 iniciado")' in SRC
      and "POLY COMBOS BOT v12.9.0" in SRC and "ESTADO v12.9.0" in SRC
      and "RECLAMAR v12.9.0" in SRC and "v12.8.4" in SRC
      and not any(x in SRC for x in ("pleaseplease123 +$1.0M", "ferrariChampions2026")),
      f"cabecera: {SRC.splitlines()[3][:60]}")

# 42 — no-regresión de v12.8.4 (SEMI real + ventaja 5%)
check("42 · v12.8.4 intacto: SEMI propone, restaurar_modo, ventaja 5%, un solo cmd_top",
      SRC.count("def proponer_combo_semi(") == 1 and SRC.count("def restaurar_modo(") == 1
      and SRC.count("VENTAJA_MIN_EV = 0.05") == 1 and SRC.count("def cmd_top(") == 1
      and SRC.count("def ejecutar_combo_rfq(") == 1 and SRC.count("def main()") == 1
      and "PROPUESTA_VALIDA_S = 600" in SRC,
      f"{len(SRC.splitlines())} líneas · caducidad SEMI {bot.PROPUESTA_VALIDA_S // 60} min")

# 43 — /copy con el estado vacío no peta
reset()
MENSAJES.clear()
bot.cmd_copy(CHAT)
check("43 · /copy con cero datos: contesta el panel (sin traders aún) y no revienta",
      len(MENSAJES) == 1 and "Aún sin traders elegidos" in MENSAJES[-1]
      and "Ninguna resuelta aún" in MENSAJES[-1], MENSAJES[-1][:60].replace("\n", " "))

# 44 — informe diario: se envía una vez y se reprograma
reset()
cp = bot.estado_copy(ESTADO)
cp["traders"] = [{"nombre": "ripley86alien", "wallet": "0xA1"}]
cp["ts_eleccion"] = time.time()
cp["ts_inicio"] = time.time() - 86400   # ya arrancó ayer: la 1ª pasada no reinicia el calendario
cp["ts_ultimo"] = AHORA - 600        # 10 min atrás: los fills i=1..10 entran en el rango
bot.NEXT_COPY_RESUMEN_TS = time.time() - 10
MIDS["tokA1_1"] = MIDS["tokA1_2"] = MIDS["tokA1_3"] = 0.56
bot.copy_pasada(CHAT)
info = [m for m in MENSAJES if "COPY-TRADING EN PAPEL" in m]
segundo_ts = bot.NEXT_COPY_RESUMEN_TS
bot.copy_pasada(CHAT)
check("44 · informe diario: se manda 1 vez, cuenta el envío y se reprograma a +24 h",
      len(info) == 1 and cp["informes"] == 1 and segundo_ts > time.time() + 80000
      and len([m for m in MENSAJES if "COPY-TRADING EN PAPEL" in m]) == 1,
      f"informes={cp['informes']} · próximo en {(segundo_ts - time.time()) / 3600:.1f} h")

print("\n" + "=" * 78)
print("G · 🔁 COMPRAS REPETIDAS: el tope cuenta MERCADOS, no fills (caso real de hoy)")
print("=" * 78)

# 45 — nombres: lb-api a veces da la wallet cruda como nombre
reset()
feo = "0x2c335066FE58fe9237c3d3Dc7b275C2a034a0563-1759935795465"
n1 = bot.nombre_lb({"name": feo, "pseudonym": feo}, "0x2c335066FE58fe9237c3d3Dc7b275C2a034a0563")
n2 = bot.nombre_lb({"name": "ripley86alien", "pseudonym": "ripley86alien"}, "0xA1")
n3 = bot.nombre_lb({"name": "", "pseudonym": None}, "0xA9abcdef12")
check("45 · nombre_lb(): apodo legible sí; wallet cruda de 48 chars, no",
      n1 == "0x2c335066" and n2 == "ripley86alien" and n3 == "0xA9abcdef",
      f"{n1} · {n2} · {n3}")

# 46 — 48 compras en la MISMA posición → 1 señal fusionada
reset()
for i in range(48):
    f = _fill("0xA1", 1, precio=0.54, usd=150.0, token="tkMISMO", cid="0xMISMO")
    f["transactionHash"], f["timestamp"] = f"0xtx{i}", AHORA - 60 * (i + 1)
    bot.registrar_señal(ESTADO, "pleaseplease123", "0xA1", f, round(0.545 + i * 0.001, 4))
r0 = ESTADO["copy_señales"][0]
check("46 · 48 compras en la misma posición → 1 señal (importe sumado, precio de la 1ª)",
      len(ESTADO["copy_señales"]) == 1 and r0["escaladas"] == 47
      and abs(r0["usd_trader"] - 48 * 150.0) < 0.01 and r0["precio_trader"] == 0.54
      and abs(r0["precio_nuestro_max"] - 0.592) < 1e-6 and bot.señales_hoy(ESTADO) == 1,
      f"1 señal · escaladas {r0['escaladas']} · ${r0['usd_trader']:,.0f} suyos · "
      f"entrada {r0['precio_trader']} · máx nuestro {r0['precio_nuestro_max']}")

# 47 — 24 fills en 2 posiciones → 2 señales (no 5, no 24)
reset()
cp = bot.estado_copy(ESTADO)
cp["traders"] = [{"nombre": "A", "wallet": "0xA1"}]
cp["ts_eleccion"] = time.time()
cp["ts_ultimo"] = AHORA - 7200
FILLS["0xA1"] = []
for mk in (1, 2):
    for j in range(12):
        f = _fill("0xA1", j, precio=0.55, token=f"tokA1_{mk}", cid=f"0xcidA1_{mk}")
        f["transactionHash"] = f"0xtx{mk}_{j}"
        f["timestamp"] = AHORA - 30 * (j + 1) - 100 * mk
        FILLS["0xA1"].append(f)
MIDS["tokA1_1"] = MIDS["tokA1_2"] = 0.56
bot.copy_pasada(CHAT)
check("47 · 24 fills en 2 posiciones → 2 señales y UNA línea de log agrupada",
      len(ESTADO["copy_señales"]) == 2
      and sorted(s["escaladas"] for s in ESTADO["copy_señales"]) == [11, 11]
      and sum(1 for l in LOGS if "fusionada" in l) == 1
      and any("22 compra(s) repetida(s) fusionada(s)" in l for l in LOGS),
      f"{len(ESTADO['copy_señales'])} señales · escaladas "
      f"{[s['escaladas'] for s in ESTADO['copy_señales']]} · "
      f"{[l for l in LOGS if 'fusionada' in l]}")

# 48 — réplica del caso REAL medido hoy (102 fills → 4 posiciones, una ya movida)
reset()
cp = bot.estado_copy(ESTADO)
cp["traders"] = [{"nombre": "pleaseplease123", "wallet": "0xPP"}]
cp["ts_eleccion"] = time.time()
cp["ts_ultimo"] = AHORA - 3600
POS = [("tkPP_1", 48, 0.54, 0.545), ("tkPP_2", 40, 0.46, 0.465),
       ("tkPP_3", 10, 0.573, 0.59), ("tkPP_4", 4, 0.74, 0.955)]   # la 4ª: +21.5 pts
FILLS["0xPP"] = []
k = 0
for tok, nfill, p_el, p_no in POS:
    MIDS[tok] = p_no
    for j in range(nfill):
        f = _fill("0xPP", j, precio=p_el, usd=150.0, token=tok, cid="0x" + tok)
        f["transactionHash"], f["timestamp"] = f"0xtxPP{k}", AHORA - 30 - k * 5
        k += 1
        FILLS["0xPP"].append(f)
bot.copy_pasada(CHAT)
señ = ESTADO["copy_señales"]
txt = bot.texto_copy(ESTADO)
check("48 · caso real (102 fills/4 posiciones): 3 señales + la tardía fuera + panel honesto",
      len(señ) == 3 and any("TARDÍA" in l for l in LOGS)
      and sum(x["escaladas"] for x in señ) == 47 + 39 + 9
      and all(x["deriva_pts"] <= 5.01 for x in señ)
      and "compras repetidas fusionadas" in txt,
      f"{len(señ)} señales · escaladas {[x['escaladas'] for x in señ]} · "
      f"${sum(x['usd_trader'] for x in señ):,.0f} suyos · "
      f"{sum(x['escaladas'] for x in señ)} fusionadas en el panel")

# ---------------------------------------------------------------------- resumen
print("\n" + "=" * 78)
tot = len(ok)
bien = sum(1 for _, p in ok if p)
print(f"RESULTADO: {bien}/{tot} OK" + (f" · FALLOS: {fallos}" if fallos else " · TODO VERDE ✅"))
print("=" * 78)
if fallos:
    print("❌ queda trabajo:", ", ".join(str(f) for f in fallos))
    sys.exit(1)
print("✅ v12.9.0 lista: 🏆 top real en vivo + 📡 copy-trading EN PAPEL ($0).")
print("   Garantizado por los tests 1-6: ninguna ruta desde el copy a firmar/comprar.")
sys.exit(0)
