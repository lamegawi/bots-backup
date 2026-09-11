#!/bin/bash
# Actualizador v12.8 — 💰 /reclamar (ganadas SIN cobrar) + RPC vivos
# Incluye TODO lo de v12.6/v12.7 (resultados reales + auto-curación): es el
# mismo fichero del bot, parcheado encima.
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v128_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

HASH="2187f7a1"
MD5_ESPERADO="68c2347f8626f888920de16e4dc1e289"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== ACTUALIZADOR v12.8 (💰 /reclamar + RPC vivos) - $(date) ==="
echo "HASH: $HASH · md5 esperado: $MD5_ESPERADO"

echo ""
echo "=== Paso 0: Copia de seguridad del estado ANTES de tocar nada ==="
if [ -f "$ESTADO" ]; then
  cp -a "$ESTADO" "$INSTALL_DIR/combos_estado.pre_v128_${TS}.json"
  echo "OK: $INSTALL_DIR/combos_estado.pre_v128_${TS}.json ($(wc -c < "$ESTADO") bytes)"
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
echo "=== Paso 1: Detener bot ==="
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2

echo ""
echo "=== Paso 2: Descargar v12.8 (HASH FIJO) ==="
mkdir -p "$INSTALL_DIR"
URL="https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/poly_combos_bot.py"
echo "URL: $URL"
curl -sL --max-time 60 -o "$INSTALL_DIR/poly_combos_bot.py" "$URL"
SIZE=$(wc -c < "$INSTALL_DIR/poly_combos_bot.py" 2>/dev/null || echo 0)
echo "Descargado: $SIZE bytes"
if [ "$SIZE" -lt 100000 ]; then
  echo "ERROR: tamano muy pequeno, no se descargo bien"
  head -5 "$INSTALL_DIR/poly_combos_bot.py"
  exit 1
fi
MD5=$(md5sum "$INSTALL_DIR/poly_combos_bot.py" | cut -d' ' -f1)
echo "md5 servidor: $MD5"
if [ "$MD5" == "$MD5_ESPERADO" ]; then echo "   OK md5 identico al del repo"; else echo "   AVISO: md5 distinto (comprobar que HASH es el bueno)"; fi

echo ""
echo "=== Paso 3: Verificar version y funciones v12.8 (+ las de v12.6/12.7) ==="
grep -m 1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" | head -1
for fn in "def cmd_reclamar" "def pendientes_reclamar" "def preflight_redeem" \
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
python3 -c "import py_compile; py_compile.compile('$INSTALL_DIR/poly_combos_bot.py', doraise=True); print('   OK    compila')"

echo ""
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
grep -a "auditoria\|auto-curación\|verdad:\|💰\|reclamar\|pre-flight" /var/log/poly-combos-bot.log 2>/dev/null | tail -10 || echo "   (aún ninguna)"

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
        print(f"      {str(v.get('titulo') or k)[:56]:58} ${float(v.get('importe') or 0):7.2f} · {str(v.get('ts'))[:16]}")
else:
    print("   💰 reclamos avisados: ninguno todavía (envía /reclamar en Telegram)")
PY

echo ""
echo "=== EN TELEGRAM ==="
echo "  /reclamar        → ganadas SIN cobrar: cuánto, cuándo, enlace y cómo cobrarlo"
echo "  /reclamar prueba → fuerza la prueba on-chain (sin usar la caché de 24h)"
echo "  💰 Reclamar      → botón nuevo en el teclado"
echo "  /status          → ahora muestra 🩺 auto-curación y 💰 sin cobrar"
echo "  /reauditar seco  → detalle de la re-auditoría sin modificar nada"

# Publicar en diag-public
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v128_${TS}.log"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v128 ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v128 ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica el log"
fi
