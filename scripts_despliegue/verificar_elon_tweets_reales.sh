#!/usr/bin/env bash
# verificar_elon_tweets_reales_v2.sh
# - Intenta primero con proxy http://127.0.0.1:8888 (Tailscale)
# - Si falla, lo desactiva y va directo
# - Ejecuta una pasada de recoger_tweets.py (jina + xcancel)
# - Compara conteo del CSV antes/después
# - Publica log a diag-public
set -u

TS=$(date -u +%Y%m%d_%H%M%S)
TS_HUMAN=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
LOG="/tmp/elon_reales_v2_${TS}.log"
DIAG="elon_reales_v2_${TS}.log"

BOT48=/opt/polymarket/bot-polymarket-elon
BOT7D=/opt/polymarket/bot-polymarket-elon-semanal
BOT30D=/opt/polymarket/bot-polymarket-elon-mensual
TOK=$(cat /opt/polymarket/.gh_token 2>/dev/null || echo "")

# Detectar proxy
TS_IP=${TS_IP:-100.83.57.99}
PROXY_URL="http://${TS_IP}:8888"
PROXY_ON=0
if curl -s --max-time 4 -x "$PROXY_URL" https://api.ipify.org >/dev/null 2>&1; then
  PROXY_ON=1
  IP_PROXY=$(curl -s --max-time 4 -x "$PROXY_URL" https://api.ipify.org)
fi
IP_DIRECT=$(curl -s --max-time 4 https://api.ipify.org 2>/dev/null || echo "?")

{
echo "=== VERIFICAR TWEETS REALES ELON v2 — ${TS_HUMAN} ==="
echo
echo "== Red =="
echo "Proxy URL       : ${PROXY_URL}"
echo "IP con proxy    : ${IP_PROXY:-NO RESPONDE}"
echo "IP sin proxy    : ${IP_DIRECT}"
if [ "$PROXY_ON" = "1" ]; then
  echo "Proxy ON"
else
  echo "Proxy OFF — yendo DIRECTO (puede fallar por Cloudflare)"
fi
echo
echo "== JINA_KEY =="
test -f /opt/polymarket/.jina_key && \
  echo "existe ($(wc -c </opt/polymarket/.jina_key) bytes)" || \
  echo "no existe — bot usara jina sin auth (rate limit)"
echo

for d in "$BOT48" "$BOT7D" "$BOT30D"; do
  nombre=$(basename "$d")
  [ -d "$d" ] || { echo "no existe $d"; continue; }
  cd "$d" || continue

  echo "=========================================="
  echo "Bot: $nombre"
  echo "=========================================="

  # Forzar / quitar proxy para jina según disponibilidad
  export http_proxy=""
  export https_proxy=""
  export HTTP_PROXY=""
  export HTTPS_PROXY=""
  if [ "$PROXY_ON" = "1" ]; then
    export http_proxy="${PROXY_URL}"
    export https_proxy="${PROXY_URL}"
    export HTTP_PROXY="${PROXY_URL}"
    export HTTPS_PROXY="${PROXY_URL}"
  fi

  echo
  echo "-- ANTES (CSV actual, últimas 8 filas) --"
  tail -8 datos_elon.csv 2>/dev/null

  echo
  echo "-- Pasada de recoger_tweets.py --fuente jina --resumen (timeout 150s) --"
  timeout 150 python3 recoger_tweets.py --fuente jina --resumen 2>&1 | tail -25 || \
    echo "[TIMEOUT o ERROR]"

  echo
  echo "-- DESPUÉS (CSV actualizado, últimas 8 filas) --"
  tail -8 datos_elon.csv 2>/dev/null

  echo
  echo "-- Tweets del periodo 4-11 sept 2026 (CSV actual) --"
  python3 - <<'PYEOF'
import csv
from datetime import date
d1, d2 = date(2026,9,4), date(2026,9,11)
total = 0
with open("datos_elon.csv") as f:
    r = csv.DictReader(f)
    for fila in r:
        try:
            f_ = date.fromisoformat(fila["fecha"])
        except Exception:
            continue
        if d1 <= f_ <= d2:
            n = int(fila["tweets"])
            total += n
            print(f"  {fila['fecha']}: {n} tweets")
print(f"  TOTAL {d1}..{d2}: {total} tweets")
PYEOF

  echo
  echo "-- Mercado activo que sigue el bot --"
  python3 -c "
import json
try:
    d=json.load(open('mercado_activo.json'))
    for m in d.get('mercados', []):
        if not m.get('cerrado'):
            print(' -', m.get('slug'),'|',m.get('titulo'),'| fin:',m.get('fin_iso'))
except Exception as e:
    print('err:', e)
" 2>/dev/null

  echo
done

echo
echo "== Estado servicios =="
for s in poly-elon poly-semanal poly-mensual; do
  st=$(systemctl is-active "$s" 2>/dev/null)
  echo "  $s : ${st}"
done

} > "$LOG" 2>&1

echo "[diag] $LOG -> diag-public/diag_hetzner/$DIAG"

# Publicar
if [ -z "$TOK" ]; then
  echo "[WARN] /opt/polymarket/.gh_token vacio. Log solo local."
else
  b64=$(base64 -w0 "$LOG")
  PAYLOAD=$(python3 -c "
import json, sys
print(json.dumps({
  'message': 'diag elon reales v2 ${TS}',
  'branch': 'diag-public',
  'content': sys.argv[1]
}))
" "$b64")
  HTTP=$(curl -s -o /tmp/ghapi_${TS}.json -w "%{http_code}" \
    -X PUT \
    -H "Authorization: token ${TOK}" \
    -H "Content-Type: application/json" \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/diag_hetzner/${DIAG}?ref=diag-public" \
    -d "$PAYLOAD")
  echo "[gh-api] HTTP $HTTP"
  head -c 400 /tmp/ghapi_${TS}.json; echo
fi

echo "log: ${LOG}"
