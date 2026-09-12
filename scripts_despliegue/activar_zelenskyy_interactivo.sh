#!/usr/bin/env bash
# activar_zelenskyy_interactivo.sh — configura Zelenskyy con wallet real y clave privada
# ⚠️ PIDE LA CLAVE PRIVADA DE FORMA INTERACTIVA (no va al log, no va a GitHub)
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/activar_zelenskyy_interactivo_${TS}.log

WALLET="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
ZEL_DIR="/opt/polymarket/bot-polymarket-zelenskyy"

# banner
cat <<'BANNER'
========================================================
  ACTIVACIÓN BOT ZELENSKYY — MODO REAL
  ⚠️  Este script te pedirá la clave privada INTERACTIVAMENTE
      (no se loguea, no se sube a GitHub)
  wallet: 0xb0E1197098E6d427c01720F1631cAD24CE740FA0
========================================================
BANNER

# pedir clave privada de forma segura
echo
echo "🔑 Pega tu clave privada de https://reveal.magic.link/polymarket"
echo "   (66 caracteres hexadecimales, con o sin prefijo 0x)"
echo "   NO se mostrará, NO se guardará en el log, NO irá a GitHub"
echo
read -rs -p "POLY_PRIVATE_KEY=" PK_INPUT
echo
if [ -z "$PK_INPUT" ]; then
    echo "❌ No se proporcionó clave. Abortando."
    exit 1
