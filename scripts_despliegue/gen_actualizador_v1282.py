#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera actualizar_v1282.sh a partir de actualizar_v1281.sh.
Cambios: HASH/md5 nuevos, nombres de log y backups, verificación de las
funciones de v12.8.2, se QUITA la migración de v12.8.1 (ya no hay nada que
migrar) y se AÑADE un paso 6b que comprueba EN VIVO (json + urllib, sin
importar el bot) que el precio de las legs ya se puede pedir: position_id del
catálogo → 404 (el bug) vs token real del CLOB → mid. Va DESPUÉS del reinicio
para que un fallo de red nunca deje el bot parado."""
import io, re, hashlib

SRC = "/home/user/bots-backup/scripts_despliegue/actualizar_v1281.sh"
DST = "/home/user/bots-backup/scripts_despliegue/actualizar_v1282.sh"
HASH = io.open("/home/user/hash_bot_v1282.txt").read().strip()
MD5 = hashlib.md5(io.open("/home/user/v12.8_reclamar/bot_v1282.py", "rb").read()).hexdigest()

s = io.open(SRC, encoding="utf-8").read()
n = [0]
# nombres de log/backups/ruta de publicación: v1281 → v1282 en todo el fichero
c = s.count("v1281"); s = s.replace("v1281", "v1282"); n[0] += c
def rep(a, b, obligatorio=True):
    if s.count(a) != 1:
        if obligatorio:
            raise SystemExit(f"ancla no única ({s.count(a)}): {a[:60]!r}")
        return
    globals()["s"] = s.replace(a, b, 1); n[0] += 1

rep("""# Actualizador v12.8.1 — 💰 /reclamar SIN falsas alarmas (cobros casados por
# título + saldo on-chain en el contrato que toca) + migración del aviso de v12.8""",
    """# Actualizador v12.8.2 — 🔒 el CIERRE de un combo vuelve a ser posible (cada leg
# se valora con su token REAL del CLOB, no con el position_id del catálogo, que
# daba 404 siempre) + anti-429 en /reclamar. Incluye todo lo de v12.6→v12.8.1.""")
rep('HASH="9869c271"', f'HASH="{HASH}"')
rep('MD5_ESPERADO="fec4801f7576ee24793866c838990016"', f'MD5_ESPERADO="{MD5}"')
rep("=== ACTUALIZADOR v12.8.1 (💰 /reclamar sin falsas alarmas)",
    "=== ACTUALIZADOR v12.8.2 (🔒 cierre de combos + precios reales)")
rep("=== Paso 1: Descargar v12.8.1 a un .new", "=== Paso 1: Descargar v12.8.2 a un .new")
rep("=== Paso 3: Verificar funciones v12.8.1 (+ v12.8 / v12.7 / v12.6) ===",
    "=== Paso 3: Verificar funciones v12.8.2 (+ v12.8.1 / v12.8 / v12.7 / v12.6) ===")
rep('for fn in "def saldo_token_op" "def _norm_titulo" "def _op_ts" "CTF_ERC1155" \\',
    'for fn in "def token_clob_de_leg" "def vivo_de" "ya_resuelta" "sin_valor" \\\n'
    '          "token_clob_de_leg(lg) or lg.get" "time.sleep(0.15)" "MOT = {" \\\n'
    '          "def saldo_token_op" "def _norm_titulo" "def _op_ts" "CTF_ERC1155" \\')
rep('grep -a "auditoria\\|auto-curación\\|verdad:\\|💰\\|reclamar\\|pre-flight" /var/log/poly-combos-bot.log',
    'grep -a "auditoria\\|auto-curación\\|verdad:\\|💰\\|reclamar\\|pre-flight\\|CIERRE" /var/log/poly-combos-bot.log')
