#!/usr/bin/env bash
# diag_csv_inflado.sh — ¿por qué el CSV se infla cada 5 min?
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/diag_csv_inflado_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

{
echo "=== DIAG CSV INFLADO — $TS UTC ==="
echo
echo "== 1. CSV actual (últimas 5 filas) =="
tail -5 datos_elon.csv
echo
echo "== 2. bak (estado tras revertir) =="
[ -f datos_elon.csv.bak ] && tail -5 datos_elon.csv.bak || echo "(no bak)"
echo
echo "== 3. ¿Qué dice el estado guardado para 09-10? =="
python3 -c "
import json
from datetime import datetime
from zoneinfo import ZoneInfo
T_FMT = '%a %b %d %H:%M:%S +0000 %Y'
ET = ZoneInfo('America/New_York')
d = json.load(open('estado_tweets.json'))
tw = d.get('tweets', {})
print(f'Total items: {len(tw)}')
dias = {}
no_parse = 0
for sid, v in tw.items():
    if v.get('kind') == 'repost' and not v.get('exacto'):
        base = v.get('primera_vista', v.get('created_at', ''))
    else:
        base = v.get('created_at', '')
    try:
        f = datetime.strptime(base, T_FMT).astimezone(ET).date()
    except Exception:
        no_parse += 1
        continue
    dias[f] = dias.get(f, 0) + 1
# solo días relevantes
for f in sorted(dias):
    if f >= __import__('datetime').date(2026, 9, 3) and f <= __import__('datetime').date(2026, 9, 11):
        print(f'  {f}: {dias[f]} tweets')
"
echo
echo "== 4. polymarket_oficial.json =="
cat polymarket_oficial.json 2>/dev/null || echo "(no existe)"
[ -f polymarket_oficial.json.disabled ] && echo "  (también hay .disabled)"
echo
echo "== 5. ¿qué tweeted se vieron en último paso de nitter? =="
tail -30 bot.log | grep -A 1 "nitter: " | head -10
echo
echo "== 6. ¿se ejecutó paso 0 (in-process) y qué dijo? =="
tail -100 bot.log | grep -B 1 -A 4 "TEST urllib\|TWEET_COUNT oficial\|scraper no devolvió" | head -30
echo
echo "== 7. ¿se sobreescribió 09-10 por el bot? =="
tail -50 bot.log | grep -iE "09-10|sept-10|september-10" | head -10
echo
echo "== 8. ¿qué tiene el bak? (estado tras revertir) =="
python3 -c "
import csv
with open('datos_elon.csv.bak') as f:
    filas = [(r['fecha'], int(r['tweets'])) for r in csv.DictReader(f)]
ult = filas[-7:]
print(f'Bak últimos 7: {ult}')
print(f'Bak AVG7: {sum(n for _,n in ult)/7:.2f}')
"
echo
echo "== 9. ¿tiene cron el wrapper correcto (sin --actualizar-csv)? =="
crontab -l 2>/dev/null | grep scraper
cat /opt/polymarket/scraper_cron_elon.sh 2>/dev/null
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
