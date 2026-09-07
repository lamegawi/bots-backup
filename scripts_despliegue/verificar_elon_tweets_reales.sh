#!/usr/bin/env bash
set -u
###############################################################################
# verificar_elon_tweets_reales.sh
#   Ejecuta una pasada de recoger_tweets.py (jina + xcancel), compara el
#   conteo REAL devuelto por las fuentes con el CSV, y publica el log
#   en diag-public. El bot de 48h es la fuente de verdad operativa.
###############################################################################

TS=$(date -u +%Y%m%d_%H%M%S)
TS_HUMAN=$(date -u "+%Y-%m-%d %H:%M:%S UTC")
FECHA_ET=$(TZ=America/New_York date "+%Y-%m-%d %H:%M:%S EDT")
LOG="/tmp/elon_reales_${TS}.log"
DIAG="elon_reales_${TS}.log"

BOT48=/opt/polymarket/bot-polymarket-elon
BOT7D=/opt/polymarket/bot-polymarket-elon-semanal
BOT30D=/opt/polymarket/bot-polymarket-elon-mensual
PROXY=http://127.0.0.1:8888

{
echo "=== VERIFICAR TWEETS REALES ELON — ${TS_HUMAN} ==="
echo "=== Hora local bot: ${FECHA_ET} ==="
echo
echo "== 0. Proxy PC =="
echo "Proxy configurado: ${PROXY}"
if curl -s --max-time 4 -x ${PROXY} https://api.ipify.org >/dev/null 2>&1; then
  echo "Proxy OK: $(curl -s --max-time 4 -x ${PROXY} https://api.ipify.org 2>/dev/null)"
else
  echo "AVISO: proxy no responde. Las llamadas a jina/xcancel pueden fallar."
fi
echo

for d in "$BOT48" "$BOT7D" "$BOT30D"; do
  nombre=$(basename "$d")
  echo "== Bot: ${nombre} =="
  echo
  echo "--- Una pasada de recoger_tweets.py (jina+xcancel, 60s timeout) ---"
  cd "$d" || { echo "no existe $d"; continue; }
  timeout 90 python3 recoger_tweets.py --fuente jina --resumen 2>&1 | tail -25 || \
    echo "[TIMEOUT o ERROR] al ejecutar recoger_tweets.py en $d"
  echo
  echo "--- CSV actual (datos_elon.csv) — últimas 12 filas ---"
  tail -12 datos_elon.csv 2>/dev/null || echo "sin CSV"
  echo
  echo "--- mercado_activo.json (slug del mercado que sigue) ---"
  python3 -c "import json; d=json.load(open('mercado_activo.json'));
ms=d.get('mercados',[]);
print('actualizado:', d.get('actualizado'));
for m in ms:
  print(' -', m.get('slug'), '|', m.get('titulo'), '| fin:', m.get('fin_iso'))" 2>/dev/null || \
    echo "sin mercado_activo.json"
  echo
  echo "---------------------------------------------------------------"
  echo
done

echo
echo "== 4. Estado servicios =="
for s in poly-elon poly-semanal poly-mensual; do
  st=$(systemctl is-active "$s" 2>/dev/null)
  echo "  $s : ${st}"
done

} > "$LOG" 2>&1

echo "[diag] $LOG -> diag-public/diag_hetzner/$DIAG"

# publicar a diag-public
ghapi_repo="lamegawi/bots-backup"
ghapi_branch="diag-public"
ghapi_path="diag_hetzner/${DIAG}"
b64=$(base64 -w0 "$LOG")

# crear/actualizar vía API
curl -s -X PUT \
  -H "Authorization: token $(cat /opt/polymarket/.gh_token 2>/dev/null || echo "${GH_TOKEN:-}")" \
  -H "Content-Type: application/json" \
  "https://api.github.com/repos/${ghapi_repo}/contents/${ghapi_path}?ref=${ghapi_branch}" \
  -d "{\"message\":\"diag: elon reales ${TS}\",\"branch\":\"${ghapi_branch}\",\"content\":\"${b64}\"}" \
  -o /tmp/ghapi_${TS}.json
echo "[ok]"
echo "log: ${LOG}"
