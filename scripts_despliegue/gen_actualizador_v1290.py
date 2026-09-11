#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera actualizar_v1290.sh a partir de actualizar_v1284.sh.
Cambios:
  · nombres v1284 → v1290 y v12.8.4 → v12.9.0 (log, backups, publicación, mensajes)
  · HASH (commit del bot v12.9.0 en el repo) y MD5_ESPERADO (md5 del bot nuevo)
  · cabecera nueva: 🏆 top real en vivo + 📡 copy-trading EN PAPEL (Fase 1, $0)
  · paso 3: añade a la verificación las funciones/constantes de v12.9.0 y un bloque
    de GARANTÍAS (COPY_DINERO=False, lista falsa del Top fuera, 0 llamadas a compra
    dentro de copy_pasada)
  · paso 3b: informa del estado del seguimiento (traders, señales, dedup, informes)
  · paso 3c: SIN CAMBIOS de fondo — sigue dejando el bot en 🟡 SEMI (el user lo pidió)
  · paso 5: el grep del log también busca las líneas [copy] y [top]
  · paso 6b: ARREGLADO el bug — leía yes_price/price pero el catálogo RFQ usa
    outcome_prices (lista de textos [yes,no]) y title/slug; por eso decía siempre
    "0 legs aprovechables"
  · paso 6c NUEVO: EN VIVO el copy-trading — top 30d real, a quién elegiría con los
    filtros, qué señales habría ahora mismo (con los dos precios) y el gasto ($0)
  · bloque final "EN TELEGRAM" con lo que va a ver: 🏆 real, 📡 Copy, /copy, 1ª ronda
    a los ~90 s, informe diario, cero dinero y el criterio de Fase 2
