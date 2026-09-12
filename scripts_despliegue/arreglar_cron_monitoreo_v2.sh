#!/usr/bin/env bash
# arreglar_cron_monitoreo_v2.sh — crea directorio y copia script
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/arreglar_cron_mon_v2_${TS}.log

CRON_FILE="/etc/cron.d/poly_monitoreo"
SCRIPTS_DIR="/opt/polymarket/scripts_despliegue"

{
echo "=== ARREGLAR CRON MONITOREO v2 — $TS UTC ==="
echo
echo "== 1. Crear directorio scripts_despliegue =="
mkdir -p "$SCRIPTS_DIR"
ls -la "$SCRIPTS_DIR"
echo
echo "== 2. Descargar monitorear_bots.sh =="
curl -sL -o "$SCRIPTS_DIR/monitorear_bots.sh" \
    "https://raw.githubusercontent.com/lamegawi/bots-backup/arena/01a058fe-bots-backup/scripts_despliegue/monitorear_bots.sh"
chmod +x "$SCRIPTS_DIR/monitorear_bots.sh"
ls -la "$SCRIPTS_DIR/monitorear_bots.sh"
echo
echo "== 3. Verificar contenido =="
head -10 "$SCRIPTS_DIR/monitorear_bots.sh"
echo "..."
wc -l "$SCRIPTS_DIR/monitorear_bots.sh"
echo
echo "== 4. Estado del cron =="
cat "$CRON_FILE"
echo
echo "== 5. Reiniciar cron =="
systemctl restart cron 2>&1
echo
echo "== 6. Probar el script manualmente AHORA =="
bash "$SCRIPTS_DIR/monitorear_bots.sh" 2>&1 | tail -30
echo
echo "== 7. Esperar al próximo minuto y verificar ejecución =="
# Esperar hasta 70 segundos
for i in {1..7}; do
    sleep 10
    NEW_LOG=$(ls -t /tmp/mon_bots_*.log 2>/dev/null | head -1)
    if [ -n "$NEW_LOG" ] && [ "$NEW_LOG" != "/tmp/mon_bots_20260912_074545.log" ]; then
        echo "¡nuevo log creado! $NEW_LOG"
        break
    fi
    echo "  intento $i/7..."
done
echo
echo "== 8. Estado final =="
ls -lat /tmp/mon_bots_*.log 2>&1 | head -3
echo
echo "== 9. Resumen =="
echo "  ✅ directorio creado: $SCRIPTS_DIR"
echo "  ✅ script copiado"
echo "  ✅ cron reiniciado"
echo "  Esperar hasta 5 min para confirmar ejecución automática"
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/arreglar_cron_mon_v2_*.log'))
LOG = logs[-1] if logs else '/tmp/arreglar_cron_mon_v2.log'
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
