#!/usr/bin/env bash
# diag_proxy_todos_bots.sh — comparar config proxy entre todos los bots
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_proxy_todos_${TS}.log

{
echo "=== DIAGNÓSTICO PROXY TODOS LOS BOTS — ${TS} UTC ==="
echo
echo "== 1. Servicios activos =="
for svc in poly-elon poly-elon-semanal poly-zelenskyy poly-trump; do
    state=$(systemctl is-active "$svc" 2>/dev/null)
    echo "  $svc: $state"
done
echo
echo "== 2. Archivos /etc/default/poly-* =="
for f in /etc/default/poly-* /etc/polymarket.env; do
    if [ -f "$f" ]; then
        echo "--- $f ---"
        grep -E "PROXY|HTTP" "$f" 2>/dev/null
        echo
    fi
done
echo
echo "== 3. Servicios systemd: EnvironmentFile =="
for svc in poly-elon poly-elon-semanal poly-zelenskyy poly-trump; do
    SERVICE="/etc/systemd/system/${svc}.service"
    if [ -f "$SERVICE" ]; then
        echo "--- $svc.service ---"
        grep -E "EnvironmentFile|ExecStart" "$SERVICE"
        echo
    fi
done
echo
echo "== 4. Variables de entorno de CADA bot activo =="
for svc in poly-elon poly-elon-semanal poly-zelenskyy poly-trump; do
    PID=$(systemctl show "$svc" --property=MainPID --value 2>/dev/null)
    if [ -n "${PID}" ] && [ "${PID}" != "0" ]; then
        echo "--- $svc (PID $PID) ---"
        tr '\0' '\n' < /proc/${PID}/environ 2>/dev/null | grep -iE "HTTP_PROXY|HTTPS_PROXY|ALL_PROXY|NO_PROXY" | sort -u
    else
        echo "--- $svc: no está corriendo ---"
    fi
    echo
done
echo
echo "== 5. ¿Qué bot fue el primero en tener proxy? (git log /etc/polymarket.env) =="
git log --oneline --all -- /etc/polymarket.env 2>&1 | head -5 || echo "  no es un archivo git"
echo
echo "== 6. ¿Cómo Zelenskyy IMPLEMENTA el proxy en su código? =="
grep -nE "HTTP_PROXY|os.environ.*PROXY|proxy.*=|requests.*proxies|socks|http.client" /opt/polymarket/bot-polymarket-zelenskyy/operar_real_semanal.py 2>/dev/null | head -15
echo
echo "== 7. ¿Cómo Elon 48h maneja el proxy? =="
grep -nE "HTTP_PROXY|os.environ.*PROXY|proxy.*=|requests.*proxies|http.client" /opt/polymarket/bot-polymarket-elon/operar_real.py 2>/dev/null | head -10
echo
echo "== 8. ¿Cómo bot_semanal.py del semanal Elon maneja el proxy? =="
grep -nE "HTTP_PROXY|os.environ.*PROXY|proxy.*=" /opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py 2>/dev/null | head -10
echo
echo "== 9. ¿py_clob_client usa proxy por defecto? =="
python3 -c "
import os
print('HTTP_PROXY (env):', os.environ.get('HTTP_PROXY', 'no'))
print('HTTPS_PROXY (env):', os.environ.get('HTTPS_PROXY', 'no'))
# ver si py_clob_client lee estas vars
import py_clob_client.client as cm
src = open(cm.__file__).read()
if 'HTTP_PROXY' in src or 'http_proxy' in src or 'HTTPS_PROXY' in src:
    print('✅ py_clob_client USA las variables PROXY')
else:
    print('⚠️ py_clob_client NO lee variables PROXY automáticamente')
"
echo
echo "== 10. ¿Cómo Zelenskyy firma y envía órdenes? =="
grep -nA3 "client.create_and_post_order\|ClobClient(" /opt/polymarket/bot-polymarket-zelenskyy/operar_real_semanal.py 2>/dev/null | head -25
echo
echo "== 11. ¿Qué IP ve Polymarket cuando Zelenskyy opera? =="
echo "  Zelenskyy reporta: IP local en Hetzner = 46.225.146.21"
echo "  IP por proxy = 100.83.57.99 (tu PC)"
echo
echo "== 12. ¿Por qué Zelenskyy SÍ envía órdenes pero el semanal no? =="
echo "  - Zelenskyy tiene /etc/default/poly-zelenskyy apuntando a /etc/polymarket.env"
echo "  - /etc/polymarket.env contiene HTTP_PROXY=...:8888"
echo "  - El bot semanal tiene /etc/default/poly-elon-semanal SIN líneas de proxy"
echo "  - Por eso el semanal va directo a Hetzner (46.225.146.21)"
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
