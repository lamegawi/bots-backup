#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_v1282.py — v12.8.2: el cierre 🔒 de un combo vuelve a ser posible
=======================================================================
Reproduce el fallo REAL visto en producción (log 11-sep 17:49:56):
  [CIERRE] sin precio vivo: no se puede dimensionar la venta
Causa: `vivo_de()` pedía el mid con `legs[].position_id` (id del CATÁLOGO de
combos) y el CLOB responde 404 a esos ids — sólo sirve el token_id real.
Los tests 1-6 son EN VIVO contra el catálogo y el CLOB de Polymarket.
"""
import importlib.util, json, os, sys, time, urllib.request

RUTA = sys.argv[1] if len(sys.argv) > 1 else "/home/user/v12.8_reclamar/bot_v1282.py"
spec = importlib.util.spec_from_file_location("bot", RUTA)
bot = importlib.util.module_from_spec(spec); sys.modules["bot"] = bot
spec.loader.exec_module(bot)
bot.WALLET = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"
MENSAJES = []
bot.log = lambda s: None
bot.enviar = lambda cid, txt, **kw: (MENSAJES.append(txt), True)[1]
ok = []
def check(n, p, x=""):
    ok.append((n, bool(p))); print(f"  {'✅' if p else '❌'} {n}{(' · '+x) if x else ''}")

SRC = open(RUTA, encoding="utf-8").read()

# ---------------------------------------------------------------- utilidades
def get(u, timeout=20):
    q = urllib.request.Request(u, headers={"User-Agent": "poly-combos-bot"})
    with urllib.request.urlopen(q, timeout=timeout) as r:
        return json.loads(r.read().decode())

class TimeShim:
    """Delega en `time` pero REGISTRA los sleep (para probar la pausa anti-429)."""
    def __init__(self, mod, reg): self._m, self.reg = mod, reg
    def __getattr__(self, k): return getattr(self._m, k)
    def sleep(self, s): self.reg.append(s)

REAL_TIME = bot.time
REAL_VIVO = bot.vivo_de
REAL_MERCADO = bot.mercado_clob

# =========================================================== EN VIVO (1-6)
print("\n🌐 TESTS EN VIVO (catálogo de combos + CLOB de Polymarket)")
legs_vivas = []
try:
    cat = get("https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets?limit=12")
    ms = cat.get("markets") or cat.get("data") or cat
    if isinstance(ms, dict):
        ms = list(ms.values())[0]
    for m in (ms if isinstance(ms, list) else []):
        cid, pids, outs = m.get("condition_id"), m.get("position_ids") or [], m.get("outcomes") or []
        if cid and pids:
            legs_vivas.append({"question": str(m.get("question") or m.get("title") or "leg"),
                               "slug": m.get("slug") or "", "condition_id": cid,
                               "position_id": str(pids[0]), "outcome": str(outs[0]) if outs else "Yes",
                               "yes_price": None})
        if len(legs_vivas) >= 2:
            break
except Exception as e:
    print("  ⚠️ sin catálogo vivo:", str(e)[:60])

if len(legs_vivas) >= 2:
    l0, l1 = legs_vivas[0], legs_vivas[1]
    mid_pid = bot.precio_mid(l0["position_id"])
    check("1. el position_id del catálogo NO da precio (el bug)", mid_pid is None,
          f"mid(position_id)={mid_pid}")
    tok0 = bot.token_clob_de_leg(l0)
    check("2. token_clob_de_leg resuelve el token REAL del CLOB",
          bool(tok0) and tok0.isdigit() and tok0 != l0["position_id"], f"{str(tok0)[:20]}…")
    mid0 = bot.precio_mid(tok0)
    check("3. ese token real SÍ cotiza", isinstance(mid0, float) and 0 < mid0 < 1, f"mid={mid0}")
    op_combo = {"tipo": "combo_rfq", "question": "combo de prueba", "legs": [l0, l1],
                "size_shares": 10.0, "stake_dolares": 5.0,
                "combo_yes_position_id": "9" * 40, "real_token": "9" * 40,
                "copiado_en": "2026-09-11T18:00:00+00:00", "status": "abierto"}
    tok1 = bot.token_clob_de_leg(l1); mid1 = bot.precio_mid(tok1)
    vivo = bot.vivo_de(op_combo)
    exp = (mid0 * mid1) if (mid0 and mid1) else None
    check("4. vivo_de(combo) ya devuelve el producto de mids",
          isinstance(vivo, float) and vivo > 0 and exp and abs(vivo - exp) < 1e-9,
          f"vivo={vivo:.5f} esperado={exp:.5f}" if vivo and exp else f"vivo={vivo}")
    # leg REAL del estado del servidor (op antigua: outcome null → índice 0)
    leg_srv = {"q": "Genoa: Thiago Seyboth Wild vs Francesco Ferrari",
               "question": "Genoa: Thiago Seyboth Wild vs Francesco Ferrari",
               "condition_id": "0xe0b5ba4d3407f7eb578d55fe41b34aeb99f0d32b8a32f1da0b330c05b0a30ae6",
               "pid": "724302561751616008899238",
               "position_id": "724302561751616008899238", "outcome": None, "yes_price": 0.605}
    tok_srv = bot.token_clob_de_leg(leg_srv)
    check("5. leg antigua del servidor (sin outcome) → token por índice 0",
          bool(tok_srv) and tok_srv.isdigit() and tok_srv != leg_srv["position_id"],
          f"{str(tok_srv)[:20]}… (pid {leg_srv['position_id'][:12]}…)")
    n_http = [0]
    real_mc = bot.mercado_clob
    def contar(cid):
        n_http[0] += 1; return real_mc(cid)
    bot.mercado_clob = contar
    bot._LEGTOK_CACHE.clear()
    bot.token_clob_de_leg(l0); bot.token_clob_de_leg(l0); bot.token_clob_de_leg(l0)
    bot.mercado_clob = real_mc
    check("6. la caché evita repetir el HTTP (1 llamada para 3 usos)", n_http[0] == 1,
          f"{n_http[0]} llamada(s)")
else:
    for i in range(1, 7):
        check(f"{i}. (sin catálogo vivo)", False, "catálogo no disponible")

# =========================================================== MOCKS (7-24)
print("\n🧪 TESTS CON MOCKS")
MK = {"tokens": [{"token_id": "111", "outcome": "Yes", "winner": False, "price": 0.6},
                 {"token_id": "222", "outcome": "No", "winner": False, "price": 0.4}],
      "closed": False}
real_mc2 = bot.mercado_clob
MK_OK = "0xabc"
bot.mercado_clob = lambda cid: dict(MK) if str(cid) == MK_OK else None
bot._LEGTOK_CACHE.clear()
check("7. outcome 'No' → token del índice 1 (no siempre el 0)",
      bot.token_clob_de_leg({"condition_id": "0xabc", "outcome": "no"}) == "222")
bot._LEGTOK_CACHE.clear()
check("8. outcome 'Yes' → token del índice 0",
      bot.token_clob_de_leg({"condition_id": "0xabc", "outcome": "YES"}) == "111")
check("9. condition_id inválido → None (sin HTTP)",
      bot.token_clob_de_leg({"condition_id": "72430256175161", "outcome": "Yes"}) is None)
bot._LEGTOK_CACHE.clear()
check("10. mercado no encontrado → None",
      bot.token_clob_de_leg({"condition_id": "0xnoexiste", "outcome": "Yes"}) is None)
bot.mercado_clob = real_mc2

real_mid = bot.precio_mid
bot.precio_mid = lambda t: {"A": 0.70, "B": 0.50}.get(str(t))
bot.mercado_clob = lambda cid: {"tokens": [{"token_id": "A" if str(cid) == "0x1" else "B",
                                            "outcome": "Yes"},
                                           {"token_id": "X", "outcome": "No"}]}
bot._LEGTOK_CACHE.clear()
op2 = {"legs": [{"condition_id": "0x1", "outcome": "Yes", "position_id": "pid1"},
                {"condition_id": "0x2", "outcome": "Yes", "position_id": "pid2"}]}
check("11. vivo_de con mids 0.70 y 0.50 → 0.35", abs((bot.vivo_de(op2) or 0) - 0.35) < 1e-9,
      f"{bot.vivo_de(op2)}")
bot._LEGTOK_CACHE.clear()
bot.mercado_clob = lambda cid: {"tokens": [{"token_id": "A" if str(cid) == "0x1" else "ZZZ",
                                            "outcome": "Yes"}]}
op3 = {"legs": [{"condition_id": "0x1", "outcome": "Yes", "position_id": "pid1"},
                {"condition_id": "0x2", "outcome": "Yes", "position_id": "pid2"}]}
check("12. si una leg no cotiza → None (no se inventa precio)", bot.vivo_de(op3) is None)
bot.precio_mid = lambda t: 0.42 if str(t) == "tok_single" else None
check("13. vivo_de(single) sigue usando real_token",
      abs((bot.vivo_de({"legs": [], "real_token": "tok_single"}) or 0) - 0.42) < 1e-9)
bot.precio_mid = real_mid

# ---- cerrar_grupo: mensajes nuevos
def grupo(resuelta=False, ganada=None):
    op = {"tipo": "combo_rfq", "question": "Combo de prueba", "legs": [{"position_id": "p1"}],
          "size_shares": 12.0, "stake_dolares": 5.0, "copiado_en": "2026-09-11T10:00:00+00:00",
          "status": "abierto"}
    return {"ops": [op]}, op
real_resolver = bot.resolver_operacion
for caso, gan, espera_det, espera_txt in [
        ("14. resuelta y GANADA", True, "ya_resuelta", "se COBRA"),
        ("15. resuelta y PERDIDA", False, "ya_resuelta", "valor es 0"),
        ("16. resuelta sin veredicto", None, "ya_resuelta", "ya está resuelta"),
        ("17. viva pero sin cotización", "viva", "sin_precio_vivo", "Inténtalo en unos minutos")]:
    g, op = grupo()
    bot.vivo_de = lambda o: None
    if gan == "viva":
        bot.resolver_operacion = lambda o: {"resuelta": False, "ganada": None, "pnl": None,
                                            "fin": None, "detalle": [], "fuente": ""}
    else:
        bot.resolver_operacion = lambda o: {"resuelta": True, "ganada": gan, "pnl": None,
                                            "fin": None, "detalle": [], "fuente": "clob"}
    MENSAJES.clear()
    r = bot.cerrar_grupo(g, chat_id=1, dry_run=True)
    check(caso, r == (False, espera_det) and any(espera_txt in m for m in MENSAJES),
          f"{r[1]} · msg: {(MENSAJES[0][:58] + '…') if MENSAJES else '—'}")
bot.vivo_de = lambda o: 0.30      # con precio vivo NO debe caer en esos mensajes
g, op = grupo()
MENSAJES.clear()
bot.resolver_operacion = real_resolver
bot.cerrar_grupo(g, chat_id=1, dry_run=True)
check("18. con precio vivo ya no dice 'sin precio vivo'",
      not any("sin precio vivo" in m for m in MENSAJES))

# ---- panel 📂 Abiertas
bot.vivo_de = lambda o: None
g, op = grupo()
bot.resolver_operacion = lambda o: {"resuelta": True, "ganada": True, "pnl": 3.0,
                                    "fin": "11-sep 18:00", "detalle": [], "fuente": "clob"}
txt = bot.render_grupo(g, num=1)
check("19. panel: 'n/d (posición resuelta: ya no cotiza)' si terminó",
      "posición resuelta: ya no cotiza" in txt)
bot.resolver_operacion = lambda o: {"resuelta": False, "ganada": None, "pnl": None,
                                    "fin": None, "detalle": [], "fuente": ""}
txt2 = bot.render_grupo(g, num=2)
check("20. panel: 'n/d' a secas si sigue en juego",
      "precio ahora: n/d" in txt2 and "ya no cotiza" not in txt2)
bot.resolver_operacion = real_resolver

# ---- pausa anti-429 + reintento de /reclamar
REG = []
bot.time = TimeShim(REAL_TIME, REG)
bot._SALDO_CACHE.clear()
real_rpc = bot._rpc_eth_call
bot._rpc_eth_call = lambda con, data: "0x" + hex(int(12.5 * 1e6))[2:].rjust(64, "0")
bot.saldo_combo_token("555", contrato=bot.PARLAY_ERC1155)
check("21. saldo_combo_token duerme 0.15 s antes del eth_call", 0.15 in REG, f"sleeps={REG}")
REG.clear()
bot.saldo_combo_token("555", contrato=bot.PARLAY_ERC1155)     # caché fresca
check("22. con caché fresca NO duerme (no ralentiza el AUTO)", REG == [], f"sleeps={REG}")
bot._rpc_eth_call = real_rpc
bot.time = REAL_TIME

def estado_con(tok, **extra):
    op = {"tipo": "combo_rfq", "question": "Combo ganado", "legs": [{"position_id": "p"}],
          "size_shares": 12.5, "stake_dolares": 5.0, "combo_yes_position_id": tok,
          "copiado_en": "2026-08-04T10:00:00+00:00", "status": "abierto"}
    op.update(extra)
    return {"historial": [op], "trades_copiados": []}, op

LLAMADAS = []
def saldo_falso(op, refrescar=False):
    LLAMADAS.append(refrescar)
    return None if not refrescar else 12.5
real_st = bot.saldo_token_op
bot.saldo_token_op = saldo_falso
bot.resolver_operacion = lambda o: {"resuelta": True, "ganada": True, "pnl": 7.5,
                                    "fin": None, "detalle": [], "fuente": "clob"}
bot.verdad_real = lambda *a, **k: ({}, {})
e, _ = estado_con("777")
REG2 = []
bot.time = TimeShim(REAL_TIME, REG2)
res = bot.pendientes_reclamar(con_saldo=True, estado=e)
bot.time = REAL_TIME
check("23. reintento tras un 429: encuentra el saldo y NO cuenta 'sin datos'",
      len(res["reclamables"]) == 1 and res["sin_datos"] == 0
      and res["importe"] == 12.5 and LLAMADAS == [False, True] and 1.2 in REG2,
      f"llamadas refrescar={LLAMADAS} · sleeps={REG2} · ${res['importe']}")
LLAMADAS.clear()
bot.saldo_token_op = lambda op, refrescar=False: (LLAMADAS.append(refrescar), None)[1]
e2, _ = estado_con("888")
res2 = bot.pendientes_reclamar(con_saldo=True, estado=e2)
check("24. si el reintento también falla → 'sin datos' y 0 reclamables",
      res2["sin_datos"] == 1 and not res2["reclamables"] and LLAMADAS == [False, True],
      f"sin_datos={res2['sin_datos']} · reclamables={len(res2['reclamables'])}")
LLAMADAS.clear()
REG3 = []
bot.time = TimeShim(REAL_TIME, REG3)
e3, _ = estado_con("999", saldo_tokens=0.0)
bot.saldo_token_op = real_st
res3 = bot.pendientes_reclamar(con_saldo=False, estado=e3)
bot.time = REAL_TIME
check("25. con_saldo=False sigue sin tocar RPC ni dormir (AUTO seguro)",
      REG3 == [] and res3["sin_datos"] == 0, f"sleeps={REG3}")
bot.saldo_token_op = real_st
bot.resolver_operacion = real_resolver

# ---- legs ya decididas: el combo conserva su valor real
print("\n🎯 LEGS DECIDIDAS (nuevo en v12.8.2)")
bot.vivo_de = REAL_VIVO                      # ⚠️ los tests 14-20 la dejaron mockeada
bot.mercado_clob = lambda cid: {
    "0xG": {"tokens": [{"token_id": "TOK_G", "outcome": "Yes", "winner": True}], "closed": True},
    "0xP": {"tokens": [{"token_id": "TOK_P", "outcome": "Yes", "winner": False},
                       {"token_id": "TOK_PN", "outcome": "No", "winner": True}], "closed": True},
    "0xV": {"tokens": [{"token_id": "VIVA", "outcome": "Yes", "winner": None}], "closed": False},
    "0xS": {"tokens": [{"token_id": "SIN", "outcome": "Yes", "winner": None}], "closed": False},
}.get(str(cid))
# un token YA DECIDIDO no tiene mid útil (el CLOB da 1.00/0.00 y precio_mid lo descarta)
bot.precio_mid = lambda t: {"VIVA": 0.60}.get(str(t))
def lg(cid, pid):
    return {"condition_id": cid, "outcome": "Yes", "position_id": pid, "question": f"leg {cid}"}
bot._LEGTOK_CACHE.clear()
check("26a. el token de una leg decidida ya no da mid (caso real)",
      bot.precio_mid(bot.token_clob_de_leg(lg("0xG", "pg"))) is None)
v = bot.vivo_de({"legs": [lg("0xG", "pg"), lg("0xV", "pv")]})
check("26. leg ganada (1.00) × leg viva (0.60) → 0.60", v is not None and abs(v - 0.60) < 1e-9, f"{v}")
v2 = bot.vivo_de({"legs": [lg("0xP", "pp"), lg("0xV", "pv")]})
check("27. leg perdida ⇒ el combo vale 0.00 (no None)", v2 == 0.0, f"{v2}")
v3 = bot.vivo_de({"legs": [lg("0xS", "ps"), lg("0xV", "pv")]})
check("28. leg sin precio NI veredicto → None (no se inventa)", v3 is None, f"{v3}")
bot.mercado_clob = REAL_MERCADO
bot.precio_mid = real_mid

# ---- guardia de resuelta ANTES del precio
g, op = grupo()
bot.vivo_de = lambda o: 1.00                      # todo ganado: el producto da 1.00
bot.resolver_operacion = lambda o: {"resuelta": True, "ganada": True, "pnl": 7.0, "fin": None,
                                    "detalle": [], "fuente": "cobro_real"}
MENSAJES.clear()
r = bot.cerrar_grupo(g, chat_id=1, dry_run=True)
check("29. resuelta y cobrada: NO intenta vender aunque el precio dé 1.00",
      r == (False, "ya_resuelta") and any("COBRADA" in m for m in MENSAJES),
      f"{r[1]} · {(MENSAJES[0][:56] + '…') if MENSAJES else '—'}")
bot.resolver_operacion = lambda o: {"resuelta": False, "ganada": None, "pnl": None, "fin": None,
                                    "detalle": [], "fuente": ""}
bot.vivo_de = lambda o: 0.0                       # una leg perdió
MENSAJES.clear()
r2 = bot.cerrar_grupo(g, chat_id=1, dry_run=True)
check("30. combo con una leg perdida → 'sin_valor' y mensaje claro",
      r2 == (False, "sin_valor") and any("leg PERDIDA" in m for m in MENSAJES),
      f"{r2[1]} · {(MENSAJES[0][:56] + '…') if MENSAJES else '—'}")
bot.vivo_de = REAL_VIVO
bot.resolver_operacion = real_resolver

# ---- payload de la inyección de las 4 ganadas de agosto
print("\n💉 INYECCIÓN DE LAS 4 DE AGOSTO (aprobada por el user)")
import json as _json, os as _os
PAY = "/home/user/v12.8_reclamar/ops_agosto_4.json"
SH  = "/home/user/bots-backup/scripts_despliegue/actualizar_v1282.sh"
if _os.path.exists(PAY):
    ops = _json.load(open(PAY))
    check("35. son 4 ops, todas ganadas y con legs reales",
          len(ops) == 4 and all(o["resultado"] == "ganada" and o["legs"] for o in ops)
          and all(l["condition_id"].startswith("0x") and l["outcome"] for o in ops for l in o["legs"]))
    check("36. el PnL de cada una es shares − stake (1 token ganador = $1)",
          all(abs(o["pnl"] - round(o["size_shares"] - o["stake_dolares"], 2)) < 0.005 for o in ops)
          and abs(sum(o["size_shares"] for o in ops) - 82.97) < 0.02,
          f"total a cobrar ${sum(o['size_shares'] for o in ops):.2f} · PnL ${sum(o['pnl'] for o in ops):+.2f}")
    check("37. ninguna se marcaría como ya cobrada (fuente legs_ganadas, sin cobro_real)",
          all(o["fuente_verdad"] == "legs_ganadas" and not o.get("cobro_real")
              and o.get("reclamo") != "reclamado" and not o.get("cerrada_manual") for o in ops))
    if _os.path.exists(SH):
        sh = open(SH, encoding="utf-8").read()
        check("38. el actualizador lleva las 4 ops y sus tx de compra embebidas",
              all(o["combo_yes_position_id"] in sh and o["tx_hash"] in sh for o in ops)
              and "Paso 3b: Inyectar las 4 combos GANADAS de agosto" in sh)
    else:
        check("38. actualizador presente", False, SH)
else:
    for i in range(35, 39):
        check(f"{i}. payload presente", False, PAY)

# ---- estructurales
print("\n🔎 ESTRUCTURA")
check("31. versión v12.8.2 en cabecera, arranque y /reclamar",
      "POLY COMBOS BOT v12.8.2" in SRC and 'log("v12.8.2 iniciado")' in SRC
      and "RECLAMAR v12.8.2" in SRC)
check("32. ya no se pide precio con el position_id del catálogo",
      "precio_mid(lg.get(\"position_id\"))" not in SRC
      and "token_clob_de_leg(lg) or lg.get(\"position_id\")" in SRC)
check("33. el RFQ sigue mandando los position_ids del catálogo (son los correctos)",
      "pids = [str(l.get(\"position_id\")) for l in legs if l.get(\"position_id\")]" in SRC
      and "\"leg_position_ids\": [str(x) for x in leg_position_ids]" in SRC)
check("34. nada de v12.8/12.8.1 perdido (reclamar, saldo_token_op, _norm_titulo)",
      all(x in SRC for x in ("def cmd_reclamar(", "def saldo_token_op(", "def _norm_titulo(",
                             "def pendientes_reclamar(", "def reclamar_check(",
                             "PARLAY_ERC1155", "CTF_ERC1155", "COBROS_PAGINAS = 2")))

# ---------------------------------------------------------------- resumen
pasan = sum(1 for _, p in ok if p)
print(f"\n{'=' * 62}\nRESULTADO v12.8.2: {pasan}/{len(ok)} OK")
if pasan != len(ok):
    print("FALLAN:")
    for n, p in ok:
        if not p:
            print("  ❌", n)
    sys.exit(1)
print("✅ TODO EN VERDE")
