#!/usr/bin/env bash
# diag_posicion_5060_otros_bots.sh — buscar 5060 en otros bots
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_5060_otros_bots_${TS}.log

cd /opt/polymarket

{
echo "=== BUSCAR 5060 EN TODOS LOS BOTS — $TS UTC ==="
echo
echo "== 1. Bot Zelenskyy =="
cd /opt/polymarket/bot-polymarket-zelenskyy 2>/dev/null && {
    ls -la real.json 2>/dev/null
    python3 -c "
import json
try:
    d = json.load(open('real.json'))
    print(f'saldo: {d.get(\"saldo\")} paso: {d.get(\"paso\")}')
    print(f'activa: {d.get(\"activa\")}')
    print(f'historial: {len(d.get(\"historial\",[]))} ops')
    hist = d.get('historial',[])
    for op in hist:
        print(f'  {op.get(\"fecha\")} | {op.get(\"mercado\",\"\")[:30]} | {op.get(\"bin\")} | {op.get(\"lado\")} | stake={op.get(\"stake\")} | {op.get(\"resultado\")}')
except Exception as e:
    print(f'[ERROR] {e}')
"
}
echo
echo "== 2. Bot Trump =="
cd /opt/polymarket/bot-polymarket-trump 2>/dev/null && {
    ls -la real.json 2>/dev/null
    python3 -c "
import json
try:
    d = json.load(open('real.json'))
    print(f'saldo: {d.get(\"saldo\")} paso: {d.get(\"paso\")}')
    print(f'activa: {d.get(\"activa\")}')
    print(f'historial: {len(d.get(\"historial\",[]))} ops')
    hist = d.get('historial',[])
    for op in hist:
        print(f'  {op.get(\"fecha\")} | {op.get(\"mercado\",\"\")[:30]} | {op.get(\"bin\")} | {op.get(\"lado\")} | stake={op.get(\"stake\")} | {op.get(\"resultado\")}')
except Exception as e:
    print(f'[ERROR] {e}')
"
}
echo
echo "== 3. grep 5060 en TODO el árbol =="
grep -rE "5060|120_139|120-139" /opt/polymarket/ 2>/dev/null | grep -vE "node_modules|\.git/" | head -20
echo
echo "== 4. ¿Hay un archivo de órdenes pendientes? =="
find /opt/polymarket -name "*.json" -mtime -10 2>/dev/null | xargs grep -lE "120-139|120_139|5060" 2>/dev/null | head -10
echo
echo "== 5. ¿Qué hay en avisos_cooldown.json? =="
cat /opt/polymarket/bot-polymarket-elon/avisos_cooldown.json
echo
echo "== 6. ¿La wallet aparece en trades de CLOB públicos? =="
python3 -c "
import urllib.request, json
# Buscar trades de la wallet usando el endpoint público del data-api
wallet = '0xb0E148FEb4bE59fD617c8Ad6ce5Cf2b5f0BB2Ae1'
url = f'https://data-api.polymarket.com/trades?user={wallet}&limit=50'
try:
    req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
    d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    print(f'trades: {len(d)}')
    for t in d[:20]:
        title = t.get('title', '?')
        ts = t.get('timestamp', '?')
        size = t.get('size', 0)
        price = t.get('price', 0)
        side = t.get('side', '?')
        print(f'  {ts} | {title[:50]} | {side} {size} @ \${price}')
except Exception as e:
    print(f'[ERROR] {e}')
"
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
