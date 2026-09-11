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
print("   asserts OK")
