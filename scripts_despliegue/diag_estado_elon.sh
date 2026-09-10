#!/usr/bin/env bash
# diag_estado_elon.sh — vuelca el estado_tweets.json real de Hetzner
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_estado_elon_${TS}.log

{
echo "=== DIAG ESTADO ELON — $TS UTC ==="
echo
echo "== 1. TAMAÑO Y TOTALES =="
ls -la /opt/polymarket/bot-polymarket-elon/estado_tweets.json
python3 -c "
import json
d = json.load(open('/opt/polymarket/bot-polymarket-elon/estado_tweets.json'))
tw = d.get('tweets', {})
print(f'Total items: {len(tw)}')
posts = sum(1 for v in tw.values() if v.get('kind')=='post')
reps = sum(1 for v in tw.values() if v.get('kind')=='repost')
print(f'Posts: {posts}  Reposts: {reps}')
"
echo
echo "== 2. ÚLTIMOS 15 ITEMS POR TIMESTAMP =="
python3 -c "
import json
from datetime import datetime
T_FMT = '%a %b %d %H:%M:%S +0000 %Y'
d = json.load(open('/opt/polymarket/bot-polymarket-elon/estado_tweets.json'))
tw = d.get('tweets', {})
items = []
for sid, v in tw.items():
    ts = v.get('created_at', '')
    try:
        dt = datetime.strptime(ts, T_FMT)
    except:
        dt = datetime(1970,1,1)
    items.append((dt, sid, v.get('kind'), ts))
items.sort()
print(f'{\"FECHA UTC\":<22}{\"KIND\":<8}{\"ID\":<22}{\"PRIMERA_VISTA\"}')
for dt, sid, kind, ts in items[-15:]:
    pv = tw[sid].get('primera_vista', '?')
    print(f'{ts:<22}{kind:<8}{sid:<22}{pv}')
"
echo
echo "== 3. DISTRIBUCIÓN POR DÍA ET (sólo items con created_at parseable) =="
python3 -c "
import json
from datetime import datetime
from zoneinfo import ZoneInfo
T_FMT = '%a %b %d %H:%M:%S +0000 %Y'
ET = ZoneInfo('America/New_York')
d = json.load(open('/opt/polymarket/bot-polymarket-elon/estado_tweets.json'))
tw = d.get('tweets', {})
dias = {}
no_parse = 0
for sid, v in tw.items():
    if v.get('kind') == 'repost' and not v.get('exacto'):
        base = v.get('primera_vista', v.get('created_at', ''))
    else:
        base = v.get('created_at', '')
    try:
        f = datetime.strptime(base, T_FMT).astimezone(ET).date()
    except Exception as e:
        no_parse += 1
        continue
    dias[f] = dias.get(f, 0) + 1
print(f'Items sin timestamp parseable: {no_parse}')
print('Días (últimos 12):')
for f in sorted(dias)[-12:]:
    print(f'  {f}  {dias[f]}')
total_411 = sum(c for f,c in dias.items() if f >= __import__('datetime').date(2026,9,4) and f <= __import__('datetime').date(2026,9,11))
print(f'TOTAL 4-11 sept (con timestamps OK): {total_411}')
"
} > "$LOG" 2>&1

echo "Log local: $LOG"
cat "$LOG"

# publicar
TOKEN=$(cat /opt/polymarket/.gh_token)
REPO="lamegawi/bots-backup"
BR="diag-public"
API="https://api.github.com/repos/$REPO/contents/diag_hetzner/$(basename $LOG)"
B64=$(base64 -w0 "$LOG")
HASH=$(printf '%s' "$B64" | sha256sum | cut -d' ' -f1)
echo "{\"message\":\"diag: $(basename $LOG)\",\"branch\":\"$BR\",\"content\":\"$B64\",\"sha\":\"\"}" > /tmp/payload.json
# (omitimos sha vacío para crear)
python3 -c "
import json, urllib.request, urllib.error
tok = open('/opt/polymarket/.gh_token').read().strip()
p = json.load(open('/tmp/payload.json'))
req = urllib.request.Request('https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/$(basename $LOG)',
    data=json.dumps(p).encode(),
    headers={'Authorization': f'token {tok}','Content-Type':'application/json','Accept':'application/vnd.github.v3+json'},
    method='PUT')
try:
    r = json.loads(urllib.request.urlopen(req, timeout=30).read())
    print('Publicado OK:', r.get('content',{}).get('path','?'))
except urllib.error.HTTPError as e:
    print('ERROR', e.code, e.read().decode()[:200])
"
