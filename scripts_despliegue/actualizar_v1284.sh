#!/bin/bash
# Actualizador v12.8.4 — 🟡 SEMI DE VERDAD + ⚖️ VENTAJA MÍNIMA 5%.
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
# Incluye TODO lo de v12.6→v12.8.3: es el mismo fichero del bot, parcheado encima.
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v1284_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

HASH="a3fee478"
MD5_ESPERADO="e08cb649f4838a963135e2f301498092"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== ACTUALIZADOR v12.8.4 (🟡 SEMI de verdad · ⚖️ ventaja 5% · ✅ modo · 🧮 cuentas) - $(date) ==="
echo "HASH: $HASH · md5 esperado: $MD5_ESPERADO"

echo ""
echo "=== Paso 0: Copia de seguridad del estado ANTES de tocar nada ==="
if [ -f "$ESTADO" ]; then
  cp -a "$ESTADO" "$INSTALL_DIR/combos_estado.pre_v1284_${TS}.json"
  echo "OK: $INSTALL_DIR/combos_estado.pre_v1284_${TS}.json ($(wc -c < "$ESTADO") bytes)"
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
echo "=== Paso 1: Descargar v12.8.4 a un .new y VALIDAR (el bot sigue corriendo) ==="
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
[ -f "$INSTALL_DIR/poly_combos_bot.py" ] && cp -a "$INSTALL_DIR/poly_combos_bot.py" "$INSTALL_DIR/poly_combos_bot.pre_v1284_${TS}.py" && echo "backup del binario: poly_combos_bot.pre_v1284_${TS}.py"
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2
mv "$INSTALL_DIR/poly_combos_bot.py.new" "$INSTALL_DIR/poly_combos_bot.py"
echo "instalado: $(wc -c < "$INSTALL_DIR/poly_combos_bot.py") bytes"

echo ""
echo "=== Paso 3: Verificar funciones v12.8.4 (🟡 SEMI · ⚖️ ventaja · ✅ modo · 🧮 cuentas) ==="
grep -m 1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" | head -1
for fn in "def proponer_combo_semi" "def ejecutar_semi_aprobado" \
          "def respuesta_propuesta" "def _marcar_propuesta" "def _prune_propuestas" \
          "def _sin_tick" "PROPUESTA_VALIDA_S" "VENTAJA_MIN_EV" "PROPUESTAS = {}" \
          'data.startswith("sm:")' 'data.startswith("smx:")' \
          "ventaja insuficiente" "CUENTAS DE COMPENSACIÓN" "pnl_wins" \
          "v12.8.4 cargado" "def restaurar_modo" "restaurar_modo(_est0)"           "def teclado_fijo" "TICK_ACTIVO" "def intervalo_min_actual" \
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
          "PARLAY_ERC1155" "AUDITORIA_CADA_H" "NEXT_AUDITORIA_TS"; do
  if grep -q "$fn" "$INSTALL_DIR/poly_combos_bot.py"; then echo "   OK    $fn"; else echo "   FALTA $fn"; fi
done
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
print("   → v12.8.4: /status y 🔍 sólo cuentan los que tienen importe > 0")
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
print("   → v12.8.4 restaura el modo al arrancar; antes el bot volvía SIEMPRE en AUTO")
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
grep -a "auditoria\|auto-curación\|verdad:\|💰\|reclamar\|pre-flight\|CIERRE" /var/log/poly-combos-bot.log 2>/dev/null | tail -10 || echo "   (aún ninguna)"

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
# 🧮 v12.8.4: las cuentas que ahora salen en 📊 Stats, calculadas aquí también
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
echo "=== Paso 6b: EN VIVO v12.8.4 (catalogo RFQ + que exigiria el filtro del 5%) ==="
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
echo "=== EN TELEGRAM ==="
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

# Publicar en diag-public
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v1284_${TS}.log"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1284 ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1284 ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica el log"
fi
