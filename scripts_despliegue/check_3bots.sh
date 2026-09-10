#!/usr/bin/env bash
# check_3bots.sh — diagnostica el estado actual de los 3 bots
#   - Servicios systemd
#   - Posiciones abiertas (proxy PC + CLOB)
#   - Mercados activos
#   - Últimas líneas de logs
set -u

TS=$(date -u +%Y%m%d_%H%M%S)
LOG="/tmp/check_3bots_${TS}.log"
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
TS_IP=${TS_IP:-100.83.57.99}
PROXY="http://${TS_IP}:8888"

{
echo "=== CHECK 3 BOTS — $(date -u "+%Y-%m-%d %H:%M:%S UTC") ==="
echo

echo "== 1. Servicios systemd =="
for s in poly-elon poly-elon-semanal poly-elon-mensual poly-zelenskyy poly-zelenskyy-semanal poly-trump poly-trump-semanal; do
  st=$(systemctl is-active "$s" 2>/dev/null)
  if [ -n "$st" ] && [ "$st" != "inactive" ]; then
    echo "  $s : $st"
  fi
done
echo

echo "== 2. Listar /opt/polymarket =="
ls -la /opt/polymarket/ 2>&1 | head -25
echo

echo "== 3. Bots detectados (cada subdir) =="
for d in /opt/polymarket/*/; do
  if [ -d "$d" ]; then
    name=$(basename "$d")
    csv=$(ls "$d"/datos_*.csv 2>/dev/null | head -1)
    mar=$(ls "$d"/mercado_activo.json 2>/dev/null | head -1)
    log=$(ls /var/log/poly-*.log 2>/dev/null | xargs -I{} sh -c "echo {} | grep -i $name || true" | head -1)
    echo "  $name"
    [ -n "$csv" ] && echo "    CSV: $csv ($(wc -l <"$csv") lineas)"
    [ -n "$mar" ] && echo "    mercado: $mar"
  fi
done
echo

echo "== 4. Posiciones abiertas (CLOB via proxy) =="
FUNDER="0xb0E1197098E6d427c01720F1631cAD24CE740FA0"
curl -s --max-time 20 -x "$PROXY" -H "Accept: application/json" \
  "https://data-api.polymarket.com/positions?user=${FUNDER}&sizeThreshold=1" \
  | python3 -c "
import json, sys
try:
    pos = json.load(sys.stdin)
    if not isinstance(pos, list):
        pos = []
    print('Total:', len(pos))
    for p in pos:
        size = float(p.get('size', 0))
        if size > 0.1:
            print(f\"  size={size:>10.2f}  {p.get('outcome','?'):<20}  slug={p.get('slug',''):<50}  avg={p.get('avgPrice',0):.4f}\")
except Exception as e:
    print('ERR:', e)
" 2>&1
echo

echo "== 5. Ordenes abiertas =="
curl -s --max-time 20 -x "$PROXY" -H "Accept: application/json" \
  "https://data-api.polymarket.com/orders?user=${FUNDER}" \
  | python3 -c "
import json, sys
try:
    o = json.load(sys.stdin)
    if not isinstance(o, list): o = []
    print('Total:', len(o))
    for x in o:
        print(f\"  side={x.get('side','?'):<5}  {x.get('outcome','?'):<20}  px={x.get('price',0):.4f}  size={x.get('size',0):.2f}  slug={x.get('slug','')[:50]}\")
except Exception as e:
    print('ERR:', e)
" 2>&1
echo

echo "== 6. Ultimas lineas de logs (cada bot) =="
for f in /var/log/poly-*.log; do
  [ -f "$f" ] || continue
  echo "--- $f (ultimas 5) ---"
  tail -5 "$f"
  echo
done

} > "$LOG" 2>&1

echo "[diag] $LOG"

# publicar
if [ -n "$TOK" ]; then
  DIAG="check_3bots_${TS}.log"
  b64=$(base64 -w0 "$LOG")
  payload=$(python3 -c "import json,sys;print(json.dumps({'message':'check 3bots $TS','branch':'diag-public','content':sys.argv[1]}))" "$b64")
  curl -s -o /dev/null -w "[pub %{http_code}]\n" \
    -X PUT \
    -H "Authorization: token ${TOK}" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$payload"
fi

echo "log: ${LOG}"
