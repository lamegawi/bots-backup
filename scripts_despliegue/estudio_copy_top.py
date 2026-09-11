#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
estudio_copy_top.py — ¿es rentable hacer copy-trading de los TOP de Polymarket?
===============================================================================
Datos reales, sin suposiciones. Tres medidas:

  A) TASA DE ACIERTO + PnL SIMULADO. Coge los fills de compra de los 10 top del
     día (lb-api.polymarket.com/profit?window=1d), mira en el CLOB público si el
     mercado YA se resolvió y si su cara ganó, y simula qué habría pasado
     comprando lo mismo con $5 (y con $10) por fill. Sólo así se sabe si el
     "top" tiene ventaja real o es suerte/mercados ya cantados.
  B) DERIVA DE PRECIO (el coste de llegar tarde). Para los mercados aún vivos,
     compara el precio al que compró él con el mid actual del CLOB: si el precio
     ya ha subido, nosotros pagaríamos más ⇒ parte de su ventaja se evapora.
  C) RETRASO DE LA FUENTE. data-api /activity es lo único que podemos vigilar;
     medimos la antigüedad del fill más reciente y, vía RPC de Polygon, la hora
     on-chain de su transacción, para acotar cuánto tardamos en verlo.

Además calcula el filtro del bot (cuota 1.20-2.50 ⇒ precio 0.40-0.833) y el
tope diario de 10 ops, porque copiar 400 fills/día con un tope de 10 no es lo
mismo que copiarlos todos.

