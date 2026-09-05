#!/bin/bash
set -e
TS=$(date +%Y%m%d_%H%M%S)
LOG="/tmp/live_v6_${TS}.log"
exec > >(tee -a "$LOG") 2>&1

PAT=""
for p in /root/diag_token.txt ~/diag_token.txt; do
  [ -f "$p" ] && PAT=$(cat "$p" | tr -d '\n') && [ -n "$PAT" ] && break
done

publicar() {
  local ruta="diag_hetzner/live_v6_${TS}.log"
  [ -z "$PAT" ] && return
  local contenido=$(cat "$LOG")
  local b64=$(echo -n "$contenido" | base64 -w0)
  local sha=""
  sha=$(curl -sL --max-time 20 \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}?ref=diag-public" \
    -H "Authorization: token ${PAT}" 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('sha',''))" 2>/dev/null || echo "")
  local payload
  if [ -n "$sha" ]; then
    payload=$(python3 -c "import json; print(json.dumps({'message':'v6 ${TS}','content':'$b64','branch':'diag-public','sha':'$sha'}))")
  else
    payload=$(python3 -c "import json; print(json.dumps({'message':'v6 ${TS}','content':'$b64','branch':'diag-public'}))")
  fi
  curl -sL --max-time 30 -X PUT \
    "https://api.github.com/repos/lamegawi/bots-backup/contents/${ruta}" \
    -H "Authorization: token ${PAT}" \
    -H "Content-Type: application/json" \
    -d "$payload" >/dev/null 2>&1
}

echo "=== LIVE LOG V6 - $(date) ==="
echo ""
echo "== systemctl =="
systemctl status poly-combos-bot --no-pager | head -10
echo ""
echo "== LOG ULTIMAS 80 LINEAS =="
tail -80 /var/log/poly-combos-bot.log 2>&1
echo ""
echo "== ESTADO GUARDADO =="
cat /opt/polymarket/combos_estado.json 2>&1 | head -80
publicar
