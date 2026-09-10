#!/bin/bash
# Actualizador v10.6 con HASH FIJO (v12.4 = ef9d7912: PIN fijo del user para el tope diario)
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_v106_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

HASH="ef9d7912"
INSTALL_DIR="/opt/polymarket"

echo "=== ACTUALIZADOR v10.6 HASH FIJO - $(date) ==="
echo "HASH: $HASH"

echo ""
echo "=== Paso 1: Detener bot ==="
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2

echo ""
echo "=== Paso 2: Descargar v10.6 (HASH FIJO) ==="
mkdir -p "$INSTALL_DIR"
URL="https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/poly_combos_bot.py"
echo "URL: $URL"
curl -sL --max-time 60 -o "$INSTALL_DIR/poly_combos_bot.py" "$URL"
SIZE=$(wc -c < "$INSTALL_DIR/poly_combos_bot.py" 2>/dev/null || echo 0)
echo "Descargado: $SIZE bytes"
if [ "$SIZE" -lt 30000 ]; then
  echo "ERROR: tamano muy pequeno, no se descargo bien"
  cat "$INSTALL_DIR/poly_combos_bot.py"
  exit 1
fi

echo ""
echo "=== Paso 3: Verificar version ==="
grep -m 1 "POLY COMBOS BOT" "$INSTALL_DIR/poly_combos_bot.py" | head -1
grep -m 1 "HTTP POST directo" "$INSTALL_DIR/poly_combos_bot.py" | head -1

echo ""
echo "=== Paso 4: Reiniciar bot ==="
systemctl start poly-combos-bot
sleep 5
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "=== Paso 5: Log ==="
sleep 3
tail -15 /var/log/poly-combos-bot.log 2>&1

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_v106_${TS}.log"
  CONTenido=$(cat "$RESULT_FILE")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'v106 ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'v106 ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "Publicado en $RUTA"
fi