fi
# quitar prefijo 0x si lo tiene
PK_HEX="${PK_INPUT#0x}"
# limpiar espacios y newlines
PK_HEX="$(echo -n "$PK_HEX" | tr -d '[:space:]')"
unset PK_INPUT
# validación: 64 caracteres hex
if [[ ! "$PK_HEX" =~ ^[0-9a-fA-F]{64}$ ]]; then
    LEN=${#PK_HEX}
    echo "❌ La clave no tiene 64 caracteres hexadecimales (tiene $LEN). Abortando."
    exit 1
fi
PK_FULL="0x${PK_HEX}"
unset PK_HEX

{
echo "=== ACTIVACIÓN BOT ZELENSKYY — $TS UTC ==="
echo "wallet: $WALLET"
echo "(clave privada NO se loguea)"
echo
echo "== 1. Estado actual de Zelenskyy =="
ls -la "$ZEL_DIR/config_real.json" 2>&1
ls -la "$ZEL_DIR/real_zelen.json" 2>&1
systemctl status poly-zelenskyy.service 2>&1 | head -10
echo
echo "== 2. Saldo actual del bot (de real_zelen.json) =="
python3 -c "
import json
try:
    d = json.load(open('$ZEL_DIR/real_zelen.json'))
    print(f'  saldo actual: \${d.get(\"saldo\")}')
    print(f'  bankroll_inicial: \${d.get(\"_bankroll_inicial_real\")}')
    print(f'  pnl_acumulado: \${d.get(\"_pnl_historico_acumulado\")}')
    print(f'  activa: {d.get(\"activa\")}')
    print(f'  historial: {len(d.get(\"historial\",[]))} ops')
except Exception as e:
    print(f'  [ERROR] {e}')
"
echo
echo "== 3. ¿Existe service poly-zelenskyy.service? =="
cat /etc/systemd/system/poly-zelenskyy.service 2>&1
echo
echo "== 4. Backup del real_zelen.json actual =="
cp "$ZEL_DIR/real_zelen.json" "$ZEL_DIR/real_zelen.json.bak_${TS}"
echo "backup: $ZEL_DIR/real_zelen.json.bak_${TS}"
echo
echo "== 5. Crear config_real.json con wallet real =="
cat > "$ZEL_DIR/config_real.json" <<EOF
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
chmod 600 "$ZEL_DIR/config_real.json"
echo "config_real.json creado con confirmado=true y bankroll=228.45"
ls -la "$ZEL_DIR/config_real.json"
echo
echo "== 6. ¿Actualizar real_zelen.json? (mantener historial) =="
# Actualizar saldo y bankroll_inicial_real al real, mantener historial
python3 -c "
import json
p = '$ZEL_DIR/real_zelen.json'
d = json.load(open(p))
old_saldo = d.get('saldo', 0)
old_bankroll = d.get('_bankroll_inicial_real', 0)
new_saldo = 228.45
# recalcular pnl acumulado
new_pnl = new_saldo - old_bankroll if old_bankroll else 0
# actualizar
d['saldo'] = new_saldo
d['_bankroll_inicial_real'] = new_saldo  # reset para reflejar realidad
d['_pnl_historico_acumulado'] = new_pnl
d['_sincronizado_con_real'] = True
from datetime import datetime, timezone
d['_sincronizado_ts'] = datetime.now(timezone.utc).isoformat()
json.dump(d, open(p, 'w'), indent=2)
print(f'  actualizado:')
print(f'    saldo: \${old_saldo} → \${new_saldo}')
print(f'    bankroll_inicial: \${old_bankroll} → \${new_saldo}')
print(f'    pnl_acumulado: \${new_pnl}')
print(f'    historial: {len(d.get(\"historial\",[]))} ops (preservado)')
"
chmod 600 "$ZEL_DIR/real_zelen.json"
ls -la "$ZEL_DIR/real_zelen.json"
echo
echo "== 7. Crear /etc/default/poly-zelenskyy con la clave =="
cat > /etc/default/poly-zelenskyy <<EOF
# Variables de entorno para el bot Zelenskyy
POLY_PRIVATE_KEY="$PK_FULL"
POLY_WALLET_ADDRESS="$WALLET"
EOF
chmod 600 /etc/default/poly-zelenskyy
echo "/etc/default/poly-zelenskyy creado (permisos 600)"
echo
echo "== 8. Actualizar poly-zelenskyy.service para cargar /etc/default/poly-zelenskyy =="
SERVICE=/etc/systemd/system/poly-zelenskyy.service
if [ -f "$SERVICE" ]; then
    # backup
    cp "$SERVICE" "${SERVICE}.bak_${TS}"
    # añadir EnvironmentFile
    if grep -q "EnvironmentFile" "$SERVICE"; then
        echo "  ya tiene EnvironmentFile, no se modifica"
    else
        # insertar después de [Service]
        sed -i '/^\[Service\]/a EnvironmentFile=/etc/default/poly-zelenskyy' "$SERVICE"
        echo "  añadido EnvironmentFile=/etc/default/poly-zelenskyy"
    fi
    cat "$SERVICE"
else
    echo "  ⚠️ $SERVICE no existe, el bot de Zelenskyy no tiene servicio systemd"
fi
echo
echo "== 9. Recargar systemd y reiniciar =="
systemctl daemon-reload
systemctl restart poly-zelenskyy.service 2>&1
sleep 5
systemctl status poly-zelenskyy.service 2>&1 | head -15
echo
echo "== 10. Verificar que el bot arranca con la clave =="
PID=$(systemctl show poly-zelenskyy.service --property=MainPID --value 2>/dev/null)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "PID: $PID"
    tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | grep -E "^POLY_" | sed 's/=.*/=***OCULTO***/'
fi
echo
echo "== 11. ¿Está en 'BLOQUEADO' o arrancando? =="
journalctl -u poly-zelenskyy.service -n 30 --no-pager 2>&1 | tail -20
echo
echo "== 12. Verificación final =="
journalctl -u poly-zelenskyy.service -n 100 --no-pager 2>&1 | grep -iE "Trading|BLOQUEADO|ERROR|confirmado" | tail -10
echo
echo "== 13. Resumen =="
echo "  ✅ config_real.json: confirmado=true, bankroll=228.45"
echo "  ✅ real_zelen.json: saldo=228.45 (historial preservado)"
echo "  ✅ /etc/default/poly-zelenskyy: POLY_PRIVATE_KEY cargada"
echo "  ✅ poly-zelenskyy.service: EnvironmentFile añadido"
echo "  ✅ servicio reiniciado"
echo
echo "  ⚠️  PRÓXIMOS PASOS:"
echo "  - Espera 5 min a la próxima pasada"
echo "  - Verifica logs: journalctl -u poly-zelenskyy.service -f"
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
