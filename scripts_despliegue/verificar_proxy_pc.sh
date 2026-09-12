#!/usr/bin/env bash
# verificar_proxy_pc.sh — comprueba si Hetzner puede usar el proxy de tu PC
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/verif_proxy_${TS}.log

{
echo "=== VERIFICAR PROXY PC — $TS UTC ==="
echo
echo "== 1. ¿Tailscale está activo? =="
which tailscale 2>/dev/null
tailscale status 2>&1 | head -5 || echo "  ⚠️ tailscale no instalado o no responde"
echo
echo "== 2. ¿El puerto 8888 del PC está accesible desde Hetzner? =="
# intentar varios nombres del PC por Tailscale
for HOST in localhost 127.0.0.1 100.64.0.1 100.100.100.100; do
    echo "  probando $HOST:8888..."
    timeout 5 bash -c "echo > /dev/tcp/$HOST/8888" 2>&1 && echo "    ✅ accesible" || echo "    ❌ no accesible"
done
echo
echo "== 3. ¿Hay algún proxy ya configurado? =="
echo "  HTTP_PROXY=$HTTP_PROXY"
echo "  HTTPS_PROXY=$HTTPS_PROXY"
echo "  http_proxy=$http_proxy"
echo "  https_proxy=$https_proxy"
echo "  NO_PROXY=$NO_PROXY"
echo
echo "== 4. ¿El bot actual usa proxy? =="
strings /usr/bin/python3 2>/dev/null | grep -i proxy | head -3
echo
echo "== 5. ¿Qué IPs salientes tiene Hetzner? =="
curl -s --max-time 10 https://api.ipify.org 2>&1
curl -s --max-time 10 https://ifconfig.me 2>&1
echo
echo "== 6. ¿Cómo acceden los otros bots a Polymarket? =="
grep -rE "proxy_pc|proxy.*8888|Tailscale" /opt/polymarket/bot-polymarket-zelenskyy/*.py 2>/dev/null | head -5
grep -rE "proxy_pc|proxy.*8888|Tailscale" /opt/polymarket/bot-polymarket-elon/*.py 2>/dev/null | head -5
echo
echo "== 7. ¿Existe proxy_pc.py? =="
ls -la /opt/polymarket/proxy_pc.py 2>&1
ls -la ~/proxy_pc.py 2>&1
find / -name "proxy_pc.py" 2>/dev/null | head -5
echo
echo "== 8. ¿El bot Zelenskyy pasó ya por este problema? =="
grep -rE "proxy_pc\.py|Tailscale|proxy.*8888" /opt/polymarket/scripts_despliegue/*.sh 2>/dev/null | head -10
echo
echo "== 9. ¿Cómo Zelenskyy configura el proxy? =="
cat /etc/default/poly 2>/dev/null
echo "---"
cat /etc/default/poly-zelenskyy 2>/dev/null
echo "---"
cat /etc/default/polymarket.env 2>/dev/null
echo
echo "== 10. ¿Hay proxy configurado en el .env? =="
cat /opt/polymarket/.env 2>/dev/null
cat /etc/polymarket.env 2>/dev/null
echo
echo "== 11. ¿Cómo Zelenskyy sale al exterior? =="
PID=$(systemctl show poly-zelenskyy.service --property=MainPID --value 2>/dev/null)
if [ -n "$PID" ] && [ "$PID" != "0" ]; then
    echo "PID Zelenskyy: $PID"
    tr '\0' '\n' < /proc/$PID/environ 2>/dev/null | grep -iE "proxy|tailscale|polygon" | head -10
fi
echo
echo "== 12. Conclusión =="
echo "  Si el proxy_pc.py no está accesible, NO podemos enviar órdenes reales."
echo "  Necesitamos que Tailscale esté activo y el PC encendido."
} > "$LOG" 2>&1

cat "$LOG"

python3 << 'PYEOF'
import base64, json, urllib.request, os, glob
logs = sorted(glob.glob('/tmp/verif_proxy_*.log'))
LOG = logs[-1] if logs else '/tmp/verif_proxy.log'
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
