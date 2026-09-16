#!/usr/bin/env bash
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/buscar_reconc_${TS}.log

{
echo "=== BUSCAR QUIEN ESCRIBE 'reconc' EN JSONS · ${TS} UTC ==="
echo

echo "== 1. Buscar 'reconc' en TODOS los .py =="
grep -rln "\"reconc\"\|'reconc'\|id.*reconc\|'id': 'reconc'" /opt/polymarket/ 2>/dev/null | grep -v __pycache__ | grep -v ".bak" | head -30
echo

echo "== 2. Buscar quien abre/escribe real_semanal.json (lsof) =="
lsof /opt/polymarket/bot-polymarket-elon-semanal/real_semanal.json 2>&1 | head -10
echo

echo "== 3. inotifywait / fuser =="
fuser /opt/polymarket/bot-polymarket-elon-semanal/real_semanal.json 2>&1
echo

echo "== 4. Buscar scripts en /opt/polymarket/ raiz =="
ls -la /opt/polymarket/*.py 2>/dev/null | head -20
echo

echo "== 5. Buscar el código de check_integral.py =="
cat /opt/polymarket/check_integral.py 2>/dev/null | head -80
echo

echo "== 6. Buscar el código de check_estado.py =="
cat /opt/polymarket/check_estado.py 2>/dev/null | head -80
echo

echo "== 7. Buscar el código de motores.py =="
cat /opt/polymarket/motores.py 2>/dev/null | head -80
echo

echo "== 8. Buscar saldo_ntfy.py =="
grep -nB2 -A10 "reconc\|beneficio\|real_semanal" /opt/polymarket/bot-polymarket-elon-semanal/saldo_ntfy.py 2>/dev/null | head -50
echo

echo "== 9. Buscar quién modificó el JSON recientemente =="
find /opt/polymarket -name "*.py" -newer /opt/polymarket/bot-polymarket-elon-semanal/bot_semanal.py 2>/dev/null | head -10
echo

echo "== 10. ¿Hay un watcher o cron que toque el JSON? =="
ls /etc/cron.d/ 2>/dev/null
ls /etc/cron.daily/ 2>/dev/null
crontab -l 2>/dev/null
echo

echo "== 11. Buscar 'real_semanal' en TODOS los directorios =="
grep -rln "real_semanal" /opt/ /root/ /etc/ 2>/dev/null | grep -v __pycache__ | grep -v ".bak" | head -30
echo

} > "${LOG}" 2>&1

cat "${LOG}"

python3 -c "
import base64, json, urllib.request, os
LOG = '${LOG}'
tok = open('/opt/polymarket/.gh_token').read().strip()
with open(LOG, 'rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = os.path.basename(LOG)
p = {'message': 'buscar reconc: ' + name, 'branch': 'diag-public', 'content': b64}
req = urllib.request.Request(
    'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/' + name,
    data=json.dumps(p).encode(),
    headers={'Authorization': 'token ' + tok, 'Content-Type': 'application/json'},
    method='PUT')
try:
    r = urllib.request.urlopen(req, timeout=30)
    print('Publicado:', json.loads(r.read())['content']['path'])
except Exception as e:
    print('ERROR publicando:', e)
"
