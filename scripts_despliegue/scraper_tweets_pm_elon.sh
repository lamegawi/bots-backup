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
echo "== HTML CRUDO RECIBIDO =="
if [ -f /tmp/pm_debug.html ]; then
  echo "tamaño: $(wc -c < /tmp/pm_debug.html) bytes"
  echo "---primeros 1500 chars---"
  head -c 1500 /tmp/pm_debug.html
  echo
  echo "---busca '150' en HTML---"
  grep -c "150" /tmp/pm_debug.html
  echo "---busca 'September 4' en HTML---"
  grep -c "September 4" /tmp/pm_debug.html
fi
echo
echo "== CSV FINAL =="
cat datos_elon.csv
echo
echo "== polymarket_oficial.json =="
cat polymarket_oficial.json 2>/dev/null || echo "(no generado)"
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