rep("""echo "  /reclamar        → ganadas SIN cobrar (ahora confirmado on-chain, sin falsas alarmas)"
echo "  /reclamar prueba → fuerza la prueba on-chain (sin usar la caché de 24h)"
echo "  💰 Reclamar      → botón nuevo en el teclado"
echo "  /status          → ahora muestra 🩺 auto-curación y 💰 sin cobrar"
echo "  /reauditar seco  → detalle de la re-auditoría sin modificar nada\"""",
    """echo "  📂 Abiertas      → AHORA sí muestra '📈 precio ahora' y el valor de los combos"
echo "  🧪 /testcerrar 1 → cotización de venta SIN vender ($0) — ya no dice 'sin precio vivo'"
echo "  🔒 /cerrar 1     → venta real; si la posición ya está resuelta lo dice en cristiano"
echo "  /reclamar        → ganadas SIN cobrar (confirmado on-chain, sin falsas alarmas)"
echo "  /status          → 🩺 auto-curación + 💰 sin cobrar"
echo "  /reauditar seco  → detalle de la re-auditoría sin modificar nada\"""")
s = s.replace("'message':'v128 ${TS}'", "'message':'v1282 ${TS}'")

# ---- fuera la migración de v12.8.1 (ya no hay nada que migrar)
i = s.index('echo "=== Paso 3b: Migracion')
i = s.rindex('echo ""', 0, i)
j = s.index("PYEOF", s.index("nada que limpiar")) + len("PYEOF\n")
s = s[:i] + s[j:]
n[0] += 1


