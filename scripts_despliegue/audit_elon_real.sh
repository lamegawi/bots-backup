#!/usr/bin/env bash
# audit_elon_real.sh — auditoría en vivo de la fuente REAL de tweets de Elon
#   - Compara 4 fuentes:
#     1) jina scraping del perfil @elonmusk (cuenta real de Twitter)
#     2) Polymarket (lo que dice el mercado oficial)
#     3) datos_elon.csv del bot (lo que cuenta el bot)
#     4) estado_tweets.json (tweets individuales guardados)
#   - Detecta discrepancias y publica el resultado
set -u

TS=$(date -u +%Y%m%d_%H%M%S)
LOG="/tmp/audit_elon_${TS}.log"
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
TS_IP=${TS_IP:-100.83.57.99}
PROXY="http://${TS_IP}:8888"

{
echo "=== AUDITORÍA ELON TIEMPO REAL — $(date -u "+%Y-%m-%d %H:%M:%S UTC") ==="
echo

echo "== 1. TIEMPO ACTUAL Y VENTANA 4-11 sept =="
echo "Ahora UTC: $(date -u)"
echo "Ahora ET:  $(TZ=America/New_York date "+%Y-%m-%d %H:%M:%S %Z")"
python3 -c "
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
fin = datetime(2026, 9, 11, 12, 0, tzinfo=ET)
ahora = datetime.now(ET)
rest = fin - ahora
horas = rest.total_seconds() / 3600
print(f'Cierre mercado 4-11: {fin.strftime(\"%Y-%m-%d %H:%M %Z\")}')
print(f'Tiempo restante: {horas:.1f}h = {int(horas)}h {int((horas%1)*60)}m')
"
echo

echo "== 2. TWEETS OFICIALES DE POLYMARKET (jina scrape) =="
URL="https://polymarket.com/event/elon-musk-of-tweets-september-4-september-11-2026"
curl -s --max-time 30 -x "$PROXY" -H "Accept: text/plain" -H "x-no-cache: true" \
  -A "Mozilla/5.0" "https://r.jina.ai/${URL}" > /tmp/_jina_polymarket.md 2>&1
python3 -c "
import re
md = open('/tmp/_jina_polymarket.md', encoding='utf-8', errors='replace').read()
m = re.search(r'TWEET\s*COUNT\s*\n?\s*(\d+)', md, re.IGNORECASE)
print('Polymarket oficial: TWEET_COUNT =', m.group(1) if m else 'NO ENCONTRADO')
# Tiempo restante
m_t = re.search(r'(\d+)\s*DAYS?\s*(\d+)\s*HOURS?\s*(\d+)\s*MIN', md, re.IGNORECASE)
if m_t:
    print(f'Polymarket tiempo restante: {m_t.group(1)}d {m_t.group(2)}h {m_t.group(3)}m')
else:
    print('Polymarket tiempo restante: NO ENCONTRADO')
"
echo

echo "== 3. TWEETS REALES DE @elonmusk EN X (jina) =="
# Scraping del perfil real de Elon
curl -s --max-time 30 -x "$PROXY" -H "Accept: text/plain" -H "x-no-cache: true" \
  -A "Mozilla/5.0" "https://r.jina.ai/https://x.com/elonmusk" > /tmp/_jina_elon.md 2>&1
python3 -c "
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
ET = ZoneInfo('America/New_York')
md = open('/tmp/_jina_elon.md', encoding='utf-8', errors='replace').read()
# Buscar timestamps relativos: 'Xh', 'Xd', 'fecha'
pat = re.compile(r'\\[@elonmusk\\]\\(https://x\\.com/elonmusk\\)\\s+\\[([^\\]]+)\\]\\(https://(?:twitter\\.com|x\\.com)/elonmusk/status/(\\d+)\\)')
matches = pat.findall(md)
print(f'Posts scrapeados: {len(matches)}')
# Filtrar del 4 al 11 sept ET
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
n_hoy = 0
ids = []
for rel, sid in matches:
    ts = rel_a_utc(rel, ahora)
    if ts and inicio.astimezone(timezone.utc) <= ts <= fin.astimezone(timezone.utc):
        n_ventana += 1
        ids.append(sid)
    if ts and ts.astimezone(ET).date() == ahora.date():
        n_hoy += 1
print(f'En ventana 4-11 sept: {n_ventana}')
print(f'Hoy (10 sept): {n_hoy}')
"
echo

echo "== 4. LO QUE DICE EL BOT (CSV) =="
tail -10 /opt/polymarket/bot-polymarket-elon/datos_elon.csv
echo
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

echo "== 5. ESTADO TWEETS GUARDADOS =="
ls -la /opt/polymarket/bot-polymarket-elon/estado_tweets.json 2>&1
if [ -f /opt/polymarket/bot-polymarket-elon/estado_tweets.json ]; then
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
fi
echo

echo "== 6. MERCADO ACTIVO.JSON DEL BOT =="
python3 -c "
import json
d = json.load(open('/opt/polymarket/bot-polymarket-elon/mercado_activo.json'))
for m in d.get('mercados', []):
    if 'september-4-september-11' in m.get('slug', ''):
        print(f\"slug: {m['slug']}\")
        print(f\"titulo: {m['titulo']}\")
        print(f\"fin: {m['fin_iso']}\")
        print(f\"inicio: {m['inicio_iso']}\")
"
echo

echo "== 7. POSICIÓN EN CLOB (lo que dice Polymarket de TU posición) =="
FUNDER="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
curl -s --max-time 30 -x "$PROXY" -H "Accept: application/json" \
  "https://data-api.polymarket.com/positions?user=${FUNDER}&sizeThreshold=0" \
  | python3 -c "
import json, sys
pos = json.load(sys.stdin)
for p in pos:
    slug = p.get('slug', '')
    if 'september-4-september-11' in slug and '120-139' in slug:
        size = float(p.get('size', 0))
        if size > 0.01:
            print(f\"  CLOB: {size:.2f} shares YES @ avg \${p.get('avgPrice', 0):.4f}\")
            print(f\"        cur=\${p.get('currentValue', 0):.2f}  pnl=\${p.get('pnl', 0):.2f}\")
"
echo

echo "== 8. RESUMEN DISCREPANCIAS =="
echo "Compara los 4 numeros:"
echo "  - Polymarket oficial: ?"
echo "  - X.com @elonmusk scrapeado: ?"
echo "  - Bot CSV: ?"
echo "  - Estado guardado: ?"
echo "Si los 4 no coinciden, hay un bug en el conteo del bot."

} > "$LOG" 2>&1

# Publicar
if [ -n "$TOK" ]; then
  DIAG="audit_elon_${TS}.log"
  b64=$(base64 -w0 "$LOG")
  PAYLOAD=$(python3 -c "import json,sys;print(json.dumps({'message':'audit elon $TS','branch':'diag-public','content':sys.argv[1]}))" "$b64")
  curl -s -o /dev/null -w "[pub %{http_code}]\n" -X PUT \
    -H "Authorization: token ${TOK}" -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$PAYLOAD"
fi
cat "$LOG"