Uso: python3 estudio_copy_top.py [n_top] [fills_por_trader]
"""
import json, statistics as st, sys, time, urllib.request

UA = {"User-Agent": "poly-combos-bot"}
N_TOP = int(sys.argv[1]) if len(sys.argv) > 1 else 10
LIM = int(sys.argv[2]) if len(sys.argv) > 2 else 200
STAKE = 5.0
CUOTA_MIN, CUOTA_MAX = 1.20, 2.50
P_MIN, P_MAX = 1 / CUOTA_MAX, 1 / CUOTA_MIN      # 0.40 … 0.833
_cache = {}


def get(u, t=25):
    q = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(q, timeout=t) as r:
        return json.loads(r.read().decode())


def mercado(cid):
    """CLOB público: {token_id: {outcome, winner, price}} · closed/active."""
    cid = str(cid)
    if cid in _cache:
        return _cache[cid]
    d = None
    try:
        d = get(f"https://clob.polymarket.com/markets/{cid}", 20)
    except Exception:
        d = None
    out = None
    if isinstance(d, dict):
        toks = {}
        for tk in (d.get("tokens") or []):
            try:
                p = float(tk.get("price") or 0)
            except Exception:
                p = 0.0
            toks[str(tk.get("token_id"))] = {"outcome": tk.get("outcome"),
                                             "winner": bool(tk.get("winner")),
                                             "price": p}
        out = {"closed": bool(d.get("closed")), "active": d.get("active"),
               "accepting": d.get("accepting_orders"), "tokens": toks,
               "question": d.get("question")}
    _cache[cid] = out
    time.sleep(0.12)
    return out


def rpc_ts(tx):
    """Hora on-chain de una tx (RPC público de Polygon) → acota el retraso."""
    cuerpo = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getTransactionByHash",
                         "params": [tx]}).encode()
    for rpc in ("https://polygon-rpc.publicnode.com", "https://polygon.drpc.org",
                "https://1rpc.io/matic"):
        try:
            q = urllib.request.Request(rpc, data=cuerpo, headers={
                "Content-Type": "application/json", "User-Agent": "poly-combos-bot"})
            with urllib.request.urlopen(q, timeout=10) as r:
                d = json.loads(r.read().decode())
            bn = (d.get("result") or {}).get("blockNumber")
            if not bn:
                continue
            cuerpo2 = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_getBlockByNumber",
                                  "params": [bn, False]}).encode()
            q2 = urllib.request.Request(rpc, data=cuerpo2, headers={
                "Content-Type": "application/json", "User-Agent": "poly-combos-bot"})
            with urllib.request.urlopen(q2, timeout=10) as r2:
                b = json.loads(r2.read().decode())
            ts = int((b.get("result") or {}).get("timestamp", "0x0"), 16)
            if ts:
                return ts
        except Exception:
            continue
        time.sleep(0.15)
    return None


print(f"=== A/B/C · copy-trading de los {N_TOP} top del día · hasta {LIM} fills cada uno ===")
lb = get(f"https://lb-api.polymarket.com/profit?window=1d&limit={N_TOP}")
now = int(time.time())
todo, por_trader = [], []
for i, t in enumerate(lb, 1):
    w = t["proxyWallet"]
    try:
        a = get(f"https://data-api.polymarket.com/activity?user={w}&limit={LIM}&type=TRADE")
    except Exception as e:
        print(f"  {i:>2} {t['name'][:20]:<20} sin actividad ({str(e)[:40]})")
        continue
    buys = [x for x in a if x.get("type") == "TRADE" and x.get("side") == "BUY"]
    for b in buys:
        b["_trader"] = t["name"]; b["_rank"] = i
    todo += buys
    por_trader.append({"i": i, "name": t["name"], "w": w, "profit": t["amount"],
                       "n": len(buys), "fills": buys})
    print(f"  {i:>2} {t['name'][:20]:<20} +${t['amount']:>10,.0f} · {len(buys):>3} compras "
          f"({len({b['conditionId'] for b in buys})} mercados) · últ. hace "
          f"{(now - max([b['timestamp'] for b in buys] or [now])) / 60:.0f} min")

print(f"\ntotal compras a estudiar: {len(todo)}")

# ------------------------------------------------- A) resolución + PnL simulado
resueltos, vivos, sin_datos = [], [], []
for b in todo:
    m = mercado(b["conditionId"])
    if not m:
        sin_datos.append(b); continue
    tk = m["tokens"].get(str(b["asset"]))
    if tk is None:
        sin_datos.append(b); continue
    b["_mk"] = m
    b["_ganador"] = tk["winner"]
    b["_mid"] = tk["price"]
    if m["closed"] or tk["winner"] or any(v["winner"] for v in m["tokens"].values()):
        resueltos.append(b)
    else:
        vivos.append(b)

print(f"resueltos: {len(resueltos)} · vivos: {len(vivos)} · sin datos: {len(sin_datos)}")


def simular(fills, stake=STAKE, solo_rango=False, tope=None):
    """PnL de copiar cada fill con `stake`: gana stake*(1/p −1), pierde stake."""
    f = list(fills)
    if solo_rango:
        f = [x for x in f if P_MIN <= float(x["price"]) <= P_MAX]
    f.sort(key=lambda x: x["timestamp"])
    if tope:
        f = f[:tope]
    pnl = gan = 0
    for x in f:
        p = float(x["price"])
        if p <= 0 or p >= 1:
            continue
        if x["_ganador"]:
            pnl += stake * (1 / p - 1); gan += 1
        else:
            pnl -= stake
    n = len(f)
    return {"n": n, "gan": gan, "wr": (gan / n * 100) if n else 0.0, "pnl": pnl,
            "roi": (pnl / (n * stake) * 100) if n else 0.0}


print("\n=== A) SIMULACIÓN: copiar sus compras con $5 por fill (mercados YA resueltos) ===")
base = simular(resueltos)
rango = simular(resueltos, solo_rango=True)
tope10 = simular(resueltos, solo_rango=True, tope=10)
for etiqueta, r in (("todas sus compras", base),
                    (f"sólo cuota {CUOTA_MIN}-{CUOTA_MAX} (filtro del bot)", rango),
                    ("lo anterior con tope de 10 ops", tope10)):
    if r["n"]:
        print(f"  {etiqueta:<44} {r['n']:>4} fills · acierto {r['wr']:5.1f}% · "
              f"PnL ${r['pnl']:+9.2f} · ROI {r['roi']:+6.1f}%")
    else:
        print(f"  {etiqueta:<44}    0 fills")

print("\n  por trader (todas sus compras resueltas, $5/fill):")
for pt in por_trader:
    f = [x for x in pt["fills"] if x in resueltos]
    if len(f) < 5:
        print(f"    {pt['i']:>2} {pt['name'][:20]:<20} sólo {len(f)} resueltos (muestra pequeña)")
        continue
    r = simular(f)
    rr = simular(f, solo_rango=True)
    print(f"    {pt['i']:>2} {pt['name'][:20]:<20} {r['n']:>4} fills · acierto {r['wr']:5.1f}% · "
          f"PnL ${r['pnl']:+9.2f} · ROI {r['roi']:+6.1f}%"
          + (f"  ‖ en rango: {rr['n']} fills, ROI {rr['roi']:+6.1f}%" if rr["n"] else ""))

# ------------------------------------------- B) deriva de precio (llegar tarde)
print("\n=== B) DERIVA DE PRECIO en mercados AÚN VIVOS (lo que cuesta llegar tarde) ===")
if vivos:
    d_abs, d_rel = [], []
    for b in vivos:
        p0 = float(b["price"]); mid = float(b.get("_mid") or 0)
        if 0 < mid < 1 and p0 > 0:
            d_abs.append(mid - p0); d_rel.append((mid / p0 - 1) * 100)
    if d_abs:
        print(f"  {len(d_abs)} compras en mercados vivos · mid actual − su precio:")
        print(f"    media {st.mean(d_abs):+.4f} ({st.mean(d_rel):+.2f}%) · "
              f"mediana {st.median(d_abs):+.4f} ({st.median(d_rel):+.2f}%)")
        print(f"    subieron (copiaríamos MÁS caro): {sum(1 for x in d_abs if x > 0.005)}/{len(d_abs)}"
              f" · bajaron: {sum(1 for x in d_abs if x < -0.005)}/{len(d_abs)}"
              f" · iguales (±0.005): {sum(1 for x in d_abs if abs(x) <= 0.005)}/{len(d_abs)}")
        if st.mean(d_abs) > 0:
            # cuánto PnL nos quitaría pagar el mid en vez de su precio
            perdida = sum(STAKE * (1 / float(b["price"]) - 1 / (float(b["price"]) + st.mean(d_abs)))
                          for b in vivos if float(b["price"]) > 0) / max(len(vivos), 1)
            print(f"    ⇒ pagar el mid actual recortaría ~${perdida:.2f} de beneficio por fill ganador")
else:
    print("  ninguna compra en mercado vivo (todos resueltos)")

# ------------------------------------------------- C) retraso de la fuente
print("\n=== C) RETRASO: ¿cuánto tardamos en ver sus fills? ===")
rec = sorted(todo, key=lambda x: -x["timestamp"])[:6]
for b in rec:
    age_min = (now - b["timestamp"]) / 60
    ts_on = rpc_ts(b.get("transactionHash") or "")
    extra = f" · on-chain hace {(now - ts_on) / 60:.1f} min" if ts_on else ""
    print(f"  {b['_trader'][:18]:<18} fill hace {age_min:6.1f} min{extra} · "
          f"${b['usdcSize']:,.0f} · p={float(b['price']):.3f} · {str(b['title'])[:38]}")
print("  (data-api /activity es la única fuente vigilable: si el fill más nuevo tiene")
print("   pocos minutos, el retraso real de copiar es de ese orden)")

# ------------------------------------------------- qué tipo de mercados son
print("\n=== ¿QUÉ COMPRAN? (para saber si encaja con tus reglas) ===")
esp = sum(1 for b in todo if any(k in (b.get("eventSlug") or "").lower() for k in
          ("nfl", "nba", "mlb", "epl", "laliga", "ucl", "atp", "wta", "f1", "nhl",
           "seriea", "bundesliga", "ligue1", "mls", "wnba", "ufc", "ren-", "fl1")))
pre = [float(b["price"]) for b in todo if 0 < float(b["price"]) < 1]
tam = [float(b["usdcSize"]) for b in todo]
print(f"  deporte: {esp}/{len(todo)} ({esp / max(len(todo), 1) * 100:.0f}%) · "
      f"en tu rango de cuota {CUOTA_MIN}-{CUOTA_MAX}: "
      f"{sum(1 for p in pre if P_MIN <= p <= P_MAX)}/{len(pre)} "
      f"({sum(1 for p in pre if P_MIN <= p <= P_MAX) / max(len(pre), 1) * 100:.0f}%)")
print(f"  precio mediano {st.median(pre):.3f} (cuota {1 / st.median(pre):.2f}) · "
      f"tamaño mediano ${st.median(tam):,.0f} (tu stake: ${STAKE:.0f})")
print(f"  mercados distintos: {len({b['conditionId'] for b in todo})} · "
      f"compras por mercado: {len(todo) / max(len({b['conditionId'] for b in todo}), 1):.1f}")

json.dump({"base": base, "rango": rango, "tope10": tope10,
           "n_todo": len(todo), "n_resueltos": len(resueltos), "n_vivos": len(vivos)},
          open("/tmp/estudio_copy_top.json", "w"), indent=1)
print("\n(resumen guardado en /tmp/estudio_copy_top.json)")
