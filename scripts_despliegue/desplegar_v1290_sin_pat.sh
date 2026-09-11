#!/bin/bash
# Despliegue v12.9.0 SIN GitHub (plan B): el parche va gzip+base64 aquí dentro.
#   🏆 Top real en vivo (lb-api, ventanas 24 h/7 d/30 d/histórico + wallet).
#   📡 Copy-trading EN PAPEL de los 5 mejores del top 30d filtrados (activos, no
#      market makers, no concentrados, ≥40% deporte): cada compra suya es una
#      SEÑAL con dos precios (el suyo y el nuestro), las repetidas se fusionan,
#      tope propio 5/día, y al resolverse apunta acierto y PnL teórico a $5.
#   🔒 COPY_DINERO=False: no hay ruta del copy a firmar o enviar una orden.
#   🟡 Sigues en SEMI con intervalo de 10 min: este despliegue no cambia tu modo.
# Cómo usarlo (bajándolo de paste.rs, que es como se hizo con v12.8.4):
#     curl -sL <URL_paste_rs> -o /tmp/d1290.sh && bash /tmp/d1290.sh
# O pegando el script ENTERO en la sesión SSH:
#     cat > /tmp/d1290.sh <<'FIN'
#     ...(todo este fichero)...
#     FIN
#     bash /tmp/d1290.sh
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v1290_sinpat_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1
INSTALL_DIR="/opt/polymarket"
BOT="$INSTALL_DIR/poly_combos_bot.py"
ESTADO="$INSTALL_DIR/combos_estado.json"
MD5_ANTES="e08cb649f4838a963135e2f301498092"
MD5_DESPUES="1b30eafa1fe1fca1dcb29a4f6d79c880"

echo "=== DESPLIEGUE v12.9.0 SIN PAT (🟡 SEMI de verdad · ⚖️ ventaja 5%) - $(date) ==="
echo "md5 esperado antes: $MD5_ANTES · después: $MD5_DESPUES"

echo ""
echo "=== Paso 0: copia de seguridad del estado + situación actual ==="
[ -f "$ESTADO" ] && cp -a "$ESTADO" "$INSTALL_DIR/combos_estado.pre_v1290_${TS}.json" && echo "   OK copia del estado"
python3 - "$ESTADO" <<'PY' || true
import json, sys, os
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado"); raise SystemExit(0)
d = json.load(open(p))
ab = d.get("trades_copiados", []) or []
hi = d.get("historial", []) or []
print(f"   ANTES: {len(ab)} abiertas · {len(hi)} archivadas · "
      f"PnL ${sum(float(o.get('pnl') or 0) for o in hi):+.2f}")
print(f"   modo {d.get('modo', 'AUTO')} · intervalo {int(d.get('intervalo_auto_s', 600)) // 60} min · "
      f"stake {d.get('stake_mode', 'AUTO')} · tope {d.get('max_ops_dia', '?')}/día")
rc = d.get("reclamos_avisados") or {}
con = {k: v for k, v in rc.items() if float(v.get("importe") or 0) > 0.000001}
print(f"   💰 avisos de reclamo: {len(rc)} · con dinero de verdad {len(con)} "
      f"(${sum(float(v.get('importe') or 0) for v in con.values()):.2f})")
PY

echo ""
echo "=== Paso 1: extraer el parche y validar el bot desplegado ==="
echo "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" | base64 -d | gunzip > /tmp/parche_v1290.py
echo "   parche: $(wc -l < /tmp/parche_v1290.py) líneas · md5 $(md5sum /tmp/parche_v1290.py | cut -d' ' -f1)"
MD5_ACTUAL=$(md5sum "$BOT" | cut -d' ' -f1)
echo "   md5 del bot en el server: $MD5_ACTUAL"
if [ "$MD5_ACTUAL" != "$MD5_ANTES" ]; then
  if [ "$MD5_ACTUAL" == "$MD5_DESPUES" ]; then
    echo "   ⚠️ el bot YA es v12.9.0: no se hace nada"; exit 0
  fi
  echo "   ❌ el bot no es la v12.8.4 esperada: NO se toca nada (revisa qué hay desplegado)"
  exit 1
fi
cp -a "$BOT" "$INSTALL_DIR/poly_combos_bot.pre_v1290_${TS}.py"
echo "   OK copia previa: poly_combos_bot.pre_v1290_${TS}.py"

echo ""
echo "=== Paso 2: aplicar el parche sobre una copia y VALIDAR ==="
python3 /tmp/parche_v1290.py "$BOT" /tmp/bot_v1290.py
MD5_NUEVO=$(md5sum /tmp/bot_v1290.py | cut -d' ' -f1)
echo "   md5 del parcheado: $MD5_NUEVO"
if [ "$MD5_NUEVO" != "$MD5_DESPUES" ]; then
  echo "   ❌ md5 distinto del esperado: NO se sustituye nada"; exit 1