Uso: python3 gen_actualizador_v1290.py <HASH_commit_bot>
"""
import hashlib, io, re, sys

SRC = "/home/user/bots-backup/scripts_despliegue/actualizar_v1284.sh"
DST = "/home/user/bots-backup/scripts_despliegue/actualizar_v1290.sh"
BOT = "/home/user/v12.9_copytrading/bot_v1290.py"
HASH = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
MD5 = hashlib.md5(io.open(BOT, "rb").read()).hexdigest()
assert re.fullmatch(r"[0-9a-f]{7,40}", HASH or ""), "falta el HASH del commit del bot"
HASH8 = HASH[:8]

s = io.open(SRC, encoding="utf-8").read()
n = [0]


def rep(viejo, nuevo, etiqueta, veces=1):
    global s
    c = s.count(viejo)
    assert c == veces, f"'{etiqueta}': {c} coincidencias (esperaba {veces})"
    s = s.replace(viejo, nuevo, veces)
    n[0] += 1
    print(f"  ✓ {etiqueta}")


# ---------------------------------------------------------------- 1) nombres
c = s.count("v1284"); s = s.replace("v1284", "v1290"); n[0] += c
c = s.count("v12.8.4"); s = s.replace("v12.8.4", "v12.9.0"); n[0] += c
print(f"  ✓ renombres (v1284→v1290, v12.8.4→v12.9.0)")

# ------------------------------------------------------- 2) hash y md5 nuevos
s2 = re.sub(r'^HASH="[0-9a-f]{8}"$', f'HASH="{HASH8}"', s, count=1, flags=re.M)
assert s2 != s, "no se sustituyó HASH"
s = s2
s2 = re.sub(r'^MD5_ESPERADO="[0-9a-f]{32}"$', f'MD5_ESPERADO="{MD5}"', s, count=1, flags=re.M)
assert s2 != s, "no se sustituyó MD5_ESPERADO"
s = s2
print(f"  ✓ HASH={HASH8} · MD5_ESPERADO={MD5}")

# ---------------------------------------------------------------- 3) cabecera
CABECERA = r'''# Actualizador v12.9.0 — 🏆 TOP REAL EN VIVO + 📡 COPY-TRADING EN PAPEL (FASE 1, $0).
#   🏆 El botón Top ya NO es una lista escrita a mano (estaba desactualizada y no se
#      parecía a la realidad): llama a lb-api.polymarket.com y enseña el ranking REAL
#      con botones 24 h / 7 días / 30 días / histórico, beneficio, volumen, margen y
#      la wallet de cada trader. Si lb-api no responde, lo dice: no inventa cifras.
#   📡 COPY-TRADING EN PAPEL: vigila los fills de los 5 mejores del top de 30 días
#      QUE PASAN los filtros automáticos — activos (≥5 compras/48 h), no market
#      makers (ventas/compras ≤0.5), no concentrados (≥3 mercados) y ≥40% deporte —
#      y ANOTA cada compra como señal con DOS precios: el suyo y el mid real al que
#      nosotros entraríamos. Si el precio ya se movió >5 pts, la señal se descarta
#      por tardía. Las compras repetidas de la MISMA posición se fusionan en una
#      señal (medido en vivo: 102 fills de un trader en 1 h eran sólo 4 posiciones),
#      así que el tope de 5 señales/día cuenta MERCADOS distintos, no fills sueltos.
#   🏁 Al resolverse el mercado apunta si la señal acertó y el PnL teórico a $5 AL
#      PRECIO NUESTRO y al SUYO → /copy da acierto, ROI, deriva, retraso medio y
#      desglose por trader. Informe automático cada 24 h. Las anuladas cuentan 0.
#   🔒 NO GASTA UN CÉNTIMO: COPY_DINERO=False y no hay ninguna ruta desde el copy a
#      firmar o enviar una orden. Las señales viven en estado["copy_señales"] (no en
#      trades_copiados: el histórico de tus combos no se mezcla). 48 tests, 6 de ellos
#      dedicados sólo a demostrar que no puede comprar (con tripwires armados).
#   🎯 Fase 2 (convertir la señal en un COMBO PROPIO por RFQ) exige ≥30 señales
#      resueltas y ROI positivo AL PRECIO NUESTRO. Nunca líneas sueltas.
#   📏 Medido antes de arrancar: copiar al top-1 histórico activo habría dado −48.8%
#      en sus últimas 48 h; en 30 días conviven +130% con −100%. Por eso, en papel.
#   🧽 Arreglado de paso: el paso 6b leía yes_price/price, pero el catálogo RFQ usa
#      outcome_prices (lista de textos [yes,no]) y title/slug → por eso decía siempre
#      "0 legs aprovechables" aunque hubiera combos válidos.
# Sigues en 🟡 SEMI con intervalo de 10 min: este despliegue NO cambia tu modo.
# Incluye TODO lo de v12.6→v12.8.4: es el mismo fichero del bot, parcheado encima.
'''
i0 = s.index("# Actualizador v12.9.0")
i1 = s.index("set -e", i0)
s = s[:i0] + CABECERA + s[i1:]
n[0] += 1
print("  ✓ cabecera nueva")

# ------------------------------------------------- 4) paso 3: funciones nuevas
rep('''          "PARLAY_ERC1155" "AUDITORIA_CADA_H" "NEXT_AUDITORIA_TS"; do''',
    r'''          "PARLAY_ERC1155" "AUDITORIA_CADA_H" "NEXT_AUDITORIA_TS" \
          "def top_traders" "def nombre_lb" "def _din_lb" "def es_deporte_copy" \
          "def perfil_trader" "def filtros_perfil" "def copy_elegir" \
          "def fills_recientes" "def registrar_señal" "def resolver_señales" \
          "def resumen_copy" "def texto_copy" "def cmd_copy" "def copy_pasada" \
          "def programar_copy_inicio" "def _caras_de" "def _lb_get" "def estado_copy" \
          "def señales_hoy" "LB_API" "VENTANAS_LB" "COPY_DINERO = False" \
          "COPY_ACTIVO = True" "COPY_VENTANA" "COPY_N_TRADERS = 5" \
          "COPY_TOPE_DIA = 5" "COPY_SONDEO_S" "COPY_MIN_COMPRAS_48H" \
          "COPY_MAX_RATIO_VENTAS" "COPY_MIN_MERCADOS" "COPY_MIN_DEPORTE" \
          "COPY_DERIVA_MAX = 0.05" "COPY_MAX_VISTOS" "COPY_RESOLVER_POR_RONDA" \
          "copy_señales" "copy_pasada(CHAT_ID)" "programar_copy_inicio()" \
          'data.startswith("lb:")' '{"text": "📡 Copy"}' "v12.9.0 cargado" \
          "NEXT_COPY_TS" "PASADA_LOCK:"; do''', "paso 3: verificación v12.9.0")

# ------------------------------------------- 5) paso 3: bloque de garantías 🔒
rep('''echo "   --- dispatch de /reclamar y del boton ---"''',
    r'''echo "   --- 🔒 garantias de que el copy-trading NO puede gastar dinero ---"
MALO=$(sed -n '/^def copy_pasada/,/^def programar_copy_inicio/p' "$INSTALL_DIR/poly_combos_bot.py" \
       | grep -c "enviar_orden(\|ejecutar_combo_rfq(\|firmar_orden_v3(\|crear_rfq(\|reservar_combo(\|ejecutar_trade(\|aceptar_rfq(\|obtener_identidad_rfq(" || true)
echo "   llamadas a compra dentro de copy_pasada: ${MALO:-0} (tiene que ser 0)"
SECC=$(sed -n '/^def _lb_get/,/^def cmd_top/p' "$INSTALL_DIR/poly_combos_bot.py" \
       | grep -c "enviar_orden(\|ejecutar_combo_rfq(\|firmar_orden_v3(\|crear_rfq(\|reservar_combo(\|ejecutar_trade(\|aceptar_rfq(" || true)
echo "   llamadas a compra en TODA la seccion 📡: ${SECC:-0} (tiene que ser 0)"
FALSA=$(grep -c 'pleaseplease123 +$1.0M' "$INSTALL_DIR/poly_combos_bot.py" || true)
echo "   lista falsa del Top escrita a mano: ${FALSA:-0} (tiene que ser 0)"
grep -n "^COPY_DINERO\|^COPY_ACTIVO\|^COPY_TOPE_DIA\|^COPY_DERIVA_MAX\|^COPY_SONDEO_S" "$INSTALL_DIR/poly_combos_bot.py" | head -6
echo "   --- dispatch de /reclamar y del boton ---"''', "paso 3: bloque de garantías")

# --------------------------------------- 6) paso 3b: estado del seguimiento 📡
rep('''print("   → v12.9.0: /status y 🔍 sólo cuentan los que tienen importe > 0")''',
    r'''print("   → v12.9.0: /status y 🔍 sólo cuentan los que tienen importe > 0")
cp = d.get("copy") or {}
se = d.get("copy_señales") or []
res = [x for x in se if x.get("resuelta") and not x.get("anulada")]
pnl = sum(float(x.get("pnl_papel_nuestro") or 0) for x in res)
print(f"   📡 copy en papel: {len(cp.get('traders') or [])} traders vigilados · "
      f"{len(se)} señales ({len(res)} resueltas, {sum(1 for x in se if x.get('anulada'))} anuladas) · "
      f"dedup {len(cp.get('vistos') or {})} fills · informes {int(cp.get('informes') or 0)}")
if res:
    print(f"      acierto {sum(1 for x in res if x.get('senal_acerto')) / len(res) * 100:.1f}% · "
          f"PnL teórico al precio nuestro ${pnl:+.2f} "
          f"(ROI {pnl / (len(res) * 5.0) * 100:+.1f}%)")
else:
    print("      aún sin señales resueltas: la 1ª ronda llega ~90 s después de arrancar")''',
    "paso 3b: estado del seguimiento")

# --------------------------------------------------- 7) paso 5: grep del log
rep(r'''grep -a "auditoria\|auto-curación\|verdad:\|💰\|reclamar\|pre-flight\|CIERRE" /var/log/poly-combos-bot.log 2>/dev/null | tail -10 || echo "   (aún ninguna)"''',
    r'''grep -a "auditoria\|auto-curación\|verdad:\|💰\|reclamar\|pre-flight\|CIERRE\|\[copy\]\|\[top\]" /var/log/poly-combos-bot.log 2>/dev/null | tail -14 || echo "   (aún ninguna)"''',
    "paso 5: el log también busca [copy]/[top]")

# ------------------------------------- 8) paso 6b: ARREGLAR el precio del catálogo
rep('''    try:
        p = float(lg.get("yes_price") or lg.get("price") or 0)
    except Exception:
        p = 0.0''',
    r'''    v = lg.get("outcome_prices")            # ← el catálogo RFQ usa ESTO
    if isinstance(v, str):                  #    (lista de textos [yes, no])
        try:
            v = json.loads(v)
        except Exception:
            v = []
    try:
        p = float((v or [0])[0])
    except Exception:
        p = 0.0''', "paso 6b: outcome_prices (antes yes_price → siempre 0 legs)")

rep('''        buenos.append((p, str(lg.get("question") or lg.get("title") or "?")[:52],
                       str(lg.get("event_slug") or lg.get("event") or "?")[:24]))''',
    r'''        buenos.append((p, str(lg.get("title") or lg.get("question") or "?")[:52],
                       str(lg.get("slug") or lg.get("event_slug") or "?")[:24]))''',
    "paso 6b: title/slug (los campos reales del catálogo)")

# ------------------------------------------------- 9) paso 6c NUEVO (copy vivo)
PASO6C = r'''echo ""
echo "=== Paso 6c: EN VIVO v12.9.0 (top real + a quien vigilaria + señales ahora) ==="
python3 - <<'PYEOF' || echo "   (comprobacion no disponible: sin red)"
import json, time, urllib.request
UA = {"User-Agent": "poly-combos-bot"}
LB = "https://lb-api.polymarket.com"
DA = "https://data-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
DEP = ("nfl", "nba", "mlb", "nhl", "epl", "laliga", "ucl", "atp", "wta", "f1",
       "seriea", "bundesliga", "ligue1", "mls", "wnba", "ufc", "soccer",
       "football", "basketball", "baseball", "tennis", "mma", "hockey",
       "cricket", "esports", "lol", "csgo", "dota", "ren-", "fl1")


def http(u, t=20):
    try:
        q = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(q, timeout=t) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def dinero(v):
    v = float(v or 0)
    a = abs(v)
    if a >= 1000000:
        return f"${v / 1000000:.2f}M"
    if a >= 1000:
        return f"${v / 1000:.1f}K"
    return f"${v:.0f}"


top = http(f"{LB}/profit?window=30d&limit=12") or []
print(f"   1) top REAL de 30 dias (lb-api): {len(top)} filas")
elegidos = []
for i, x in enumerate(top, 1):
    w = str(x.get("proxyWallet") or "")
    nom = str(x.get("pseudonym") or x.get("name") or w[:10])
    if nom.startswith("0x") or len(nom) > 24:
        nom = w[:10]
    act = http(f"{DA}/activity?user={w}&limit=300&type=TRADE") or []
    corte = time.time() - 48 * 3600
    tr = [a for a in act if a.get("type") == "TRADE" and int(a.get("timestamp") or 0) >= corte]
    c = sum(1 for a in tr if a.get("side") == "BUY")
    v = sum(1 for a in tr if a.get("side") == "SELL")
    mk = len({str(a.get("conditionId")) for a in tr})
    dep = 0.0
    if tr:
        dep = sum(1 for a in tr if any(k in str(a.get("eventSlug") or a.get("title") or "").lower()
                                       for k in DEP)) / len(tr)
    ratio = v / max(c, 1)
    ok = c >= 5 and ratio <= 0.5 and mk >= 3 and dep >= 0.40
    mot = ("activo" if ok else ("inactivo" if c < 5 else
           ("market maker" if ratio > 0.5 else
            ("concentrado en %d" % mk if mk < 3 else "%.0f%% deporte" % (dep * 100)))))
    print(f"      #{i:<2} {nom[:22]:<22} {dinero(x.get('amount')):>9} · "
          f"{c:>4} compras /{v:>4} ventas · {mk:>3} mercados · {dep * 100:>3.0f}% dep · "
          f"{'ELEGIDO' if ok else 'fuera (' + mot + ')'}")
    if ok:
        elegidos.append((nom, w))
    time.sleep(0.15)
    if len(elegidos) >= 5:
        break
print(f"   2) vigilando a {len(elegidos)}: " + ", ".join(nm for nm, _ in elegidos))
desde = time.time() - 3600
pos, ntardia, nsin = {}, 0, 0
for nom, w in elegidos:
    act = http(f"{DA}/activity?user={w}&limit=200&type=TRADE") or []
    fills = [a for a in act if a.get("side") == "BUY" and int(a.get("timestamp") or 0) > desde]
    for f in fills:
        tok = str(f.get("asset") or "")
        if (w, tok) in pos:
            continue                      # compras repetidas = 1 sola señal
        try:
            pe = float(f.get("price") or 0)
        except Exception:
            continue
        mid = http(f"{CLOB}/midpoint?token_id={tok}", 10) or {}
        try:
            pn = float(mid.get("mid"))
        except Exception:
            pn = 0.0
        if not (0 < pe < 1):
            continue
        if not (0 < pn < 1):
            nsin += 1
            continue
        if abs(pn - pe) > 0.05:
            ntardia += 1
            continue
        pos[(w, tok)] = (nom, str(f.get("title") or "?")[:44], pe, pn)
    time.sleep(0.15)
print(f"   3) señales que habria AHORA (ultima hora, 1ª entrada por posicion): {len(pos)}")
for nom, tit, pe, pn in list(pos.values())[:6]:
    print(f"      · {nom[:16]:<16} {tit:<44} el {pe:.3f} -> nosotros {pn:.3f} "
          f"({(pn - pe) * 100:+.1f} pts) · cuota {1 / pn:.2f} · papel $5")
print(f"      (tardias descartadas {ntardia} · sin libro {nsin})")
print("   4) 🔒 gastado: $0.00 · COPY_DINERO=False · tope 5 señales/dia · "
      "Fase 2 = combos propios, nunca lineas sueltas")
PYEOF

'''
rep('''echo ""
echo "   --- servicio y modo tras el arranque ---"''',
    PASO6C + '''echo ""
echo "   --- servicio y modo tras el arranque ---"''', "paso 6c nuevo (copy en vivo)")

# ------------------------------------------------------- 10) bloque EN TELEGRAM
TELEGRAM = r'''echo ""
echo "=== EN TELEGRAM ==="
echo "  🏆 Top         → ranking REAL de Polymarket (lb-api) con botones 24 h / 7 días /"
echo "                   30 días / histórico: beneficio, volumen, margen y wallet. La"
echo "                   lista de antes estaba escrita a mano y ya no se parecía a nada."
echo "  📡 Copy        → panel del seguimiento EN PAPEL: a quiénes vigila, señales de hoy"
echo "                   (tope 5), acierto, ROI AL PRECIO NUESTRO, deriva, retraso medio"
echo "                   y desglose por trader. También con /copy (o /señales)."
echo "  🕐 1ª ronda    → ~90 s después de arrancar: elige los traders y te lo dice en el"
echo "                   chat. Después sondea cada 3 min e informa automáticamente cada 24 h."
echo "  🔒 Dinero      → CERO. COPY_DINERO=False: el copy no firma ni envía ninguna orden,"
echo "                   sólo lee ranking, fills y mids públicos (ni siquiera usa el proxy)."
echo "  🎯 Fase 2      → con ≥30 señales resueltas y ROI positivo AL PRECIO NUESTRO, la"
echo "                   señal se convertiría en un COMBO PROPIO por RFQ. Nunca líneas"
echo "                   sueltas: la regla de los combos multi-leg sigue intacta."
echo "  📊 Tus combos  → TODO sigue igual: 🟡 SEMI con propuesta ✅/❌ cada 10 min, filtro"
echo "                   de ventaja 5%, stake $5-10 y tope de 10 ops/día. El copy tiene su"
echo "                   propio tope (5 señales/día) y NO toca ese contador."
echo "  🟡 Modo        → sigues en SEMI: este despliegue no lo cambia (el bot restaura el"
echo "                   modo guardado al arrancar)."

'''
i0 = s.index('echo ""\necho "=== EN TELEGRAM ==="')
i1 = s.index("# Publicar en diag-public", i0)
s = s[:i0] + TELEGRAM + s[i1:]
n[0] += 1
print("  ✓ bloque final EN TELEGRAM")

# ------------------------------------------------------------- 11) comprobaciones
assert s.count(f'HASH="{HASH8}"') == 1
assert s.count(f'MD5_ESPERADO="{MD5}"') == 1
assert "v1284" not in s and "v12.8.4" not in s, "queda algún nombre viejo"
assert s.count("Paso 6c:") == 1 and s.count("COPY_DINERO=False") >= 2
assert 'lg.get("yes_price")' not in s, "sigue el bug del precio del catálogo"
assert 'lg.get("outcome_prices")' in s
assert s.count('d["modo"] = "SEMI"') == 1, "el paso 3c debe seguir dejando SEMI"
assert s.count("diag_hetzner/combos_update_v1290_") == 1
assert s.count("PYEOF") == 4, f"heredocs: {s.count('PYEOF')} (esperaba 4)"
io.open(DST, "w", encoding="utf-8").write(s)
print(f"\n✅ {DST} · {len(s.splitlines())} líneas · {n[0]} cambios")
print(f"   HASH={HASH8} · MD5_ESPERADO={MD5}")
