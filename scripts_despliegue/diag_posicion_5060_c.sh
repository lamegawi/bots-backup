#!/usr/bin/env bash
# diag_posicion_5060_c.sh — buscar posición 5060 shares con Gamma API
# El endpoint /positions es privado; usamos Gamma con el wallet
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_posicion_5060_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== DIAG POSICIÓN 5060 — $TS UTC ==="
echo
echo "== 1. Buscar posición vía Gamma API con wallet =="
python3 -c "
import urllib.request, json
wallet = '0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1'
url = f'https://gamma-api.polymarket.com/positions?user={wallet}'
try:
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    print(f'posiciones gamma: {len(d)}')
    for p in d:
        print(f'  {p}')
except Exception as e:
    print(f'[ERROR gamma] {e}')
"
echo
echo "== 2. Buscar posición con CLOB API =="
python3 -c "
import urllib.request, json
# CLOB API pública de market positions
wallet = '0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1'
url = f'https://clob.polymarket.com/positions?user={wallet}'
try:
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    print(f'posiciones clob: {len(d) if isinstance(d, list) else \"?\"}')
    print(json.dumps(d, indent=2)[:2000])
except Exception as e:
    print(f'[ERROR clob] {e}')
"
echo
echo "== 3. ¿Qué dice bot.log sobre la posición 5060? =="
grep -i "5060\|120-139\|120_139\|bin 120" bot.log | head -30
echo
echo "== 4. Buscar id 7fabd7fc2966 (la única con id real del sept) =="
grep -i "7fabd7fc\|7fabd" bot.log | head -10
echo
echo "== 5. Buscar todas las id reales (no 'reconc') =="
python3 -c "
import json
d = json.load(open('real.json'))
ids = [(op.get('id'), op.get('fecha'), op.get('mercado'), op.get('bin'), op.get('lado'), op.get('resultado')) for op in d['historial']]
print('todas las ids:')
for i in ids:
    print(f'  {i}')
"
echo
echo "== 6. ¿Hay archivo de trades/orders? =="
ls -la *.json *.txt 2>/dev/null | head -20
echo
echo "== 7. Buscar en logs del cron =="
ls -la /tmp/*cron*.log 2>/dev/null | head -10
ls -la /tmp/*.log 2>/dev/null | tail -10
echo
echo "== 8. ¿Algún log con 'compra' en sept 4-11? =="
grep -iE "compra|vendida|orden" bot.log | grep -E "2026-09-(0[4-9]|1[0-1])" | head -30
} > "$LOG" 2>&1

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