fi
python3 -m py_compile /tmp/bot_v1290.py && echo "   OK compila"
for fn in "def proponer_combo_semi" "def ejecutar_semi_aprobado" "def respuesta_propuesta" \
          "def _marcar_propuesta" "def _prune_propuestas" "def _sin_tick" \
          "PROPUESTA_VALIDA_S" "VENTAJA_MIN_EV" "ventaja insuficiente" \
          "CUENTAS DE COMPENSACIÓN" "pnl_wins" "v12.9.0 cargado" \
          "def restaurar_modo" "restaurar_modo(_est0)" \
          "def teclado_fijo" "def cmd_leer_ahora" "def curar_abiertas" "def _reparto_mapa" \
          "def top_traders" "def nombre_lb" "def perfil_trader" "def filtros_perfil" \
          "def copy_elegir" "def fills_recientes" "def registrar_señal" \
          "def resolver_señales" "def resumen_copy" "def texto_copy" "def cmd_copy" \
          "def copy_pasada" "def programar_copy_inicio" "def _caras_de" "def _lb_get" \
          "LB_API" "COPY_DINERO = False" "COPY_ACTIVO = True" "COPY_N_TRADERS = 5" \
          "COPY_TOPE_DIA = 5" "COPY_DERIVA_MAX = 0.05" "COPY_MAX_VISTOS" \
          "copy_señales" "copy_pasada(CHAT_ID)" "programar_copy_inicio()" \
          'data.startswith("lb:")' '{"text": "📡 Copy"}' "NEXT_COPY_TS"; do
  if grep -q "$fn" /tmp/bot_v1290.py; then echo "   OK    $fn"; else echo "   FALTA $fn"; fi
done
if grep -q "pleaseplease123 +\$1.0M" /tmp/bot_v1290.py; then
  echo "   ❌ sigue la lista falsa del Top escrita a mano"; exit 1
else
  echo "   OK    la lista falsa del Top ya no está (ahora es lb-api en vivo)"
fi
MALO=$(sed -n '/^def _lb_get/,/^def cmd_top/p' /tmp/bot_v1290.py \
       | grep -c "enviar_orden(\|ejecutar_combo_rfq(\|firmar_orden_v3(\|crear_rfq(\|reservar_combo(\|ejecutar_trade(\|aceptar_rfq(\|obtener_identidad_rfq(" || true)
echo "   🔒 llamadas a compra en TODA la sección 📡: ${MALO:-0} (tiene que ser 0)"
if [ "${MALO:-0}" != "0" ]; then echo "   ❌ el copy-trading podría gastar: NO se despliega"; exit 1; fi
if ! grep -q "COPY_DINERO = False" /tmp/bot_v1290.py; then
  echo "   ❌ falta COPY_DINERO = False: NO se despliega"; exit 1
fi

echo ""
echo "=== Paso 3: parar, dejar el modo en 🟡 SEMI, sustituir y arrancar ==="
systemctl stop poly-combos-bot
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
print("   → v12.9.0 restaura el modo al arrancar; antes el bot volvía SIEMPRE en AUTO")
PY
cp /tmp/bot_v1290.py "$BOT"
systemctl start poly-combos-bot
sleep 8
systemctl status poly-combos-bot --no-pager | head -8

echo ""
echo "=== Paso 4: log (arranque + 1ª auto-curación ~25 s) ==="
sleep 35
tail -30 /var/log/poly-combos-bot.log 2>&1
echo "   --- v12.9.0 cargado / modo / curación ---"
grep -a "v12.9.0 cargado\|modo=\|curación\|🧹\|↩️\|🟡\|⚖️" /var/log/poly-combos-bot.log 2>/dev/null | tail -8 || echo "   (aún ninguna)"

echo ""
echo "=== Paso 5: estado tras la cura + 🧮 cuentas de compensación ==="
python3 - "$ESTADO" <<'PY' || true
import json, sys, os
p = sys.argv[1]
if not os.path.exists(p):
    print("   sin estado"); raise SystemExit(0)
d = json.load(open(p))
ab = d.get("trades_copiados", []) or []
hi = d.get("historial", []) or []
de = d.get("descartadas", []) or []
anu = [o for o in hi if o.get("resultado") == "anulada"]
print(f"   AHORA: {len(ab)} abiertas · {len(hi)} archivadas (↩️ anuladas {len(anu)}) · "
      f"🧹 descartadas {len(de)} · PnL ${sum(float(o.get('pnl') or 0) for o in hi):+.2f}")
w = [o for o in hi if o.get("resultado") == "ganada" and float(o.get("pnl") or 0) > 0]
l = [o for o in hi if o.get("resultado") == "perdida" and float(o.get("pnl") or 0) < 0]
if w and l:
    mw = sum(float(o.get("pnl") or 0) for o in w) / len(w)
    ml = -sum(float(o.get("pnl") or 0) for o in l) / len(l)
    sw = sum(float(o.get("stake_dolares") or 0) for o in w) / len(w)
    print(f"   🧮 {len(w)} ganadas (+${mw:.2f} de media) · {len(l)} pérdidas (-${ml:.2f} de media)")
    print(f"      ⇒ {ml / mw:.2f} victorias por derrota · equilibrio {ml / (mw + ml) * 100:.1f}% "
          f"· tu win-rate {len(w) / (len(w) + len(l)) * 100:.1f}%")
    if sw > 0:
        print("      stake medio $" + f"{sw:.2f}" + " → para recuperar -$" + f"{ml:.2f}" + ": "
              + " · ".join(f"cuota {q:.1f} → {ml / (sw * (q - 1)):.1f}" for q in (1.5, 2.0, 2.5)))
    print("      ⚖️ v12.9.0 sólo compra si prob × cuota_real ≥ 1.05")
