#!/usr/bin/env bash
# posiciones_actuales.sh — descarga posiciones actuales vía proxy
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
TS_IP=${TS_IP:-100.83.57.99}
PROXY="http://${TS_IP}:8888"
FUNDER="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
LOG="/tmp/pos_${TS}.log"
{
echo "=== POSICIONES ACTUALES — $(date -u "+%Y-%m-%d %H:%M:%S UTC") ==="
echo
echo "== Total en CLOB =="
curl -s --max-time 30 -x "$PROXY" -H "Accept: application/json" \
  "https://data-api.polymarket.com/positions?user=${FUNDER}&sizeThreshold=1" \
  | python3 -c "
import json, sys
pos = json.load(sys.stdin)
if not isinstance(pos, list): pos = []
total = 0
items = []
for p in pos:
    size = float(p.get('size', 0))
    if size > 0.1:
        slug = p.get('slug', '')
        items.append((size, slug, p.get('outcome',''), p.get('avgPrice', 0)))
        total += 1
print(f'Total posiciones: {total}')
print()
print('Por mercado:')
from collections import defaultdict
mk = defaultdict(int)
for s, slug, o, _ in items:
    mk[slug] += s
for slug, sum_sz in sorted(mk.items(), key=lambda x: -x[1]):
    if 'september-4-september-11' in slug or 'september-1-september-8' in slug:
        print(f'  {slug:<70}  total_shares={sum_sz:.2f}')
"
echo
echo "== Posiciones en el mercado 4-11 sept (detalle) =="
curl -s --max-time 30 -x "$PROXY" -H "Accept: application/json" \
  "https://data-api.polymarket.com/positions?user=${FUNDER}&sizeThreshold=0" \
  | python3 -c "
import json, sys
pos = json.load(sys.stdin)
for p in pos:
    slug = p.get('slug', '')
    if 'september-4-september-11' in slug:
        size = float(p.get('size', 0))
        if size > 0.01:
            print(f\"  size={size:>10.2f}  outcome={p.get('outcome','?'):<10}  avg=\${p.get('avgPrice', 0):.4f}  slug={slug}\")
            print(f\"    condition: {p.get('conditionId', '?')[:20]}...\")
            print(f\"    current_value: \${p.get('currentValue', 0):.4f}\")
"
} > "$LOG" 2>&1
cat "$LOG"
# publicar
if [ -n "$TOK" ]; then
  DIAG="pos_${TS}.log"
  b64=$(base64 -w0 "$LOG")
  payload=$(python3 -c "import json,sys;print(json.dumps({'message':'posiciones $TS','branch':'diag-public','content':sys.argv[1]}))" "$b64")
  curl -s -o /dev/null -w "[pub %{http_code}]\n" \
    -X PUT -H "Authorization: token ${TOK}" -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$payload"
fi
