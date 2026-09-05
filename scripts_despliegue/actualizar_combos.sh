#!/bin/bash
# Actualiza poly_combos_bot a la version mas reciente
set -e
INSTALL_DIR="/opt/polymarket"
BOT_NAME="poly_combos_bot"
TS=$(date +%Y%m%d_%H%M%S)
RESULT_FILE="/tmp/combos_update_${TS}.log"
exec > >(tee -a "$RESULT_FILE") 2>&1

echo "=========================================="
echo "ACTUALIZADOR COMBOS - $(date)"
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
  local ruta="diag_hetzner/combos_update_${TS}.log"
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
    payload=$(python3 -c "import json,sys; print(json.dumps({'message':'combos update ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json,sys; print(json.dumps({'message':'combos update ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
  echo "(publicado en $ruta)"
}

echo ""
echo "=== Paso 1: Detectar branch HEAD ==="
BRANCH=$(curl -sL --max-time 20 "https://api.github.com/repos/lamegawi/bots-backup/commits/arena/01a058fe-bots-backup" | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha','')[:8])" 2>/dev/null || echo "")
[ -z "$BRANCH" ] && BRANCH="d7d8e65"
echo "Branch HEAD: $BRANCH"

echo ""
echo "=== Paso 2: Detener bot anterior ==="
systemctl stop poly-combos-bot 2>/dev/null || true
pkill -9 -f poly_combos_bot.py 2>/dev/null || true
sleep 2
echo "OK"

echo ""
echo "=== Paso 3: Descargar nuevo codigo ==="
mkdir -p "$INSTALL_DIR"
curl -sL --max-time 60 \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/scripts_despliegue/poly_combos_bot.py" \
  -o "$INSTALL_DIR/poly_combos_bot.py"
SIZE=$(wc -c < "$INSTALL_DIR/poly_combos_bot.py")
echo "Descargado: $SIZE bytes"

echo ""
echo "=== Paso 4: Verificar /opt/polymarket ==="
ls -la "$INSTALL_DIR/" 2>&1 | head -10

echo ""
echo "=== Paso 5: Verificar /etc/polymarket.env ==="
if [ -f /etc/polymarket.env ]; then
  echo "OK env existe"
  grep -c "POLY_" /etc/polymarket.env
else
  echo "[AVISO] no existe /etc/polymarket.env"
fi

echo ""
echo "=== Paso 6: Verificar token Telegram ==="
if [ -f /root/poly_combos_token.txt ]; then
  echo "OK token existe"
else
  echo "[AVISO] no existe /root/poly_combos_token.txt"
fi

echo ""
echo "=== Paso 7: Verificar servicio systemd ==="
SERVICE_FILE="/etc/systemd/system/poly-combos-bot.service"
if [ -f "$SERVICE_FILE" ]; then
  echo "OK servicio existe"
  cat "$SERVICE_FILE" | head -15
else
  echo "Creando servicio..."
  cat > "$SERVICE_FILE" << 'EOF'
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
EOF
  systemctl daemon-reload
  systemctl enable poly-combos-bot
  echo "Servicio creado"
fi

echo ""
echo "=== Paso 8: Iniciar bot ==="
systemctl start poly-combos-bot
sleep 5
systemctl status poly-combos-bot --no-pager | head -10

echo ""
echo "=== Paso 9: Verificar log ==="
sleep 3
tail -20 /var/log/poly-combos-bot.log 2>&1

echo ""
echo "=== FIN update ==="
publicar "$(cat $RESULT_FILE)"
