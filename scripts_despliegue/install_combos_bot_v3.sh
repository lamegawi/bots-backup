#!/bin/bash
# Instala poly_combos_bot v3 - PUBLICA RESULTADOS a diag-public
# Para que el agente pueda leer el resultado sin tener que pegar nada.
set -e
INSTALL_DIR="/opt/polymarket"
BOT_NAME="poly_combos_bot"
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_install_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

echo "=========================================="
echo "INSTALADOR v3 - $(date)"
echo "=========================================="

# Cargar PAT
PAT=""
for p in /root/diag_token.txt ~/diag_token.txt /tmp/diag_token.txt; do
  if [ -f "$p" ]; then
    PAT=$(cat "$p" | tr -d '\n')
    if [ -n "$PAT" ]; then break; fi
  fi
done

publicar() {
  local contenido="$1"
  local ruta="diag_hetzner/combos_install_${TS}.log"
  if [ -z "$PAT" ]; then
    echo "(sin PAT, no se publica)"
    return
  fi
  local b64=$(echo -n "$contenido" | base64 -w0)
  local sha=""
  sha=$(curl -sL --max-time 20 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}?ref=diag-public" \
    -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  local payload
  if [ -n "$sha" ]; then
    payload=$(python3 -c "import json,sys; print(json.dumps({'message':'combos install ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json,sys; print(json.dumps({'message':'combos install ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
  echo "(publicado en $ruta)"
}

echo ""
echo "=== Paso 1: Detener bot anterior ==="
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2
echo "OK"

echo ""
echo "=== Paso 2: Verificar /root ==="
ls -la /root/copy* 2>&1 || echo "(no hay copy.py - OK)"
ls -la /opt/polymarket/ 2>&1 || mkdir -p /opt/polymarket

echo ""
echo "=== Paso 3: Detectar Python ==="
PY_BIN=$(which python3)
echo "Python: $PY_BIN ($($PY_BIN -c 'import sys; print(sys.version)'))"

echo ""
echo "=== Paso 4: Instalar py-clob-client-v2 ==="
pip install --break-system-packages --quiet py-clob-client-v2 eth_account requests 2>&1 | tail -3 || echo "(pip ya instalado o error)"

echo ""
echo "=== Paso 5: Test de importacion ==="
$PY_BIN -c "from py_clob_client_v2.client import ClobClient; print('OK')" 2>&1

echo ""
echo "=== Paso 6: Descargar bot ==="
BRANCH="0ea7b68"
SIZE=0
URL="https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/scripts_despliegue/${BOT_NAME}.py"
echo "Probando: $URL"
curl -sL --max-time 60 "$URL" -o $INSTALL_DIR/${BOT_NAME}.py
SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
echo "Descarga 1 (raw): $SIZE bytes"
if [ "$SIZE" -lt 1000 ]; then
  echo "Probando API GH..."
  curl -sL --max-time 60 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/scripts_despliegue/${BOT_NAME}.py?ref=${BRANCH}" \
    -H "Accept: application/vnd.github.v3.raw" \
    -o $INSTALL_DIR/${BOT_NAME}.py
  SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
  echo "Descarga 2 (api-raw): $SIZE bytes"
fi
if [ "$SIZE" -lt 1000 ]; then
  echo "Probando API GH + base64..."
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
  echo "Descarga 3 (base64): $SIZE bytes"
fi
chmod +x $INSTALL_DIR/${BOT_NAME}.py
echo "Tamano final: $SIZE bytes"
if [ "$SIZE" -lt 1000 ]; then
  echo "ERROR: archivo no se descargo bien"
  publicar "$(cat $RESULT_FILE 2>/dev/null) ERROR DESCARGA"
  exit 1
fi

echo ""
echo "=== Paso 7: Verificar sintaxis ==="
$PY_BIN -c "import ast; ast.parse(open('$INSTALL_DIR/${BOT_NAME}.py').read())" && echo "OK sintaxis"
echo "head:"
head -3 $INSTALL_DIR/${BOT_NAME}.py

echo ""
echo "=== Paso 8: Crear servicio systemd ==="
cat > /etc/systemd/system/poly-combos-bot.service << SVC
[Unit]
Description=Poly Combos Bot (Telegram copy-trading)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_DIR
ExecStart=$PY_BIN -u $INSTALL_DIR/${BOT_NAME}.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/poly-combos-bot.log
StandardError=append:/var/log/poly-combos-bot.log
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONPATH=/usr/lib/python3/dist-packages:/usr/local/lib/python3.12/dist-packages

[Install]
WantedBy=multi-user.target
SVC
systemctl daemon-reload
systemctl enable poly-combos-bot
systemctl restart poly-combos-bot
sleep 6
echo ""
echo "=== Paso 9: Estado del servicio ==="
systemctl status poly-combos-bot --no-pager | head -15
echo ""
echo "=== Paso 10: Log ==="
tail -20 /var/log/poly-combos-bot.log 2>&1

echo ""
echo "=========================================="
echo "FIN - $(date)"
echo "=========================================="
publicar "$(cat $RESULT_FILE 2>/dev/null)"
echo "Resultado publicado en diag_hetzner/combos_install_${TS}.log"
