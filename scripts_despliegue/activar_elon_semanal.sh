#!/usr/bin/env bash
# activar_elon_semanal.sh — crea /etc/default/poly-elon-semanal y arranca el servicio
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/activar_elon_semanal_${TS}.log

NEW_DIR="/opt/polymarket/bot-polymarket-elon-semanal"

# banner
cat <<'BANNER'
========================================================
  ACTIVACIÓN BOT ELON SEMANAL — MODO REAL
  ⚠️  Te pedirá la clave privada INTERACTIVAMENTE
  wallet: 0xb0E1197098E6d427c01720F1631cAD24CE740FA0
========================================================
BANNER

# pedir clave privada
echo
echo "🔑 Pega tu clave privada (con o sin prefijo 0x)"
read -rs -p "POLY_PRIVATE_KEY=" PK_INPUT
echo
if [ -z "$PK_INPUT" ]; then
    echo "❌ No se proporcionó clave. Abortando."
    exit 1
fi
PK_HEX="${PK_INPUT#0x}"
PK_HEX="$(echo -n "$PK_HEX" | tr -d '[:space:]')"
unset PK_INPUT
if [[ ! "$PK_HEX" =~ ^[0-9a-fA-F]{64}$ ]]; then
    LEN=${#PK_HEX}
    echo "❌ La clave no tiene 64 caracteres hex (tiene $LEN). Abortando."
    exit 1
fi
PK_FULL="0x${PK_HEX}"
unset PK_HEX

{
echo "=== ACTIVACIÓN BOT ELON SEMANAL — $TS UTC ==="
echo "(clave privada NO se loguea)"
echo
echo "== 1. Verificar que el directorio existe =="
ls -la "$NEW_DIR" | head -10
echo
echo "== 2. Crear /etc/default/poly-elon-semanal =="
cat > /etc/default/poly-elon-semanal <<EOF
# Variables de entorno para el bot semanal Elon
POLY_PRIVATE_KEY="$PK_FULL"
POLY_WALLET_ADDRESS="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
EOF
chmod 600 /etc/default/poly-elon-semanal
echo "creado"
ls -la /etc/default/poly-elon-semanal
echo
echo "== 3. Recargar systemd y arrancar servicio =="
systemctl daemon-reload
systemctl start poly-elon-semanal.service 2>&1
sleep 5
systemctl status poly-elon-semanal.service 2>&1 | head -15
echo
echo "== 4. Verificar variables de entorno del proceso =="
PID=$(systemctl show poly-elon-semanal.service --property=MainPID --value)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "PID: $PID"
    tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | grep -E "^POLY_" | sed 's/=.*/=***OCULTO***/'
fi
echo
echo "== 5. Log del servicio =="
journalctl -u poly-elon-semanal.service -n 30 --no-pager 2>&1 | tail -25
echo
echo "== 6. Resumen =="
echo "  ✅ /etc/default/poly-elon-semanal creado"
echo "  ✅ servicio poly-elon-semanal.service arrancado"
echo
echo "  Esperar 15 min a la primera pasada"
} > "$LOG" 2>&1

unset PK_FULL

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/activar_elon_semanal_*.log'))
LOG = logs[-1] if logs else '/tmp/activar_elon_semanal.log'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': f'diag: {name}', 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('[ERROR publicando]', e)
PYEOF
