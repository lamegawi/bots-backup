#!/usr/bin/env bash
# test_fuentes_elon.sh — compara lo que devuelve cada fuente
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/test_fuentes_elon_${TS}.log

{
echo "=== TEST FUENTES ELON — $TS UTC ==="
echo
echo "== 1. jina sobre twitter.com (la fuente que más suele funcionar) =="
python3 -c "
import sys
sys.path.insert(0, '/opt/polymarket/bot-polymarket-elon')
import recoger_tweets as rt
try:
    items = rt.descargar_jina_tw()
    print(f'jina twitter.com: {len(items)} items')
    if items:
        for sid in list(items.keys())[:5]:
            v = items[sid]
            print(f'  {sid}  {v.get(\"kind\")}  {v.get(\"created_at\")}')
except Exception as e:
    print(f'jina twitter.com: [ERROR] {e}')
"
echo
echo "== 2. jina sobre x.com =="
python3 -c "
import sys
sys.path.insert(0, '/opt/polymarket/bot-polymarket-elon')
import recoger_tweets as rt
try:
    items = rt.descargar_jina_x()
    print(f'jina x.com: {len(items)} items')
    if items:
        for sid in list(items.keys())[:5]:
            v = items[sid]
            print(f'  {sid}  {v.get(\"kind\")}  {v.get(\"created_at\")}')
except Exception as e:
    print(f'jina x.com: [ERROR] {e}')
"
echo
echo "== 3. Nitter/xcancel =="
python3 -c "
import sys
sys.path.insert(0, '/opt/polymarket/bot-polymarket-elon')
import recoger_tweets as rt
try:
    items = rt.descargar_nitter()
    print(f'nitter: {len(items)} items')
    if items:
        for sid in list(items.keys())[:5]:
            v = items[sid]
            print(f'  {sid}  {v.get(\"kind\")}  {v.get(\"created_at\")}')
except Exception as e:
    print(f'nitter: [ERROR] {e}')
"
echo
echo "== 4. IDs en estado guardado del 09-10 =="
python3 -c "
import json
from datetime import datetime
from zoneinfo import ZoneInfo
T_FMT = '%a %b %d %H:%M:%S +0000 %Y'
ET = ZoneInfo('America/New_York')
d = json.load(open('/opt/polymarket/bot-polymarket-elon/estado_tweets.json'))
tw = d.get('tweets', {})
ids_910 = []
for sid, v in tw.items():
    try:
        f = datetime.strptime(v.get('created_at',''), T_FMT).astimezone(ET).date()
    except:
        continue
    if f == datetime(2026,9,10, tzinfo=ET).date():
        ids_910.append((sid, v.get('kind'), v.get('created_at')))
print(f'IDs 09-10: {len(ids_910)}')
for sid, k, ts in ids_910:
    print(f'  {sid}  {k}  {ts}')
"
} > "$LOG" 2>&1

cat "$LOG"

# publicar
TOKEN=$(cat /opt/polymarket/.gh_token)
python3 -c "
import base64, json, urllib.request, urllib.error
tok = open('/opt/polymarket/.gh_token').read().strip()
with open('$LOG','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
name = '$(basename $LOG)'
p = {'message':f'diag: {name}','branch':'diag-public','content':b64}
req = urllib.request.Request(f'https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/{name}',
    data=json.dumps(p).encode(),
    headers={'Authorization':f'token {tok}','Content-Type':'application/json','Accept':'application/vnd.github.v3+json'},
    method='PUT')
try:
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print('Publicado:', r['content']['path'])
except urllib.error.HTTPError as e:
    print('ERROR', e.code, e.read().decode()[:200])
"
