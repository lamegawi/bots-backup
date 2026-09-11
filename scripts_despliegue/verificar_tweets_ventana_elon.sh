#!/usr/bin/env bash
# verificar_tweets_ventana_elon.sh — descarga verificar_tweets_ventana.py,
#   lo ejecuta y publica el resultado. Compara los tweets que el bot ve
#   con los que muestra xtracker.polymarket.com (vista oficial de Polymarket).
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
LOG=/tmp/verificar_tweets_${TS}.log

cd /opt/polymarket/bot-polymarket-elon

# descargar el .py
BRANCH="arena/01a058fe-bots-backup"
TS_CACHE=$(date +%s)
curl -sL -o verificar_tweets_ventana.py \
  "https://raw.githubusercontent.com/lamegawi/bots-backup/${BRANCH}/poly/codigo/bot-polymarket-elon/verificar_tweets_ventana.py?ts=${TS_CACHE}"
chmod +x verificar_tweets_ventana.py

{
echo "=== VERIFICACIÓN DE TWEETS — $TS UTC ==="
python3 verificar_tweets_ventana.py --user elonmusk
echo
echo "== ESTADO DEL SERVICIO =="
systemctl status poly-elon --no-pager -n 3 2>/dev/null | head -10
echo
echo "== ÚLTIMAS 5 LÍNEAS DE bot.log =="
tail -5 bot.log
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
