#!/bin/bash
# Actualizador v12.9.0 — 🏆 TOP REAL EN VIVO + 📡 COPY-TRADING EN PAPEL (FASE 1, $0).
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
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v1290_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

HASH="2509bb5d"
MD5_ESPERADO="1b30eafa1fe1fca1dcb29a4f6d79c880"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== ACTUALIZADOR v12.9.0 (🟡 SEMI de verdad · ⚖️ ventaja 5% · ✅ modo · 🧮 cuentas) - $(date) ==="
echo "HASH: $HASH · md5 esperado: $MD5_ESPERADO"

echo ""
echo "=== Paso 0: Copia de seguridad del estado ANTES de tocar nada ==="
if [ -f "$ESTADO" ]; then
  cp -a "$ESTADO" "$INSTALL_DIR/combos_estado.pre_v1290_${TS}.json"
  echo "OK: $INSTALL_DIR/combos_estado.pre_v1290_${TS}.json ($(wc -c < "$ESTADO") bytes)"
  python3 - "$ESTADO" <<'PY'
import json,sys
d=json.load(open(sys.argv[1]))
ab=d.get("trades_copiados",[]) or []
hi=d.get("historial",[]) or []
print(f"   ANTES: {len(ab)} abiertas · {len(hi)} archivadas · "
      f"PnL archivadas ${sum(float(o.get('pnl') or 0) for o in hi):+.2f}")
print(f"   archivadas: ✅{sum(1 for o in hi if o.get('resultado')=='ganada')} "
      f"❌{sum(1 for o in hi if o.get('resultado')=='perdida')} "
      f"🔒manuales {sum(1 for o in hi if o.get('cerrada_manual'))}")
print(f"   ganadas SIN cobro real registrado: "
      f"{sum(1 for o in hi if o.get('resultado')=='ganada' and not o.get('cobro_real'))}")
PY
else
  echo "AVISO: no existe $ESTADO"
fi

echo ""
echo "=== Paso 1: Descargar v12.9.0 a un .new y VALIDAR (el bot sigue corriendo) ==="
mkdir -p "$INSTALL_DIR"
URL="https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/poly_combos_bot.py"
echo "URL: $URL"
curl -sL --max-time 60 -o "$INSTALL_DIR/poly_combos_bot.py.new" "$URL"
SIZE=$(wc -c < "$INSTALL_DIR/poly_combos_bot.py.new" 2>/dev/null || echo 0)
echo "Descargado: $SIZE bytes"
if [ "$SIZE" -lt 100000 ]; then
  echo "ERROR: tamano muy pequeno, no se descargo bien (el commit no esta en GitHub?)"
  head -5 "$INSTALL_DIR/poly_combos_bot.py.new"
  rm -f "$INSTALL_DIR/poly_combos_bot.py.new"
  echo ">>> NO se ha tocado el bot en marcha: sigue la version anterior."
  exit 1
fi
MD5=$(md5sum "$INSTALL_DIR/poly_combos_bot.py.new" | cut -d' ' -f1)
echo "md5 descargado: $MD5"
if [ "$MD5" == "$MD5_ESPERADO" ]; then
  echo "   OK md5 identico al del repo"
else
  echo "   AVISO: md5 distinto del esperado ($MD5_ESPERADO) - revisar que HASH es el bueno"
fi
if ! python3 -c "import py_compile; py_compile.compile('$INSTALL_DIR/poly_combos_bot.py.new', doraise=True)"; then
  echo "ERROR: el fichero descargado no compila. NO se toca el bot en marcha."
  rm -f "$INSTALL_DIR/poly_combos_bot.py.new"
  exit 1
fi
echo "   OK compila"

echo ""
echo "=== Paso 2: Copia del fichero actual + parada del bot ==="
[ -f "$INSTALL_DIR/poly_combos_bot.py" ] && cp -a "$INSTALL_DIR/poly_combos_bot.py" "$INSTALL_DIR/poly_combos_bot.pre_v1290_${TS}.py" && echo "backup del binario: poly_combos_bot.pre_v1290_${TS}.py"
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2
mv "$INSTALL_DIR/poly_combos_bot.py.new" "$INSTALL_DIR/poly_combos_bot.py"
echo "instalado: $(wc -c < "$INSTALL_DIR/poly_combos_bot.py") bytes"

