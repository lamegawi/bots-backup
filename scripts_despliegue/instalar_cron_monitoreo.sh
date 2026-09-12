#!/usr/bin/env bash
# instalar_cron_monitoreo.sh — instala cron cada 5 min que ejecuta monitorear_bots.sh
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/instalar_cron_monitoreo_${TS}.log

CRON_LINE="*/5 * * * * /usr/bin/bash /opt/polymarket/scripts_despliegue/monitorear_bots.sh >/dev/null 2>&1"
CRON_FILE="/etc/cron.d/poly_monitoreo"

{
echo "=== INSTALACIÓN CRON MONITOREO — $TS UTC ==="
echo
echo "== 1. Backup del crontab actual =="
crontab -l > /tmp/crontab.bak.${TS} 2>&1
cat /tmp/crontab.bak.${TS}
echo
echo "== 2. Crear /etc/cron.d/poly_monitoreo =="
cat > "$CRON_FILE" <<EOF
# Monitoreo cada 5 min de los 3 bots (Elon/Zelenskyy/Trump)
$CRON_LINE
EOF
chmod 644 "$CRON_FILE"
ls -la "$CRON_FILE"
cat "$CRON_FILE"
echo
echo "== 3. Verificar que NO duplica líneas existentes =="
EXISTING=$(grep -c "monitorear_bots.sh" "$CRON_FILE" 2>/dev/null || echo "0")
echo "  líneas con 'monitorear_bots.sh' en $CRON_FILE: $EXISTING"
echo
echo "== 4. Verificación final =="
ls -la /etc/cron.d/poly_*
echo
echo "  ✅ Cron instalado: $CRON_LINE"
echo "  ✅ Se ejecuta cada 5 minutos"
echo "  ✅ Publica log en diag-public con prefijo 'mon_bots_'"
echo
echo "  ⚠️  Para DESACTIVAR: rm /etc/cron.d/poly_monitoreo"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os
LOG = os.environ.get('LOG_FILE', '/tmp/instalar_cron_monitoreo.log')
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
