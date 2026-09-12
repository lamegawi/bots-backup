#!/usr/bin/env bash
# diag_cierres_anticipados_global.sh — leer cierres_anticipados.json + bot semanal v2
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_cierres_anticipados_global_${TS}.log

{
echo "=== DIAG CIERRES ANTICIPADOS GLOBAL — $TS UTC ==="
echo
echo "== 1. /opt/polymarket/cierres_anticipados.json =="
if [ -f /opt/polymarket/cierres_anticipados.json ]; then
    cat /opt/polymarket/cierres_anticipados.json | python3 -m json.tool | head -100
    echo
    echo "--- resumen ---"
    python3 -c "
import json
d = json.load(open('/opt/polymarket/cierres_anticipados.json'))
if isinstance(d, list):
    print(f'total cierres: {len(d)}')
    for c in d[-20:]:
        print(f'  {c}')
else:
    print(f'claves: {list(d.keys())}')
    for k, v in d.items():
        print(f'  {k}: {v if not isinstance(v, list) else len(v)}')
"
else
    echo 'NO EXISTE'
fi
echo
echo "== 2. bot-polymarket-elon-semanal-v2/ (segundo bot) =="
ls -la /opt/polymarket/bot-polymarket-elon-semanal-v2/ 2>&1 | head -20
echo
echo "== 2.1. ¿tiene real.json? =="
ls -la /opt/polymarket/bot-polymarket-elon-semanal-v2/real.json 2>&1
python3 -c "
import json
try:
    d = json.load(open('/opt/polymarket/bot-polymarket-elon-semanal-v2/real.json'))
    print(json.dumps(d, indent=2)[:3000])
except Exception as e:
    print(f'[ERROR] {e}')
"
echo
echo "== 3. ¿Qué hay en poly_overreaction_bot/data/spike_queue.json (120-139)? =="
python3 -c "
import json
d = json.load(open('/opt/polymarket/poly_overreaction_bot/data/spike_queue.json'))
print(json.dumps(d, indent=2)[:2000])
" 2>&1
echo
echo "== 4. ¿Hay logs de CLOB en bot.log? =="
grep -iE "CLOB|orden|compra|comprada" /opt/polymarket/bot-polymarket-elon/bot.log | tail -30
echo
echo "== 5. ¿Último log del bot? =="
tail -30 /opt/polymarket/bot-polymarket-elon/bot.log
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