rc = d.get("reclamos_avisados") or {}
con = {k: v for k, v in rc.items() if float(v.get("importe") or 0) > 0.000001}
print(f"   💰 sin cobrar: {len(con)} posiciones (${sum(float(v.get('importe') or 0) for v in con.values()):.2f})"
      f" · {len(rc) - len(con)} avisos de importe 0 ya no cuentan")
PY

echo ""
echo "=== Paso 6: EN VIVO — qué exigiría el filtro del 5% con el catálogo real ==="
python3 - <<'PYEOF' || echo "   (sin red: comprobación omitida)"
import json, urllib.request
UA = {"User-Agent": "poly-combos-bot"}


def http(u):
    try:
        q = urllib.request.Request(u, headers=UA)
        with urllib.request.urlopen(q, timeout=20) as r:
            return r.getcode(), json.loads(r.read().decode())
    except Exception as e:
        return (getattr(e, "code", None) or 0), None


st, d = http("https://combos-rfq-api.polymarket.com/v1/rfq/combo-markets?limit=50")
legs = (d.get("markets") or d.get("data") or []) if isinstance(d, dict) else (d or [])
print(f"   catálogo RFQ (HTTP {st}): {len(legs)} legs")
b = []
for lg in legs:
    v = lg.get("outcome_prices")            # ← el catálogo RFQ usa ESTO
    if isinstance(v, str):                  #    (lista de textos [yes, no])
        try:
            v = json.loads(v)
        except Exception:
            v = []
    try:
        p = float((v or [0])[0])
    except Exception:
        p = 0.0
    if 0.70 <= p < 0.995:
        b.append((p, str(lg.get("title") or lg.get("question") or "?")[:52]))
b.sort(reverse=True)
print(f"   legs aprovechables (prob 0.70-0.995): {len(b)}")
if len(b) >= 2:
    prod = b[0][0] * b[1][0]
    est = round(1 / prod, 2) if prod > 0 else 0
    st_ = min(max(5 + 6 / est, 5), 10) if est > 1 else 5
    print(f"   mejor combo base ahora: {b[0][1]} ({b[0][0]:.2f}) + {b[1][1]} ({b[1][0]:.2f})")
    print(f"   prob {prod * 100:.1f}% · cuota est. {est:.2f} · stake ${st_:.2f} · gana +${st_ * (est - 1):.2f}")
    print(f"   ⚖️ exigiría cuota REAL ≥ {est * 1.05:.2f}; por debajo se omite ($0)")
    print(f"   🟡 en SEMI eso llegaría como PROPUESTA con ✅/❌ (caduca a los 10 min)")
PYEOF

echo "=== Paso 7: EN VIVO v12.9.0 (top real + a quien vigilaria + señales ahora) ==="
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

echo ""
echo "=== EN TELEGRAM ==="
echo "  🏆 Top         → ranking REAL (lb-api) con botones 24 h / 7 días / 30 días /"
echo "                   histórico: beneficio, volumen, margen y wallet de cada uno."
echo "                   La lista de antes estaba escrita a mano y ya no se parecía a nada."
echo "  📡 Copy        → panel del seguimiento EN PAPEL: a quiénes vigila, señales de hoy"
echo "                   (tope 5), acierto, ROI AL PRECIO NUESTRO, deriva, retraso medio y"
echo "                   desglose por trader. También con /copy (o /señales)."
echo "  🕐 1ª ronda    → ~90 s después de arrancar: elige los traders y te lo dice en el"
echo "                   chat. Después sondea cada 3 min e informa automáticamente cada 24 h."
echo "  🔒 Dinero      → CERO. COPY_DINERO=False: el copy no firma ni envía ninguna orden,"
echo "                   sólo lee ranking, fills y mids públicos (ni usa el proxy)."
echo "  🎯 Fase 2      → con ≥30 señales resueltas y ROI positivo AL PRECIO NUESTRO, la"
echo "                   señal se convertiría en un COMBO PROPIO por RFQ. Nunca líneas"
echo "                   sueltas: la regla de los combos multi-leg sigue intacta."
echo "  📊 Tus combos  → TODO sigue igual: 🟡 SEMI con propuesta ✅/❌ cada 10 min, filtro"
echo "                   de ventaja 5%, stake $5-10 y tope de 10 ops/día. El copy tiene su"
echo "                   propio tope (5 señales/día) y NO toca ese contador."
echo "  🟡 Modo        → sigues en SEMI: este despliegue no lo cambia (el bot restaura el"
echo "                   modo guardado al arrancar)."

# Publicar en diag-public (mismo mecanismo que el actualizador)
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v1290_sinpat_${TS}.log"
  B64L=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1290 sinpat ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64L" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1290 sinpat ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64L")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica el log (queda en $RESULT_FILE)"
fi
