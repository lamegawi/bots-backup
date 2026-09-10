#!/usr/bin/env bash
# test_senal_vivo_detalle.sh — evalúa señal y publica log COMPLETO
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")

LOG="/tmp/senal_detalle_${TS}.log"
{
echo "=== TEST SENAL VIVO DETALLE (Elon) — $(date -u) ==="
cd /opt/polymarket/bot-polymarket-elon
python3 senal_vivo.py --actualizar 2>&1
echo
echo "=== TEST SENAL VIVO DETALLE (Zelenskyy) ==="
cd /opt/polymarket/bot-polymarket-zelenskyy
python3 senal_vivo.py --actualizar 2>&1
} > "$LOG" 2>&1

wc -l "$LOG"
echo
head -300 "$LOG"

if [ -n "$TOK" ]; then
  DIAG="senal_detalle_${TS}.log"
  b64=$(base64 -w0 "$LOG")
  PAYLOAD=$(python3 -c "import json,sys;print(json.dumps({'message':'senal detalle $TS','branch':'diag-public','content':sys.argv[1]}))" "$b64")
  curl -s -o /dev/null -w "[pub %{http_code}]\n" -X PUT \
    -H "Authorization: token ${TOK}" -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$PAYLOAD"
fi
