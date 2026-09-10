#!/usr/bin/env bash
# scraper_tweets_pm_elon.sh — extrae TWEET_COUNT de xtracker/PM/gamma (sin jina)
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/scraper_tweets_pm_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

# 0) descargar el .py desde la rama (con cache-buster)
BRANCH="arena/01a058fe-bots-backup"
TS_CACHE=$(date +%s)
curl -sL -o scraper_tweets_pm.py \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/scraper_tweets_pm.py?ts=${TS_CACHE}"
echo "  descargado: $(wc -c < scraper_tweets_pm.py) bytes"
head -1 scraper_tweets_pm.py
chmod +x scraper_tweets_pm.py

{
echo "=== SCRAPER POLYMARKET (sin jina) — $TS UTC ==="
echo
python3 scraper_tweets_pm.py --user elonmusk --debug-html
echo
echo "== HTML DE XTRACKER (descargado aparte) =="
curl -sL --max-time 20 -A "Mozilla/5.0" "https://xtracker.polymarket.com/user/elonmusk" -o /tmp/xtracker.html
echo "tamaño: $(wc -c < /tmp/xtracker.html) bytes"
echo "---busca '150' en xtracker---"
grep -c "150" /tmp/xtracker.html
echo "---busca 'Sep 4' en xtracker---"
grep -c "Sep 4" /tmp/xtracker.html
echo "---busca 'September 4' en xtracker---"
grep -c "September 4" /tmp/xtracker.html
echo "---lineas con '150' (200 chars antes/después)---"
grep -o ".\{0,200\}150.\{0,200\}" /tmp/xtracker.html | head -3
echo "---lineas con 'September' (si existe)---"
grep -o ".\{0,100\}September.\{0,100\}" /tmp/xtracker.html | head -3
echo "---todo el texto entre 'September' y el siguiente '<':---"
python3 -c "
import re
with open('/tmp/xtracker.html') as f:
    h = f.read()
# extraer todos los textos visibles (entre > y <, que tengan letras)
textos = re.findall(r'>([^<>]{5,200})<', h)
print(f'Total textos extraídos: {len(textos)}')
# mostrar los que tengan September, Sep, tweet, post
for t in textos:
    if 'Sep' in t or 'tweet' in t.lower() or 'post' in t.lower() or '150' in t or 'elon' in t.lower():
        print(f'  {t[:150]}')
"
echo
echo "== CSV FINAL =="
cat datos_elon.csv
} > "$LOG" 2>&1

cat "$LOG"

# publicar
python3 -c "
import base64, json, urllib.request, urllib.error
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
