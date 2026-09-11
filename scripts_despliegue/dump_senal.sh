#!/usr/bin/env bash
# dump_senal.sh — publica log con todos los bins y veredictos
set -u
TS=$(date -u +%Y%m%d_%H%M%S)
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")
LOG="/tmp/dump_senal_${TS}.log"

# actualizar mercado
cd /opt/polymarket/bot-polymarket-elon
python3 mercado_polymarket.py 2>&1 | tail -3

# ejecutar dump
{
echo "=== DUMP SENAL (sin filtro ENTRADA_MAX_H) — $(date -u) ==="
curl -sL -o /tmp/dump_senal.py https://raw.githubusercontent.com/lamegawi/bots-backup/HEAD/scripts_despliegue/dump_senal.py
python3 /tmp/dump_senal.py 2>&1
echo
echo "=== ZELENSKYY ==="
cd /opt/polymarket/bot-polymarket-zelenskyy
python3 mercado_polymarket.py 2>&1 | tail -3
sed -i 's|/opt/polymarket/bot-polymarket-elon|/opt/polymarket/bot-polymarket-zelenskyy|g' /tmp/dump_senal.py
python3 /tmp/dump_senal.py 2>&1
} > "$LOG" 2>&1

wc -l "$LOG"
head -200 "$LOG"

if [ -n "$TOK" ]; then
  DIAG="dump_senal_${TS}.log"
  b64=$(base64 -w0 "$LOG")
  PAYLOAD=$(python3 -c "import json,sys;print(json.dumps({'message':'dump senal $TS','branch':'diag-public','content':sys.argv[1]}))" "$b64")
  curl -s -o /dev/null -w "[pub %{http_code}]\n" -X PUT \
    -H "Authorization: token ${TOK}" -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$PAYLOAD"
fi
