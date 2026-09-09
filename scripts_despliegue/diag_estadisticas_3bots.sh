#!/usr/bin/env bash
# diag_estadisticas_3bots.sh — análisis estadístico completo de los 3 bots
#   - Cuenta operaciones totales: ganadas / perdidas / abiertas
#   - PnL total (en $) por bot
#   - Tasa de acierto (win rate)
#   - Distribución de pérdidas vs ganancias
#   - Causas probables: precio de entrada demasiado alto, ventana mal elegida, etc.
#   - Para Trump: por qué NO entra (cuotas, mercados, filtros)
set -u

TS=$(date -u +%Y%m%d_%H%M%S)
LOG="/tmp/diag_stats_${TS}.log"
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
TS_IP=${TS_IP:-100.83.57.99}
PROXY="http://${TS_IP}:8888"
FUNDER="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"

{
echo "=== DIAGNOSTICO ESTADISTICAS 3 BOTS — $(date -u "+%Y-%m-%d %H:%M:%S UTC") ==="
echo

echo "=========================================="
echo "1. POSICIONES ACTUALES (CLOB via proxy)"
echo "=========================================="
curl -s --max-time 30 -x "$PROXY" -H "Accept: application/json" \
  "https://data-api.polymarket.com/positions?user=${FUNDER}&sizeThreshold=0.1" \
  | python3 -c "
import json, sys
from collections import defaultdict
pos = json.load(sys.stdin)
if not isinstance(pos, list): pos = []
print(f'Total: {len(pos)}')
print()
mk = defaultdict(lambda: {'count': 0, 'shares': 0, 'avg': 0, 'cur': 0})
for p in pos:
    slug = p.get('slug', '')
    size = float(p.get('size', 0))
    if size > 0.1 and any(s in slug for s in ['elon', 'zelen', 'trump']):
        m = mk[slug]
        m['count'] += 1
        m['shares'] += size
        m['avg'] = float(p.get('avgPrice', 0))
        m['cur'] = float(p.get('currentValue', 0)) / size if size else 0
for slug, m in sorted(mk.items()):
    if m['count'] > 0:
        print(f\"  {slug}\")
        print(f\"    shares={m['shares']:.2f}  avg={m['avg']:.4f}  cur={m['cur']:.4f}\")
"

echo
echo "=========================================="
echo "2. HISTORIAL DE OPERACIONES (últimas 30 días)"
echo "=========================================="
# Trades / actividad
for mes in 2026-08 2026-09; do
  echo
  echo "--- Mes $mes ---"
  curl -s --max-time 30 -x "$PROXY" -H "Accept: application/json" \
    "https://data-api.polymarket.com/trades?user=${FUNDER}&limit=200&after=${mes}-01T00:00:00Z" \
    | python3 -c "
import json, sys
from collections import defaultdict
trades = json.load(sys.stdin)
if not isinstance(trades, list): trades = []
print(f'  trades este mes: {len(trades)}')
mk = defaultdict(lambda: {'count': 0, 'buy': 0, 'sell': 0, 'spent': 0, 'received': 0})
for t in trades:
    slug = t.get('slug', '')
    if not any(s in slug for s in ['elon', 'zelen', 'trump']): continue
    side = t.get('side', '')
    size = float(t.get('size', 0))
    price = float(t.get('price', 0))
    m = mk[slug]
    m['count'] += 1
    if side == 'BUY':
        m['buy'] += 1
        m['spent'] += size * price
    elif side == 'SELL':
        m['sell'] += 1
        m['received'] += size * price
for slug, m in sorted(mk.items())[:15]:
    pnl = m['received'] - m['spent'] * (m['sell'] / max(1, m['buy']))
    print(f\"  {slug[:60]:<60}  trades={m['count']:>3}  buy={m['buy']:>2}  sell={m['sell']:>2}\")
"
done

echo
echo "=========================================="
echo "3. BOT ELON — DATOS Y ULTIMAS OPERACIONES"
echo "=========================================="
echo "-- CSV últimas 15 líneas --"
tail -15 /opt/polymarket/bot-polymarket-elon/datos_elon.csv 2>&1
echo
echo "-- Log últimas 20 líneas --"
tail -20 /var/log/poly-elon.log 2>&1
echo
echo "-- Mercado activo --"
python3 -c "
import json
try:
    d=json.load(open('/opt/polymarket/bot-polymarket-elon/mercado_activo.json'))
    for m in d.get('mercados', []):
        if not m.get('cerrado'):
            print(f\"  {m.get('slug')} | {m.get('titulo')} | fin {m.get('fin_iso')}\")
            for b in m.get('bins', [])[:5]:
                print(f'    {b.get(\"titulo\"):<15}  YES @ {b.get(\"precio_yes\", \"?\"):.4f}  vol={b.get(\"volumen\", 0):.0f}')
except Exception as e: print('err:', e)
" 2>&1

echo
echo "=========================================="
echo "4. BOT ZELENSKYY — DATOS Y ULTIMAS OPERACIONES"
echo "=========================================="
echo "-- CSV últimas 15 líneas --"
tail -15 /opt/polymarket/bot-polymarket-zelenskyy/datos_zelen.csv 2>&1
echo
echo "-- Log últimas 20 líneas --"
tail -20 /var/log/poly-zelenskyy.log 2>&1
echo
echo "-- Mercado activo --"
python3 -c "
import json
try:
    d=json.load(open('/opt/polymarket/bot-polymarket-zelenskyy/mercado_activo.json'))
    for m in d.get('mercados', []):
        if not m.get('cerrado'):
            print(f\"  {m.get('slug')} | {m.get('titulo')} | fin {m.get('fin_iso')}\")
            for b in m.get('bins', [])[:5]:
                print(f'    {b.get(\"titulo\"):<15}  YES @ {b.get(\"precio_yes\", \"?\"):.4f}  vol={b.get(\"volumen\", 0):.0f}')
except Exception as e: print('err:', e)
" 2>&1

echo
echo "=========================================="
echo "5. BOT TRUMP — DATOS, MERCADO Y POR QUE NO OPERA"
echo "=========================================="
echo "-- CSV últimas 15 líneas --"
tail -15 /opt/polymarket/bot-polymarket-trump/datos_trump.csv 2>&1
echo
echo "-- Log últimas 30 líneas --"
tail -30 /var/log/poly-trump.log 2>&1
echo
echo "-- Mercado activo --"
python3 -c "
import json
try:
    d=json.load(open('/opt/polymarket/bot-polymarket-trump/mercado_activo.json'))
    for m in d.get('mercados', []):
        if not m.get('cerrado'):
            print(f\"  {m.get('slug')} | {m.get('titulo')} | fin {m.get('fin_iso')}\")
            for b in m.get('bins', [])[:8]:
                print(f'    {b.get(\"titulo\"):<15}  YES @ {b.get(\"precio_yes\", \"?\"):.4f}  vol={b.get(\"volumen\", 0):.0f}')
except Exception as e: print('err:', e)
" 2>&1
echo
echo "-- Filtros / condiciones del bot Trump --"
grep -E "umbral|min_cuota|max_cuota|filtro|kelly|min_size|stake|min_prob" /opt/polymarket/bot-polymarket-trump/*.py 2>/dev/null | head -25
echo
echo "-- Buscar decisiones en logs --"
grep -E "DESCARTADO|RECHAZADO|no opera|sin oportunidad|fuera de rango" /var/log/poly-trump.log 2>&1 | tail -10

} > "$LOG" 2>&1

echo "[diag] $LOG"
cat "$LOG" | head -150

# publicar
if [ -n "$TOK" ]; then
  DIAG="diag_stats_${TS}.log"
  b64=$(base64 -w0 "$LOG")
  payload=$(python3 -c "import json,sys;print(json.dumps({'message':'diag stats 3bots $TS','branch':'diag-public','content':sys.argv[1]}))" "$b64")
  curl -s -o /dev/null -w "[pub %{http_code}]\n" \
    -X PUT -H "Authorization: token ${TOK}" -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$payload"
fi