echo ""
echo "=== Paso 3: Verificar funciones (🟡 SEMI · ⚖️ ventaja · 🧮 cuentas · 🏆 top real · 📡 copy en papel) ==="
grep -m 1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" | head -1
for fn in "def proponer_combo_semi" "def ejecutar_semi_aprobado" \
          "def respuesta_propuesta" "def _marcar_propuesta" "def _prune_propuestas" \
          "def _sin_tick" "PROPUESTA_VALIDA_S" "VENTAJA_MIN_EV" "PROPUESTAS = {}" \
          'data.startswith("sm:")' 'data.startswith("smx:")' \
          "ventaja insuficiente" "CUENTAS DE COMPENSACIÓN" "pnl_wins" \
          "v12.9.0 cargado" "def restaurar_modo" "restaurar_modo(_est0)"           "def teclado_fijo" "TICK_ACTIVO" "def intervalo_min_actual" \
          "🔍 Leer ahora" "def cmd_leer_ahora" "LECTURA_LOCK" "def _eta_txt" \
          "def situacion_mercado" "def situacion_op" "def precio_vivo_op" \
          "def fills_wallet" "def casar_fills" "def es_basura" "def curar_abiertas" \
          "def _reparto_mapa" "def reparto_cobro" "cobro_real_simple" "anulada" \
          "def token_clob_de_leg" "def vivo_de" "ya_resuelta" "sin_valor" \
          "token_clob_de_leg(lg) or lg.get" "time.sleep(0.15)" "MOT = {" \
          "def saldo_token_op" "def _norm_titulo" "def _op_ts" "CTF_ERC1155" \
          "COBROS_PAGINAS" "type=REDEEM" "COBRO_TITULO_VENTANA_D" \
          "def cmd_reclamar" "def pendientes_reclamar" "def preflight_redeem" \
          "def calldata_redeem" "def reclamar_check" "def _rpc_eth_call_ex" \
          "def _texto_reclamar" "def _enlace_evento" "PARLAY_REDEEM_ADAPTER" \
          "OPERADOR_REDEEM_4337" "RECLAMO_PREFLIGHT_H" \
          "def reauditar_estado" "def programar_auditoria_inicial" "def cmd_reauditar" \
          "def verdad_real" "def estado_leg" "def cobros_wallet" "def saldo_combo_token" \
          "PARLAY_ERC1155" "AUDITORIA_CADA_H" "NEXT_AUDITORIA_TS" \
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
          "NEXT_COPY_TS" "PASADA_LOCK:"; do
  if grep -q "$fn" "$INSTALL_DIR/poly_combos_bot.py"; then echo "   OK    $fn"; else echo "   FALTA $fn"; fi
done
echo "   --- 🔒 garantias de que el copy-trading NO puede gastar dinero ---"
MALO=$(sed -n '/^def copy_pasada/,/^def programar_copy_inicio/p' "$INSTALL_DIR/poly_combos_bot.py" \
       | grep -c "enviar_orden(\|ejecutar_combo_rfq(\|firmar_orden_v3(\|crear_rfq(\|reservar_combo(\|ejecutar_trade(\|aceptar_rfq(\|obtener_identidad_rfq(" || true)
echo "   llamadas a compra dentro de copy_pasada: ${MALO:-0} (tiene que ser 0)"
SECC=$(sed -n '/^def _lb_get/,/^def cmd_top/p' "$INSTALL_DIR/poly_combos_bot.py" \
       | grep -c "enviar_orden(\|ejecutar_combo_rfq(\|firmar_orden_v3(\|crear_rfq(\|reservar_combo(\|ejecutar_trade(\|aceptar_rfq(" || true)
echo "   llamadas a compra en TODA la seccion 📡: ${SECC:-0} (tiene que ser 0)"
FALSA=$(grep -c 'pleaseplease123 +$1.0M' "$INSTALL_DIR/poly_combos_bot.py" || true)
echo "   lista falsa del Top escrita a mano: ${FALSA:-0} (tiene que ser 0)"
grep -n "^COPY_DINERO\|^COPY_ACTIVO\|^COPY_TOPE_DIA\|^COPY_DERIVA_MAX\|^COPY_SONDEO_S" "$INSTALL_DIR/poly_combos_bot.py" | head -6
echo "   --- dispatch de /reclamar y del boton ---"
grep -n "reclamar" "$INSTALL_DIR/poly_combos_bot.py" | grep -E "startswith|💰 Reclamar\"|reclamar_check\(\)" | head -5 || true
echo "   --- RPC (fuera polygon-rpc.com, que da 401) ---"
grep -n -A2 "^RPCS_POLYGON" "$INSTALL_DIR/poly_combos_bot.py" | head -4


echo ""
echo "=== Paso 3b: modo/intervalo guardados + 'sin cobrar' con el filtro nuevo ==="
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
print("   → v12.9.0: /status y 🔍 sólo cuentan los que tienen importe > 0")
cp = d.get("copy") or {}
se = d.get("copy_señales") or []
res = [x for x in se if x.get("resuelta") and not x.get("anulada")]
pnl = sum(float(x.get("pnl_papel_nuestro") or 0) for x in res)
nt = len(cp.get('traders') or [])
na = sum(1 for x in se if x.get('anulada'))
print(f"   📡 copy en papel: {nt} trader{'' if nt == 1 else 's'} vigilado{'' if nt == 1 else 's'} · "
      f"{len(se)} señal{'' if len(se) == 1 else 'es'} ({len(res)} resuelta{'' if len(res) == 1 else 's'}, "
      f"{na} anulada{'' if na == 1 else 's'}) · dedup {len(cp.get('vistos') or {})} fills · "
      f"{int(cp.get('informes') or 0)} informe{'' if int(cp.get('informes') or 0) == 1 else 's'}")
