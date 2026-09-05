#!/bin/bash
# Actualiza poly_combos_bot a la version mas reciente
set -e
INSTALL_DIR="/opt/polymarket"
BOT_NAME="poly_combos_bot"
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

echo "=========================================="
echo "ACTUALIZACION - $(date)"
echo "=========================================="

PAT=""
for p in /root/diag_token.txt ~/diag_token.txt /tmp/diag_token.txt; do
  if [ -f "$p" ]; then
    PAT=$(cat "$p" | tr -d '\n')
    [ -n "$PAT" ] && break
  fi
done

publicar() {
  local contenido="$1"
  local ruta="diag_hetzner/combos_update_${TS}.log"
  [ -z "$PAT" ] && return
  local b64=$(echo -n "$contenido" | base64 -w0)
  local sha=""
  sha=$(curl -sL --max-time 20 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}?ref=diag-public" \
    -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  local payload
  if [ -n "$sha" ]; then
    payload=$(python3 -c "import json; print(json.dumps({'message':'combos update ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json; print(json.dumps({'message':'combos update ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
  echo "(publicado en $ruta)"
}

echo "== Detener bot =="
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2

echo ""
echo "== Borrar archivo antiguo =="
rm -f $INSTALL_DIR/${BOT_NAME}.py

echo ""
echo "== Descargar nueva version =="
# Detectar el hash actual de la rama y usar la URL con ref (no main)
BRANCH=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/commits/arena/01a058fe-bots-backup" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha','')[:8])" 2>/dev/null)
[ -z "$BRANCH" ] && BRANCH="be6594c"
echo "Branch: $BRANCH"
SIZE=0
# Intento 1: raw URL
curl -sL --max-time 60 "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/scripts_despliegue/${BOT_NAME}.py" -o $INSTALL_DIR/${BOT_NAME}.py
SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
echo "raw: $SIZE bytes"
if [ "$SIZE" -lt 1000 ]; then
  # Intento 2: API GH + base64 (parsear JSON)
  echo "fallback: API GH base64"
  JSON=$(curl -sL --max-time 60 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/scripts_despliegue/${BOT_NAME}.py?ref=${BRANCH}")
  echo "$JSON" | python3 -c "
import sys, json, base64
try:
    d = json.load(sys.stdin)
    if 'content' in d:
        sys.stdout.buffer.write(base64.b64decode(d['content']))
except: pass
" > $INSTALL_DIR/${BOT_NAME}.py
  SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
  echo "api+base64: $SIZE bytes"
fi
chmod +x $INSTALL_DIR/${BOT_NAME}.py
echo "Tamano final: $SIZE bytes"

if [ "$SIZE" -lt 1000 ]; then
  echo "ERROR descarga"
  publicar "$(cat $RESULT_FILE 2>/dev/null)"
  exit 1
fi

echo ""
echo "== Verificar sintaxis =="
python3 -c "import ast; ast.parse(open('$INSTALL_DIR/${BOT_NAME}.py').read())" && echo "OK"
head -3 $INSTALL_DIR/${BOT_NAME}.py

echo ""
echo "== Reiniciar servicio =="
systemctl restart poly-combos-bot
sleep 8
systemctl status poly-combos-bot --no-pager | head -15
echo ""
echo "== Log reciente =="
tail -25 /var/log/poly-combos-bot.log 2>&1

echo ""
echo "=========================================="
echo "FIN - $(date)"
echo "=========================================="
publicar "$(cat $RESULT_FILE 2>/dev/null)"
