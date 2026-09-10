#!/usr/bin/env bash
# recount_elon.sh — fuerza actualización del CSV de Elon y vuelve a contar
#   1) Ejecuta recoger_tweets.py con jina+xcancel (varias pasadas)
#   2) Vuelca el estado_tweets.json al CSV
#   3) Recuenta el periodo 4-11 sept
#   4) Compara con Polymarket oficial
#   5) Publica el resultado a diag-public
set -u

TS=$(date -u +%Y%m%d_%H%M%S)
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
TS_IP=${TS_IP:-100.83.57.99}
PROXY="http://${TS_IP}:8888"
LOG="/tmp/recount_elon_${TS}.log"

# Backup del CSV actual
cp /opt/polymarket/bot-polymarket-elon/datos_elon.csv /tmp/datos_elon.bak.${TS}.csv 2>/dev/null
cp /opt/polymarket/bot-polymarket-elon/estado_tweets.json /tmp/estado_tweets.bak.${TS}.json 2>/dev/null

{
echo "=== RECOUNT ELON — $(date -u "+%Y-%m-%d %H:%M:%S UTC") ==="
echo
echo "== 1. ANTES (CSV actual) =="
echo "Total filas en CSV:"
wc -l /opt/polymarket/bot-polymarket-elon/datos_elon.csv
echo
echo "Últimas 12 filas:"
tail -12 /opt/polymarket/bot-polymarket-elon/datos_elon.csv
echo

echo "== 2. ESTADO GUARDADO (estado_tweets.json) =="
echo "Tamaño:"
ls -la /opt/polymarket/bot-polymarket-elon/estado_tweets.json
echo "Total tweets individuales guardados:"
python3 -c "
import json
d = json.load(open('/opt/polymarket/bot-polymarket-elon/estado_tweets.json'))
print(len(d.get('tweets', {})))
"
echo

echo "== 3. EJECUTAR recoger_tweets.py (3 pasadas) =="
cd /opt/polymarket/bot-polymarket-elon
for i in 1 2 3; do
  echo "--- pasada $i ---"
  timeout 150 python3 recoger_tweets.py --fuente jina --resumen 2>&1 | tail -15
  echo
  sleep 10
done
echo

echo "== 4. DESPUÉS (CSV actualizado) =="
echo "Total filas en CSV:"
wc -l /opt/polymarket/bot-polymarket-elon/datos_elon.csv
echo
echo "Últimas 12 filas:"
tail -12 /opt/polymarket/bot-polymarket-elon/datos_elon.csv
echo

echo "== 5. RECUENTO 4-11 sept (CSV) =="
python3 -c "
import csv
from datetime import date
d1, d2 = date(2026,9,4), date(2026,9,11)
total = 0
with open('/opt/polymarket/bot-polymarket-elon/datos_elon.csv') as f:
    r = csv.DictReader(f)
    for fila in r:
        try:
            f_ = date.fromisoformat(fila['fecha'])
        except: continue
        if d1 <= f_ <= d2:
            n = int(fila['tweets'])
            total += n
            print(f'  {fila[\"fecha\"]}: {n} tweets')
print(f'  TOTAL bot 4-11 sept: {total} tweets')
"
echo

echo "== 6. POLYMARKET OFICIAL (jina) =="
URL="https://polymarket.com/event/elon-musk-of-tweets-september-4-september-11-2026"
curl -s --max-time 30 -x "$PROXY" -H "Accept: text/plain" -H "x-no-cache: true" \
  -A "Mozilla/5.0" "https://r.jina.ai/${URL}" > /tmp/_jina_polymarket.md 2>&1
python3 -c "
import re
md = open('/tmp/_jina_polymarket.md', encoding='utf-8', errors='replace').read()
m = re.search(r'TWEET\s*COUNT\s*\n?\s*(\d+)', md, re.IGNORECASE)
print('Polymarket oficial: TWEET_COUNT =', m.group(1) if m else 'NO ENCONTRADO')
m_t = re.search(r'(\d+)\s*DAYS?\s*(\d+)\s*HOURS?\s*(\d+)\s*MIN', md, re.IGNORECASE)
if m_t:
    print(f'Polymarket tiempo restante: {m_t.group(1)}d {m_t.group(2)}h {m_t.group(3)}m')
"
echo

echo "== 7. ESTADO GUARDADO (post-recoger) =="
python3 -c "
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
d = json.load(open('/opt/polymarket/bot-polymarket-elon/estado_tweets.json'))
tweets = d.get('tweets', {})
inicio = datetime(2026, 9, 4, 0, 0, tzinfo=ET)
fin = datetime(2026, 9, 11, 23, 59, tzinfo=ET)
n = 0
reposts = 0
posts = 0
for sid, v in tweets.items():
    ts = datetime.strptime(v['created_at'], '%a %b %d %H:%M:%S +0000 %Y').replace(tzinfo=timezone.utc).astimezone(ET)
    if inicio <= ts <= fin:
        n += 1
        if v.get('kind') == 'repost': reposts += 1
        else: posts += 1
print(f'Estado guardado 4-11 sept: {n} (posts: {posts}, reposts: {reposts})')
print(f'Total guardados: {len(tweets)}')
"
echo

echo "== 8. SCRAPE X.COM (jina) =="
curl -s --max-time 30 -x "$PROXY" -H "Accept: text/plain" -H "x-no-cache: true" \
  -A "Mozilla/5.0" "https://r.jina.ai/https://x.com/elonmusk" > /tmp/_jina_elon.md 2>&1
python3 -c "
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
md = open('/tmp/_jina_elon.md', encoding='utf-8', errors='replace').read()
pat = re.compile(r'\\[@elonmusk\\]\\(https://x\\.com/elonmusk\\)\\s+\\[([^\\]]+)\\]\\(https://(?:twitter\\.com|x\\.com)/elonmusk/status/(\\d+)\\)')
matches = pat.findall(md)
print(f'Posts scrapeados visibles: {len(matches)}')
inicio = datetime(2026, 9, 4, 0, 0, tzinfo=ET)
fin = datetime(2026, 9, 11, 23, 59, tzinfo=ET)
ahora = datetime.now(ET)
def rel_a_utc(rel, ahora):
    rel = rel.strip()
    m = re.match(r'^(\\d+)([smhd])$', rel)
    if m:
        n, u = int(m.group(1)), m.group(2)
        delta = {'s': 0, 'm': 60, 'h': 3600, 'd': 86400}[u] * n
        return ahora.astimezone(timezone.utc) - timedelta(seconds=delta)
    return None
n_ventana = 0
for rel, sid in matches:
    ts = rel_a_utc(rel, ahora)
    if ts and inicio.astimezone(timezone.utc) <= ts <= fin.astimezone(timezone.utc):
        n_ventana += 1
print(f'Posts visibles en ventana 4-11 sept: {n_ventana}')
print('NOTA: jina solo muestra el primer fold (~20-30 tweets). Para contar TODOS se necesita API o paginación.')
"
echo

echo "== 9. CONCLUSIÓN =="
python3 -c "
import csv
from datetime import date
d1, d2 = date(2026,9,4), date(2026,9,11)
total = 0
with open('/opt/polymarket/bot-polymarket-elon/datos_elon.csv') as f:
    r = csv.DictReader(f)
    for fila in r:
        try:
            f_ = date.fromisoformat(fila['fecha'])
        except: continue
        if d1 <= f_ <= d2:
            total += int(fila['tweets'])
print(f'Total bot: {total}')
"
echo "(Si el bot sigue dando ~94 y Polymarket da 150, hay un bug en el bot)"
echo "(Si el bot se acerca a 150, es que el scrapeo estaba atrasado)"

} > "$LOG" 2>&1

# Publicar
if [ -n "$TOK" ]; then
  DIAG="recount_elon_${TS}.log"
  b64=$(base64 -w0 "$LOG")
  PAYLOAD=$(python3 -c "import json,sys;print(json.dumps({'message':'recount elon $TS','branch':'diag-public','content':sys.argv[1]}))" "$b64")
  curl -s -o /dev/null -w "[pub %{http_code}]\n" -X PUT \
    -H "Authorization: token ${TOK}" -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$PAYLOAD"
fi

echo "[log] $LOG"
cat "$LOG"