# ---- paso 3b: inyección de las 4 ganadas de agosto (aprobada por el user)
PASO3B = """echo ""
echo "=== Paso 3b: Inyectar las 4 combos GANADAS de agosto SIN cobrar ($82.97) ==="
python3 - "$ESTADO" <<'PYEOF' || echo "   (inyeccion fallida: el bot arranca igual, sin esas 4 ops)"
import json, os, sys, tempfile
p = sys.argv[1]
OPS = json.loads(r'''[
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-03T19:20:06+00:00",
  "question": "Dota 2: Team Liquid vs Vici Gaming (BO3) - 1win Essence Playoffs + Dota 2: Rune Eaters vs LGD Gaming (BO3) - Games of the Future Playoffs",
  "n_legs": 2,
  "legs": [
   {
    "question": "Dota 2: Team Liquid vs Vici Gaming (BO3) - 1win Essence Playoffs",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x4a9befb06bc73f1227bbe2c3ad2ae71d4cc5a5f1770d43bcfd7194d3985be115",
    "outcome": "Team Liquid"
   },
   {
    "question": "Dota 2: Rune Eaters vs LGD Gaming (BO3) - Games of the Future Playoffs",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x2338f99dacc9238d9a1ee36c9e8e7451f263a51dbb1d8f84222513e91a06969d",
    "outcome": "Rune Eaters"
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x033d7bbf065bdf8ccf1b2bc32295db4dee0000000000000000000000000000",
  "combo_yes_position_id": "1465570281521417484089349842073433359851434826329862370366262471336197619712",
  "precio_ejecutado": 0.779,
  "cuota_ejecutada": 1.2837,
  "cuota_estimada": 1.2837,
  "size_shares": 19.045017,
  "stake_dolares": 15.0,
  "order_id": "",
  "tx_hash": "0x166cd5b6a1755cad1ce610ab6a39cb8af905a507f06d201aeac96642ae5f1454",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x033d7bbf065bdf8ccf1b2bc32295db4dee0000000000000000000000000000",
  "real_token": "1465570281521417484089349842073433359851434826329862370366262471336197619712",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 4.05,
  "fin_real": "",
  "cerrado_en": "2026-08-03T19:20:06+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 },
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-03T19:29:35+00:00",
  "question": "Counter-Strike: Imperial vs Procyon Gaming (BO3) - BetBoom Storm Group Stage + Counter-Strike: QUINTESSÊNCIA vs BESTIA Academy (BO3) - Gamers Club Liga Série A Playoffs",
  "n_legs": 2,
  "legs": [
   {
    "question": "Counter-Strike: Imperial vs Procyon Gaming (BO3) - BetBoom Storm Group Stage",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x24a11994a0829cfde4ec8d190d67d3786212423f60331fac7aa03a14ea2ba953",
    "outcome": "Imperial"
   },
   {
    "question": "Counter-Strike: QUINTESSÊNCIA vs BESTIA Academy (BO3) - Gamers Club Liga Série A Playoffs",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xaa09530d294cf484e2e0840a908e0db8e18714b59a1a300e1fe50980c1d9f24a",
    "outcome": "QUINTESSÊNCIA"
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x0363b325260260a9ea31152e985e6e760b0000000000000000000000000000",
  "combo_yes_position_id": "1533092819279806577548982495808019581896059581058309727707081807910034997248",
  "precio_ejecutado": 0.767674,
  "cuota_ejecutada": 1.3026,
  "cuota_estimada": 1.3026,
  "size_shares": 19.315185,
  "stake_dolares": 15.0,
  "order_id": "",
  "tx_hash": "0x10d6dcaa5a0df4dfc7ed554e6fcbfd52efd42c411d2ff5d1bb580aaa67928893",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x0363b325260260a9ea31152e985e6e760b0000000000000000000000000000",
  "real_token": "1533092819279806577548982495808019581896059581058309727707081807910034997248",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 4.32,
  "fin_real": "",
  "cerrado_en": "2026-08-03T19:29:35+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 },
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-04T19:22:06+00:00",
  "question": "LoL: Baam Esports vs 3BL Esports (BO3) - Arabian League Group Stage + LoL: Croatian Flair x RLX  vs Lupus Esports (BO3) - EBL Regular Season",
  "n_legs": 2,
  "legs": [
   {
    "question": "LoL: Baam Esports vs 3BL Esports (BO3) - Arabian League Group Stage",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x121cd07691a328aa5d479afc2468ab52a329a742fac215e35c22086633aa2432",
    "outcome": "Baam Esports"
   },
   {
    "question": "LoL: Croatian Flair x RLX  vs Lupus Esports (BO3) - EBL Regular Season",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x3366af39100675e511b8d663f1b2aa74b058fb9d2135f28e540e4108af2ddf7b",
    "outcome": "Croatian Flair x RLX "
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x03e8fbb9de7fc700d1ac768e1cf437385e0000000000000000000000000000",
  "combo_yes_position_id": "1768584414133455489888940688163027989874358868667303883292282436255504924672",
  "precio_ejecutado": 0.701842,
  "cuota_ejecutada": 1.4248,
  "cuota_estimada": 1.4248,
  "size_shares": 14.038948,
  "stake_dolares": 10.0,
  "order_id": "",
  "tx_hash": "0x0285c158f7624e405e9ff31879276f545d05e52f92c9777e196df3c84540a619",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x03e8fbb9de7fc700d1ac768e1cf437385e0000000000000000000000000000",
  "real_token": "1768584414133455489888940688163027989874358868667303883292282436255504924672",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 4.04,
  "fin_real": "",
  "cerrado_en": "2026-08-04T19:22:06+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 },
 {
  "tipo": "combo_rfq",
  "copiado_en": "2026-08-06T13:29:02+00:00",
  "question": "LoL: Dark Passage vs Team Phoenix (BO3) - TCL Play-Ins + LoL: Team WE vs Anyone's Legend (BO3) - LPL Group Ascend + LoL: G2 NORD vs Unicorns Of Love Sexy Edition (BO3) - Prime League 1st Division Group B + LoL: Ici Japon Corp. Esport vs Esp",
  "n_legs": 4,
  "legs": [
   {
    "question": "LoL: Dark Passage vs Team Phoenix (BO3) - TCL Play-Ins",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xe9da2c806b4717975454ddc446937a785f6dbf2b6360557fa875461efe60578e",
    "outcome": "Dark Passage"
   },
   {
    "question": "LoL: Team WE vs Anyone's Legend (BO3) - LPL Group Ascend",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0x24f18bdec315f767612d94e386bc60589185ab6a84e97b080a661a3fce1b2739",
    "outcome": "Team WE"
   },
   {
    "question": "LoL: G2 NORD vs Unicorns Of Love Sexy Edition (BO3) - Prime League 1st Division Group B",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xffc355c1e352588af427f0e82061d63bba145f0a27efcf12436df32a89f7d220",
    "outcome": "G2 NORD"
   },
   {
    "question": "LoL: Ici Japon Corp. Esport vs Esprit Shōnen (BO1) - LFL Regular Season",
    "slug": "",
    "yes_price": null,
    "position_id": "",
    "condition_id": "0xefe382db7be026073b08fbbe1e96a0bcd6a246c6ef69f9abc70b927202878f36",
    "outcome": "Ici Japon Corp. Esport"
   }
  ],
  "rfq_id": "",
  "quote_id": "",
  "combo_condition_id": "0x03db6d7b77e598cc1229347bba6c2f56810000000000000000000000000000",
  "combo_yes_position_id": "1744633671988118944301970785967107214763206080678570968048928890271939166208",
  "precio_ejecutado": 0.316261,
  "cuota_ejecutada": 3.1619,
  "cuota_estimada": 3.1619,
  "size_shares": 30.574245,
  "stake_dolares": 10.0,
  "order_id": "",
  "tx_hash": "0x3f05b81a6d44dec15bcdb2604bc7b1977f56e3d97951c7ab8c8502a01ce0b727",
  "status": "cerrado",
  "estado_rfq": "FILLED",
  "slug": "",
  "market_id": "",
  "condition_id": "0x03db6d7b77e598cc1229347bba6c2f56810000000000000000000000000000",
  "real_token": "1744633671988118944301970785967107214763206080678570968048928890271939166208",
  "volumen": 0,
  "tags": [
   "combo-rfq",
   "inyectada-agosto"
  ],
  "franja": "base",
  "extendida": false,
  "super": false,
  "resultado": "ganada",
  "pnl": 20.57,
  "fin_real": "",
  "cerrado_en": "2026-08-06T13:29:02+00:00",
  "fuente_verdad": "legs_ganadas",
  "cerrada_manual": false,
  "motivo_cierre": "resolucion_real",
  "nota": "Inyectada el 11-sep-2026 (v12.8.2): combo GANADO de agosto que Polymarket no autocobró; los tokens siguen en la cartera (saldo on-chain > 0)."
 }
]''')
if not os.path.exists(p):
    print("   sin estado: nada que inyectar"); raise SystemExit(0)
d = json.load(open(p))
hi = d.setdefault("historial", [])
ab = d.setdefault("trades_copiados", [])
toks = {str(o.get("combo_yes_position_id") or o.get("real_token") or "")
        for o in list(hi) + list(ab)}
nuevas = [o for o in OPS if o["combo_yes_position_id"] not in toks]
if not nuevas:
    print(f"   OK: las {len(OPS)} ops de agosto YA estan en el libro (nada que inyectar)")
    raise SystemExit(0)
hi.extend(nuevas)
fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p) or ".", suffix=".tmp")
with os.fdopen(fd, "w") as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
os.replace(tmp, p)
tot = sum(float(o["size_shares"]) for o in nuevas)
st = sum(float(o["stake_dolares"]) for o in nuevas)
print(f"   INYECTADAS {len(nuevas)} ops GANADAS de agosto: pagado ${st:.2f} -> a cobrar ${tot:.2f} (+${tot-st:.2f})")
for o in nuevas:
    print(f"     {o['copiado_en'][:16]} · {o['n_legs']} legs · ${float(o['stake_dolares']):.2f} -> "
          f"${float(o['size_shares']):.2f} · token ...{o['combo_yes_position_id'][-8:]}")
print("   Con sus condition_id reales: la auditoria las CONFIRMA (fuente legs_ganadas)")
print("   y /reclamar las mostrara como ganadas SIN cobrar (saldo on-chain > 0).")
PYEOF

"""
k = s.index('echo ""\necho "=== Paso 4: Reiniciar bot ==="')
s = s[:k] + PASO3B + s[k:]
n[0] += 1
# ---- paso 6b: comprobación EN VIVO del camino de precios (tras el reinicio)
PASO6B = r'''echo ""
echo "=== Paso 6b: Comprobacion EN VIVO del precio de las legs (el bug de v12.8.1) ==="
python3 - "$ESTADO" <<'PYEOF' || echo "   (comprobacion no disponible: sin red o sin estado)"
import json, sys, os, urllib.request
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado"); raise SystemExit(0)
d = json.load(open(p))
UA = {"User-Agent": "poly-combos-bot"}
def http(u):
    try:
        q = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(q, timeout=12) as r:
            return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return (getattr(e, "code", None) or 0), None
NUESTRO = {"yes", "over", "true", "si"}          # misma regla que estado_leg()
ab = d.get("trades_copiados", []) or []
con = [o for o in ab if o.get("legs")][:3]
print(f"   abiertas: {len(ab)} · combos con legs: {sum(1 for o in ab if o.get('legs'))} (se miran {len(con)})")
for o in con:
    print(f"\n   🎫 {str(o.get('question','?'))[:66]}")
    prod = 1.0
    for lg in (o.get("legs") or [])[:3]:
        pid = str(lg.get("position_id") or "")
        cid = str(lg.get("condition_id") or "")
        nuestro = str(lg.get("outcome") or "").strip().lower()
        c1, _ = http(f"https://clob.polymarket.com/midpoint?token_id={pid}")   # ← el bug: 404
        tok, mid, win, iwin, c3 = None, None, None, None, 0
        if cid.startswith("0x"):
            c2, m = http(f"https://clob.polymarket.com/markets/{cid}")
            toks = (m or {}).get("tokens") or []
            if toks:
                idx = 0
                if nuestro:
                    for i, t in enumerate(toks):
                        if str(t.get("outcome") or "").strip().lower() == nuestro:
                            idx = i; break
                tok = str(toks[idx].get("token_id") or "")
                for i, t in enumerate(toks):
                    if t.get("winner"):
                        win = str(t.get("outcome") or "").strip(); iwin = i
        if tok:
            c3, mp = http(f"https://clob.polymarket.com/midpoint?token_id={tok}")
            if c3 == 200:
                try:
                    v = float((mp or {}).get("mid"))
                    mid = v if 0 < v < 1 else None
                except Exception:
                    mid = None
        if mid is not None:
            txt = f"mid {mid:.3f}"
        elif win:
            gano = (nuestro == win.lower()) if nuestro else (iwin == 0 or win.lower() in NUESTRO)
            mid = 1.0 if gano else 0.0
            txt = f"leg decidida → {'GANADA' if gano else 'PERDIDA'} (ganó '{win}')"
        else:
            txt = "sin mid y sin ganador declarado (resolución pendiente)"
        print(f"      {str(lg.get('question','?'))[:38]:40} pid→{c1} · token real→{c3} · {txt}")
        prod = None if (prod is None or mid is None) else prod * mid
    sh = float(o.get("size_shares") or 0); st = float(o.get("stake_dolares") or 0)
    if prod is None:
        print("      ⇒ precio vivo: n/d (alguna leg sin cotización ni veredicto)")
    else:
        print(f"      ⇒ precio vivo {prod:.4f} · valor ≈ ${sh*prod:.2f} (pago ${st:.2f})")
print("\n   ANTES de v12.8.2 el bot sólo miraba 'pid→404' y decía 'sin precio vivo'.")
PYEOF

'''
k = s.index('echo ""\necho "=== EN TELEGRAM ==="')
s = s[:k] + PASO6B + s[k:]
n[0] += 1

io.open(DST, "w", encoding="utf-8").write(s)
print(f"✅ {DST} · {n[0]} sustituciones · HASH={HASH} · md5={MD5}")
print(f"   líneas: {len(s.splitlines())} · bytes: {len(s)}")
for chk in (HASH, MD5, "def token_clob_de_leg", "Paso 6b", "combos_update_v1282_", "v1282 ${TS}"):
    assert chk in s, chk
assert "Paso 3b: Migracion" not in s
assert "Paso 3b: Inyectar las 4 combos GANADAS de agosto" in s
assert s.count("1465570281521417484089349842073433359851434826329862370366262471336197619712") == 2
assert "0x3f05b81a6d44dec15bcdb2604bc7b1977f56e3d97951c7ab8c8502a01ce0b727" in s
assert '"legs_ganadas"' in s
print("   asserts OK")
