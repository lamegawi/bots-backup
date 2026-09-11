#!/bin/bash
# Actualizador v12.8.3 — EL PANEL DICE LA VERDAD + ✅ + 🔍 Leer ahora.
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
# (Se QUITA el paso 3b de v12.8.2: las 4 ops de agosto YA están inyectadas.)
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v1283_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

HASH="05b658b2"
MD5_ESPERADO="d096c581d57f05a66784c10f004fbf9b"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== ACTUALIZADOR v12.8.3 (✅ tick del intervalo · 🔍 Leer ahora · panel honesto · 🧹 cura) - $(date) ==="
echo "HASH: $HASH · md5 esperado: $MD5_ESPERADO"

echo ""
echo "=== Paso 0: Copia de seguridad del estado ANTES de tocar nada ==="
if [ -f "$ESTADO" ]; then
  cp -a "$ESTADO" "$INSTALL_DIR/combos_estado.pre_v1283_${TS}.json"
  echo "OK: $INSTALL_DIR/combos_estado.pre_v1283_${TS}.json ($(wc -c < "$ESTADO") bytes)"
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
echo "=== Paso 1: Descargar v12.8.3 a un .new y VALIDAR (el bot sigue corriendo) ==="
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
[ -f "$INSTALL_DIR/poly_combos_bot.py" ] && cp -a "$INSTALL_DIR/poly_combos_bot.py" "$INSTALL_DIR/poly_combos_bot.pre_v1283_${TS}.py" && echo "backup del binario: poly_combos_bot.pre_v1283_${TS}.py"
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2
mv "$INSTALL_DIR/poly_combos_bot.py.new" "$INSTALL_DIR/poly_combos_bot.py"
echo "instalado: $(wc -c < "$INSTALL_DIR/poly_combos_bot.py") bytes"

echo ""
echo "=== Paso 3: Verificar funciones v12.8.3 (✅ tick · 🔍 leer · ⏸/↩️ · 🧹 cura) ==="
grep -m 1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" | head -1
for fn in "def teclado_fijo" "TICK_ACTIVO" "def intervalo_min_actual" \
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
echo "=== Paso 3b: (quitado en v12.8.3) las 4 ops de agosto YA están inyectadas ==="
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
echo "=== Paso 6b: Comprobacion EN VIVO v12.8.3 (suspendido + fills reales + cura) ==="
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
echo "=== EN TELEGRAM ==="
echo "  Teclado        → el botón ⏱ del intervalo ACTIVO lleva ✅ (se mueve solo al cambiarlo)"
echo "  🔍 Leer ahora  → lectura inmediata: bankroll, catálogo, qué abriría y estado REAL"
echo "                   de cada posición. SÓLO MIRAR: no abre, no vende, no archiva (/leer)"
echo "  📂 Abiertas    → ⏸ SUSPENDIDO (sin libro + fecha prevista) y ↩️ ANULADO en cristiano;"
echo "                   si /midpoint da 404 muestra el último precio publicado"
echo "  ✅ Cerradas    → ↩️ anuladas/devueltas aparte de 🟢/🔴 (PnL real, no inventado)"
echo "  /status        → v12.8.3 + 🩺 auto-curación (ahora con 🧹 limpieza de basura/duplicados)"
echo "  /reauditar seco→ detalle de la curación sin modificar nada"
echo "  🧹 descartadas → nada se borra: los registros fantasma/vacíos quedan auditables"

# Publicar en diag-public
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v1283_${TS}.log"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1283 ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v1283 ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica el log"
fi
