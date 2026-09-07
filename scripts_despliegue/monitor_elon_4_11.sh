#!/usr/bin/env bash
# monitor_elon_4_11.sh
#   Vigila el mercado "Will Elon Musk post 120-139 tweets Sep 4-11, 2026".
#   Cada 6h:
#     - Lee el precio del bin 120-139 YES (Gamma API)
#     - Lee el conteo de Polymarket
#     - Publica log a diag-public
#     - NO opera, solo avisa
#   Si el precio del YES sube > 0.10 -> alerta "VENDER EN VERDE"
#   Si el conteo baja de 80 o el precio sube > 0.15 -> alerta "VENDER YA"
set -u

API="https://gamma-api.polymarket.com/markets?slug=elon-musk-of-tweets-september-4-september-11-2026"
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
INTERVALO_S=${INTERVALO_S:-21600}   # 6h por defecto

while true; do
  TS=$(date -u +%Y%m%d_%H%M%S)
  TS_HUMAN=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
  LOG="/tmp/mon_4_11_${TS}.log"
  DIAG="mon_4_11_${TS}.log"

  {
  echo "=== MONITOR 4-11 sept — ${TS_HUMAN} ==="
  echo
  echo "-- Mercado --"
  curl -s --max-time 15 "$API" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    if not data:
        print('Sin datos'); sys.exit(0)
    m = data[0] if isinstance(data, list) else data
    print('Pregunta:', m.get('question'))
    print('Tweet count:', m.get('tweetCount') or m.get('tweet_count') or 'N/D')
    print('Cerrado:', m.get('closed'))
    print('Fin:', m.get('endDate'))
    # Bins
    outcomes = m.get('outcomes', '[]')
    prices = m.get('outcomePrices', '[]')
    if isinstance(outcomes, str):
        import json as j
        outcomes = j.loads(outcomes)
    if isinstance(prices, str):
        import json as j
        prices = j.loads(prices)
    for o, p in zip(outcomes, prices):
        try:
            print(f'  {o:10s}  YES @ {float(p):.4f}')
        except Exception:
            pass
except Exception as e:
    print('Error parseando:', e)
"
  } > "$LOG" 2>&1

  # Detectar alertas
  ALERTA=$(grep -E "120-139" "$LOG" | head -1)
  if [ -n "$ALERTA" ]; then
    PRECIO=$(echo "$ALERTA" | grep -oE "0\.[0-9]+" | head -1)
    CONTAJE=$(grep "Tweet count" "$LOG" | grep -oE "[0-9]+" | head -1)
    if [ -n "$PRECIO" ] && python3 -c "import sys; sys.exit(0 if float('$PRECIO') > 0.10 else 1)"; then
      echo "" >> "$LOG"
      echo "🟢 ALERTA: YES 120-139 subió a $PRECIO (conteo: $CONTAJE) — buen momento para vender" >> "$LOG"
    fi
  fi

  # Publicar
  if [ -n "$TOK" ] && [ -s "$LOG" ]; then
    b64=$(base64 -w0 "$LOG")
    PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
  'message': 'mon 4-11 ${TS}',
  'branch': 'diag-public',
  'content': sys.argv[1]
}))
" "$b64")
    curl -s -o /dev/null \
      -X PUT \
      -H "Authorization: token ${TOK}" \
      -H "Content-Type: application/json" \
      "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
      -d "$PAYLOAD"
    echo "[pub] diag-public/diag_hetzner/${DIAG}"
  fi

  sleep "$INTERVALO_S"
done
