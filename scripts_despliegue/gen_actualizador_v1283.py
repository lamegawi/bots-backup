#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera actualizar_v1283.sh a partir de actualizar_v1282.sh.
Cambios:
  · nombres v1282 → v1283 (log, backups, ruta de publicación, mensajes)
  · HASH y MD5_ESPERADO nuevos (md5 del bot v12.8.3)
  · cabecera nueva (qué arregla v12.8.3)
  · se QUITA el paso 3b (la inyección de las 4 ops de agosto YA se hizo en el
    despliegue de v12.8.2; repetirla no procede)
  · paso 3: se añaden las funciones de v12.8.3 a la verificación
  · paso 6b nuevo: comprobación EN VIVO de lo que v12.8.3 cambia de verdad
    (mercado suspendido según el CLOB, fills reales de Barranquilla en data-api
    frente a los registros del bot, y estado tras la curación: abiertas /
    archivadas / ↩️ anuladas / 🧹 descartadas)
  · bloque final "EN TELEGRAM" con lo que el usuario va a ver
"""
import io, re, hashlib, sys

SRC = "/home/user/bots-backup/scripts_despliegue/actualizar_v1282.sh"
DST = "/home/user/bots-backup/scripts_despliegue/actualizar_v1283.sh"
BOT = "/home/user/v12.8.3_panel/bot_v1283.py"
HASH = io.open("/home/user/hash_bot_v1283.txt").read().strip()
MD5 = hashlib.md5(io.open(BOT, "rb").read()).hexdigest()

s = io.open(SRC, encoding="utf-8").read()
n = [0]

# ---------------------------------------------------------------- 1) nombres
c = s.count("v1282"); s = s.replace("v1282", "v1283"); n[0] += c
c = s.count("v12.8.2"); s = s.replace("v12.8.2", "v12.8.3"); n[0] += c

# ------------------------------------------------------- 2) hash y md5 nuevos
s2 = re.sub(r'^HASH="[0-9a-f]{8}"$', f'HASH="{HASH}"', s, count=1, flags=re.M)
assert s2 != s, "no se sustituyó HASH"
s = s2
s2 = re.sub(r'^MD5_ESPERADO="[0-9a-f]{32}"$', f'MD5_ESPERADO="{MD5}"', s, count=1, flags=re.M)
assert s2 != s, "no se sustituyó MD5_ESPERADO"
s = s2
n[0] += 2

# ------------------------------------------------------------- 3) cabecera
vieja = '''# Actualizador v12.8.3 — 🔒 el CIERRE de un combo vuelve a ser posible (cada leg
# se valora con su token REAL del CLOB, no con el position_id del catálogo, que
# daba 404 siempre) + anti-429 en /reclamar. Incluye todo lo de v12.6→v12.8.1.
# Incluye TODO lo de v12.6/v12.7 (resultados reales + auto-curación): es el
# mismo fichero del bot, parcheado encima.'''
nueva = '''# Actualizador v12.8.3 — EL PANEL DICE LA VERDAD + ✅ + 🔍 Leer ahora.
#   ✅ El botón ⏱ del intervalo ACTIVO sale marcado con un tick verde (teclado
#      dinámico: se reconstruye en cada mensaje, así que el tick se mueve solo).
#   🔍 Nuevo botón "Leer ahora" (+ /leer): lectura inmediata que cuenta bankroll,
#      catálogo, qué combo abriría y el estado REAL de cada posición. SÓLO MIRAR:
#      no abre, no vende, no archiva ni mueve la pasada AUTO.
#   ⏸ Mercado SUSPENDIDO y ↩️ ANULADO en cristiano, con la fecha de resolución
#      prevista, y último precio publicado cuando /midpoint da 404.
#   🧹 Curación por evidencia de cadena: los registros de Abiertas se casan con
#      los fills reales de data-api; basura y duplicados fantasma salen a
#      estado["descartadas"] (sin prueba no se borra nada).
#   💰 Mercados simples cerrados SIN ganador: si la wallet ya cobró se archivan
#      con el dinero REAL, repartido entre los fills en proporción a sus shares.
# Incluye TODO lo de v12.6→v12.8.2: es el mismo fichero del bot, parcheado encima.
# (Se QUITA el paso 3b de v12.8.2: las 4 ops de agosto YA están inyectadas.)'''
assert s.count(vieja) == 1, f"cabecera no encontrada ({s.count(vieja)})"
s = s.replace(vieja, nueva, 1); n[0] += 1

# ------------------------------------------------- 4) fuera el paso 3b (inyección)
i0 = s.index('echo "=== Paso 3b:')
i1 = s.index('echo "=== Paso 4:')
assert 0 < i0 < i1
s = s[:i0] + '''echo "=== Paso 3b: (quitado en v12.8.3) las 4 ops de agosto YA están inyectadas ==="
python3 - "$ESTADO" <<'PY' || true
import json, sys, os
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado"); raise SystemExit(0)
d = json.load(open(p))
hi = d.get("historial", []) or []
ago = [o for o in hi if str(o.get("question") or "").strip()
       and not o.get("cobro_real") and o.get("resultado") == "ganada"]
print(f"   archivadas ganadas SIN cobro real registrado: {len(ago)} "
      f"(${sum(float(o.get('pnl') or 0) + float(o.get('stake_dolares') or 0) for o in ago):.2f} por cobrar)")
PY

''' + s[i1:]
n[0] += 1

# ------------------------------------------- 5) paso 3: funciones de v12.8.3
old_lista = '''for fn in "def token_clob_de_leg" "def vivo_de" "ya_resuelta" "sin_valor" \\'''
new_lista = '''for fn in "def teclado_fijo" "TICK_ACTIVO" "def intervalo_min_actual" \\
          "🔍 Leer ahora" "def cmd_leer_ahora" "LECTURA_LOCK" "def _eta_txt" \\
          "def situacion_mercado" "def situacion_op" "def precio_vivo_op" \\
          "def fills_wallet" "def casar_fills" "def es_basura" "def curar_abiertas" \\
          "def _reparto_mapa" "def reparto_cobro" "cobro_real_simple" "anulada" \\
          "def token_clob_de_leg" "def vivo_de" "ya_resuelta" "sin_valor" \\'''
assert s.count(old_lista) == 1
s = s.replace(old_lista, new_lista, 1); n[0] += 1
s = s.replace('echo "=== ACTUALIZADOR v12.8.3 (🔒 cierre de combos + precios reales) - $(date) ==="',
              'echo "=== ACTUALIZADOR v12.8.3 (✅ tick del intervalo · 🔍 Leer ahora · panel honesto · 🧹 cura) - $(date) ==="', 1)
s = s.replace('echo "=== Paso 3: Verificar funciones v12.8.3 (+ v12.8.1 / v12.8 / v12.7 / v12.6) ==="',
              'echo "=== Paso 3: Verificar funciones v12.8.3 (✅ tick · 🔍 leer · ⏸/↩️ · 🧹 cura) ==="', 1)

# --------------------------------------------------- 6) paso 6b nuevo (en vivo)
j0 = s.index('echo "=== Paso 6b:')
j1 = s.index('echo "=== EN TELEGRAM ==="')
assert 0 < j0 < j1
paso6b = '''echo "=== Paso 6b: Comprobacion EN VIVO v12.8.3 (suspendido + fills reales + cura) ==="
python3 - "$ESTADO" <<'PYEOF' || echo "   (comprobacion no disponible: sin red o sin estado)"
import json, sys, os, urllib.request
p = sys.argv[1]
UA = {"User-Agent": "poly-combos-bot"}
CID_SEYB = "0xe0b5ba4d3407f7eb578d55fe41b34aeb99f0d32b8a32f1da0b330c05b0a30ae6"
TOK_BARR = "102190795601065752692316941866482150736520688268644150542153831580824160844279"
W = "0xb0e1197098e6d427c01720f1631cad24ce740fa0"


def http(u):
    try:
        q = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(q, timeout=15) as r:
            return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return (getattr(e, "code", None) or 0), None


st, m = http("https://clob.polymarket.com/markets/" + CID_SEYB)
if m:
    print(f"   1) Seyboth Wild (CLOB {st}): closed={m.get('closed')} active={m.get('active')} "
          f"accepting_orders={m.get('accepting_orders')} end={m.get('end_date_iso')}")
    if m.get("active") is False or m.get("accepting_orders") is False:
        print("      ⇒ el bot debe mostrar ⏸ SUSPENDIDO + resolución prevista (v12.8.3)")
        for tk in (m.get("tokens") or []):
            print(f"      cara {str(tk.get('outcome'))[:28]:30} price={tk.get('price')} "
                  f"winner={tk.get('winner')}  ← último precio publicado (libro cerrado)")
    else:
        print("      ⇒ el mercado ya está activo: se podrá vender/resolver con normalidad")
else:
    print(f"   1) Seyboth Wild: sin datos del CLOB (status {st})")

st2, acts = http(f"https://data-api.polymarket.com/activity?user={W}&limit=500&type=TRADE")
if acts:
    fills = [a for a in acts if str(a.get("asset")) == TOK_BARR]
    print(f"   2) Barranquilla: {len(fills)} fills REALES en data-api (el bot tenía 4 registros)")
    for a in fills:
        print(f"      {a.get('timestamp')} · {a.get('size')} sh · {a.get('usdcSize')} USD · "
              f"{str(a.get('transactionHash'))[:20]}")
else:
    print(f"   2) Barranquilla: sin data-api (status {st2})")

if os.path.exists(p):
    d = json.load(open(p))
    ab = d.get("trades_copiados", []) or []
    hi = d.get("historial", []) or []
    de = d.get("descartadas", []) or []
    anu = [o for o in hi if o.get("resultado") == "anulada"]
    print(f"   3) estado tras la cura: {len(ab)} abiertas · {len(hi)} archivadas "
          f"(↩️ anuladas {len(anu)}) · 🧹 descartadas {len(de)}")
    for o in de[:6]:
        print(f"      🧹 {str(o.get('question') or '(registro vacío)')[:42]:44} "
              f"{str(o.get('descartada') or '')[:52]}")
    for o in anu[:4]:
        print(f"      ↩️ {str(o.get('question') or '?')[:42]:44} "
              f"cobro ${float(o.get('cobro_real') or 0):.2f} · PnL ${float(o.get('pnl') or 0):+.2f}")
    r = d.get("ultimo_auditoria_resumen") or {}
    cu = r.get("cura") or {}
    if cu:
        print(f"      🩺 cura: basura {cu.get('basura')} · fantasma {cu.get('fantasma')} · "
              f"casadas {cu.get('casadas')} · sin evidencia {cu.get('sin_evidencia')}")
else:
    print("   3) sin estado")
PYEOF

echo ""
'''
s = s[:j0] + paso6b + s[j1:]
n[0] += 1

# ------------------------------------------------- 7) bloque final EN TELEGRAM
k0 = s.index('echo "=== EN TELEGRAM ==="')
k1 = s.index('# Publicar en diag-public')
assert 0 < k0 < k1
telegram = '''echo "=== EN TELEGRAM ==="
echo "  Teclado        → el botón ⏱ del intervalo ACTIVO lleva ✅ (se mueve solo al cambiarlo)"
echo "  🔍 Leer ahora  → lectura inmediata: bankroll, catálogo, qué abriría y estado REAL"
echo "                   de cada posición. SÓLO MIRAR: no abre, no vende, no archiva (/leer)"
echo "  📂 Abiertas    → ⏸ SUSPENDIDO (sin libro + fecha prevista) y ↩️ ANULADO en cristiano;"
echo "                   si /midpoint da 404 muestra el último precio publicado"
echo "  ✅ Cerradas    → ↩️ anuladas/devueltas aparte de 🟢/🔴 (PnL real, no inventado)"
echo "  /status        → v12.8.3 + 🩺 auto-curación (ahora con 🧹 limpieza de basura/duplicados)"
echo "  /reauditar seco→ detalle de la curación sin modificar nada"
echo "  🧹 descartadas → nada se borra: los registros fantasma/vacíos quedan auditables"

'''
s = s[:k0] + telegram + s[k1:]
n[0] += 1

# ------------------------------------------------------------- 8) saneamiento
assert "v1282" not in s, "queda algún v1282"
# las únicas menciones a v12.8.2 permitidas son las dos del comentario de cabecera
_menc = [l for l in s.splitlines() if "v12.8.2" in l]
assert len(_menc) == 2 and all(l.startswith("#") for l in _menc), \
    f"menciones raras a v12.8.2: {_menc}"
assert s.count("PYEOF") % 2 == 0, "heredocs PYEOF desbalanceados"
assert s.count('echo "=== Paso 4: Reiniciar bot ==="') == 1
assert "Paso 3b: Inyectar" not in s
io.open(DST, "w", encoding="utf-8").write(s)
print(f"✅ {DST}")
print(f"   HASH={HASH} · MD5_ESPERADO={MD5} · {len(s.splitlines())} líneas · {n[0]} sustituciones")
