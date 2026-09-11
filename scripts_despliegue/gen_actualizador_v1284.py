#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera actualizar_v1284.sh a partir de actualizar_v1283.sh.
Cambios:
  · nombres v1283 → v1284 y v12.8.3 → v12.8.4 (log, backups, publicación, mensajes)
  · HASH (commit del bot en el repo) y MD5_ESPERADO (md5 del bot v12.8.4)
  · cabecera nueva: qué cambia en v12.8.4 (🟡 SEMI de verdad + ⚖️ ventaja 5%)
  · paso 3: añade las funciones/constantes de v12.8.4 a la verificación
  · paso 3b: sustituye el recordatorio de la inyección de agosto por una
    comprobación del MODO/intervalo guardados y del contador "sin cobrar" con el
    filtro nuevo (sólo avisos con importe > 0 → los 7 de antes son 4 reales)
  · paso 6: añade las CUENTAS DE COMPENSACIÓN calculadas sobre el historial real
    (media ganada/perdida, victorias por derrota, win-rate de equilibrio)
  · paso 6b nuevo: EN VIVO con el catálogo RFQ real — construye el mejor combo
    base como lo haría el bot y dice qué cuota real mínima exigiría el filtro
    del 5%; más el estado del servicio y del modo tras el arranque
  · bloque final "EN TELEGRAM" con lo que el usuario va a ver y cómo pasar a SEMI
