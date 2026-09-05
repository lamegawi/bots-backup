#!/bin/bash
# Instala poly_combos_bot como servicio systemd
# v2: trabaja desde /opt/bots/ (evita el shadow module de /root)
set -e
INSTALL_DIR="/opt/polymarket"
BOT_NAME="poly_combos_bot"

echo "== Detectando version de Python =="
PYTHON_BIN=$(which python3)
PY_VER=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  Python: $PY_BIN ($PY_VER)"

echo "== Creando directorio $INSTALL_DIR =="
mkdir -p $INSTALL_DIR

BRANCH="${BRANCH:-8a1348c}"
echo "== Bajando bot (branch $BRANCH) =="
# Estrategia 1: raw URL con rama
curl -sL --max-time 60 "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/scripts_despliegue/${BOT_NAME}.py" -o $INSTALL_DIR/${BOT_NAME}.py
chmod +x $INSTALL_DIR/${BOT_NAME}.py
SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
echo "  intento 1 (raw $BRANCH): $SIZE bytes"

if [ "$SIZE" -lt 1000 ]; then
  # Estrategia 2: API GitHub sin auth (sirve para repos publicos)
  echo "  fallback: API GH sin auth..."
  curl -sL --max-time 60 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/scripts_despliegue/${BOT_NAME}.py?ref=${BRANCH}" \
    -H "Accept: application/vnd.github.v3.raw" \
    -o $INSTALL_DIR/${BOT_NAME}.py
  SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
  echo "  intento 2 (API GH): $SIZE bytes"
fi

if [ "$SIZE" -lt 1000 ]; then
  # Estrategia 3: API GH con base64 (parsear el content)
  echo "  fallback: API GH + base64..."
  JSON=$(curl -sL --max-time 60 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/scripts_despliegue/${BOT_NAME}.py?ref=${BRANCH}")
  echo "$JSON" | python3 -c "
import sys, json, base64
try:
    d = json.load(sys.stdin)
    if 'content' in d:
        sys.stdout.buffer.write(base64.b64decode(d['content']))
    else:
        sys.exit(1)
" > $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null
  SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
  echo "  intento 3 (base64): $SIZE bytes"
fi

if [ "$SIZE" -lt 1000 ]; then
  # Estrategia 4: API GH desde diag-public
  echo "  fallback: diag-public..."
  curl -sL --max-time 60 \
    "https://raw.githubusercontent.com/lamegawi/bots-backup/diag-public/diag_hetzner/${BOT_NAME}_latest.py" \
    -o $INSTALL_DIR/${BOT_NAME}.py
  SIZE=$(stat -c %s $INSTALL_DIR/${BOT_NAME}.py 2>/dev/null || echo 0)
  echo "  intento 4 (diag-public): $SIZE bytes"
fi

chmod +x $INSTALL_DIR/${BOT_NAME}.py
echo "  tamano final: $SIZE bytes"

echo "== Instalando py-clob-client-v2 =="
pip install --break-system-packages --quiet py-clob-client-v2 eth_account requests 2>&1 | tail -5

echo "== Test rapido de importacion =="
$PYTHON_BIN -c "from py_clob_client_v2.client import ClobClient; print('  OK py-clob-client-v2 importa correctamente')" 2>&1 | head -3

echo "== Creando servicio systemd =="
cat > /etc/systemd/system/poly-combos-bot.service << SVC
[Unit]
Description=Poly Combos Bot (Telegram copy-trading)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
# Trabajamos en /opt/polymarket (evita shadow modules de /root)
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_BIN -u $INSTALL_DIR/${BOT_NAME}.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/poly-combos-bot.log
StandardError=append:/var/log/poly-combos-bot.log
Environment=PYTHONUNBUFFERED=1
# Limpia PYTHONPATH para evitar modulos shadow de /root
Environment=PYTHONPATH=/usr/lib/python3/dist-packages:/usr/local/lib/python3.12/dist-packages

[Install]
WantedBy=multi-user.target
SVC

systemctl daemon-reload
systemctl enable poly-combos-bot
systemctl restart poly-combos-bot
sleep 5
systemctl status poly-combos-bot --no-pager
echo ""
echo "== Ultimas lineas del log =="
tail -10 /var/log/poly-combos-bot.log 2>&1 || echo "(no hay log todavia)"
echo ""
echo "== Listo =="
