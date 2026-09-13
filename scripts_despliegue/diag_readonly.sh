#!/usr/bin/env bash
# diag_readonly.sh — solo lectura, NO modifica nada
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_readonly_${TS}.log

{
echo "=== DIAGNOSTICO READONLY — ${TS} UTC ==="
echo
echo "== 1. Estado de TODOS los servicios poly-* =="
systemctl list-units --type=service --all --no-pager 2>&1 | grep -E "poly-|combos" || echo "  no se encontraron servicios poly-*"
echo
echo "== 2. Estado de cada servicio =="
for svc in poly-elon poly-elon-semanal poly-semanal poly-mensual poly-gestor poly-telegram poly-zelenskyy poly-trump poly-combos-bot; do
    echo "--- $svc ---"
    systemctl status $svc --no-pager -l 2>&1 | head -8
    echo
done
echo
echo "== 3. Ultimos logs de cada servicio =="
for svc in poly-elon poly-elon-semanal poly-semanal poly-mensual poly-trump poly-combos-bot; do
    echo "--- $svc (ultimas 5 lineas) ---"
    journalctl -u $svc -n 5 --no-pager 2>&1 | tail -10
    echo
done
echo
echo "== 4. Servicios poly-combos-bot especificamente =="
systemctl status poly-combos-bot --no-pager -l 2>&1
echo
echo "== 5. Procesos python en ejecucion =="
ps -ef | grep -E "python.*(bot|polymarket)" | grep -v grep
echo
echo "== 6. Contenido del .service de poly-combos-bot (si existe) =="
cat /etc/systemd/system/poly-combos-bot.service 2>&1 | head -20 || echo "  no existe"
echo
echo "== 7. EnvironmentFile de cada .service =="
for svc in poly-elon poly-elon-semanal poly-semanal poly-mensual poly-trump poly-combos-bot poly-zelenskyy; do
    echo "--- $svc ---"
    SVC=/etc/systemd/system/${svc}.service
    if [ -f "$SVC" ]; then
        grep -E "EnvironmentFile|ExecStart|WorkingDirectory" "$SVC"
    else
        echo "  no existe $SVC"
    fi
done
echo
echo "== 8. Conectividad desde el servidor =="
curl -s --max-time 10 https://data-api.polymarket.com/positions?user=0xb0E1197098E6d427c01720F1631cAD24CE740FA0 2>&1 | head -5
echo
echo "== 9. Tailscale status =="
tailscale status 2>&1 | head -10 || echo "  tailscale no instalado"
echo
echo "== 10. Salida IP =="
curl -s --max-time 5 https://api.ipify.org 2>&1
echo
} > "${LOG}" 2>&1

cat "${LOG}"

# publicar
python3 -c "
import base64, json, urllib.request, os
LOG = '${LOG}'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': 'diag: ' + name, 'branch': 'diag-public', 'content': b64}
try:
    req = urllib.request.urlopen(urllib.request.Request(
        'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/' + name,
        data=json.dumps(p).encode(),
        headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json', 'Accept': 'application/vnd.github.v3+json'},
        method='PUT'), timeout=30)
    print('Publicado:', json.loads(req.read())['content']['path'])
except Exception as e:
    print('ERROR publicando:', e)
"
