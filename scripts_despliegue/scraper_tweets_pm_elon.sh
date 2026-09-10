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
python3 scraper_tweets_pm.py --user elonmusk --actualizar-csv --debug-html
echo
echo "== HTML DE XTRACKER (descargado aparte) =="
curl -sL --max-time 20 -A "Mozilla/5.0" "https://xtracker.polymarket.com/user/elonmusk" -o /tmp/xtracker.html
echo "tamaño: $(wc -c < /tmp/xtracker.html) bytes"
echo "---busca 'TWEET COUNT' (texto) en xtracker---"
grep -c "TWEET COUNT" /tmp/xtracker.html
echo "---busca 'TweetCount' (camelCase) en xtracker---"
grep -c "TweetCount" /tmp/xtracker.html
echo "---busca 'tweetCount' (camelCase) en xtracker---"
grep -c "tweetCount" /tmp/xtracker.html
echo "---busca 'TWEET_COUNT' (snake) en xtracker---"
grep -c "TWEET_COUNT" /tmp/xtracker.html
echo "---busca 'postCount' en xtracker---"
grep -c "postCount" /tmp/xtracker.html
echo "---busca '150' en xtracker (mostrar contexto)---"
grep -o ".\{0,80\}150.\{0,80\}" /tmp/xtracker.html | head -3
echo
echo "== HTML DE POLYMARKET.COM (mercado) =="
curl -sL --max-time 20 -A "Mozilla/5.0" "https://polymarket.com/event/elon-musk-of-tweets-september-4-september-11-2026" -o /tmp/pm_com.html
echo "tamaño: $(wc -c < /tmp/pm_com.html) bytes"
echo "---busca 'TWEET COUNT' (texto) en PM---"
grep -c "TWEET COUNT" /tmp/pm_com.html
echo "---contexto de 'TWEET COUNT' en PM (200 chars antes/después)---"
grep -o ".\{0,200\}TWEET COUNT.\{0,200\}" /tmp/pm_com.html | head -3
echo "---contexto de 'TWEET\\u00a0COUNT' (con nbsp) en PM---"
grep -c "TWEET" /tmp/pm_com.html
echo "---primera ocurrencia de 'TWEET' en PM (contexto)---"
grep -o ".\{0,100\}TWEET.\{0,100\}" /tmp/pm_com.html | head -3
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
