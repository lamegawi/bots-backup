#!/bin/bash
# Actualizador v12.7 — RESULTADOS REALES en ✅ Cerradas + AUTO-CURACIÓN
# (la re-auditoría corre sola al arrancar y cada 4h; ya no hace falta pedirla)
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v127_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

HASH="4731f473"
INSTALL_DIR="/opt/polymarket"
ESTADO="$INSTALL_DIR/combos_estado.json"

echo "=== ACTUALIZADOR v12.7 (RESULTADOS REALES + AUTO-CURACION) - $(date) ==="
echo "HASH: $HASH"

echo ""
echo "=== Paso 0: Copia de seguridad del estado ANTES de tocar nada ==="
if [ -f "$ESTADO" ]; then
  cp -a "$ESTADO" "$INSTALL_DIR/combos_estado.pre_v127_${TS}.json"
  echo "OK: $INSTALL_DIR/combos_estado.pre_v127_${TS}.json ($(wc -c < "$ESTADO") bytes)"
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
print(f"   stake aún en abiertas: ${sum(float(o.get('stake_dolares') or 0) for o in ab):.2f}")
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
echo "=== Paso 2: Descargar v12.7 (HASH FIJO) ==="
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

echo ""
echo "=== Paso 3: Verificar version, funciones y auto-curacion ==="
grep -m 1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" | head -1
for fn in "def reauditar_estado" "def programar_auditoria_inicial" "def cmd_reauditar" \
          "def verdad_real" "def estado_leg" "def cobros_wallet" "def saldo_combo_token" \
          "PARLAY_ERC1155" "AUDITORIA_CADA_H" "NEXT_AUDITORIA_TS"; do
  if grep -q "$fn" "$INSTALL_DIR/poly_combos_bot.py"; then echo "   OK    $fn"; else echo "   FALTA $fn"; fi
done
echo "   --- la auto-curacion esta enganchada al bucle? ---"
grep -n -A2 "v12.7: auto-curación (no depende del modo" "$INSTALL_DIR/poly_combos_bot.py" | head -6 || true
python3 -c "import py_compile; py_compile.compile('$INSTALL_DIR/poly_combos_bot.py', doraise=True); print('   OK    compila')"

echo ""
echo "=== Paso 4: Reiniciar bot ==="
systemctl start poly-combos-bot
sleep 8
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "=== Paso 5: Log (la 1ª auto-auditoria salta ~25s tras arrancar) ==="
sleep 30
tail -30 /var/log/poly-combos-bot.log 2>&1
echo ""
echo "   --- lineas de auditoria ---"
grep -a "auditoria\|auto-curación\|verdad:" /var/log/poly-combos-bot.log 2>/dev/null | tail -8 || echo "   (aún ninguna)"

echo ""
echo "=== Paso 6: Estado tras la auto-curacion ==="
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
corr=[o for o in hi if o.get("resultado_antes")]
if corr:
    print("   --- corregidas (antes → ahora) ---")
    for o in corr[-10:]:
        print(f"     {str(o.get('question'))[:52]:54} {o.get('resultado_antes')} "
              f"${float(o.get('pnl_antes') or 0):+7.2f} → {o.get('resultado')} ${float(o.get('pnl') or 0):+7.2f}")
PY

echo ""
echo "=== EN TELEGRAM (opcional, para ver el detalle) ==="
echo "  /reauditar seco  → informe detallado SIN modificar"
echo "  /cerradas /stats → cifras ya corregidas"

# Publicar en diag-public
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v127_${TS}.log"
  B64=$(base64 -w0 "$RESULT_FILE")
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v127 ${TS}','content':sys.argv[1],'branch':'diag-public','sha':sys.argv[2]}))" "$B64" "$SHA")
  else
    PAYLOAD=$(python3 -c "import json,sys; print(json.dumps({'message':'v127 ${TS}','content':sys.argv[1],'branch':'diag-public'}))" "$B64")
  fi
  curl -sL --max-time 40 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
else
  echo "AVISO: sin diag_token.txt, no se publica el log"
fi
