#!/usr/bin/env bash
# verificar_proxy_pc_v2.sh — versión robusta sin set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/verif_proxy_v2_${TS}.log

{
echo "=== VERIFICAR PROXY PC v2 — ${TS} UTC ==="
echo
echo "== 1. ¿Tailscale está instalado? =="
which tailscale 2>/dev/null || echo "  ⚠️ tailscale no instalado"
echo
echo "== 2. ¿Tailscale activo? =="
tailscale status 2>&1 | head -5 || echo "  ⚠️ tailscale no responde"
echo
echo "== 3. Puerto 8888 del PC accesible? =="
for HOST in localhost 127.0.0.1 100.64.0.1 100.100.100.100; do
    echo "  probando ${HOST}:8888..."
    timeout 5 bash -c "echo > /dev/tcp/${HOST}/8888" 2>/dev/null && echo "    ✅ accesible" || echo "    ❌ no accesible"
done
echo
echo "== 4. Proxy ya configurado? =="
echo "  HTTP_PROXY=${HTTP_PROXY:-no}"
echo "  HTTPS_PROXY=${HTTPS_PROXY:-no}"
echo "  NO_PROXY=${NO_PROXY:-no}"
echo
echo "== 5. ¿proxy_pc.py existe? =="
ls -la /opt/polymarket/proxy_pc.py 2>&1
ls -la ~/proxy_pc.py 2>&1
find /opt/polymarket -name "proxy_pc.py" 2>/dev/null | head -3
echo
echo "== 6. ¿Cómo Zelenskyy configura el proxy? =="
cat /etc/polymarket.env 2>/dev/null || echo "  /etc/polymarket.env no existe"
echo
echo "== 7. Variables de entorno del bot Zelenskyy =="
PID=$(systemctl show poly-zelenskyy.service --property=MainPID --value 2>/dev/null)
if [ -n "${PID}" ] && [ "${PID}" != "0" ]; then
    echo "PID Zelenskyy: ${PID}"
    tr '\0' '\n' < /proc/${PID}/environ 2>/dev/null | grep -iE "proxy|tailscale|polygon" | head -10
fi
echo
echo "== 8. ¿Otros bots usan proxy? =="
grep -rE "proxy_pc|proxy.*8888|http_proxy" /opt/polymarket/bot-polymarket-*/operar_real*.py 2>/dev/null | head -5
echo
echo "== 9. ¿Cómo Zelenskyy hace requests HTTP? =="
grep -rE "urllib|requests|session|HTTPAdapter" /opt/polymarket/bot-polymarket-zelenskyy/operar_real_semanal.py 2>/dev/null | head -10
echo
echo "== 10. IPs salientes de Hetzner =="
curl -s --max-time 10 https://api.ipify.org 2>&1 || echo "  ⚠️ no responde"
echo
echo "== Conclusión =="
echo "  Si proxy_pc.py:8888 responde, configuramos HTTP_PROXY para el bot"
echo "  Si NO responde, NO podemos ejecutar órdenes reales"
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
