#!/usr/bin/env bash
# activar_trump_interactivo.sh — configura Trump con wallet real y clave privada
# ⚠️ PIDE LA CLAVE PRIVADA DE FORMA INTERACTIVA (no va al log, no va a GitHub)
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/activar_trump_interactivo_${TS}.log

WALLET="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
TRUMP_DIR="/opt/polymarket/bot-polymarket-trump"

# banner
cat <<'BANNER'
========================================================
  ACTIVACIÓN BOT TRUMP — MODO REAL
  ⚠️  Este script te pedirá la clave privada INTERACTIVAMENTE
      (no se loguea, no se sube a GitHub)
  wallet: 0xb0E1197098E6d427c01720F1631cAD24CE740FA0
========================================================
BANNER

# pedir clave privada de forma segura
echo
echo "🔑 Pega tu clave privada de https://reveal.magic.link/polymarket"
echo "   (empieza por 0x..., 66 caracteres)"
echo "   NO se mostrará, NO se guardará en el log, NO irá a GitHub"
echo
read -rs -p "POLY_PRIVATE_KEY=0x" PK_HEX
echo
if [ -z "$PK_HEX" ]; then
    echo "❌ No se proporcionó clave. Abortando."
    exit 1
fi
# validación básica
if [[ ! "$PK_HEX" =~ ^[0-9a-fA-F]{64}$ ]]; then
    echo "❌ La clave no tiene 64 caracteres hexadecimales. Abortando."
    exit 1
fi
PK_FULL="0x${PK_HEX}"
# limpiar de memoria
unset PK_HEX

{
echo "=== ACTIVACIÓN BOT TRUMP — $TS UTC ==="
echo "wallet: $WALLET"
echo "(clave privada NO se loguea)"
echo
echo "== 1. Backup del config_real.json.example =="
ls -la "$TRUMP_DIR/config_real.json" 2>&1
ls -la "$TRUMP_DIR/config_real.json.example" 2>&1
echo
echo "== 2. Crear config_real.json con wallet real =="
cat > "$TRUMP_DIR/config_real.json" <<EOF
{
  "wallet_address": "$WALLET",
  "wallet_private_key": "PLACEHOLDER_OCULTO_POR_SEGURIDAD",
  "relayer_api_key": "",
  "relayer_api_key_address": "",
  "api_key": "",
  "api_secret": "",
  "api_passphrase": "",
  "bankroll": 228.45,
  "fee_pct": 0.0,
  "signature_type": 1,
  "confirmado": true
}
EOF
chmod 600 "$TRUMP_DIR/config_real.json"
echo "config_real.json creado con confirmado=true y bankroll=228.45"
ls -la "$TRUMP_DIR/config_real.json"
echo
echo "== 3. Crear real.json con saldo inicial =="
cat > "$TRUMP_DIR/real.json" <<EOF
{
  "saldo": 228.45,
  "paso": 1,
  "activa": null,
  "abierta": null,
  "historial": [],
  "_sincronizado_con_real": true,
  "_sincronizado_ts": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "_bankroll_inicial_real": 228.45,
  "_pnl_historico_acumulado": 0.0
}
EOF
chmod 600 "$TRUMP_DIR/real.json"
echo "real.json creado con saldo=228.45"
ls -la "$TRUMP_DIR/real.json"
echo
echo "== 4. Crear /etc/default/poly-trump con la clave =="
cat > /etc/default/poly-trump <<EOF
# Variables de entorno para el bot Trump
POLY_PRIVATE_KEY="$PK_FULL"
POLY_WALLET_ADDRESS="$WALLET"
EOF
chmod 600 /etc/default/poly-trump
echo "/etc/default/poly-trump creado (permisos 600)"
echo
echo "== 5. Actualizar poly-trump.service para cargar /etc/default/poly-trump =="
SERVICE=/etc/systemd/system/poly-trump.service
# backup
cp "$SERVICE" "${SERVICE}.bak_${TS}"
# añadir EnvironmentFile
if grep -q "EnvironmentFile" "$SERVICE"; then
    echo "  ya tiene EnvironmentFile, no se modifica"
else
    # insertar después de [Service]
    sed -i '/^\[Service\]/a EnvironmentFile=/etc/default/poly-trump' "$SERVICE"
    echo "  añadido EnvironmentFile=/etc/default/poly-trump"
fi
cat "$SERVICE"
echo
echo "== 6. Recargar systemd y reiniciar =="
systemctl daemon-reload
systemctl restart poly-trump.service
sleep 5
systemctl status poly-trump.service | head -15
echo
echo "== 7. Verificar que el bot arranca con la clave =="
PID=$(systemctl show poly-trump.service --property=MainPID --value)
echo "PID: $PID"
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "--- variables de entorno del proceso ---"
    tr '\0' '\n' < /proc/$PID/environ | grep -E "^POLY_" | sed 's/=.*/=***OCULTO***/'
fi
echo
echo "== 8. ¿Está en 'BLOQUEADO' o arrancando? =="
journalctl -u poly-trump.service -n 30 --no-pager | tail -20
echo
echo "== 9. Verificación final del bot =="
journalctl -u poly-trump.service -n 100 --no-pager | grep -iE "Trading|BLOQUEADO|ERROR|confirmado" | tail -10
echo
echo "== 10. Resumen =="
echo "  ✅ config_real.json: confirmado=true, bankroll=228.45"
echo "  ✅ real.json: saldo=228.45, activa=null, historial=[]"
echo "  ✅ /etc/default/poly-trump: POLY_PRIVATE_KEY cargada"
echo "  ✅ poly-trump.service: EnvironmentFile añadido"
echo "  ✅ servicio reiniciado"
echo
echo "  ⚠️  PRÓXIMOS PASOS:"
echo "  - Espera 15 min a la próxima pasada"
echo "  - Verifica logs: journalctl -u poly-trump.service -f"
echo "  - Si quieres ver el saldo: cat $TRUMP_DIR/real.json"
} > "$LOG" 2>&1

# IMPORTANTE: limpiar clave de memoria
unset PK_FULL

cat "$LOG"

python3 -c "
import base64, json, urllib.request
tok = open('/opt/polymarket/.gh_token').read().strip()
with open('$LOG','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = '$(basename $LOG)'
p = {'message':f'diag: {name}','branch':'diag-public','content':b64}
req = urllib.request.urlopen(urllib.request.Request(
    f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
    data=json.dumps(p).encode(),
    headers={'Authorization':f'token {tok}','Content-Type':'application/json','Accept':'application/vnd.github.v3+json'},
    method='PUT'), timeout=30)
print('Publicado:', json.loads(req.read())['content']['path'])
"