Uso: python3 gen_actualizador_v1284.py <HASH_commit_bot>
"""
import io, re, hashlib, sys

SRC = "/home/user/bots-backup/scripts_despliegue/actualizar_v1283.sh"
DST = "/home/user/bots-backup/scripts_despliegue/actualizar_v1284.sh"
BOT = "/home/user/v12.8.4_semi/bot_v1284.py"
HASH = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
MD5 = hashlib.md5(io.open(BOT, "rb").read()).hexdigest()
assert re.fullmatch(r"[0-9a-f]{7,40}", HASH or ""), "falta el HASH del commit del bot"
HASH8 = HASH[:8]

s = io.open(SRC, encoding="utf-8").read()
n = [0]

MODO_STEP = r'''echo "=== Paso 3c: dejar el bot en 🟡 SEMI (modo guardado) + 1ª propuesta en ~2 min ==="
python3 - "$ESTADO" <<'PY' || true
import json, os, sys, time
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado: no se cambia el modo (pulsa 🟡 SEMI en Telegram)"); raise SystemExit(0)
d = json.load(open(p))
antes = d.get("modo", "AUTO")
d["modo"] = "SEMI"
d["proximo_paso_ts"] = time.time() + 120      # 1ª pasada (propuesta) en ~2 min
tmp = p + ".tmp"
json.dump(d, open(tmp, "w"), ensure_ascii=False, indent=1)
os.replace(tmp, p)
print(f"   modo {antes} → SEMI · próxima pasada (propuesta) en ~2 min")
print("   → v12.8.4 restaura el modo al arrancar; antes el bot volvía SIEMPRE en AUTO")
PY

'''

# ---------------------------------------------------------------- 1) nombres
c = s.count("v1283"); s = s.replace("v1283", "v1284"); n[0] += c
c = s.count("v12.8.3"); s = s.replace("v12.8.3", "v12.8.4"); n[0] += c

# ------------------------------------------------------- 2) hash y md5 nuevos
s2 = re.sub(r'^HASH="[0-9a-f]{8}"$', f'HASH="{HASH8}"', s, count=1, flags=re.M)
assert s2 != s, "no se sustituyó HASH"
s = s2
s2 = re.sub(r'^MD5_ESPERADO="[0-9a-f]{32}"$', f'MD5_ESPERADO="{MD5}"', s, count=1, flags=re.M)
assert s2 != s, "no se sustituyó MD5_ESPERADO"
s = s2
n[0] += 2

# ------------------------------------------------------------- 3) cabecera
vieja = '''# Actualizador v12.8.4 — EL PANEL DICE LA VERDAD + ✅ + 🔍 Leer ahora.
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
nueva = '''# Actualizador v12.8.4 — 🟡 SEMI DE VERDAD + ⚖️ VENTAJA MÍNIMA 5%.
#   🟡 SEMI ya no es un OFF disfrazado: el bot escanea igual que en AUTO y TE
#      PROPONE el combo con botones ✅ Aceptar y comprar / ❌ Descartar. Nada se
#      compra sin tu ✅. La propuesta CADUCA a los 10 min y sus botones se
#      sustituyen por el resultado (✅ aceptada / ❌ descartada / ⌛ caducada), así
#      que no se puede aprobar dos veces. Al aceptar se pide una cotización NUEVA
#      (las del RFQ viven segundos: expires_at ≈ +5 s) y se ejecuta por la misma
#      ruta que AUTO: stake dinámico, tope diario, anti-duplicados y el filtro.
#   ⚖️ FILTRO DE VENTAJA: sólo compra si prob × cuota_real ≥ 1.05 (prob = precio
#      implícito de los legs). Antes bastaba con que el RFQ no fuera PEOR que el
#      mercado (esperanza ≈ 0): comprar algo que sólo empata es perder. Vale en
#      🟢 AUTO y 🟡 SEMI; los botones manuales 🚀/💥 siguen operando siempre.
#   ✅ El botón del MODO activo también lleva su tick verde (🟡 SEMI ✅) y
#      cmd_modo explica qué hace cada modo de verdad.
#   🧮 📊 Stats trae las CUENTAS DE COMPENSACIÓN con tu libro real: media por
#      ganada/perdida, victorias necesarias por derrota, win-rate de equilibrio
#      frente al tuyo y tabla por cuota (1.5/2.0/2.5).
#   🟡 El MODO guardado ya sobrevive al reinicio (main() no leía estado["modo"]: el
#      bot volvía SIEMPRE en AUTO). Este despliegue te deja EN SEMI (paso 3c) con la
#      primera pasada programada a ~2 min para que veas la propuesta enseguida.
#   🧽 Cosméticos: el arranque decía "v12.8.1 cargado"; las anuladas archivadas
#      no guardaban cobro_real; "sin cobrar" contaba avisos de importe 0 (7 → 4).
# Incluye TODO lo de v12.6→v12.8.3: es el mismo fichero del bot, parcheado encima.'''
assert s.count(vieja) == 1, f"cabecera no encontrada ({s.count(vieja)})"
s = s.replace(vieja, nueva, 1); n[0] += 1

s = s.replace('echo "=== ACTUALIZADOR v12.8.4 (✅ tick del intervalo · 🔍 Leer ahora · panel honesto · 🧹 cura) - $(date) ==="',
              'echo "=== ACTUALIZADOR v12.8.4 (🟡 SEMI de verdad · ⚖️ ventaja 5% · ✅ modo · 🧮 cuentas) - $(date) ==="', 1)

# ------------------------------------------- 4) paso 3: funciones de v12.8.4
old_lista = '''for fn in "def teclado_fijo" "TICK_ACTIVO" "def intervalo_min_actual" \\'''
new_lista = '''for fn in "def proponer_combo_semi" "def ejecutar_semi_aprobado" \\
          "def respuesta_propuesta" "def _marcar_propuesta" "def _prune_propuestas" \\
          "def _sin_tick" "PROPUESTA_VALIDA_S" "VENTAJA_MIN_EV" "PROPUESTAS = {}" \\
          'data.startswith("sm:")' 'data.startswith("smx:")' \\
          "ventaja insuficiente" "CUENTAS DE COMPENSACIÓN" "pnl_wins" \\
          "v12.8.4 cargado" "def restaurar_modo" "restaurar_modo(_est0)" \
          "def teclado_fijo" "TICK_ACTIVO" "def intervalo_min_actual" \\'''
assert s.count(old_lista) == 1
s = s.replace(old_lista, new_lista, 1); n[0] += 1
s = s.replace('echo "=== Paso 3: Verificar funciones v12.8.4 (✅ tick · 🔍 leer · ⏸/↩️ · 🧹 cura) ==="',
              'echo "=== Paso 3: Verificar funciones v12.8.4 (🟡 SEMI · ⚖️ ventaja · ✅ modo · 🧮 cuentas) ==="', 1)

# ------------------------------- 5) paso 3b: modo guardado + sin cobrar real
i0 = s.index('echo "=== Paso 3b:')
i1 = s.index('echo "=== Paso 4:')
assert 0 < i0 < i1
paso3b = r'''echo "=== Paso 3b: modo/intervalo guardados + 'sin cobrar' con el filtro nuevo ==="
python3 - "$ESTADO" <<'PY' || true
import json, sys, os
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado"); raise SystemExit(0)
d = json.load(open(p))
print(f"   modo guardado: {d.get('modo', 'AUTO')} · intervalo {int(d.get('intervalo_auto_s', 600)) // 60} min · "
      f"stake {d.get('stake_mode', 'AUTO')} · tope {d.get('max_ops_dia', '?')}/día · "
      f"prob mín {d.get('prob_min_auto', '?')}")
print("   → en Telegram: 🟡 SEMI para que PROPONGA (✅/❌) · 🟢 AUTO para que abra solo")
rc = d.get("reclamos_avisados") or {}
con = {k: v for k, v in rc.items() if float(v.get("importe") or 0) > 0.000001}
print(f"   💰 avisos de reclamo: {len(rc)} en total · {len(con)} con dinero de verdad "
      f"(${sum(float(v.get('importe') or 0) for v in con.values()):.2f}) · "
      f"{len(rc) - len(con)} con importe 0 (ya revisados: saldo 0 on-chain)")
print("   → v12.8.4: /status y 🔍 sólo cuentan los que tienen importe > 0")
PY

'''
s = s[:i0] + paso3b + s[i1:]
n[0] += 1

# ------------------- 6) paso 6: cuentas de compensación sobre el historial
old6 = '''r=d.get("ultimo_auditoria_resumen") or {}
print(f"   ultima auditoria: {str(d.get('ultima_auditoria'))[:19]} · origen={r.get('origen')} "'''
new6 = '''# 🧮 v12.8.4: las cuentas que ahora salen en 📊 Stats, calculadas aquí también
w=[o for o in hi if o.get("resultado")=="ganada" and float(o.get("pnl") or 0)>0]
l=[o for o in hi if o.get("resultado")=="perdida" and float(o.get("pnl") or 0)<0]
if w and l:
    mw=sum(float(o.get("pnl") or 0) for o in w)/len(w)
    ml=-sum(float(o.get("pnl") or 0) for o in l)/len(l)
    sw=sum(float(o.get("stake_dolares") or 0) for o in w)/len(w)
    print(f"   🧮 compensación: {len(w)} ganadas (+${mw:.2f} de media) · "
          f"{len(l)} pérdidas (-${ml:.2f} de media)")
    print(f"      ⇒ {ml / mw:.2f} victorias por derrota · win-rate de equilibrio "
          f"{ml / (mw + ml) * 100:.1f}% · el tuyo {len(w) / (len(w) + len(l)) * 100:.1f}%")
    if sw > 0:
        print(f"      stake medio ${sw:.2f} → para recuperar -${ml:.2f}: "
              + " · ".join(f"cuota {q:.1f} → {ml / (sw * (q - 1)):.1f} victorias"
                           for q in (1.5, 2.0, 2.5)))
    print(f"      ⚖️ con el filtro de v12.8.4 sólo se compra si prob × cuota ≥ 1.05")
r=d.get("ultimo_auditoria_resumen") or {}
print(f"   ultima auditoria: {str(d.get('ultima_auditoria'))[:19]} · origen={r.get('origen')} "'''
# --------------------- 6b) paso 3c: el despliegue deja el bot en 🟡 SEMI
old3c = 'echo "=== Paso 4: Reiniciar bot ==="'
assert s.count(old3c) == 1
s = s.replace(old3c, MODO_STEP + old3c, 1); n[0] += 1

assert s.count(old6) == 1
s = s.replace(old6, new6, 1); n[0] += 1

# ------------------------------------- 7) paso 6b nuevo (EN VIVO con el catálogo)
j0 = s.index('echo "=== Paso 6b:')
j1 = s.index('echo "=== EN TELEGRAM ==="')
assert 0 < j0 < j1
paso6b = r'''echo "=== Paso 6b: EN VIVO v12.8.4 (catalogo RFQ + que exigiria el filtro del 5%) ==="
python3 - <<'PYEOF' || echo "   (comprobacion no disponible: sin red)"
import json, urllib.request
UA = {"User-Agent": "poly-combos-bot"}
CAT = "https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets?limit=50"


def http(u):
    try:
        q = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(q, timeout=20) as r:
            return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return (getattr(e, "code", None) or 0), None


st, d = http(CAT)
legs = []
if isinstance(d, dict):
    legs = d.get("markets") or d.get("data") or []
elif isinstance(d, list):
    legs = d
print(f"   1) catalogo RFQ (HTTP {st}): {len(legs)} legs")
buenos = []
for lg in legs:
    try:
        p = float(lg.get("yes_price") or lg.get("price") or 0)
    except Exception:
        p = 0.0
    if 0.70 <= p < 0.995:
        buenos.append((p, str(lg.get("question") or lg.get("title") or "?")[:52],
                       str(lg.get("event_slug") or lg.get("event") or "?")[:24]))
buenos.sort(reverse=True)
print(f"      legs con prob 0.70-0.995: {len(buenos)}")
if len(buenos) >= 2:
    prod = buenos[0][0] * buenos[1][0]
    est = round(1 / prod, 2) if prod > 0 else 0
    print(f"   2) mejor combo base posible ahora: {buenos[0][1]} ({buenos[0][0]:.2f}) + "
          f"{buenos[1][1]} ({buenos[1][0]:.2f})")
    print(f"      prob {prod * 100:.1f}% · cuota est. {est:.2f} · stake AUTO "
          f"${min(max(5 + 6 / est, 5), 10):.2f} · ganancia si acierta "
          f"+${min(max(5 + 6 / est, 5), 10) * (est - 1):.2f}")
    print(f"      ⚖️ el filtro de v12.8.4 exige cuota REAL >= {est * 1.05:.2f} "
          f"(+5% sobre {est:.2f}); por debajo, se omite y no gasta nada")
    print(f"      🟡 en SEMI eso te llegaria como PROPUESTA con ✅/❌ (caduca a los 10 min)")
else:
    print("   2) ahora mismo no hay dos legs aprovechables para un combo base")
PYEOF

echo ""
echo "   --- servicio y modo tras el arranque ---"
systemctl is-active poly-combos-bot || true
grep -a "v12.8.4 cargado\|modo=\|🟡\|⚖️" /var/log/poly-combos-bot.log 2>/dev/null | tail -6 || true

echo ""
'''
s = s[:j0] + paso6b + s[j1:]
n[0] += 1

# ------------------------------------------------- 8) bloque final EN TELEGRAM
k0 = s.index('echo "=== EN TELEGRAM ==="')
k1 = s.index('# Publicar en diag-public')
assert 0 < k0 < k1
telegram = '''echo "=== EN TELEGRAM ==="
echo "  🟡 SEMI        → pulsa el boton 🟡 SEMI (ahora sale '🟡 SEMI ✅'). Cada 10 min el"
echo "                   bot busca y te PROPONE un combo con ✅ Aceptar y comprar / ❌ Descartar."
echo "                   NADA se compra sin tu ✅ y la propuesta caduca a los 10 min."
echo "  ✅ Aceptar     → pide cotizacion NUEVA (las del RFQ viven segundos) y compra solo si"
echo "                   mejora el mercado >=5%; si no, te lo dice y no gasta nada."
echo "  ⚖️ Ventaja 5%  → prob × cuota_real >= 1.05. Vale en AUTO y en SEMI; los botones"
echo "                   manuales 🚀/💥 siguen operando siempre (los eliges tu)."
echo "  📊 Stats       → ahora trae 🧮 CUENTAS DE COMPENSACION: media por ganada/perdida,"
echo "                   victorias por derrota, win-rate de equilibrio y tabla por cuota."
echo "  Teclado        → ✅ en el intervalo ACTIVO y en el MODO activo (se mueven solos)."
echo "  🔍 Leer ahora  → lectura inmediata + propuestas SEMI vivas. Solo mirar (/leer)."
echo "  /status        → 'sin cobrar' ya solo cuenta los avisos con dinero de verdad."
echo "  🟡 Ya estás en SEMI: el despliegue guarda modo=SEMI y programa la 1ª pasada"
echo "                   a ~2 min. Si no hay ningún combo válido, no llega propuesta"
echo "                   (el log dice por qué); 🔍 Leer ahora te enseña qué propondría."

'''
s = s[:k0] + telegram + s[k1:]
n[0] += 1

# ------------------------------------------------------------- 9) saneamiento
assert "v1283" not in s, "queda algún v1283"
_menc = [l for l in s.splitlines() if "v12.8.3" in l]
assert len(_menc) == 1 and _menc[0].startswith("#"), f"menciones raras a v12.8.3: {_menc}"
assert s.count(f'HASH="{HASH8}"') == 1 and s.count(f'MD5_ESPERADO="{MD5}"') == 1
assert "proponer_combo_semi" in s and "VENTAJA_MIN_EV" in s and "combos_update_v1284_" in s
assert s.count('Paso 3c: dejar el bot en') == 1 and 'd["modo"] = "SEMI"' in s
assert "def restaurar_modo" in s
assert "diag-public" in s and s.count("PYEOF") == 2

io.open(DST, "w", encoding="utf-8").write(s)
print(f"✅ {DST}\n   {len(s.splitlines())} líneas · {n[0]} sustituciones · "
      f"HASH={HASH8} · MD5_ESPERADO={MD5}")