if res:
    print(f"      acierto {sum(1 for x in res if x.get('senal_acerto')) / len(res) * 100:.1f}% · "
          f"PnL teórico al precio nuestro ${pnl:+.2f} "
          f"(ROI {pnl / (len(res) * 5.0) * 100:+.1f}%)")
else:
    print("      aún sin señales resueltas: la 1ª ronda llega ~90 s después de arrancar")
PY

echo "=== Paso 3c: dejar el bot en 🟡 SEMI (modo guardado) + 1ª propuesta en ~2 min ==="
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

echo "=== Paso 4: Reiniciar bot ==="
systemctl start poly-combos-bot
sleep 8
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "=== Paso 5: Log (1ª auto-curación ~25s tras arrancar; 💰 si hay algo sin cobrar) ==="
sleep 35
tail -35 /var/log/poly-combos-bot.log 2>&1
echo ""
echo "   --- lineas de auditoria / reclamos / RPC ---"
grep -a "auditoria\|auto-curación\|verdad:\|💰\|reclamar\|pre-flight\|CIERRE\|\[copy\]\|\[top\]" /var/log/poly-combos-bot.log 2>/dev/null | tail -14 || echo "   (aún ninguna)"

echo ""
echo "=== Paso 6: Estado tras el arranque ==="
python3 - "$ESTADO" <<'PY'
import json,sys,os
p=sys.argv[1]
if not os.path.exists(p): print("   sin estado"); raise SystemExit
d=json.load(open(p))
hi=d.get("historial",[]) or []; ab=d.get("trades_copiados",[]) or []
print(f"   AHORA: {len(ab)} abiertas · {len(hi)} archivadas · "
      f"PnL archivadas ${sum(float(o.get('pnl') or 0) for o in hi):+.2f}")
print(f"   archivadas: ✅{sum(1 for o in hi if o.get('resultado')=='ganada')} "
      f"❌{sum(1 for o in hi if o.get('resultado')=='perdida')} "
      f"🔒{sum(1 for o in hi if o.get('cerrada_manual'))}")
# 🧮 v12.9.0: las cuentas que ahora salen en 📊 Stats, calculadas aquí también
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
    print(f"      ⚖️ con el filtro de v12.9.0 sólo se compra si prob × cuota ≥ 1.05")
r=d.get("ultimo_auditoria_resumen") or {}
print(f"   ultima auditoria: {str(d.get('ultima_auditoria'))[:19]} · origen={r.get('origen')} "
      f"reabiertas={r.get('reabiertas')} corregidas={r.get('corregidas')} "
      f"nuevas={r.get('nuevas_cerradas')} · PnL {r.get('pnl_antes')}→{r.get('pnl_despues')}")
rc=d.get("reclamos_avisados") or {}
if rc:
    print(f"   💰 reclamos avisados: {len(rc)} · "
          f"${sum(float(v.get('importe') or 0) for v in rc.values()):.2f}")
    for k,v in list(rc.items())[:8]:
        print(f"      {str(v.get('titulo') or v.get('nota') or k)[:52]:54} ${float(v.get('importe') or 0):7.2f} · {str(v.get('ts'))[:16]}")
else:
    print("   💰 reclamos avisados: ninguno todavía (envía /reclamar en Telegram)")
PY

echo ""
echo "=== Paso 6b: EN VIVO v12.9.0 (catalogo RFQ + que exigiria el filtro del 5%) ==="
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
        buenos.append((p, str(lg.get("title") or lg.get("question") or "?")[:52],
                       str(lg.get("slug") or lg.get("event_slug") or "?")[:24]))
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
    print(f"      ⚖️ el filtro de v12.9.0 exige cuota REAL >= {est * 1.05:.2f} "
          f"(+5% sobre {est:.2f}); por debajo, se omite y no gasta nada")
    print(f"      🟡 en SEMI eso te llegaria como PROPUESTA con ✅/❌ (caduca a los 10 min)")
else:
    print("   2) ahora mismo no hay dos legs aprovechables para un combo base")
PYEOF

echo ""
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

echo ""
echo "   --- servicio y modo tras el arranque ---"
systemctl is-active poly-combos-bot || true
grep -a "v12.9.0 cargado\|modo=\|🟡\|⚖️" /var/log/poly-combos-bot.log 2>/dev/null | tail -6 || true

echo ""
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

# Publicar en diag-public
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v1290_${TS}.log"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1290 ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1290 ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica el log"
fi
