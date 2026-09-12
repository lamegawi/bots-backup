#!/usr/bin/env bash
# compartir_proxy_env.sh — hacer que poly-elon-semanal y poly-trump usen /etc/polymarket.env
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/compartir_proxy_${TS}.log

{
echo "=== COMPARTIR PROXY ENV — ${TS} UTC ==="
echo
echo "== 1. Backup de los .service =="
mkdir -p /etc/systemd/system/backups
for svc in poly-elon-semanal poly-trump; do
    cp /etc/systemd/system/${svc}.service /etc/systemd/system/backups/${svc}.service.bak_${TS}
done
ls -la /etc/systemd/system/backups/
echo
echo "== 2. Modificar poly-elon-semanal.service =="
SVC=/etc/systemd/system/poly-elon-semanal.service
if grep -q "EnvironmentFile=/etc/polymarket.env" "$SVC"; then
    echo "  ya apunta a polymarket.env, no se modifica"
else
    # Reemplazar EnvironmentFile=/etc/default/poly-elon-semanal por /etc/polymarket.env
    sed -i 's|EnvironmentFile=/etc/default/poly-elon-semanal|EnvironmentFile=/etc/polymarket.env\nEnvironmentFile=-/etc/default/poly-elon-semanal|' "$SVC"
    echo "  modificado"
fi
cat "$SVC"
echo
echo "== 3. Modificar poly-trump.service =="
SVC=/etc/systemd/system/poly-trump.service
if grep -q "EnvironmentFile=/etc/polymarket.env" "$SVC"; then
    echo "  ya apunta a polymarket.env, no se modifica"
else
    sed -i 's|EnvironmentFile=/etc/default/poly-trump|EnvironmentFile=/etc/polymarket.env\nEnvironmentFile=-/etc/default/poly-trump|' "$SVC"
    echo "  modificado"
fi
cat "$SVC"
echo
echo "== 4. Recargar systemd =="
systemctl daemon-reload
echo
echo "== 5. Reiniciar los 2 servicios =="
systemctl restart poly-elon-semanal.service 2>&1
systemctl restart poly-trump.service 2>&1
sleep 5
echo
echo "== 6. Verificar que tienen proxy =="
for svc in poly-elon-semanal poly-trump; do
    PID=$(systemctl show "$svc" --property=MainPID --value 2>/dev/null)
    if [ -n "${PID}" ] && [ "${PID}" != "0" ]; then
        echo "--- $svc (PID $PID) ---"
        tr '\0' '\n' < /proc/${PID}/environ 2>/dev/null | grep -iE "HTTP_PROXY|HTTPS_PROXY|ALL_PROXY" | sort -u
    fi
done
echo
echo "== 7. Probar bot semanal con proxy =="
timeout 30 python3 /opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py 2>&1 | tail -20
echo
echo "== 8. Resumen =="
echo "  poly-elon-semanal.service: ahora usa /etc/polymarket.env (con proxy)"
echo "  poly-trump.service: ahora usa /etc/polymarket.env (con proxy)"
echo "  Backups guardados en /etc/systemd/system/backups/"
echo
echo "  ⚠️  Para que funcione realmente, proxy_pc.py debe estar corriendo en 100.83.57.99:8888"
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
