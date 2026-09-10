#!/usr/bin/env bash
# deploy_fix_automatico_elon.sh — despliega todos los cambios del fix
#   1) descarga el .py nuevo
#   2) reinicia el servicio poly-elon
#   3) publica el log
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/deploy_fix_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

BRANCH="arena/01a058fe-bots-backup"
TS_CACHE=$(date +%s)

{
echo "=== DEPLOY FIX AUTOMÁTICO — $TS UTC ==="
echo
echo "== 1. Descargando scraper_tweets_pm.py (con cache-buster) =="
CACHE_BUST=$(date +%s%N)
curl -sL -o scraper_tweets_pm.py \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/scraper_tweets_pm.py?nocache=${CACHE_BUST}"
echo "  $(wc -c < scraper_tweets_pm.py) bytes"
grep -c "TWEET_COUNT" scraper_tweets_pm.py | xargs echo "  matches TWEET_COUNT (modo silent):"
chmod +x scraper_tweets_pm.py

echo
echo "== 2. Descargando bot.py (con paso 0) =="
curl -sL -o bot.py \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/bot.py?nocache=${CACHE_BUST}"
echo "  $(wc -c < bot.py) bytes"
chmod +x bot.py
grep -c "actualizar_polymarket_oficial" bot.py | xargs echo "  matches paso 0:"

echo
echo "== 2b. Test directo del scraper (sin silent) para ver qué pasa =="
python3 scraper_tweets_pm.py --user elonmusk --actualizar-csv 2>&1 | head -20

echo
echo "== 3. Reiniciando servicio poly-elon =="
systemctl restart poly-elon
sleep 3
systemctl status poly-elon --no-pager -n 5 | head -10

echo
echo "== 4. Esperando 90s para ver log del bot con el nuevo paso 0 =="
sleep 90
tail -30 bot.log
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
