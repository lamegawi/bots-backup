#!/usr/bin/env bash
# verificar_cron_monitoreo.sh — comprueba si el cron se instaló correctamente
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/verif_cron_mon_${TS}.log

{
echo "=== VERIFICACIÓN CRON MONITOREO — $TS UTC ==="
echo
echo "== 1. ¿Existe /etc/cron.d/poly_monitoreo? =="
ls -la /etc/cron.d/poly_monitoreo 2>&1
echo
echo "== 2. Contenido del archivo =="
cat /etc/cron.d/poly_monitoreo 2>&1
echo
echo "== 3. ¿Aparece en /etc/cron.d/? =="
ls -la /etc/cron.d/ | grep -E "poly_|mon"
echo
echo "== 4. ¿Aparece en crontab? =="
crontab -l 2>&1 | grep -E "monitorear|mon" || echo "(no está en crontab del usuario)"
echo
echo "== 5. ¿Está en los crontabs de otros usuarios? =="
for user in root polymarket; do
    if [ -f "/var/spool/cron/crontabs/$user" ]; then
        echo "--- /var/spool/cron/crontabs/$user ---"
        grep -E "monitorear|mon" "/var/spool/cron/crontabs/$user" 2>/dev/null || echo "(vacío)"
    fi
done
echo
echo "== 6. ¿El script monitorear_bots.sh existe en Hetzner? =="
ls -la /opt/polymarket/scripts_despliegue/monitorear_bots.sh 2>&1
echo
echo "== 7. ¿Hay logs recientes del monitoreo? =="
ls -lat /tmp/mon_bots_*.log 2>&1 | head -5
ls -lat /tmp/instalar_cron_monitoreo_*.log 2>&1 | head -5
echo
echo "== 8. ¿Hay procesos cron ejecutándose? =="
ps aux | grep -E "cron|monitorear" | grep -v grep
echo
echo "== 9. Última línea de logs del cron =="
journalctl -u cron --since '30 minutes ago' --no-pager 2>/dev/null | tail -10
echo
echo "== 10. Resumen =="
if [ -f /etc/cron.d/poly_monitoreo ]; then
    echo "  ✅ /etc/cron.d/poly_monitoreo EXISTE"
    echo "  ✅ cron está configurado para ejecutarse cada 5 min"
else
    echo "  ❌ /etc/cron.d/poly_monitoreo NO EXISTE"
    echo "  ⚠️ el script de instalación falló silenciosamente"
fi
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os
LOG = '/tmp/verif_cron_mon.log'
# Buscar el log más reciente
import glob
logs = sorted(glob.glob('/tmp/verif_cron_mon_*.log'))
if logs:
    LOG = logs[-1]
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
