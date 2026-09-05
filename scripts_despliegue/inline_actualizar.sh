#!/bin/bash
# Actualizador INLINE - no descarga nada, todo embebido
set -e
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

echo "=========================================="
echo "ACTUALIZADOR INLINE v10.5 - $(date)"
echo "=========================================="

HASH="0d7c701c"
INSTALL_DIR="/opt/polymarket"

echo ""
echo "=== Paso 1: Detener bot anterior ==="
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2
echo "OK"

echo ""
echo "=== Paso 2: Descargar codigo v10.5 desde GitHub ==="
mkdir -p "$INSTALL_DIR"
echo "URL: https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/poly_combos_bot.py"
curl -sL --max-time 60 -o "$INSTALL_DIR/poly_combos_bot.py" \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${HASH}/scripts_despliegue/poly_combos_bot.py"
SIZE=$(wc -c < "$INSTALL_DIR/poly_combos_bot.py" 2>/dev/null || echo 0)
echo "Descargado: $SIZE bytes"
if [ "$SIZE" -lt 1000 ]; then
  echo "[ERROR] descarga muy pequena o fallida"
  cat "$INSTALL_DIR/poly_combos_bot.py"
  exit 1
fi

echo ""
echo "=== Paso 3: Verificar setup ==="
ls -la "$INSTALL_DIR/poly_combos_bot.py"
[ -f /etc/polymarket.env ] && echo "env: OK" || echo "env: FALTA"
[ -f /root/poly_combos_token.txt ] && echo "token: OK" || echo "token: FALTA"

echo ""
echo "=== Paso 4: Verificar servicio systemd ==="
SERVICE_FILE="/etc/systemd/system/poly-combos-bot.service"
if [ ! -f "$SERVICE_FILE" ]; then
  cat > "$SERVICE_FILE" << 'SVCEOF'
[Unit]
Description=Poly Combos Bot (Telegram copy-trading)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/polymarket
ExecStart=/usr/bin/python3 -u /opt/polymarket/poly_combos_bot.py
Restart=always
RestartSec=10
StandardOutput=append:/var/log/poly-combos-bot.log
StandardError=append:/var/log/poly-combos-bot.log
EnvironmentFile=/etc/polymarket.env

[Install]
WantedBy=multi-user.target
SVCEOF
  systemctl daemon-reload
  systemctl enable poly-combos-bot
  echo "Servicio creado"
else
  echo "Servicio existe OK"
fi

echo ""
echo "=== Paso 5: Iniciar bot ==="
systemctl start poly-combos-bot
sleep 5
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "=== Paso 6: Verificar log ==="
sleep 3
tail -15 /var/log/poly-combos-bot.log 2>&1

echo ""
echo "=== FIN update ==="

# Publicar
PAT=$(cat /root/diag_token.txt 2>/dev/null | tr -d '\n' || true)
[ -z "$PAT" ] && PAT=$(cat ~/diag_token.txt 2>/dev/null | tr -d '\n' || true)
if [ -n "$PAT" ]; then
  RUTA="diag_hetzner/combos_update_${TS}.log"
  CONTenido=$(cat "$RESULT_FILE")
  B64=$(echo -n "$CONTenido" | base64 -w0)
  SHA=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}?ref=diag-public" -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  if [ -n "$SHA" ]; then
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'update ${TS}','content':'$B64','branch':'diag-public','sha':'$SHA'}))")
  else
    PAYLOAD=$(python3 -c "import json; print(json.dumps({'message':'update ${TS}','content':'$B64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT "https://api.github.com/repos/lamegawi/bots-backup/contents/${RUTA}" -H "Authorization: token ${PAT}" -H "Content-Type: application/json" -d "$PAYLOAD" >/dev/null 2>&1
  echo "(publicado en $RUTA)"
fi
