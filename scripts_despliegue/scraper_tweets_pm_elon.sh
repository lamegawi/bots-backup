#!/usr/bin/env bash
# scraper_tweets_pm_elon.sh — descarga scraper_tweets_pm.py, lo prueba
#   contra el mercado 48h activo de Polymarket, y vuelca TWEET_COUNT al CSV
#   si --actualizar-csv.
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/scraper_tweets_pm_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

# 0) descargar el .py desde la rama (con cache-buster por si el raw tarda en propagar)
BRANCH="arena/01a058fe-bots-backup"
TS_CACHE=$(date +%s)
curl -sL -o scraper_tweets_pm.py \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/scraper_tweets_pm.py?ts=${TS_CACHE}"
echo "  descargado: $(wc -c < scraper_tweets_pm.py) bytes"
head -1 scraper_tweets_pm.py
grep -c "debug-html" scraper_tweets_pm.py | xargs echo "  matches debug-html:"
chmod +x scraper_tweets_pm.py

{
echo "=== SCRAPER TWEETS PM — $TS UTC ==="
echo
echo "== 1. AUTO-DETECTAR SLUG =="
python3 scraper_tweets_pm.py --auto
echo
echo "== 2. SCRAPEAR MERCADO =="
# slug correcto del 48h 4-11 sept (con "of-tweets", no "tweets"):
SLUG="elon-musk-of-tweets-september-4-september-11-2026"
echo "Slug a usar: $SLUG"
if [ -n "$SLUG" ]; then
  python3 scraper_tweets_pm.py --slug "$SLUG" --actualizar-csv --debug-html
fi
echo
echo "== 3. CSV FINAL =="
cat datos_elon.csv
echo
echo "== 4. TOTAL 4-11 sept (CSV) =="
awk -F, 'NR>1 && $1>="2026-09-04" && $1<="2026-09-11" {s+=$2} END {print s}' datos_elon.csv
echo
echo "== 5. POLYMARKET OFICIAL (TWEET_COUNT guardado aparte) =="
if [ -f polymarket_oficial.json ]; then
  cat polymarket_oficial.json
else
  echo "No se generó polymarket_oficial.json"
fi
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
